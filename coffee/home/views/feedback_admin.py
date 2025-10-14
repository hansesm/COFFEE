import json

from django.db.models import Q, Prefetch
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
    Feedback,
    FeedbackCriteria,
    Task,
)
from coffee.home.views.utils import check_permissions_and_group


class CrudFeedbackView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Show only feedback the user can view (either through viewing_groups OR editing_groups)
        feedback_list = Feedback.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).select_related('course', 'task').distinct().order_by("task")

        course_list = Course.objects.filter(
            Q(viewing_groups__in=request.user.groups.all()) |
            Q(editing_groups__in=request.user.groups.all())
        ).prefetch_related('viewing_groups').distinct()

        task_list = Task.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all()),
            active=True
        ).select_related('course').distinct()

        criteria_set = Criteria.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all()),
            active=True
        ).select_related('course').distinct()

        # Add a helper JSON field for each feedback's criteria - optimized to avoid N+1 queries
        feedback_list = feedback_list.prefetch_related(
            Prefetch('criteria_set', queryset=Criteria.objects.select_related()),
            'feedbackcriteria_set__criteria'
        )
        for fdb in feedback_list:
            fdb.criteria_set_json = fdb.get_criteria_set_json()

        context = {
            "feedback_list": feedback_list,
            "course_list": course_list,
            "task_list": task_list,
            "criteria_set": criteria_set,
        }
        return render(request, "pages/crud_feedback.html", context)

    def post(self, request, *args, **kwargs):
        request_type = request.POST.get("request_type")

        if request_type == "update":
            feedback_id = request.POST.get("feedback_id")
            course_id = request.POST.get("course")
            task_id = request.POST.get("task")
            active = request.POST.get("active") == "true"
            criteria_set = json.loads(request.POST.get("criteria_set", "[]"))

            if feedback_id:
                # UPDATE
                feedback = get_object_or_404(Feedback, pk=feedback_id)
                has_permission, error_message = check_permissions_and_group(request.user, feedback, "change")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})
            else:
                # CREATE
                feedback = Feedback()
                # we must set course early so the object-level check knows which course it is
                feedback.course_id = course_id

                has_permission, error_message = check_permissions_and_group(request.user, feedback, "add")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})

            feedback.course_id = course_id
            feedback.task_id = task_id
            feedback.active = active
            feedback.save()

            # Update the feedback's criteria
            feedback.criteria_set.clear()
            for crit in criteria_set:
                criteria_id = crit["id"]
                rank = crit.get("rank", 0)
                FeedbackCriteria.objects.create(
                    feedback=feedback, criteria_id=criteria_id, rank=rank
                )

            return JsonResponse({"success": True})

        elif request_type == "delete":
            feedback_id = request.POST.get("feedback_id")
            feedback = get_object_or_404(Feedback, pk=feedback_id)

            has_permission, error_message = check_permissions_and_group(request.user, feedback, "delete")
            if not has_permission:
                return JsonResponse({"success": False, "error": error_message})

            try:
                feedback.delete()
            except ProtectedError as e:
                # Return the error message from ProtectedError
                return JsonResponse({"success": False, "error": str(e)})
            return JsonResponse({"success": True})

        return JsonResponse({"success": False, "error": "Invalid request type"})
