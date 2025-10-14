# app/admin_mixins.py
from django import forms
from django.contrib import admin
from django.db.models import Field
from coffee.home.security.encryption import EncryptedTextField

class PreserveEncryptedOnEmptyAdminMixin(admin.ModelAdmin):
    """
    Sorgt dafür, dass EncryptedTextField-Werte erhalten bleiben,
    wenn der Admin sie leer lässt (nicht überschreibt).
    Außerdem sorgt get_form() dafür, dass die Felder maskiert bleiben
    (falls ein externes Form irgendwas überschreibt).
    """

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Safety: erzwinge PasswordInput + Hint (falls externe Form was ändert)
        for name, f in self._encrypted_fields():
            if name in form.base_fields:
                bf = form.base_fields[name]
                if not isinstance(bf.widget, forms.PasswordInput):
                    bf.widget = forms.PasswordInput(render_value=False, attrs={"placeholder": "••••••••"})
                if not bf.help_text:
                    bf.help_text = "Leer lassen, um bestehenden Wert unverändert zu lassen."
                bf.required = False
        return form

    def save_model(self, request, obj, form, change):
        if change and obj.pk:
            # Für alle EncryptedTextFields: leere Eingaben -> alten Wert beibehalten
            old_obj = self.model.objects.only(*(n for n, _ in self._encrypted_fields())).get(pk=obj.pk)
            for name, _ in self._encrypted_fields():
                if name in form.cleaned_data:
                    new_val = form.cleaned_data.get(name)
                    if new_val in (None, ""):
                        setattr(obj, name, getattr(old_obj, name))
        return super().save_model(request, obj, form, change)

    def _encrypted_fields(self):
        # Liefert (feldname, feldobjekt) aller EncryptedTextFields des Modells
        for f in self.model._meta.get_fields():
            if isinstance(f, Field) and isinstance(f, EncryptedTextField):
                yield f.name, f
