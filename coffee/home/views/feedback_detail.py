import logging

from django.http import (
    HttpResponseBadRequest,
    StreamingHttpResponse,
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
# from coffee.home.ai_provider.ollama_api import stream_chat_response TODO


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


def feedback_stream(request, feedback_uuid, criteria_uuid):
    user_input = request.POST.get("user_input")
    if not user_input:
        return HttpResponseBadRequest("No user input provided")

    criteria = get_object_or_404(Criteria, id=criteria_uuid)
    feedback_obj = get_object_or_404(Feedback, id=feedback_uuid)
    task = feedback_obj.task
    course = feedback_obj.course

    try:
        custom_prompt = criteria.prompt.replace("##submission##", user_input)
        custom_prompt = custom_prompt.replace("##task_title##", task.title or "")
        custom_prompt = custom_prompt.replace("##task_description##", task.description or "")
        custom_prompt = custom_prompt.replace("##task_context##", task.task_context or "")
        custom_prompt = custom_prompt.replace("##course_name##", course.course_name or "")
        custom_prompt = custom_prompt.replace("##course_context##", course.course_context or "")

        # Parse model and backend from criteria.llm field
        from django.conf import settings
        from coffee.home.llm_backends import parse_model_backend, stream_llm_response

        llm_field = criteria.llm.strip() if criteria.llm and criteria.llm.strip() else settings.OLLAMA_DEFAULT_MODEL
        model_name, backend = parse_model_backend(llm_field)

        logging.info(f"Using {backend} backend with model: {model_name}")

        generator = stream_llm_response(model_name, backend, user_input, custom_prompt)

        # 2) Wrap the generator in a StreamingHttpResponse
        streaming_response = StreamingHttpResponse(generator, content_type="text/plain")

        # 3) Set headers on the StreamingHttpResponse
        streaming_response["Cache-Control"] = "no-cache"
        streaming_response["X-Accel-Buffering"] = "no"

        # response = stream_chat_response(custom_prompt, model_name)

        return streaming_response
    except Exception as e:
        logging.exception("Error generating streaming response:")
        return HttpResponseBadRequest("An error occurred while generating the response.")
