# Optimized Views for COFFEE Application
# Replace the existing views in home/views.py with these optimized versions

import json
from django.core.cache import cache
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, Prefetch
from django.shortcuts import render
from django.views import View
from .models import Course, Feedback, FeedbackSession, FeedbackCriteria
from .mixins import ManagerRequiredMixin


class OptimizedFeedbackListView(View):
    """Optimized version of FeedbackListView with better query performance"""
    
    def get(self, request, *args, **kwargs):
        # Single optimized query with select_related
        feedbacks = Feedback.objects.filter(active=True).select_related(
            "course", "task"
        ).order_by("course", "task")

        # Collect filter values
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


class OptimizedCrudFeedbackView(ManagerRequiredMixin, View):
    """Optimized version of CrudFeedbackView with N+1 query fixes"""
    
    def get(self, request, *args, **kwargs):
        # Optimized queries with proper select_related and prefetch_related
        feedback_list = Feedback.objects.filter(
            course__viewing_groups__in=request.user.groups.all()
        ).select_related('course', 'task').prefetch_related(
            Prefetch('feedbackcriteria_set', 
                    queryset=FeedbackCriteria.objects.select_related('criteria').order_by('rank'))
        ).distinct().order_by("task")

        course_list = Course.objects.filter(
            viewing_groups__in=request.user.groups.all()
        ).distinct().only('id', 'course_name', 'faculty')  # Only load necessary fields

        task_list = Task.objects.filter(
            course__viewing_groups__in=request.user.groups.all(),
            active=True
        ).select_related('course').distinct().only('id', 'title', 'course__course_name')

        criteria_set = Criteria.objects.filter(
            course__viewing_groups__in=request.user.groups.all(),
            active=True
        ).select_related('course').distinct().only('id', 'title', 'course__course_name')

        # Pre-compute criteria JSON to avoid N+1 queries
        feedback_criteria_data = {}
        for feedback in feedback_list:
            criteria_data = []
            for fc in feedback.feedbackcriteria_set.all():
                criteria_data.append({
                    "criteria__id": str(fc.criteria.id),
                    "criteria__title": fc.criteria.title,
                    "rank": fc.rank
                })
            feedback_criteria_data[feedback.id] = json.dumps(criteria_data, cls=DjangoJSONEncoder)

        # Assign pre-computed JSON data
        for feedback in feedback_list:
            feedback.criteria_set_json = feedback_criteria_data.get(feedback.id, "[]")

        context = {
            "feedback_list": feedback_list,
            "course_list": course_list,
            "task_list": task_list,
            "criteria_set": criteria_set,
        }
        return render(request, "pages/crud_feedback.html", context)


class OptimizedFeedbackSessionAnalysisView(ManagerRequiredMixin, View):
    """Optimized version of FeedbackSessionAnalysisView with pagination and N+1 fixes"""
    
    def get(self, request, *args, **kwargs):
        # Single optimized query with all necessary relations
        sessions = FeedbackSession.objects.filter(
            course__viewing_groups__in=request.user.groups.all()
        ).select_related(
            'course', 'feedback', 'feedback__task'
        ).order_by('-timestamp').distinct()

        # Add pagination for better performance with large datasets
        paginator = Paginator(sessions, 50)  # Show 50 sessions per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Process sessions efficiently (no N+1 queries)
        session_data = []
        for session in page_obj:
            # All related data is already loaded via select_related
            criteria_data = {"criteria": (session.feedback_data or {}).get("criteria", [])}
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

        context = {
            "feedbacksession_list": session_data,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
        }
        return render(request, "pages/analysis.html", context)


class OptimizedFeedbackSessionCSVView(ManagerRequiredMixin, View):
    """Optimized CSV export with efficient query"""
    
    def get(self, request, *args, **kwargs):
        # Optimized query for CSV export
        sessions = FeedbackSession.objects.filter(
            course__viewing_groups__in=request.user.groups.all()
        ).select_related(
            'course', 'feedback', 'feedback__task'
        ).order_by('-timestamp').distinct()

        # Prepare CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="feedback_sessions.csv"'
        
        import csv
        writer = csv.writer(response, quoting=csv.QUOTE_ALL)
        
        # Write header row
        writer.writerow([
            'Timestamp', 'Course', 'Task Title',
            'Staff', 'Submission', 'NPS Score', 'Feedback Data'
        ])
        
        # Write data efficiently (no N+1 queries)
        for session in sessions:
            raw_data = session.feedback_data or {}
            data_string = json.dumps(raw_data, cls=DjangoJSONEncoder, ensure_ascii=False)
            
            writer.writerow([
                session.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                session.course.course_name if session.course else "N/A",
                session.feedback.task.title if session.feedback and session.feedback.task else "N/A",
                session.staff_user or "Student",
                session.submission or "",
                session.nps_score or "",
                data_string
            ])
        
        return response


# Performance monitoring decorator
def monitor_queries(view_func):
    """Decorator to monitor database queries in development"""
    def wrapper(request, *args, **kwargs):
        from django.db import connection
        from django.conf import settings
        
        if settings.DEBUG:
            initial_queries = len(connection.queries)
            
        response = view_func(request, *args, **kwargs)
        
        if settings.DEBUG:
            final_queries = len(connection.queries)
            query_count = final_queries - initial_queries
            print(f"View {view_func.__name__} executed {query_count} queries")
            
        return response
    return wrapper


# Usage example:
# @monitor_queries
# def my_view(request):
#     # Your view code here
#     pass