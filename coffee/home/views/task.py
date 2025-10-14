from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import (
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views import View

from coffee.home.forms import (
    TaskForm,
)
from coffee.home.mixins import ManagerRequiredMixin
from coffee.home.models import (
    Course,
    Task,
)
from coffee.home.views.utils import check_permissions_and_group


def task(request):
    if request.method == "POST":
        if "save" in request.POST:
            form = TaskForm(request.POST)
            form.save()

    context = {
        "form": TaskForm(),
        "tasks": Task.objects.all(),
        "title": "New Tasks",
    }
    return render(request, "pages/newtask.html", context)


class CrudTaskView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Show only tasks for courses the user can view (either through viewing_groups OR editing_groups)
        task_qs = Task.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).distinct()

        # Also only show courses they can view in the dropdown
        course_qs = Course.objects.filter(
            Q(viewing_groups__in=request.user.groups.all()) |
            Q(editing_groups__in=request.user.groups.all())
        ).distinct()

        context = {
            "form": TaskForm(),
            "task_set": task_qs,
            "course_set": course_qs,
        }
        return render(request, "pages/crud_task.html", context)

    def post(self, request, *args, **kwargs):
        request_type = request.POST.get("request_type")

        if request_type == "update":
            task_id = request.POST.get("task_id")
            title = request.POST.get("title")
            active = request.POST.get("active") == "true"
            description = request.POST.get("description")
            task_context = request.POST.get("task_context")
            course_id = request.POST.get("course_id")  # if you allow user to choose a Course

            if task_id:
                # UPDATE existing
                task_obj = get_object_or_404(Task, pk=task_id)
                has_permission, error_message = check_permissions_and_group(request.user, task_obj, "change")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})
            else:
                # CREATE new
                task_obj = Task()
                # Attach the chosen course before checking "add" permission
                if course_id:
                    task_obj.course_id = course_id

                has_permission, error_message = check_permissions_and_group(request.user, task_obj, "add")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})

            try:
                task_obj.title = title
                task_obj.active = active
                task_obj.description = description
                task_obj.task_context = task_context
                if course_id:
                    task_obj.course_id = course_id
                task_obj.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif request_type == "delete":
            task_id = request.POST.get("task_id")
            task_obj = get_object_or_404(Task, pk=task_id)

            has_permission, error_message = check_permissions_and_group(request.user, task_obj, "delete")
            if not has_permission:
                return JsonResponse({"success": False, "error": error_message})

            try:
                task_obj.delete()
            except ProtectedError as e:
                # Return the error message from ProtectedError
                return JsonResponse({"success": False, "error": str(e)})
            return JsonResponse({"success": True})

        return JsonResponse({"success": False, "error": "Invalid request type"})