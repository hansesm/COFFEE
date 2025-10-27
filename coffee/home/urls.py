from django.urls import path

from django.contrib.auth import views as auth_views
from django.conf.urls import include
from django.views.generic import TemplateView

from coffee.home.views import *
from coffee.home.views.utils import feedback_pdf_download, FeedbackSessionAnalysisView, FeedbackSessionCSVView, \
    save_feedback_session, FetchRelatedDataView
from coffee.home.views.metrics import CourseMetricsView

urlpatterns = [
    path("", FeedbackListView.as_view(), name="feedback_list"),
    path("feedback/<uuid:id>/", feedback, name="feedback"),
    path("feedback/", feedback, name="feedback"),
    path("newtask/", task, name="newtask"),
    path(
        "feedback-stream/<uuid:feedback_uuid>/<uuid:criteria_uuid>/",
        feedback_stream,
        name="feedback_stream",
    ),
    path("course/", CrudCourseView.as_view(), name="course"),
    path("criteria/", CrudCriteriaView.as_view(), name="criteria"),
    path("task/", CrudTaskView.as_view(), name="task"),
    path(
        "managefeedback/",
        CrudFeedbackView.as_view(),
        name="managefeedback",
    ),
    path("analysis/", FeedbackSessionAnalysisView.as_view(), name="analysis"),
    path("analysis/download/", FeedbackSessionCSVView.as_view(), name="feedback_csv"),
    path("feedback/<uuid:feedback_session_id>/download/", feedback_pdf_download, name="feedback_pdf_download"),
    path("accounts/login/", UserLoginView.as_view(), name="login"),
    path("accounts/logout/", logout_view, name="logout"),
    path("models/assignments/", AssignmentExplorerView.as_view(), name="llm_assignments"),
    path("accounts/register/", register, name="register"),
    path(
        "accounts/password-change/",
        UserPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "accounts/password-change-done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path(
        "accounts/password-reset/",
        UserPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "accounts/password-reset-confirm/<uidb64>/<token>/",
        UserPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "accounts/password-reset-done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("i18n/", include("django.conf.urls.i18n")),
    path("save-feedback-session/", save_feedback_session, name="save_feedback_session"),
    path('fetch-related-data/', FetchRelatedDataView.as_view(), name='fetch_related_data'),
    path('policies/', policies, name='policies'),
    # Account page that shows user information
    path('account/', TemplateView.as_view(template_name="pages/account.html"), name="account"),
    path("metrics/criteria/", CourseMetricsView.as_view(), name="criteria_metrics"),
]
