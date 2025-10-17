from datetime import timedelta

from django.views import View
from django.shortcuts import render
from django.utils import timezone
from django.db.models.functions import TruncDay, TruncWeek, Coalesce, TruncMonth

from coffee.home.mixins import ManagerRequiredMixin
from coffee.home.models import Course, FeedbackSession, FeedbackCriterionResult
from django.db.models import Q, F, Count, Sum, Avg, Value, DurationField, FloatField, Case, When



class CourseMetricsView(ManagerRequiredMixin, View):
    """
    Kursbasierte, tabellarische Metriken ohne Charts.
    Filter:
      ?course_id=<uuid> (optional, sonst erster sichtbarer Kurs)
      ?start=ISO ?end=ISO
      ?bucket=day|week   (Default: day)
    """
    def get(self, request, *args, **kwargs):
        # --- Sichtbare Kurse (Dropdown) ---
        visible_courses_q = (
            Q(viewing_groups__in=request.user.groups.all()) |
            Q(editing_groups__in=request.user.groups.all())
        )
        courses_qs = (
            Course.objects
            .filter(visible_courses_q, active=True)
            .distinct()
            .order_by("faculty", "course_name")
        )

        # Wenn kein Kurs gewählt ist, nimm den ersten sichtbaren
        selected_course_id = request.GET.get("course_id") or ""
        if not selected_course_id:
            first = courses_qs.values_list("id", flat=True).first()
            selected_course_id = str(first) if first else ""

        # Zeitraum & Bucket
        bucket = (request.GET.get("bucket") or "day").lower()
        start_iso = request.GET.get("start")
        end_iso = request.GET.get("end")
        now = timezone.now()
        time_start = timezone.datetime.fromisoformat(start_iso) if start_iso else now - timedelta(days=30)
        time_end = timezone.datetime.fromisoformat(end_iso) if end_iso else now

        # --- Sessions (nur sichtbarer Kurs + Zeitraum) ---
        sessions = (
            FeedbackSession.objects
            .filter(
                Q(course__viewing_groups__in=request.user.groups.all()) |
                Q(course__editing_groups__in=request.user.groups.all()),
                timestamp__gte=time_start,
                timestamp__lt=time_end,
            )
            .select_related("course", "feedback", "feedback__task")
            .distinct()
        )
        if selected_course_id:
            sessions = sessions.filter(course_id=selected_course_id)

        # --- KPIs ---
        kpi_total_sessions = sessions.count()

        # FloatField -> kein Cast/Regex mehr nötig
        kpi_avg_help = sessions.aggregate(avg=Avg("helpfulness_score"))["avg"]

        # Gesamt-Tokens (über alle CriteriaResults der gefilterten Sessions)
        results = FeedbackCriterionResult.objects.filter(session__in=sessions)
        kpi_total_tokens = results.aggregate(
            total=Coalesce(
                Sum(
                    F("tokens_used_system")
                    + F("tokens_used_user")
                    + F("tokens_used_completion")
                ),
                0,
            )
        )["total"] or 0

        # ===== Tabellen =====
        bucket = (request.GET.get("bucket") or "day").lower()
        if bucket not in {"day", "week", "month"}:
            bucket = "day"

        trunc_fn = (
            TruncWeek if bucket == "week"
            else TruncMonth if bucket == "month"
            else TruncDay
        )

        # A) Aufrufe pro Tag/Woche (Sessions zählen)
        calls_by_bucket = (
            sessions
            .annotate(b=trunc_fn("timestamp"))
            .values("b")
            .annotate(count=Count("id"))
            .order_by("b")
        )
        calls_rows = [
            {
                "bucket": (row["b"].date().isoformat() if hasattr(row["b"], "date") else str(row["b"])),
                "count": row["count"],
            }
            for row in calls_by_bucket
        ]

        # B) Token je Einreichung + Dauer je Einreichung (SUM über alle Results der Session)
        per_submission = (
            sessions
            .annotate(
                tokens=Coalesce(
                    Sum(
                        F("criteria_results__tokens_used_system")
                        + F("criteria_results__tokens_used_user")
                        + F("criteria_results__tokens_used_completion")
                    ),
                    0,
                ),
                total_duration=Coalesce(  # Summe Duration über alle CriteriaResults der Session
                    Sum("criteria_results__generation_duration"),
                    Value(timedelta(0), output_field=DurationField()),
                ),
            )
            .values("id", "timestamp", "feedback__task__title", "tokens", "total_duration")
            .order_by("-timestamp")
        )
        token_rows = [
            {
                "session_id": str(row["id"]),
                "timestamp": row["timestamp"].strftime("%d.%m.%Y %H:%M:%S"),
                "task": row["feedback__task__title"] or "N/A",
                "tokens": int(row["tokens"] or 0),
                "duration_seconds": (
                    row["total_duration"].total_seconds() if row["total_duration"] else 0.0
                ),
            }
            for row in per_submission
        ]

        # KPI: Ø Dauer (s) = Mittel der Session-Gesamtdauern
        avg_duration_td = (
            sessions
            .annotate(
                total_duration=Coalesce(
                    Sum("criteria_results__generation_duration"),
                    Value(timedelta(0), output_field=DurationField()),
                )
            )
            .aggregate(avg=Avg("total_duration"))["avg"]
        )
        kpi_avg_duration_seconds = avg_duration_td.total_seconds() if avg_duration_td else None

        # Dropdown-Daten
        courses_for_select = [
            {"id": str(c.id), "name": f"{c.faculty} – {c.course_name}"}
            for c in courses_qs
        ]
        selected_course_name = ""
        if selected_course_id:
            selected_course_name = (
                courses_qs.filter(id=selected_course_id)
                .values_list("course_name", flat=True)
                .first()
                or ""
            )

        # Average tokens per task without nested aggregates:
        # avg_tokens = total_tokens_across_results_for_task / distinct_sessions_for_task
        avg_tokens_per_task_qs = (
            sessions
            .values(task_title=F("feedback__task__title"))
            .annotate(
                total_tokens=Coalesce(
                    Sum(
                        F("criteria_results__tokens_used_system")
                        + F("criteria_results__tokens_used_user")
                        + F("criteria_results__tokens_used_completion")
                    ),
                    0,
                ),
                session_count=Count("id", distinct=True),  # distinct because of the JOIN to results
            )
            .annotate(
                avg_tokens=Case(
                    When(session_count__gt=0, then=F("total_tokens") * 1.0 / F("session_count")),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
            )
            .order_by("-avg_tokens")
        )

        avg_tokens_per_task = [
            {"task": row["task_title"] or "N/A", "avg_tokens": float(row["avg_tokens"] or 0.0)}
            for row in avg_tokens_per_task_qs
        ]

        context = {
            # Filter
            "courses": courses_for_select,
            "selected_course_id": selected_course_id,
            "selected_course_name": selected_course_name,
            "start": time_start,
            "end": time_end,
            "bucket": bucket,

            # KPIs
            "kpi": {
                "total_sessions": kpi_total_sessions,
                "total_tokens": int(kpi_total_tokens),
                "avg_helpfulness": kpi_avg_help,
                "avg_duration_seconds": kpi_avg_duration_seconds,
            },

            # Tabellen
            "calls_rows": calls_rows,
            "token_rows": token_rows,
            "avg_tokens_per_task": avg_tokens_per_task,
        }
        return render(request, "pages/course_metrics.html", context)
