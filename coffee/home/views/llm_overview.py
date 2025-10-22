from collections import defaultdict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render
from django.views import View

from coffee.home.models import Course, Criteria, FeedbackCriteria


class LLMModelAssignmentsView(LoginRequiredMixin, View):
    """
    Zeigt für Lehrende eine hierarchische Übersicht,
    welche Kriterien (und damit Aufgaben/Kurse) einem Sprachmodell zugeordnet sind.
    """

    template_name = "pages/llm_model_assignments.html"

    def _get_visible_courses(self, user):
        if user.is_superuser:
            return Course.objects.all()

        if not user.is_authenticated:
            return Course.objects.none()

        groups = user.groups.all()
        if not groups.exists():
            return Course.objects.none()

        return Course.objects.filter(
            Q(editing_groups__in=groups) | Q(viewing_groups__in=groups)
        ).distinct()

    def get(self, request, *args, **kwargs):
        visible_course_ids = self._visible_course_ids(request.user)
        context = self._build_initial_context(visible_course_ids)

        if not visible_course_ids:
            return render(request, self.template_name, context)

        criteria_qs = self._get_visible_criteria(visible_course_ids)

        if not criteria_qs:
            return render(request, self.template_name, context)

        llm_hierarchy = self._build_llm_hierarchy(criteria_qs, visible_course_ids)

        context["llm_hierarchy"] = llm_hierarchy
        context["llm_count"] = len(llm_hierarchy)
        context["visible_course_count"] = len(visible_course_ids)

        return render(request, self.template_name, context)

    def _visible_course_ids(self, user):
        return [
            course.id for course in self._get_visible_courses(user)
        ]

    def _build_initial_context(self, visible_course_ids):
        return {
            "llm_hierarchy": [],
            "visible_course_count": len(visible_course_ids),
        }

    def _get_visible_criteria(self, visible_course_ids):
        return list(
            Criteria.objects.filter(
                llm_fk__isnull=False,
                course_id__in=visible_course_ids,
            ).select_related("course", "llm_fk", "llm_fk__provider")
        )

    def _build_llm_hierarchy(self, criteria_qs, visible_course_ids):
        criteria_ids = [criterion.id for criterion in criteria_qs]
        feedback_links = self._get_feedback_links(criteria_ids, visible_course_ids)
        llm_map, used_criteria = self._map_feedback_links(feedback_links)
        self._include_unassigned_criteria(criteria_qs, llm_map, used_criteria)
        return self._serialize_llm_hierarchy(llm_map)

    def _get_feedback_links(self, criteria_ids, visible_course_ids):
        return FeedbackCriteria.objects.filter(
            criteria_id__in=criteria_ids,
            feedback__course_id__in=visible_course_ids,
            feedback__active=True,
            feedback__task__active=True,
        ).select_related(
            "criteria",
            "criteria__course",
            "criteria__llm_fk",
            "criteria__llm_fk__provider",
            "feedback",
            "feedback__task",
            "feedback__course",
        ).order_by(
            "feedback__course__course_name",
            "feedback__task__title",
            "rank",
            "criteria__title",
        )

    def _map_feedback_links(self, feedback_links):
        llm_map = {}
        used_criteria = set()

        for link in feedback_links:
            criterion = link.criteria
            llm = getattr(criterion, "llm_fk", None)
            if llm is None:
                continue

            used_criteria.add(criterion.id)

            llm_entry = llm_map.setdefault(
                llm.id,
                {"llm": llm, "courses": defaultdict(lambda: {"tasks": {}, "unassigned": []})},
            )

            course = link.feedback.course or criterion.course
            course_entry = llm_entry["courses"][course.id]
            course_entry.setdefault("course", course)

            task = link.feedback.task
            if task is None:
                continue

            task_entry = course_entry["tasks"].setdefault(
                task.id,
                {"task": task, "criteria": {}},
            )

            crit_entry = task_entry["criteria"].setdefault(
                criterion.id,
                {"criterion": criterion, "rank": link.rank},
            )

            if link.rank is not None:
                previous_rank = crit_entry.get("rank")
                if previous_rank is None or link.rank < previous_rank:
                    crit_entry["rank"] = link.rank

        return llm_map, used_criteria

    def _include_unassigned_criteria(self, criteria_qs, llm_map, used_criteria):
        for criterion in criteria_qs:
            llm = getattr(criterion, "llm_fk", None)
            if llm is None:
                continue

            llm_entry = llm_map.setdefault(
                llm.id,
                {"llm": llm, "courses": defaultdict(lambda: {"tasks": {}, "unassigned": []})},
            )

            course = criterion.course
            course_entry = llm_entry["courses"][course.id]
            course_entry.setdefault("course", course)

            if criterion.id not in used_criteria:
                course_entry["unassigned"].append(criterion)

    def _serialize_llm_hierarchy(self, llm_map):
        def llm_sort_key(item):
            llm_obj = item[1]["llm"]
            provider_name = getattr(llm_obj.provider, "name", "") if llm_obj.provider else ""
            return (provider_name.lower(), llm_obj.name.lower())

        llm_hierarchy = []

        for _, llm_data in sorted(llm_map.items(), key=llm_sort_key):
            courses_list = []
            for _, course_data in sorted(
                llm_data["courses"].items(),
                key=lambda value: (value[1]["course"].course_name or "").lower(),
            ):
                tasks_list = []
                for task_data in sorted(
                    course_data["tasks"].values(),
                    key=lambda value: (value["task"].title or "").lower(),
                ):
                    criteria_list = sorted(
                        task_data["criteria"].values(),
                        key=lambda entry: (
                            entry["rank"] if entry["rank"] is not None else float("inf"),
                            entry["criterion"].title.lower(),
                        ),
                    )
                    tasks_list.append(
                        {
                            "task": task_data["task"],
                            "criteria": criteria_list,
                            "criteria_count": len(criteria_list),
                        }
                    )

                unassigned_sorted = sorted(
                    course_data["unassigned"],
                    key=lambda crit: (crit.title or "").lower(),
                )

                courses_list.append(
                    {
                        "course": course_data["course"],
                        "tasks": tasks_list,
                        "unassigned": unassigned_sorted,
                        "task_count": len(tasks_list),
                        "criteria_count": (
                            sum(task["criteria_count"] for task in tasks_list)
                            + len(unassigned_sorted)
                        ),
                    }
                )

            llm_hierarchy.append(
                {
                    "llm": llm_data["llm"],
                    "courses": courses_list,
                    "course_count": len(courses_list),
                    "criteria_count": sum(course["criteria_count"] for course in courses_list),
                }
            )

        return llm_hierarchy
