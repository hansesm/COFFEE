from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import (
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.views import View

from coffee.home.forms import (
    CourseForm,
    TaskForm,
)
from coffee.home.mixins import ManagerRequiredMixin
from coffee.home.models import (
    Course,
)
from coffee.home.views.utils import check_permissions_and_group


def course(request):
    if request.method == "POST":
        if "save" in request.POST:
            form = TaskForm(request.POST)
            form.save()

    context = {
        "form": CourseForm(),
        "tasks": Course.objects.all(),
        "title": "New Tasks",
    }
    return render(request, "pages/newtask.html", context)


class CrudCourseView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Show courses the user can *at least* view (either through viewing_groups OR editing_groups)
        course_qs = Course.objects.filter(
            Q(viewing_groups__in=request.user.groups.all()) |
            Q(editing_groups__in=request.user.groups.all())
        ).distinct()

        context = {
            "form": CourseForm(),
            "course_set": course_qs,
        }
        return render(request, "pages/crud_course.html", context)

    def post(self, request, *args, **kwargs):
        request_type = request.POST.get("request_type")

        if request_type == "update":
            course_id = request.POST.get("course_id")
            faculty = request.POST.get("faculty")
            study_programme = request.POST.get("study_programme")
            chair = request.POST.get("chair")
            term = request.POST.get("term")
            course_name = request.POST.get("course_name")
            course_number = request.POST.get("course_number")
            active = request.POST.get("active") == "true"
            course_context = request.POST.get("course_context")

            if course_id:
                # UPDATE existing course
                course_obj = get_object_or_404(Course, pk=course_id)
                has_permission, error_message = check_permissions_and_group(request.user, course_obj, "change")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})
            else:
                # CREATE new
                # We need a dummy Course object for the add permission check
                course_obj = Course()
                has_permission, error_message = check_permissions_and_group(request.user, course_obj, "add")
                if not has_permission:
                    return JsonResponse({"success": False, "error": error_message})

            try:
                course_obj.faculty = faculty
                course_obj.study_programme = study_programme
                course_obj.chair = chair
                course_obj.term = term
                course_obj.course_name = course_name
                course_obj.course_number = course_number
                course_obj.active = active
                course_obj.course_context = course_context
                course_obj.save()

                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif request_type == "delete":
            course_id = request.POST.get("course_id")
            course_obj = get_object_or_404(Course, pk=course_id)

            has_permission, error_message = check_permissions_and_group(request.user, course_obj, "delete")
            if not has_permission:
                return JsonResponse({"success": False, "error": error_message})

            try:
                course_obj.delete()
            except ProtectedError as e:
                # Return the error message from ProtectedError
                return JsonResponse({"success": False, "error": str(e)})
            return JsonResponse({"success": True})

        return JsonResponse({"success": False, "error": "Invalid request type"})