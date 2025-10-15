from django.db import transaction

from coffee.home.models import FeedbackSession, FeedbackCriterionResult


def check_permissions_and_group(user, instance, permission_codename):
    """
    Check both the global (model-level) permission via user.has_perm(...)
    and the per-object logic via the course's own can_edit() / can_view() methods.
    """

    # 1) Build the global permission name, e.g. "home.change_course"
    model_name = instance.__class__.__name__.lower()
    permission_name = f"home.{permission_codename}_{model_name}"

    # 2) Check the model-level permission
    if not user.has_perm(permission_name):
        return False, f"You do not have global '{permission_codename}' permission on {model_name}."

    # 3) Determine the course object
    if hasattr(instance, "course"):
        course = instance.course  # e.g. feedback.course, task.course, etc.
    else:
        course = instance  # instance is the Course itself

    # 4) Object-level check
    if permission_codename in ["change", "delete"]:
        # Must have "can_edit" on that course
        if not course.can_edit(user):
            return False, f"You are not allowed to {permission_codename} this {model_name}."
    elif permission_codename in ["view"]:
        # Must have "can_view" on that course
        if not course.can_view(user):
            return False, f"You are not allowed to view this {model_name}."

    return True, None


import csv

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from django.utils import translation

from coffee.home.views.feedback_admin import *
from coffee.home.views.feedback_detail import *
from coffee.home.views.feedback_list import *
from coffee.home.views.task import *


# -------------------------------------------------------------------------
# Language / Index
# -------------------------------------------------------------------------

def set_language(request):
    user_language = "de"
    translation.activate(user_language)
    response = HttpResponse(...)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
    return response


def index(request):
    feedback_set = Feedback.objects.all()
    return render(request, "pages/index.html", {"feedback_set": feedback_set})


# -------------------------------------------------------------------------
# Fetch Related Data (AJAX helper)
# -------------------------------------------------------------------------

class FetchRelatedDataView(View):
    def get(self, request, *args, **kwargs):
        course_id = request.GET.get("course_id")
        if not course_id:
            return JsonResponse({"error": "Invalid course ID"}, status=400)

        tasks = Task.objects.filter(course_id=course_id, active=True).values("id", "title")
        criteria = Criteria.objects.filter(course_id=course_id, active=True).values("id", "title")

        return JsonResponse({"tasks": list(tasks), "criteria": list(criteria)})


# -------------------------------------------------------------------------
# Feedback Session Save
# -------------------------------------------------------------------------
def save_feedback_session(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        # Ensure the session is saved for anonymous users
        if not request.session.session_key:
            request.session.save()

        data = json.loads(request.body)
        feedback_data = data.get("feedback_data")
        if not isinstance(feedback_data, dict):
            return JsonResponse({"error": "feedback_data is missing or invalid"}, status=400)

        staff_user = request.user.username if request.user.is_authenticated else None
        feedback_id = feedback_data.get("feedback_id")
        course_id = feedback_data.get("course_id")
        user_input = feedback_data.get("user_input", "")
        helpfulness_score = feedback_data.get("helpfulness_score")

        # Session anlegen + Criteria-Rows in einer TX speichern
        with transaction.atomic():
            # 1) Session erstmal speichern (inkl. Rohdaten für Backward-Compat)
            new_session = FeedbackSession(
                feedback_data=feedback_data,
                submission=user_input,
                helpfulness_score=helpfulness_score,
                staff_user=staff_user,
                session_key=request.session.session_key,
            )

            # Links setzen (best effort)
            if feedback_id:
                try:
                    new_session.feedback = Feedback.objects.get(id=feedback_id)
                except Feedback.DoesNotExist:
                    pass

            if course_id:
                try:
                    new_session.course = Course.objects.get(id=course_id)
                except Course.DoesNotExist:
                    pass

            new_session.save()

            # 2) Kriterien aus feedback_data in FeedbackCriterionResult ablegen
            crit_rows = []
            for crit in (feedback_data.get("criteria") or []):
                u = crit.get("usage") or {}
                llm_external = crit.get("llm") #TODO get llm via FK

                llm_obj = None
                provider_obj = None
                if llm_external:
                    try:
                        llm_obj = LLMModel.objects.get(external_name=llm_external)
                        provider_obj = llm_obj.provider
                    except LLMModel.DoesNotExist:
                        pass

                client_uuid = crit.get("id")
                crit_rows.append(FeedbackCriterionResult(
                    session=new_session,
                    client_criterion_id=client_uuid,
                    title=crit.get("title") or "",
                    ai_response=crit.get("ai_response") or "",
                    llm_model=llm_obj,
                    provider=provider_obj,
                    llm_external_name=llm_external,
                    tokens_used_system=int(u.get("tokens_used_system") or 0),
                    tokens_used_user=int(u.get("tokens_used_user") or 0),
                    tokens_used_completion=int(u.get("tokens_used_completion") or 0)
                ))

            if crit_rows:
                FeedbackCriterionResult.objects.bulk_create(crit_rows, ignore_conflicts=True)

            if helpfulness_score:
                FeedbackSession.objects.filter(
                    session_key=request.session.session_key,
                    feedback_id=feedback_id,
                    submission=user_input,
                    helpfulness_score__isnull=True
                ).exclude(id=new_session.id).delete()

        return JsonResponse({
            "message": "Feedback session saved successfully",
            "session_id": str(new_session.id)
        })

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# -------------------------------------------------------------------------
# Analysis for FeedbackSessions
# -------------------------------------------------------------------------

class FeedbackSessionAnalysisView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Filter sessions by course viewing permission with optimized query to avoid N+1 queries
        sessions = FeedbackSession.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).select_related('course', 'feedback', 'feedback__task').order_by('-timestamp').distinct()

        session_data = []
        for session in sessions:
            # Ensure feedback_data is a dictionary (fallback to empty dict if None)
            feedback = session.feedback_data or {}
            # Extract only the "criteria" part from the feedback data
            criteria_data = {"criteria": feedback.get("criteria", [])}
            # Convert criteria data to JSON string (preserving special characters)
            criteria_json = json.dumps(criteria_data, cls=DjangoJSONEncoder, ensure_ascii=False)

            session_data.append({
                "id": str(session.id),
                "timestamp": session.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                "staff": session.staff_user or "anonymous",
                "submission": session.submission or "",
                "nps": session.helpfulness_score or "",
                "course": session.course.course_name if session.course else "N/A",
                "task": session.feedback.task.title if session.feedback and session.feedback.task else "N/A",
                "criteria_json": criteria_json,
            })

        return render(request, "pages/analysis.html", {"feedbacksession_list": session_data})


class FeedbackSessionCSVView(ManagerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Filter sessions by course viewing permission with optimized query (either through viewing_groups OR editing_groups)
        sessions = FeedbackSession.objects.filter(
            Q(course__viewing_groups__in=request.user.groups.all()) |
            Q(course__editing_groups__in=request.user.groups.all())
        ).select_related('course', 'feedback', 'feedback__task').order_by('-timestamp').distinct()

        # Prepare CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="feedback_sessions.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_ALL)

        # Write header row
        writer.writerow([
            'Timestamp', 'Course', 'Task Title',
            'Staff', 'Submission', 'NPS Score', 'Feedback Data'
        ])

        # Write a row for each session (no N+1 queries due to select_related)
        for fs in sessions:
            raw_data = fs.feedback_data or {}
            data_string = json.dumps(raw_data, cls=DjangoJSONEncoder, ensure_ascii=False)
            timestamp = fs.timestamp.strftime("%d.%m.%Y %H:%M:%S")
            course_name = fs.course.course_name if fs.course else "N/A"
            task_title = fs.feedback.task.title if fs.feedback and fs.feedback.task else "N/A"
            staff_user = fs.staff_user or "Student"
            submission = fs.submission or ""
            helpfulness_score = fs.helpfulness_score or ""
            writer.writerow([
                timestamp,
                course_name,
                task_title,
                staff_user,
                submission,
                helpfulness_score,
                data_string
            ])

        return response


def feedback_pdf_download(request, feedback_session_id):
    """Generate and download PDF for a specific feedback session."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    import pytz
    import json
    from django.utils.translation import gettext as _

    try:
        # Get the feedback session
        session = FeedbackSession.objects.select_related(
            'course', 'feedback', 'feedback__task'
        ).get(id=feedback_session_id)

        # Check if user has permission to download this session
        user_has_permission = (
            # User owns this session (by session key for anonymous users)
                session.session_key == request.session.session_key or
                # Authenticated user who created this session
                (request.user.is_authenticated and request.user.username == session.staff_user) or
                # Users with course viewing/editing permissions
                (session.course and (
                        session.course.viewing_groups.filter(id__in=request.user.groups.all()).exists() or
                        session.course.editing_groups.filter(id__in=request.user.groups.all()).exists()
                ))
        )

        if not user_has_permission:
            return HttpResponseForbidden("You don't have permission to download this feedback.")

        # Create HTTP response with PDF content type
        response = HttpResponse(content_type='application/pdf')
        filename = f"feedback_{session.feedback.task.title}_{session.timestamp.astimezone(pytz.timezone('Europe/Berlin')).strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Create PDF document
        doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.8 * inch)
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            spaceBefore=15
        )

        content_style = ParagraphStyle(
            'CustomContent',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            alignment=TA_LEFT
        )

        # Build PDF content
        story = []

        # Title
        story.append(Paragraph(_("Feedback Report"), title_style))
        story.append(Spacer(1, 0.2 * inch))

        # Header information table
        header_data = [
            [_('Course:'), session.course.course_name if session.course else _('N/A')],
            [_('Task:'), session.feedback.task.title if session.feedback and session.feedback.task else _('N/A')],
            [_('Date:'), session.timestamp.astimezone(pytz.timezone('Europe/Berlin')).strftime('%d.%m.%Y %H:%M:%S')],
        ]

        if session.helpfulness_score:
            header_data.append([_('Rating:'), f"{session.helpfulness_score}/10"])

        header_table = Table(header_data, colWidths=[1.5 * inch, 4 * inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(header_table)
        story.append(Spacer(1, 0.3 * inch))

        # Task description (if available)
        if session.feedback and session.feedback.task and session.feedback.task.description:
            story.append(Paragraph(_("Task Description"), heading_style))
            task_description = str(session.feedback.task.description) if session.feedback.task.description else _(
                "No description available")
            story.append(Paragraph(task_description, content_style))
            story.append(Spacer(1, 0.2 * inch))

        # User submission
        story.append(Paragraph(_("User Solution"), heading_style))
        submission_text = str(session.submission) if session.submission else _("No submission provided")
        story.append(Paragraph(submission_text, content_style))
        story.append(Spacer(1, 0.3 * inch))

        # AI feedback for each criteria
        story.append(Paragraph(_("AI Feedback"), heading_style))

        if session.feedback_data:
            try:
                feedback_data = json.loads(session.feedback_data) if isinstance(session.feedback_data,
                                                                                str) else session.feedback_data

                # Extract criteria responses from the feedback data structure
                criteria_list = feedback_data.get('criteria', [])

                if criteria_list:
                    for criterion in criteria_list:
                        if isinstance(criterion, dict):
                            criteria_title = criterion.get('title', _('Unknown Criteria'))
                            criteria_id = criterion.get('id')
                            feedback_text = criterion.get('ai_response', _('No feedback provided'))

                            # Ensure feedback_text is a string
                            if not isinstance(feedback_text, str):
                                feedback_text = str(feedback_text) if feedback_text else _("No feedback provided")

                            # Get criteria description from database
                            criteria_description = None
                            if criteria_id:
                                try:
                                    from coffee.home.models import Criteria
                                    criteria_obj = Criteria.objects.get(id=criteria_id)
                                    criteria_description = criteria_obj.description
                                except:
                                    pass

                            # Add criteria title
                            story.append(Paragraph(f"<b>{criteria_title}</b>", content_style))

                            # Add criteria description if available
                            if criteria_description:
                                story.append(
                                    Paragraph(f"<i>{_('Description:')}</i> {criteria_description}", content_style))
                                story.append(Spacer(1, 0.1 * inch))

                            # Add feedback text
                            story.append(Paragraph(f"<i>{_('Feedback:')}</i>", content_style))
                            story.append(Paragraph(feedback_text, content_style))
                            story.append(Spacer(1, 0.2 * inch))
                else:
                    # Fallback: try to find criteria responses in a different structure
                    story.append(Paragraph(_("No criteria feedback found in the expected format"), content_style))

            except (json.JSONDecodeError, TypeError) as e:
                story.append(Paragraph(f"{_('Error parsing feedback data:')} {str(e)}", content_style))
        else:
            story.append(Paragraph(_("No feedback data available"), content_style))

        # Build PDF
        doc.build(story)

        return response

    except FeedbackSession.DoesNotExist:
        return HttpResponseNotFound("Feedback session not found")
    except Exception as e:
        return HttpResponseServerError(f"Error generating PDF: {str(e)}")


