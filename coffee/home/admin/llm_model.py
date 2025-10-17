from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, path
from django.utils.html import format_html

from coffee.home.models import LLMModel, Criteria


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