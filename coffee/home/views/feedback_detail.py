import asyncio
import logging
import threading

from asgiref.sync import sync_to_async
from django.http import (
    HttpResponseBadRequest,
    StreamingHttpResponse, Http404,
)
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _

from coffee.home.forms import (
    FeedbackSessionForm,
)
from coffee.home.models import (
    Criteria,
    Feedback,
    FeedbackCriteria,
)
from coffee.home.ai_provider.llm_provider_base import AIBaseClient
from coffee.home.models import LLMModel
from coffee.home.registry import SCHEMA_REGISTRY
from coffee.home.models import LLMProvider
from coffee.home.ai_provider.models import CoffeeUsage
from coffee.home.views.streaming import sse_event


logger = logging.getLogger(__name__)


def feedback(request, id):
    form = FeedbackSessionForm()
    feedback_obj = get_object_or_404(Feedback, id=id)
    feedbackcriteria_set = FeedbackCriteria.objects.filter(feedback=feedback_obj).order_by("rank")
    scores = list(range(1, 11))  # Generates [1..10]

    context = {
        "form": form,
        "title": "Submission",
        "feedback": feedback_obj,
        "feedbackcriteria_set": feedbackcriteria_set,
        "scores": scores,
    }
    return render(request, "pages/feedback.html", context)


async def feedback_stream(request, feedback_uuid, criteria_uuid):
    if request.method != "POST":
        return HttpResponseBadRequest("POST expected")

    user_input = request.POST.get("user_input")
    if not user_input:
        return HttpResponseBadRequest("No user input provided")

    @sync_to_async
    def load_db():
        try:
            criteria = (
                Criteria.objects
                .select_related("llm_fk__provider")
                .get(id=criteria_uuid)
            )
        except Criteria.DoesNotExist:
            raise Http404("Criteria not found")

        try:
            feedback = (
                Feedback.objects
                .select_related("task", "course")
                .get(id=feedback_uuid)
            )
        except Feedback.DoesNotExist:
            raise Http404("Feedback not found")

        llm_model = criteria.llm_fk or LLMModel.get_default()  # meist ORM
        task, course = feedback.task, feedback.course
        provider: LLMProvider = llm_model.provider
        return criteria, llm_model, task, course, provider

    try:
        criteria, llm_model, task, course, provider = await load_db()

        custom_prompt = criteria.prompt.replace("##submission##", user_input)
        custom_prompt = custom_prompt.replace("##task_title##", task.title or "")
        custom_prompt = custom_prompt.replace("##task_description##", task.description or "")
        custom_prompt = custom_prompt.replace("##task_context##", task.task_context or "")
        custom_prompt = custom_prompt.replace("##course_name##", course.course_name or "")
        custom_prompt = custom_prompt.replace("##course_context##", course.course_context or "")

        provider_config, provider_class = SCHEMA_REGISTRY[provider.type]
        config = provider_config.from_provider(provider)
        ai_client: AIBaseClient = provider_class(config)

        logger.info("Using model: %s", llm_model)

        loop = asyncio.get_running_loop()
        q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=32)

        def on_usage_report(report: CoffeeUsage):
            """
            Wird vom Provider am Ende des Streams aufgerufen.
            Wir verpacken die Usage als eigenes SSE-Event.
            """
            try:
                data = report.model_dump()
                asyncio.run_coroutine_threadsafe(q.put(sse_event("usage", data)), loop)
            except Exception:
                logger.exception("on_usage_report failed")

        provider: LLMProvider = provider
        reset_anchor = provider.last_reset_at
        reset_eta_utc = reset_anchor + provider.token_reset_interval
        reset_eta_local = timezone.localtime(reset_eta_utc)
        formatted = reset_eta_local.strftime("%d.%m.%Y %H:%M")

        await sync_to_async(provider.roll_window_optimistic)()
        quoata_exceeded = await sync_to_async(provider.soft_limit_exceeded)(0)
        if quoata_exceeded:
            logger.warning("Quota exceeded")
            return HttpResponseBadRequest(
                _("Token limit exceeded. Please try again at %(time)s.") % {"time": formatted}
            )


        generator = ai_client.stream(
            llm_model,
            user_input,
            custom_prompt,
            on_usage_report=on_usage_report,
        )

        def feeder():
            """
            Läuft im Hintergrundthread, liest den Provider-Generator und schiebt
            'delta'-Events in die Queue. Das finale 'usage'-Event kommt über on_usage_report().
            """
            try:
                buffer = []
                for piece in generator:
                    if not piece:
                        continue
                    buffer.append(piece)

                    # Flush heuristisch (wie bei dir): auf Leerzeichen/Zeilenumbruch
                    if " " in piece or "\n" in piece:
                        text = "".join(buffer)
                        asyncio.run_coroutine_threadsafe(
                            q.put(sse_event("delta", {"text": text})), loop
                        )
                        buffer.clear()

                # Rest flushen
                if buffer:
                    text = "".join(buffer)
                    asyncio.run_coroutine_threadsafe(
                        q.put(sse_event("delta", {"text": text})), loop
                    )

            except Exception as e:
                logger.exception("stream feeder failed")
                asyncio.run_coroutine_threadsafe(
                    q.put(sse_event("error", {"message": str(e)})), loop
                )
            finally:
                # Signalisiert dem Client das Ende des Streams (nachdem 'usage' gesendet wurde)
                asyncio.run_coroutine_threadsafe(q.put(sse_event("end", {})), loop)
                asyncio.run_coroutine_threadsafe(q.put(None), loop)

        threading.Thread(target=feeder, daemon=True).start()

        async def async_byte_iter():
            # optional: initiales Kommentar-Heartbeat (SSE)
            yield b": keep-alive\n\n"
            while True:
                chunk = await q.get()
                if chunk is None:
                    break
                yield chunk

        # StreamingHttpResponse mit SSE
        resp = StreamingHttpResponse(async_byte_iter(), content_type="text/event-stream; charset=utf-8")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        resp["Connection"] = "keep-alive"
        return resp
    except Exception:
        logger.exception("Error generating streaming response:")
        return HttpResponseBadRequest("An error occurred while generating the response.")
