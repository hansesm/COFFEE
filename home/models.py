import uuid
from django.db import models
from django.core.serializers import serialize
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.contrib.auth.models import Group


def get_default_course():
    """
    Either create or fetch a specific Course that acts as a 'default course'.
    """
    return Course.objects.get_or_create(
        course_name="#Sample course",
        defaults={
            "faculty": "#Sample Faculty",
            "study_programme": "#Sample Programme",
            "chair": "#Sample Chair",
            "term": "#Sample term",
            "active": False,
        } #needed for migrations
    )[0].id

class Course(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    faculty = models.CharField(max_length=250)
    study_programme = models.CharField(max_length=250)
    chair = models.CharField(max_length=250)
    course_name = models.CharField(max_length=250)
    course_number = models.CharField(max_length=250, blank=True)
    term = models.CharField(max_length=250, blank=True)
    active = models.BooleanField(default=True)
    course_context = models.TextField(null=True, blank=True, max_length=65535)
    editing_groups = models.ManyToManyField(Group, related_name="editable_courses", blank=True)
    viewing_groups = models.ManyToManyField(Group, related_name="viewable_courses", blank=True)
    
    def can_edit(self, user):
        # Check if user is in any group that can edit
        return self.editing_groups.filter(pk__in=user.groups.all()).exists()

    def can_view(self, user):
        # user can view if they can edit OR their group is in viewing_groups
        return self.can_edit(user) or self.viewing_groups.filter(pk__in=user.groups.all()).exists()
    
    class Meta:
        ordering = ["faculty"]
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return self.course_name


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=250)
    active = models.BooleanField(default=True)
    description = models.TextField()
    task_context = models.TextField(null=True, blank=True, max_length=65535)

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="tasks",
        default=get_default_course
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return self.title


class Criteria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=250)
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    llm = models.TextField(null=True, blank=True)
    prompt = models.TextField()
    sequels = models.JSONField(null=True, blank=True, default=dict)
    tag = models.CharField(max_length=250, null=True, blank=True)

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="criteria",
        default=get_default_course
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "Criteria"
        verbose_name_plural = "Criteria"

    def __str__(self):
        return self.title


class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    # This still allows referencing the Course (distinct from the Task’s Course if needed)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    criteria_set = models.ManyToManyField(Criteria, through="FeedbackCriteria")

    class Meta:
        ordering = ["course"]

    def __str__(self):
        return f"{self.course} - {self.task.title}"

    def get_criteria_set_json(self):
        criteria_set_json = FeedbackCriteria.objects.filter(feedback=self).values(
            "criteria__id", "criteria__title", "rank"
        )
        return json.dumps(list(criteria_set_json), cls=DjangoJSONEncoder)


class FeedbackCriteria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE)
    criteria = models.ForeignKey(Criteria, on_delete=models.CASCADE)
    rank = models.IntegerField(null=True, blank=True, default=0)

    class Meta:
        ordering = ["rank"]
        unique_together = [["feedback", "criteria"]]
        verbose_name = "Feedback Criteria"
        verbose_name_plural = "Feedback Criteria"

    def __str__(self):
        return f"{self.feedback} - {self.criteria.title} (Rank: {self.rank})"


class FeedbackSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(default=timezone.now)
    session_key = models.TextField(null=True, blank=True)
    staff_user = models.TextField(null=True, blank=True)
    submission = models.TextField()
    feedback_data = models.JSONField(default=dict)  
    nps_score = models.CharField(max_length=10, blank=True, null=True)
    feedback = models.ForeignKey(Feedback, null=True, blank=True, on_delete=models.SET_NULL)
    # This still allows referencing the Course (distinct from the Feedbacks Course if needed)
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Session {self.id} at {self.timestamp}"

