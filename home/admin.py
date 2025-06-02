from django.contrib import admin
from .models import Task, Criteria, Feedback, FeedbackCriteria, FeedbackSession, Course

# Register your models here.
admin.site.register(Task)
admin.site.register(Criteria)
admin.site.register(Feedback)
admin.site.register(FeedbackCriteria)
admin.site.register(FeedbackSession)
admin.site.register(Course)