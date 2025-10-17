from django.contrib import admin

from coffee.home.models import Task, Criteria, Feedback, FeedbackCriteria, FeedbackSession, \
    Course, FeedbackCriterionResult

admin.site.register(Task)
admin.site.register(Criteria)
admin.site.register(Feedback)
admin.site.register(FeedbackCriteria)
admin.site.register(FeedbackSession)
admin.site.register(Course)

@admin.register(FeedbackCriterionResult)
class FeedbackCriterionResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "created_at",
    )

    ordering = ("-created_at",)
    date_hierarchy = "created_at"
