import json
import uuid
from datetime import timedelta

import django
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from coffee.home.security.encryption import EncryptedTextField
from coffee.home.registry import ProviderType
from coffee.home.validations import validate_config_for_type


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


def get_default_llm():
    provider, _ = LLMProvider.objects.get_or_create(
        name="Default", defaults={"type": ProviderType.OLLAMA, "config": {}, "endpoint": "", "is_active": True}
    )
    llm, _ = LLMModel.objects.get_or_create(
        provider=provider,
        external_name="phi-4",
        defaults={"name": "phi-4", "default_params": {}, "is_active": False},
    )
    return llm.id


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

class LLMProvider(models.Model):
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=32, choices=ProviderType.choices)

    # Configuration (validated via Pydantic)
    config = models.JSONField(default=dict, blank=True)

    # Encrypted API Key
    api_key = EncryptedTextField(blank=True, default="")
    endpoint = models.URLField(blank=True, default="")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    token_limit = models.PositiveBigIntegerField(
        default=0,
        help_text="Max. Tokens per Interval. 0 = No Limit."
    )
    token_reset_interval = models.DurationField(
        default=timedelta(hours=24),
        help_text="Reset-Interval (e.g. 24h)."
    )
    last_reset_at = models.DateTimeField(null=True, blank=True, default=django.utils.timezone.now)

    @transaction.atomic
    def reset_quota(self, at=None, save=True):
        self.last_reset_at = at or timezone.now()
        if save:
            self.save(update_fields=["last_reset_at"])
        return self.last_reset_at

    @transaction.atomic
    def roll_window_optimistic(self) -> bool:
        now = timezone.now()
        start, end = self.quota_window_bounds()
        if now > end:
            updated = (
                LLMProvider.objects
                .filter(pk=self.pk)
                .update(last_reset_at=now)
            )
            if updated:
                self.last_reset_at = now
                return True
        return False

    def quota_window_bounds(self):
        start = self.last_reset_at
        end = start + self.token_reset_interval
        return start, end

    def used_tokens_soft(self) -> int:
        """Summe der in der Fensterzeit verbrauchten Tokens (system + user + completion)."""
        if self.token_limit == 0:
            return 0
        start, end = self.quota_window_bounds()

        qs = FeedbackCriterionResult.objects.filter(
            provider=self,
            created_at__gte=start,
            created_at__lt=end,
        )

        agg = qs.aggregate(
            sys=Coalesce(Sum("tokens_used_system"), 0),
            usr=Coalesce(Sum("tokens_used_user"), 0),
            comp=Coalesce(Sum("tokens_used_completion"), 0),
        )
        return int(agg["sys"] + agg["usr"] + agg["comp"])

    def soft_limit_exceeded(self, planned_tokens: int = 0) -> bool:
        if self.token_limit == 0:
            return False
        return (self.used_tokens_soft() + planned_tokens) >= self.token_limit

    def remaining_tokens_soft(self, planned_tokens: int = 0):
        if self.token_limit == 0:
            return None  # unlimited
        rem = self.token_limit - self.used_tokens_soft() - planned_tokens
        return max(0, rem)

    class Meta:
        verbose_name = "LLM Provider"
        verbose_name_plural = "LLM Providers"
        db_table = "home_provider"
        indexes = [
            models.Index(fields=["type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name}"

    def clean(self):
        try:
            validate_config_for_type(self.type, self.config)
        except ValueError as e:
            raise ValidationError({"config": str(e)})

        errors = {}
        if self.type in [ProviderType.AZURE_OPENAI, ProviderType.AZURE_AI]:
            if not self.endpoint:
                errors["endpoint"] = "Endpoint ist erforderlich."
            if not self.api_key:
                errors["api_key"] = "API-Key ist erforderlich."
        elif self.type == ProviderType.OLLAMA:
            # Meist nur ein lokaler Endpoint, kein Key erforderlich
            if not self.endpoint:
                errors["endpoint"] = "Base-URL/Endpoint ist erforderlich (z. B. http://localhost:11434)."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LLMModel(models.Model):
    """
    Konfigurierbares Sprachmodell eines Providers.
    Beispiel:
      - external_name: "gpt-4o-mini" (oder "Meta-Llama-3.1-70B")
      - deployment_name: bei Azure-OpenAI der konkrete Deployment-Name
    """

    provider = models.ForeignKey(
        LLMProvider,
        on_delete=models.PROTECT,
        related_name="llm_models",
    )

    # Anzeigename intern (frei wählbar)
    name = models.CharField(max_length=100)

    # Externer Modell-Identifikator (z. B. "gpt-4o", "gpt-4o-mini", "mistral-large")
    external_name = models.CharField(max_length=200)

    # Default-Parameter, die beim Aufruf genutzt werden können (temperature, top_p, max_tokens, etc.)
    default_params = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Save to obtain primary key
            super().save(*args, **kwargs)
            if self.is_default:
                # Reset other default model
                (self.__class__.objects
                 .exclude(pk=self.pk)
                 .filter(is_default=True)
                 .update(is_default=False))

    @classmethod
    def get_default(cls):
        try:
            return cls.objects.get(is_default=True)
        except ObjectDoesNotExist:
            # Fallback: take first active model
            return cls.objects.filter(is_active=True).first()

    class Meta:
        verbose_name = "LLM Model"
        verbose_name_plural = "LLM Models"
        models.UniqueConstraint(fields=["provider", "external_name"], name="unique_provider_external-name")
        indexes = [
            models.Index(fields=["provider", "is_active"]),
            models.Index(fields=["external_name"]),
        ]

    def display_name(self):
        return f"{self.provider.name}: {self.name} [{self.external_name}]"

    def __str__(self):
        return self.display_name()

    def clean(self):
        """
        Typabhängige Minimal-Validierung:
        - Azure OpenAI/Azure AI: Deployment-Name sinnvollerweise Pflicht
        - Ollama: external_name Pflicht (z. B. 'llama3:8b'), deployment optional
        """
        errors = {}

        # immer: external_name erforderlich
        if not self.external_name:
            errors["external_name"] = "Externer Modellname ist erforderlich."

        if errors:
            raise ValidationError(errors)

class Criteria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=250, db_index=True)  # Indexed for searching
    description = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True, db_index=True)  # Indexed for filtering
    llm = models.TextField(null=True, blank=True, help_text="Deprecated")
    llm_fk = models.ForeignKey(
        LLMModel,
        on_delete=models.RESTRICT,
        related_name="llm",
        null=True, blank=True
    )
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
        models.UniqueConstraint(fields=["feedback", "criteria"], name="unique_feedback_criteria")
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
    helpfulness_score = models.CharField(max_length=10, blank=True, null=True)
    feedback = models.ForeignKey(Feedback, null=True, blank=True, on_delete=models.SET_NULL,
                                 db_index=True)  # Indexed for foreign key lookups
    # This still allows referencing the Course (distinct from the Feedbacks Course if needed)
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL,
                               db_index=True)  # Indexed for foreign key lookups

    class Meta:
        verbose_name = "Feedback Session"
        verbose_name_plural = "Feedback Sessions"
        ordering = ["-timestamp"]  # Most recent first
        indexes = [
            models.Index(fields=['course', 'timestamp'], name='idx_fbsess_course_timestamp'),
            models.Index(fields=['feedback', 'timestamp'], name='idx_fbsess_feedback_timestamp'),
        ]

    def __str__(self):
        return f"Session {self.id} at {self.timestamp}"

class FeedbackCriterionResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        FeedbackSession, on_delete=models.CASCADE,
        related_name="criteria_results", db_index=True
    )
    # Client-seitige Kriteriums-ID (aus feedback_data.criteria[i].id)
    client_criterion_id = models.UUIDField(db_index=True)

    title = models.TextField(blank=True, null=True)

    # Antwort
    ai_response = models.TextField(blank=True, null=True)

    # LLM / Provider (optional direkte FKs; alternativ: strings)
    llm_model = models.ForeignKey(
        LLMModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="criterion_results"
    )
    provider = models.ForeignKey(
        LLMProvider, on_delete=models.SET_NULL, null=True, blank=True, related_name="criterion_results"
    )
    llm_external_name = models.TextField(blank=True, null=True)  # z.B. "phi4:latest"

    # Usage (normalisiert, gleiche Semantik wie Session)
    tokens_used_system = models.PositiveBigIntegerField(default=0)
    tokens_used_user = models.PositiveBigIntegerField(default=0)
    tokens_used_completion = models.PositiveBigIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Feedback Criteria Result"
        verbose_name_plural = "Feedback Criteria Results"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "client_criterion_id"],
                name="uq_critresult_session_clientid",
            )
        ]
        indexes = [
            models.Index(fields=["llm_model", "created_at"], name="idx_crit_llm_time"),
            models.Index(fields=["provider", "created_at"], name="idx_crit_provider_time"),
        ]

    @property
    def tokens_used_total(self) -> int:
        return (self.tokens_used_system or 0) + (self.tokens_used_user or 0) + (self.tokens_used_completion or 0)

