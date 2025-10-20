import json

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.http import JsonResponse
from django.urls import reverse, path
from django.utils import timezone
from django.utils.html import format_html

from coffee.home.models import LLMModel, LLMProvider
from coffee.home.registry import SCHEMA_REGISTRY, ProviderType
from coffee.home.security.admin_mixins import PreserveEncryptedOnEmptyAdminMixin


def test_provider_connection(provider: LLMProvider) -> tuple[bool, str]:
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

    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Leave empty to keep the previously stored key."
    )

    class Media:
        js = ("admin/js/admin/ProviderTypeAutosubmit.js",)

    config = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12, "spellcheck": "false", "style": "font-family:monospace"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provider_type = self.data.get("type") or getattr(self.instance, "type", None)
        schema_cls = (SCHEMA_REGISTRY.get(provider_type) or SCHEMA_REGISTRY.get(ProviderType.OLLAMA))[0]
        if self.instance and self.instance.config:
            self.fields["config"].initial = self.instance.config
        self.fields["config"].help_text = schema_help(schema_cls) if schema_cls else \
            f"Free JSON (no registered schema for '{provider_type}')."

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
    change_form_template = "admin/home/provider/change_form_with_test.html"

    def _schema_help_map(self):
        data = {}
        for t, (schema_cls, _provider_cls) in SCHEMA_REGISTRY.items():
            data[t] = schema_help(schema_cls)
        # Fallback-Text für unbekannte Typen
        data["_fallback"] = f"Free JSON (no registered schema)."
        return data

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["schema_help_map_json"] = json.dumps(self._schema_help_map())
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

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

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/test-connection/",
                self.admin_site.admin_view(self.test_connection_view),
                name="home_llmprovider_test_connection",
            ),
            path(
                "test-connection/new/",
                self.admin_site.admin_view(self.test_connection_view),
                name="home_llmprovider_test_connection_new",
            ),
        ]
        return custom + urls

    def test_connection_view(self, request, object_id=None):
        if request.method != "POST":
            return JsonResponse({"ok": False, "message": "POST required"}, status=405)

        # vorhandenes Objekt laden (wenn vorhanden), aber NICHT speichern
        instance = self.get_object(request, object_id) if object_id else None
        form = self.form(request.POST, request.FILES, instance=instance)

        # Validierung der Form (Schema etc.)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

        temp = form.save(commit=False)  # unsaved instance mit aktuellen Formwerten
        ok, msg = test_provider_connection(temp)
        return JsonResponse({"ok": ok, "message": msg})
