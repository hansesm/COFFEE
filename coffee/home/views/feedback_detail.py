import asyncio
import logging
import threading

from asgiref.sync import sync_to_async
from django.http import (
    HttpResponseBadRequest,
    StreamingHttpResponse, Http404,
)
from django.shortcuts import get_object_or_404, render

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
from home.ai_provider.models import CoffeeUsage


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
        provider: AIBaseClient = provider_class(config)

        logging.info(f"Using model: {llm_model}")

        def on_usage_report(report: CoffeeUsage):
            pass

        generator = provider.stream(llm_model.external_name, user_input, custom_prompt, on_usage_report=on_usage_report)

        async def async_byte_iter():
            loop = asyncio.get_running_loop()
            q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=8)

            def feeder():
                try:
                    buffer = []
                    for piece in generator:
                        if not piece:
                            continue

                        buffer.append(piece)

                        # Flush on spaces or new lines
                        if " " in piece or "\n" in piece:
                            data = "".join(buffer).encode("utf-8")
                            asyncio.run_coroutine_threadsafe(q.put(data), loop)
                            buffer.clear()

                    # Send rest
                    if buffer:
                        data = "".join(buffer).encode("utf-8")
                        asyncio.run_coroutine_threadsafe(q.put(data), loop)

                except Exception as e:
                    logging.exception("stream feeder failed")
                    asyncio.run_coroutine_threadsafe(
                        q.put(f"[error] {e}\n".encode("utf-8"), loop),
                        loop,
                    )
                finally:
                    asyncio.run_coroutine_threadsafe(q.put(None), loop)

            threading.Thread(target=feeder, daemon=True).start()

            yield b""
            while True:
                chunk = await q.get()
                if chunk is None:
                    break
                yield chunk

        # 2) Wrap the generator in a StreamingHttpResponse
        streaming_response = StreamingHttpResponse(async_byte_iter(), content_type="text/plain; charset=utf-8")

        # 3) Set headers on the StreamingHttpResponse
        streaming_response["Cache-Control"] = "no-cache"
        streaming_response["X-Accel-Buffering"] = "no"
        streaming_response["Connection"] = "keep-alive"

        return streaming_response
    except Exception as e:
        logging.exception("Error generating streaming response:")
        return HttpResponseBadRequest("An error occurred while generating the response.")
