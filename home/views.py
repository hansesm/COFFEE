import csv
import json
import logging

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import logout
from django.contrib.auth.models import Group
from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetConfirmView,
    PasswordChangeView,
)
from django.db.models import Q, Prefetch
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .forms import (
    CourseForm,
    FeedbackSessionForm,
    LoginForm,
    RegistrationForm,
    TaskForm,
    UserPasswordChangeForm,
    UserPasswordResetForm,
    UserSetPasswordForm,
)
from .mixins import ManagerRequiredMixin
from .models import (
    Course,
    Criteria,
    Feedback,
    FeedbackCriteria,
    FeedbackSession,
    Task,
)
from .ollama_api import stream_chat_response, list_models
from django.db.models.deletion import ProtectedError



# -------------------------------------------------------------------------
# Language / Index
# -------------------------------------------------------------------------

def set_language(request):
    user_language = "de"
    translation.activate(user_language)
    response = HttpResponse(...)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
    return response


def index(request):
    feedback_set = Feedback.objects.all()
    return render(request, "pages/index.html", {"feedback_set": feedback_set})


# -------------------------------------------------------------------------
# Permission Checks
# -------------------------------------------------------------------------

def check_permissions_and_group(user, instance, permission_codename):
    """
    Check both the global (model-level) permission via user.has_perm(...)
    and the per-object logic via the course's own can_edit() / can_view() methods.
    """

    # 1) Build the global permission name, e.g. "home.change_course"
    model_name = instance.__class__.__name__.lower()
    permission_name = f"home.{permission_codename}_{model_name}"

    # 2) Check the model-level permission
    if not user.has_perm(permission_name):
        return False, f"You do not have global '{permission_codename}' permission on {model_name}."

    # 3) Determine the course object
    if hasattr(instance, "course"):
        course = instance.course  # e.g. feedback.course, task.course, etc.
    else:
        course = instance  # instance is the Course itself

    # 4) Object-level check
    if permission_codename in ["change", "delete"]:
        # Must have "can_edit" on that course
        if not course.can_edit(user):
            return False, f"You are not allowed to {permission_codename} this {model_name}."
    elif permission_codename in ["view"]:
        # Must have "can_view" on that course
        if not course.can_view(user):
            return False, f"You are not allowed to view this {model_name}."

    return True, None


# -------------------------------------------------------------------------
# Policies View
# -------------------------------------------------------------------------

def policies(request):
    return render(request, "pages/policies.html")


# -------------------------------------------------------------------------
# Feedback View
# -------------------------------------------------------------------------

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
        from .llm_backends import parse_model_backend, stream_llm_response
        
        llm_field = criteria.llm.strip() if criteria.llm and criteria.llm.strip() else settings.OLLAMA_DEFAULT_MODEL
        model_name, backend = parse_model_backend(llm_field)
        
        logging.info(f"Using {backend} backend with model: {model_name}")
        
        generator = stream_llm_response(model_name, backend, user_input, custom_prompt)

        # 2) Wrap the generator in a StreamingHttpResponse
        streaming_response = StreamingHttpResponse(generator, content_type="text/plain")

        # 3) Set headers on the StreamingHttpResponse
        streaming_response["Cache-Control"] = "no-cache"
        streaming_response["X-Accel-Buffering"] = "no"

        response = stream_chat_response(custom_prompt, model_name)
        
        return streaming_response
    except Exception as e:
        logging.exception("Error generating streaming response:")
        return HttpResponseBadRequest("An error occurred while generating the response.")


# -------------------------------------------------------------------------
# Feedback List View (Filterable)
# -------------------------------------------------------------------------

class FeedbackListView(View):
    def get(self, request, *args, **kwargs):
        # Single optimized query with select_related
        feedbacks = Feedback.objects.filter(active=True).select_related(
            "course", "task"
        ).order_by("course", "task")

        # Collect filter values efficiently
        filters = {}
        for field, param in [
            ("course__faculty", "faculty"),
            ("course__study_programme", "study_programme"),
            ("course__chair", "chair"),
            ("course__term", "term"),
            ("course__course_name", "course_name"),
        ]:
            value = request.GET.get(param, "")
            if value:
                filters[field] = value

        # Apply filters if any were provided
        if filters:
            feedbacks = feedbacks.filter(**filters)

        # Get filter options using cached approach
        filter_options = self.get_filter_options()

        context = {
            "feedbacks": feedbacks,
            "faculties": filter_options['faculties'],
            "study_programmes": filter_options['study_programmes'],
            "chairs": filter_options['chairs'],
            "terms": filter_options['terms'],
            "course_names": filter_options['course_names'],
            "selected_term": request.GET.get("term", ""),
        }
        return render(request, "pages/feedback_list.html", context)

    def get_filter_options(self):
        """Get filter options with caching for better performance"""
        from django.core.cache import cache
        from django.db.models import Q
        
        cache_key = 'course_filter_options'
        options = cache.get(cache_key)
        
        if options is None:
            # Single query to get all unique values
            course_fields = Course.objects.exclude(
                Q(faculty__startswith="#") | Q(study_programme__startswith="#") | 
                Q(chair__startswith="#") | Q(term__startswith="#") | 
                Q(course_name__startswith="#")
            ).values('faculty', 'study_programme', 'chair', 'term', 'course_name').distinct()
            
            # Extract unique values efficiently
            faculties = sorted(set(item['faculty'] for item in course_fields))
            study_programmes = sorted(set(item['study_programme'] for item in course_fields))
            chairs = sorted(set(item['chair'] for item in course_fields))
            terms = sorted(set(item['term'] for item in course_fields))
            course_names = sorted(set(item['course_name'] for item in course_fields))
            
            options = {
                'faculties': faculties,
                'study_programmes': study_programmes,
                'chairs': chairs,
                'terms': terms,
                'course_names': course_names,
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, options, 300)
        
        return options


# -------------------------------------------------------------------------
# CRUD for Feedback
# -------------------------------------------------------------------------

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


# -------------------------------------------------------------------------
# Course Views
# -------------------------------------------------------------------------

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


# -------------------------------------------------------------------------
# Task Views
# -------------------------------------------------------------------------

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


# -------------------------------------------------------------------------
# Criteria Views
# -------------------------------------------------------------------------

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
            from .llm_backends import get_all_available_models
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


# -------------------------------------------------------------------------
# Fetch Related Data (AJAX helper)
# -------------------------------------------------------------------------

class FetchRelatedDataView(View):
    def get(self, request, *args, **kwargs):
        course_id = request.GET.get("course_id")
        if not course_id:
            return JsonResponse({"error": "Invalid course ID"}, status=400)

        tasks = Task.objects.filter(course_id=course_id, active=True).values("id", "title")
        criteria = Criteria.objects.filter(course_id=course_id, active=True).values("id", "title")


        return JsonResponse({"tasks": list(tasks), "criteria": list(criteria)})


# -------------------------------------------------------------------------
# Feedback Session Save
# -------------------------------------------------------------------------

def save_feedback_session(request):
    if request.method == "POST":
        try:
            # Ensure the session is saved for anonymous users
            if not request.session.session_key:
                request.session.save()  # create a session key if it doesn't exist

            data = json.loads(request.body)
            feedback_data = data.get("feedback_data")
            if not feedback_data:
                return JsonResponse({"error": "feedback_data is missing or invalid"}, status=400)

            staff_user = request.user.username if request.user.is_authenticated else None
            feedback_id = feedback_data.get("feedback_id")
            course_id = feedback_data.get("course_id")
            user_input = feedback_data.get("user_input", "")
            nps_score = feedback_data.get("nps_score") 

            # Build our new FeedbackSession
            new_session = FeedbackSession(
                feedback_data=feedback_data,
                submission=user_input,
                nps_score=nps_score,
                staff_user=staff_user,
                session_key=request.session.session_key
            )

            # Link the Feedback if present
            if feedback_id:
                try:
                    feedback_obj = Feedback.objects.get(id=feedback_id)
                    new_session.feedback = feedback_obj
                except Feedback.DoesNotExist:
                    pass

            # Link the Course if present
            if course_id:
                try:
                    course_obj = Course.objects.get(id=course_id)
                    new_session.course = course_obj
                except Course.DoesNotExist:
                    pass

            # Save the new session first
            new_session.save()

            # If we received an NPS rating, delete the "old" incomplete session
            #      that has the same session_key (and optionally same feedback).
            #      We only delete sessions that do NOT have an NPS score.
            if nps_score:  # or `if nps_score is not None:`
                # For example, restrict to the same session_key & feedback
                # and no nps_score set previously:
                FeedbackSession.objects.filter(
                    session_key=request.session.session_key,
                    feedback_id=feedback_id,
                    submission=user_input,
                    nps_score__isnull=True
                ).exclude(id=new_session.id).delete()

            return JsonResponse({
                "message": "Feedback session saved successfully",
                "session_id": str(new_session.id)
            })

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON in request body"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

# -------------------------------------------------------------------------
# Analysis for FeedbackSessions
# -------------------------------------------------------------------------

class FeedbackSessionAnalysisView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Filter sessions by course viewing permission with optimized query to avoid N+1 queries
        sessions = FeedbackSession.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).select_related('course', 'feedback', 'feedback__task').order_by('-timestamp').distinct()
        
        session_data = []
        for session in sessions:
            # Ensure feedback_data is a dictionary (fallback to empty dict if None)
            feedback = session.feedback_data or {}
            # Extract only the "criteria" part from the feedback data
            criteria_data = {"criteria": feedback.get("criteria", [])}
            # Convert criteria data to JSON string (preserving special characters)
            criteria_json = json.dumps(criteria_data, cls=DjangoJSONEncoder, ensure_ascii=False)
            
            session_data.append({
                "id": str(session.id),
                "timestamp": session.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                "staff": session.staff_user or "anonymous",
                "submission": session.submission or "",
                "nps": session.nps_score or "",
                "course": session.course.course_name if session.course else "N/A",
                "task": session.feedback.task.title if session.feedback and session.feedback.task else "N/A",
                "criteria_json": criteria_json,
            })
        
        return render(request, "pages/analysis.html", {"feedbacksession_list": session_data})


class FeedbackSessionCSVView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Filter sessions by course viewing permission with optimized query (either through viewing_groups OR editing_groups)
        sessions = FeedbackSession.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).select_related('course', 'feedback', 'feedback__task').order_by('-timestamp').distinct()
        
        # Prepare CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="feedback_sessions.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_ALL)
        
        # Write header row
        writer.writerow([
            'Timestamp', 'Course', 'Task Title',
            'Staff', 'Submission', 'NPS Score', 'Feedback Data'
        ])
        
        # Write a row for each session (no N+1 queries due to select_related)
        for fs in sessions:
            raw_data = fs.feedback_data or {}
            data_string = json.dumps(raw_data, cls=DjangoJSONEncoder, ensure_ascii=False)
            timestamp = fs.timestamp.strftime("%d.%m.%Y %H:%M:%S")
            course_name = fs.course.course_name if fs.course else "N/A"
            task_title = fs.feedback.task.title if fs.feedback and fs.feedback.task else "N/A"
            staff_user = fs.staff_user or "Student"
            submission = fs.submission or ""
            nps_score = fs.nps_score or ""
            writer.writerow([
                timestamp,
                course_name,
                task_title,
                staff_user,
                submission,
                nps_score,
                data_string
            ])
        
        return response


def feedback_pdf_download(request, feedback_session_id):
    """Generate and download PDF for a specific feedback session."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import pytz
    import json
    from django.utils.translation import gettext as _
    
    try:
        # Get the feedback session
        session = FeedbackSession.objects.select_related(
            'course', 'feedback', 'feedback__task'
        ).get(id=feedback_session_id)
        
        # Check if user has permission to download this session
        user_has_permission = (
            # User owns this session (by session key for anonymous users)
            session.session_key == request.session.session_key or
            # Authenticated user who created this session
            (request.user.is_authenticated and request.user.username == session.staff_user) or
            # Users with course viewing/editing permissions
            (session.course and (
                session.course.viewing_groups.filter(id__in=request.user.groups.all()).exists() or
                session.course.editing_groups.filter(id__in=request.user.groups.all()).exists()
            ))
        )
        
        if not user_has_permission:
            return HttpResponseForbidden("You don't have permission to download this feedback.")
        
        # Create HTTP response with PDF content type
        response = HttpResponse(content_type='application/pdf')
        filename = f"feedback_{session.feedback.task.title}_{session.timestamp.astimezone(pytz.timezone('Europe/Berlin')).strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Create PDF document
        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.8*inch)
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            spaceBefore=15
        )
        
        content_style = ParagraphStyle(
            'CustomContent',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            alignment=TA_LEFT
        )
        
        # Build PDF content
        story = []
        
        # Title
        story.append(Paragraph(_("Feedback Report"), title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Header information table
        header_data = [
            [_('Course:'), session.course.course_name if session.course else _('N/A')],
            [_('Task:'), session.feedback.task.title if session.feedback and session.feedback.task else _('N/A')],
            [_('Date:'), session.timestamp.astimezone(pytz.timezone('Europe/Berlin')).strftime('%d.%m.%Y %H:%M:%S')],
        ]
        
        if session.nps_score:
            header_data.append([_('Rating:'), f"{session.nps_score}/10"])
        
        header_table = Table(header_data, colWidths=[1.5*inch, 4*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Task description (if available)
        if session.feedback and session.feedback.task and session.feedback.task.description:
            story.append(Paragraph(_("Task Description"), heading_style))
            task_description = str(session.feedback.task.description) if session.feedback.task.description else _("No description available")
            story.append(Paragraph(task_description, content_style))
            story.append(Spacer(1, 0.2*inch))
        
        # User submission
        story.append(Paragraph(_("User Solution"), heading_style))
        submission_text = str(session.submission) if session.submission else _("No submission provided")
        story.append(Paragraph(submission_text, content_style))
        story.append(Spacer(1, 0.3*inch))
        
        # AI feedback for each criteria
        story.append(Paragraph(_("AI Feedback"), heading_style))
        
        if session.feedback_data:
            try:
                feedback_data = json.loads(session.feedback_data) if isinstance(session.feedback_data, str) else session.feedback_data
                
                # Extract criteria responses from the feedback data structure
                criteria_list = feedback_data.get('criteria', [])
                
                if criteria_list:
                    for criterion in criteria_list:
                        if isinstance(criterion, dict):
                            criteria_title = criterion.get('title', _('Unknown Criteria'))
                            criteria_id = criterion.get('id')
                            feedback_text = criterion.get('ai_response', _('No feedback provided'))
                            
                            # Ensure feedback_text is a string
                            if not isinstance(feedback_text, str):
                                feedback_text = str(feedback_text) if feedback_text else _("No feedback provided")
                            
                            # Get criteria description from database
                            criteria_description = None
                            if criteria_id:
                                try:
                                    from .models import Criteria
                                    criteria_obj = Criteria.objects.get(id=criteria_id)
                                    criteria_description = criteria_obj.description
                                except:
                                    pass
                            
                            # Add criteria title
                            story.append(Paragraph(f"<b>{criteria_title}</b>", content_style))
                            
                            # Add criteria description if available
                            if criteria_description:
                                story.append(Paragraph(f"<i>{_('Description:')}</i> {criteria_description}", content_style))
                                story.append(Spacer(1, 0.1*inch))
                            
                            # Add feedback text
                            story.append(Paragraph(f"<i>{_('Feedback:')}</i>", content_style))
                            story.append(Paragraph(feedback_text, content_style))
                            story.append(Spacer(1, 0.2*inch))
                else:
                    # Fallback: try to find criteria responses in a different structure
                    story.append(Paragraph(_("No criteria feedback found in the expected format"), content_style))
                    
            except (json.JSONDecodeError, TypeError) as e:
                story.append(Paragraph(f"{_('Error parsing feedback data:')} {str(e)}", content_style))
        else:
            story.append(Paragraph(_("No feedback data available"), content_style))
        
        # Build PDF
        doc.build(story)
        
        return response
        
    except FeedbackSession.DoesNotExist:
        return HttpResponseNotFound("Feedback session not found")
    except Exception as e:
        return HttpResponseServerError(f"Error generating PDF: {str(e)}")


# -------------------------------------------------------------------------
# Authentication
# -------------------------------------------------------------------------

class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/accounts/login/")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("/")


class UserPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    form_class = UserPasswordResetForm


class UserPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = UserSetPasswordForm


class UserPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = UserPasswordChangeForm
