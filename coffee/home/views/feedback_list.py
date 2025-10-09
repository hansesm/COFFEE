from django.shortcuts import render
from django.views import View

from coffee.home.models import (
    Course,
    Feedback,
)


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

