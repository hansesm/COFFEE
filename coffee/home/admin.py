from django.db.models import Count
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django import forms
from ollama import Client

from coffee.home.models import LLMModel, ProviderType
from coffee.home.models import Task, Criteria, Feedback, FeedbackCriteria, FeedbackSession, Course, Provider
from coffee.home.security.admin_mixins import PreserveEncryptedOnEmptyAdminMixin

# Register your models here.
admin.site.register(Task)
admin.site.register(Criteria)
admin.site.register(Feedback)
admin.site.register(FeedbackCriteria)
admin.site.register(FeedbackSession)
admin.site.register(Course)


def test_provider_connection(provider: Provider) -> tuple[bool, str]:
    """
    Hier deine echte Verbindungslogik (kurzer Timeout!).
    """
    try:
        if provider.type == ProviderType.OLLAMA:
            def get_primary_headers():
                """Get headers for primary Ollama host"""
                headers = {"Content-Type": "application/json"}
                headers["Authorization"] = f"Bearer {provider.api_key}"
                return headers


            test_client = Client(
                host=provider.endpoint,
                headers=get_primary_headers(),
                timeout=5,  # Short timeout for connection test
            )
            # Lightweight operation here to verify connectivity
            list = test_client.list()
            response_message = f"Successfully. Found {len(list.models)} models!"
        return True, response_message
    except Exception as e:
        return False, str(e)

class ProviderAdminForm(forms.ModelForm):
    class Meta:
        model = Provider
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        data = {f.name: getattr(self.instance, f.name, None) for f in self.instance._meta.fields}
        data.update(cleaned)

        # Secret-Feld: empty api_key in form => use old value
        if self.instance.pk and not cleaned.get("api_key"):
            data["api_key"] = Provider.objects.get(pk=self.instance.pk).api_key

        temp = Provider(**data)

        ok, msg = test_provider_connection(temp)
        if not ok:
            raise ValidationError({"endpoint": f"Connection check failed: {msg}"})

        return cleaned

@admin.register(Provider)
class ProviderAdmin(PreserveEncryptedOnEmptyAdminMixin):
    form = ProviderAdminForm
    list_display = ("name", "type", "is_active", "updated_at")
    list_filter = ("type", "is_active")
    search_fields = ("name", "endpoint")


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

@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "provider",
        "external_name",
        "is_active",
        "criteria_count_link",   # <- neue Zählspalte mit Link
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "external_name", "provider__name")
    list_filter = ("provider", "is_active")
    inlines = [CriteriaInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # WICHTIG: 'llm' entspricht deinem related_name an Criteria.llm_fk
        # Falls du den änderst (z.B. auf "criteria"), hier + in Count anpassen.
        return qs.annotate(_criteria_count=Count("llm", distinct=True))

    @admin.display(ordering="_criteria_count", description="Criteria genutzt")
    def criteria_count_link(self, obj):
        count = getattr(obj, "_criteria_count", 0)
        url = (
            reverse("admin:home_criteria_changelist")
            + f"?llm_fk__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)