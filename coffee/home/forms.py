from django import forms
from django.forms import inlineformset_factory
from .models import *
from django import forms
from django.contrib.auth.forms import (
    UserCreationForm,
    AuthenticationForm,
    PasswordChangeForm,
    UsernameField,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "faculty",
            "study_programme",
            "chair",
            "course_name",
            "course_number",
            "term",
            "active",
            "course_context",
        ]


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "active", "task_context"]


class FeedbackSessionForm(forms.ModelForm):
    class Meta:
        model = FeedbackSession
        fields = [
            "submission",
        ]

        widgets = {
            "submission": forms.Textarea(attrs={"class": "form-control", "rows": "35"}),
            "feedback_data": forms.HiddenInput(attrs={"hidden": "true"}),
        }


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["task", "course", "active"]


class FeedbackCriteriaForm(forms.ModelForm):
    class Meta:
        model = FeedbackCriteria
        fields = ["criteria", "rank"]


# Define the formset
FeedbackCriteriaFormSet = inlineformset_factory(
    Feedback, FeedbackCriteria, form=FeedbackCriteriaForm, extra=1, can_delete=True
)


class RegistrationForm(UserCreationForm):
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        ),
    )
    password2 = forms.CharField(
        label=_("Password Confirmation"),
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password Confirmation"}
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
        )

        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Username"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "Email"}
            ),
        }


class LoginForm(AuthenticationForm):
    username = UsernameField(
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username"}
        )
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        ),
    )


class UserPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))


class UserSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        max_length=50,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
        label="New Password",
    )
    new_password2 = forms.CharField(
        max_length=50,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
        label="Confirm New Password",
    )


class UserPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        max_length=50,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Old Password"}
        ),
        label="Old Password",
    )
    new_password1 = forms.CharField(
        max_length=50,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "New Password"}
        ),
        label="New Password",
    )
    new_password2 = forms.CharField(
        max_length=50,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm New Password"}
        ),
        label="Confirm New Password",
    )
