import logging

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import (
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views import View

from coffee.home.mixins import ManagerRequiredMixin
from coffee.home.models import (
    Course,
    Criteria,
)
from coffee.home.views.utils import check_permissions_and_group


class CrudCriteriaView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Show criteria for courses the user can view (either through viewing_groups OR editing_groups)
        criteria_set = Criteria.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).distinct()

        # Also only show courses user can view
        course_set = Course.objects.filter(
            Q(viewing_groups__in=request.user.groups.all()) |
            Q(editing_groups__in=request.user.groups.all())
        ).distinct()

        # Try to get LLM models, but don't fail the entire page if Ollama is unavailable
        llm_models_error = None
        llm_models = []

        try:
            logging.info("Attempting to fetch LLM models from all backends...")
            from coffee.home.llm_backends import get_all_available_models
            llm_models = get_all_available_models()
            logging.info("Successfully fetched %d LLM models from all backends", len(llm_models))
        except Exception as e:
            logging.error("Failed to fetch LLM models: %s", e)
            llm_models = []
            llm_models_error = str(e)
            logging.info("Continuing with empty LLM models list due to error")

        return render(
            request,
            "pages/crud_criteria.html",
            {
                "criteria_set": criteria_set,
                "course_set": course_set,
                "llm_models": llm_models,
                "llm_models_error": llm_models_error,
            },
        )

    def post(self, request, *args, **kwargs):
        request_type = request.POST.get("request_type")

        if request_type == "update":
            criteria_id = request.POST.get("criteria_id")
            title = request.POST.get("title")
            active = request.POST.get("active") == "true"
            description = request.POST.get("description")
            llm = request.POST.get("llm")
            prompt = request.POST.get("prompt")
            sequels = request.POST.get("sequels")
            tag = request.POST.get("tag")
            course_id = request.POST.get("course_id")

            if criteria_id:
                # UPDATE
                criteria_obj = get_object_or_404(Criteria, pk=criteria_id)
                has_permission, error_message = check_permissions_and_group(request.user, criteria_obj, "change")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})
            else:
                # CREATE
                criteria_obj = Criteria()
                if course_id:
                    criteria_obj.course_id = course_id

                has_permission, error_message = check_permissions_and_group(request.user, criteria_obj, "add")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})

            try:
                criteria_obj.title = title
                criteria_obj.description = description
                criteria_obj.active = active
                criteria_obj.llm = llm
                criteria_obj.prompt = prompt
                criteria_obj.sequels = sequels
                criteria_obj.tag = tag
                if course_id:
                    criteria_obj.course_id = course_id
                criteria_obj.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif request_type == "delete":
            criteria_id = request.POST.get("criteria_id")
            criteria_obj = get_object_or_404(Criteria, pk=criteria_id)

            has_permission, error_message = check_permissions_and_group(request.user, criteria_obj, "delete")
            if not has_permission:
                return JsonResponse({"success": False, "error": error_message})

            try:
                criteria_obj.delete()
            except ProtectedError as e:
                # Return the error message from ProtectedError
                return JsonResponse({"success": False, "error": str(e)})
            return JsonResponse({"success": True})

        return JsonResponse({"success": False, "error": "Invalid request type"})