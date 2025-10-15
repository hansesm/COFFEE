from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, path
from django.utils import timezone
from django.utils.html import format_html

from coffee.home.models import LLMModel, Task, Criteria, Feedback, FeedbackCriteria, FeedbackSession, \
    Course, LLMProvider, FeedbackCriterionResult
from coffee.home.security.admin_mixins import PreserveEncryptedOnEmptyAdminMixin
from coffee.home.registry import SCHEMA_REGISTRY

admin.site.register(Task)
admin.site.register(Criteria)
admin.site.register(Feedback)
admin.site.register(FeedbackCriteria)
admin.site.register(FeedbackSession)
admin.site.register(FeedbackCriterionResult)
admin.site.register(Course)



def test_provider_connection(provider: LLMProvider) -> tuple[bool, str]:
    """
    Hier deine echte Verbindungslogik (kurzer Timeout!).
    """
    try:
        provider_config, provider_class = SCHEMA_REGISTRY[provider.type]
        config = provider_config.from_provider(provider)
        test_client = provider_class(config)
        return test_client.test_connection()
    except Exception as e:
        return False, str(e)

def schema_help(schema_cls):
    lines = []
    for name, field in schema_cls.model_fields.items():
        extra = field.json_schema_extra or {}
        if extra.get("admin_visible") is False:
            continue

        desc = field.description or ""
        default = field.default if field.default is not None else "—"
        typ = getattr(field.annotation, "__name__", str(field.annotation))
        lines.append(f"- <code>{name}</code> ({typ}, default: {default}) {desc}")
    return "<br>".join(lines)


@admin.action(description="Reset token quota window now")
def reset_quota_now(modeladmin, request, queryset):
    for p in queryset:
        p.reset_quota()

class LLMProviderAdminForm(forms.ModelForm):
    class Meta:
        model = LLMProvider
        fields = "__all__"

    class Media:
        js = ("admin/js/admin/ProviderTypeAutosubmit.js",)

    config = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12, "spellcheck": "false", "style": "font-family:monospace"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Typ ermitteln (bei Add ggf. aus POST)
        provider_type = self.data.get("type") or getattr(self.instance, "type", None)
        schema_cls = SCHEMA_REGISTRY.get(provider_type)
        schema_cls = schema_cls[0]

        # JSON initial befüllen
        if self.instance and self.instance.config:
            self.fields["config"].initial = self.instance.config

        # Hilfetext aus Pydantic-Schema
        if schema_cls:
            self.fields["config"].help_text = schema_help(schema_cls)
        else:
            self.fields["config"].help_text = f"Free JSON (no registriertes Schema for '{provider_type}')."

    def clean(self):
        cleaned = super().clean()

        data = {f.name: getattr(self.instance, f.name, None) for f in self.instance._meta.fields}
        data.update(cleaned)

        # Secret-Feld: empty api_key in form => use old value
        if self.instance.pk and not cleaned.get("api_key"):
            data["api_key"] = LLMProvider.objects.get(pk=self.instance.pk).api_key

        temp = LLMProvider(**data)

        ok, msg = test_provider_connection(temp)
        if not ok:
            raise ValidationError({"endpoint": f"Connection check failed: {msg}"})

        return cleaned

class ProviderModelsInline(admin.TabularInline):
    model = LLMModel
    fields = ("name_link", "external_name", "is_default", "is_active")
    readonly_fields = ("name_link", "external_name", "is_default", "is_active")
    extra = 0
    show_change_link = True
    can_delete = False

    @admin.display(description="Name")
    def name_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:home_llmmodel_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.name)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LLMProvider)
class LLMProviderAdmin(PreserveEncryptedOnEmptyAdminMixin):
    form = LLMProviderAdminForm
    list_display = ("name", "type", "is_active", "models_count_link", "quota_soft", "next_reset_eta", "updated_at")
    list_filter = ("type", "is_active")
    search_fields = ("name", "endpoint")
    inlines = [ProviderModelsInline]
    actions = [reset_quota_now]

    def get_fields(self, request, obj=None):
        return [
            "name",
            "type",
            "endpoint",
            "api_key",
            "is_active",
            "token_limit",
            "token_reset_interval",
            "config"
        ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_models_count=Count("llm_models", distinct=True))

    @admin.display(ordering="_models_count", description="LLM Models")
    def models_count_link(self, obj):
        count = getattr(obj, "_models_count", 0)
        url = reverse("admin:home_llmmodel_changelist") + f"?provider__id__exact={obj.id}"
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description="Quota (soft)")
    def quota_soft(self, obj):
        if obj.token_limit == 0:
            return format_html('<span style="color:gray;">unlimited</span>')

        used = obj.used_tokens_soft()
        limit = obj.token_limit
        percent = used / limit if limit else 0

        if used > limit:
            color = "#b00"  # rot: exceeded
            weight = "bold"
        elif percent > 0.9:
            color = "#e67e22"  # orange: >90%
            weight = "bold"
        elif percent > 0.7:
            color = "#f1c40f"  # gelb: >70%
            weight = "normal"
        else:
            color = "#2ecc71"  # grün: ok
            weight = "normal"

        used_str = f"{used:,}"
        limit_str = f"{limit:,}"

        return format_html(
            '<span style="color:{}; font-weight:{};">{} / {}</span>',
            color, weight, used_str, limit_str
        )

    @admin.display(description="Next reset")
    def next_reset_eta(self, obj):
        if obj.token_limit == 0:
            return "—"
        start, end = obj.quota_window_bounds()
        overdue = timezone.now() >= end
        text = timezone.localtime(end).strftime("%d.%m.%Y %H:%M")
        return format_html(
            '<span style="{}">{}</span>',
            "color:#b00;font-weight:600;" if overdue else "",
            text
        )


class CriteriaInline(admin.TabularInline):
    model = Criteria
    fields = ("title_link", "active", "course")
    readonly_fields = ("title_link", "course", "active")
    extra = 0
    show_change_link = True
    raw_id_fields = ("course",)
    can_delete = False

    @admin.display(description="Title")
    def title_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:home_criteria_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)

    def has_add_permission(self, request, obj=None):
        return False


class ReassignForm(forms.Form):
    """Formular zum Umhängen aller Criteria eines LLM auf ein anderes LLM."""
    target_llm = forms.ModelChoiceField(
        queryset=LLMModel.objects.none(),
        label="Target-LLM",
        help_text="All criteria linked to this LLM will be reassigned to the selected LLM",
    )
    confirm = forms.BooleanField(
        required=True,
        label="Confirm bulk change"
    )

    def __init__(self, *args, current_llm=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = LLMModel.objects.all()
        if current_llm is not None:
            qs = qs.exclude(pk=current_llm.pk)
        self.fields["target_llm"].queryset = qs

@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider",
        "external_name",
        "is_default_icon",
        "is_active",
        "criteria_count_link",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "external_name", "provider__name")
    list_filter = ("provider", "is_active", "is_default")
    inlines = [CriteriaInline]

    change_form_template = "admin/home/llmmodel/change_form.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_criteria_count=Count("llm", distinct=True))

    @admin.display(boolean=True, description="Default", ordering="is_default")
    def is_default_icon(self, obj):
        return obj.is_default

    @admin.display(ordering="_criteria_count", description="Used in Criteria")
    def criteria_count_link(self, obj):
        count = getattr(obj, "_criteria_count", 0)
        url = (
                reverse("admin:home_criteria_changelist")
                + f"?llm_fk__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/bulk-reassign/",
                self.admin_site.admin_view(self.bulk_reassign_view),
                name="home_llmmodel_bulk_reassign",
            )
        ]
        return custom + urls

    def bulk_reassign_view(self, request, object_id, *args, **kwargs):
        llm_model = get_object_or_404(LLMModel, pk=object_id)

        # Berechtigung: nur wer dieses Objekt ändern darf
        if not self.has_change_permission(request, llm_model):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        # Anzahl der betroffenen Criteria vorab
        affected_qs = Criteria.objects.filter(llm_fk=llm_model)
        affected_count = affected_qs.count()

        if request.method == "POST":
            form = ReassignForm(request.POST, current_llm=llm_model)
            if form.is_valid():
                target = form.cleaned_data["target_llm"]

                if target.pk == llm_model.pk:
                    form.add_error("target_llm", "The target LLM must be distinct from the previous model.")
                else:
                    with transaction.atomic():
                        updated = affected_qs.update(llm_fk=target)
                    messages.success(
                        request,
                        "{} Criteria was changed to '{}'.".format(updated, target)
                    )

                    change_url = reverse("admin:home_llmmodel_change", args=[llm_model.pk])
                    return redirect(change_url)
        else:
            form = ReassignForm(current_llm=llm_model)

        context = {
            **self.admin_site.each_context(request),
            "title": "Bulk: Change LLM for Criteria",
            "original": llm_model,
            "opts": self.model._meta,
            "form": form,
            "affected_count": affected_count,
        }
        return render(request, "admin/home/llmmodel/bulk_reassign.html", context)

    # Link in Tools in Toolbar upper right
    def render_change_form(self, request, context, *args, **kwargs):
        obj = context.get("original")
        if obj and self.has_change_permission(request, obj):
            context["bulk_reassign_url"] = reverse(
                "admin:home_llmmodel_bulk_reassign", args=[obj.pk]
            )
        return super().render_change_form(request, context, *args, **kwargs)
