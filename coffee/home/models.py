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
        }
    )[0].id

class Course(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    faculty = models.CharField(max_length=250, db_index=True)  # Indexed for filtering
    study_programme = models.CharField(max_length=250, db_index=True)  # Indexed for filtering
    chair = models.CharField(max_length=250, db_index=True)  # Indexed for filtering
    course_name = models.CharField(max_length=250, db_index=True)  # Indexed for searching
    course_number = models.CharField(max_length=250, blank=True)
    term = models.CharField(max_length=250, blank=True, db_index=True)  # Indexed for filtering
    active = models.BooleanField(default=True, db_index=True)  # Indexed for filtering
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
        indexes = [
            models.Index(fields=['active', 'faculty'], name='idx_course_active_faculty'),
            models.Index(fields=['faculty', 'study_programme'], name='idx_course_faculty_programme'),
        ]

    def __str__(self):
        return self.course_name


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=250, db_index=True)  # Indexed for searching
    active = models.BooleanField(default=True, db_index=True)  # Indexed for filtering
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
        indexes = [
            models.Index(fields=['course', 'active'], name='idx_task_course_active'),
        ]

    def __str__(self):
        return self.title


class Criteria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=250, db_index=True)  # Indexed for searching
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True, db_index=True)  # Indexed for filtering
    llm = models.TextField(null=True, blank=True)
    prompt = models.TextField()
    sequels = models.JSONField(null=True, blank=True, default=dict)
    tag = models.CharField(max_length=250, null=True, blank=True, db_index=True)  # Indexed for filtering by tag

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
        indexes = [
            models.Index(fields=['course', 'active'], name='idx_criteria_course_active'),
        ]

    def __str__(self):
        return self.title


class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.PROTECT, db_index=True)  # Indexed for foreign key lookups
    active = models.BooleanField(default=True, db_index=True)  # Indexed for filtering

    # This still allows referencing the Course (distinct from the Task's Course if needed)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, db_index=True)  # Indexed for foreign key lookups
    
    criteria_set = models.ManyToManyField(Criteria, through="FeedbackCriteria")

    class Meta:
        ordering = ["course"]
        indexes = [
            models.Index(fields=['course', 'active'], name='idx_feedback_course_active'),
        ]

    def __str__(self):
        return f"{self.course} - {self.task.title}"

    def get_criteria_set_json(self):
        # Optimized query with select_related to avoid N+1 queries
        criteria_set_json = FeedbackCriteria.objects.filter(
            feedback=self
        ).select_related('criteria').values(
            "criteria__id", "criteria__title", "rank"
        ).order_by('rank')
        return json.dumps(list(criteria_set_json), cls=DjangoJSONEncoder)


class FeedbackCriteria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, db_index=True)  # Indexed for foreign key lookups
    criteria = models.ForeignKey(Criteria, on_delete=models.CASCADE, db_index=True)  # Indexed for foreign key lookups
    rank = models.IntegerField(null=True, blank=True, default=0, db_index=True)  # Indexed for ordering

    class Meta:
        ordering = ["rank"]
        unique_together = [["feedback", "criteria"]]
        verbose_name = "Feedback Criteria"
        verbose_name_plural = "Feedback Criteria"
        indexes = [
            models.Index(fields=['feedback', 'rank'], name='idx_fbcrit_feedback_rank'),
        ]

    def __str__(self):
        return f"{self.feedback} - {self.criteria.title} (Rank: {self.rank})"


class FeedbackSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)  # Indexed for time-based queries
    session_key = models.TextField(null=True, blank=True, db_index=True)  # Indexed for session lookups
    staff_user = models.TextField(null=True, blank=True, db_index=True)  # Indexed for staff filtering
    submission = models.TextField()
    feedback_data = models.JSONField(default=dict)  
    nps_score = models.CharField(max_length=10, blank=True, null=True)
    feedback = models.ForeignKey(Feedback, null=True, blank=True, on_delete=models.SET_NULL, db_index=True)  # Indexed for foreign key lookups
    # This still allows referencing the Course (distinct from the Feedbacks Course if needed)
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL, db_index=True)  # Indexed for foreign key lookups

    class Meta:
        ordering = ["-timestamp"]  # Most recent first
        indexes = [
            models.Index(fields=['course', 'timestamp'], name='idx_fbsess_course_timestamp'),
            models.Index(fields=['feedback', 'timestamp'], name='idx_fbsess_feedback_timestamp'),
        ]

    def __str__(self):
        return f"Session {self.id} at {self.timestamp}"

