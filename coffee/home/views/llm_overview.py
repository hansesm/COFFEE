from collections import defaultdict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from coffee.home.models import Course, Criteria, FeedbackCriteria


class LLMModelAssignmentsView(LoginRequiredMixin, View):
    """
    Zeigt für Lehrende eine hierarchische Übersicht,
    welche Kriterien (und damit Aufgaben/Kurse) einem Sprachmodell zugeordnet sind.
    """

    template_name = "pages/llm_model_assignments.html"
    DEFAULT_PIVOT = "llm"
    PIVOT_CHOICES = (
        ("llm", _("Sprachmodell")),
        ("criteria", _("Kriterium")),
        ("task", _("Aufgabe")),
        ("course", _("Kurs")),
    )

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
        pivot = self._resolve_pivot(request.GET.get("pivot"))
        visible_course_ids = self._visible_course_ids(request.user)
        context = self._build_initial_context(visible_course_ids, pivot)

        if not visible_course_ids:
            return render(request, self.template_name, context)

        criteria_qs = self._get_visible_criteria(visible_course_ids)

        if not criteria_qs:
            return render(request, self.template_name, context)

        llm_map = self._build_llm_map(criteria_qs, visible_course_ids)
        pivot_payload = self._build_pivot_payload(llm_map)
        hierarchy = pivot_payload.get(pivot, [])

        context["hierarchy"] = hierarchy
        context["hierarchy_count"] = len(hierarchy)
        context["pivot"] = pivot
        context["pivot_choices"] = self.PIVOT_CHOICES
        context["llm_count"] = len(pivot_payload.get("llm", []))
        context["visible_course_count"] = len(visible_course_ids)

        return render(request, self.template_name, context)

    def _resolve_pivot(self, raw_value):
        valid_values = {key for key, _ in self.PIVOT_CHOICES}
        if not raw_value:
            return self.DEFAULT_PIVOT
        if raw_value in valid_values:
            return raw_value
        return self.DEFAULT_PIVOT

    def _visible_course_ids(self, user):
        return [
            course.id for course in self._get_visible_courses(user)
        ]

    def _build_initial_context(self, visible_course_ids, pivot):
        return {
            "hierarchy": [],
            "visible_course_count": len(visible_course_ids),
            "pivot": pivot,
            "pivot_choices": self.PIVOT_CHOICES,
            "hierarchy_count": 0,
            "llm_count": 0,
        }

    def _get_visible_criteria(self, visible_course_ids):
        return list(
            Criteria.objects.filter(
                llm_fk__isnull=False,
                course_id__in=visible_course_ids,
            ).select_related("course", "llm_fk", "llm_fk__provider")
        )

    def _build_llm_map(self, criteria_qs, visible_course_ids):
        criteria_ids = [criterion.id for criterion in criteria_qs]
        feedback_links = self._get_feedback_links(criteria_ids, visible_course_ids)
        llm_map, used_criteria = self._map_feedback_links(feedback_links)
        self._include_unassigned_criteria(criteria_qs, llm_map, used_criteria)
        return llm_map

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

    def _build_pivot_payload(self, llm_map):
        return {
            "llm": self._serialize_llm_hierarchy(llm_map),
            "criteria": self._build_criteria_pivot(llm_map),
            "task": self._build_task_pivot(llm_map),
            "course": self._build_course_pivot(llm_map),
        }

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

    def _build_criteria_pivot(self, llm_map):
        criteria_map = {}

        for llm_data in llm_map.values():
            llm = llm_data["llm"]
            for course_data in llm_data["courses"].values():
                course = course_data.get("course")
                for task_data in course_data["tasks"].values():
                    task = task_data["task"]
                    for entry in task_data["criteria"].values():
                        criterion = entry["criterion"]
                        crit_entry = criteria_map.setdefault(
                            criterion.id,
                            {
                                "criterion": criterion,
                                "llm": llm,
                                "course": course,
                                "tasks": [],
                                "task_count": 0,
                                "has_assignments": False,
                            },
                        )

                        crit_entry["llm"] = llm
                        crit_entry["course"] = course or getattr(criterion, "course", None)
                        crit_entry["tasks"].append(
                            {
                                "task": task,
                                "rank": entry.get("rank"),
                            }
                        )
                        crit_entry["has_assignments"] = True

                for criterion in course_data["unassigned"]:
                    crit_entry = criteria_map.setdefault(
                        criterion.id,
                        {
                            "criterion": criterion,
                            "llm": getattr(criterion, "llm_fk", None),
                            "course": getattr(criterion, "course", None),
                            "tasks": [],
                            "task_count": 0,
                            "has_assignments": False,
                        },
                    )
                    crit_entry.setdefault("course", getattr(criterion, "course", None))
                    crit_entry.setdefault("llm", getattr(criterion, "llm_fk", None))

        criteria_list = []
        for crit_entry in criteria_map.values():
            crit_entry["tasks"].sort(
                key=lambda value: (
                    value["rank"] if value["rank"] is not None else float("inf"),
                    (value["task"].title or "").lower() if value["task"] else "",
                )
            )
            crit_entry["task_count"] = len(crit_entry["tasks"])
            criteria_list.append(crit_entry)

        criteria_list.sort(
            key=lambda value: (
                (value["course"].course_name or "").lower() if value.get("course") else "",
                (value["criterion"].title or "").lower(),
            )
        )

        return criteria_list

    def _build_task_pivot(self, llm_map):
        task_map = {}

        for llm_data in llm_map.values():
            llm = llm_data["llm"]
            for course_data in llm_data["courses"].values():
                course = course_data.get("course")
                for task_data in course_data["tasks"].values():
                    task = task_data["task"]
                    task_entry = task_map.setdefault(
                        task.id,
                        {
                            "task": task,
                            "course": course,
                            "criteria": [],
                            "criteria_count": 0,
                            "llms": {},
                        },
                    )

                    task_entry["course"] = course or getattr(task, "course", None)
                    task_entry["llms"][llm.id] = llm

                    for entry in task_data["criteria"].values():
                        task_entry["criteria"].append(
                            {
                                "criterion": entry["criterion"],
                                "llm": llm,
                                "rank": entry.get("rank"),
                            }
                        )

        task_list = []
        for task_entry in task_map.values():
            task_entry["criteria"].sort(
                key=lambda value: (
                    value["rank"] if value["rank"] is not None else float("inf"),
                    (value["criterion"].title or "").lower(),
                )
            )
            task_entry["criteria_count"] = len(task_entry["criteria"])
            task_entry["llm_list"] = sorted(
                task_entry["llms"].values(),
                key=lambda llm_obj: (
                    (getattr(llm_obj.provider, "name", "") or "").lower(),
                    (llm_obj.name or "").lower(),
                ),
            )
            task_list.append(task_entry)

        task_list.sort(
            key=lambda value: (
                (value["course"].course_name or "").lower() if value.get("course") else "",
                (value["task"].title or "").lower(),
            )
        )

        return task_list

    def _build_course_pivot(self, llm_map):
        course_map = {}

        for llm_data in llm_map.values():
            llm = llm_data["llm"]
            for course_data in llm_data["courses"].values():
                course = course_data.get("course")
                if course is None:
                    continue

                course_entry = course_map.setdefault(
                    course.id,
                    {
                        "course": course,
                        "tasks": {},
                        "task_count": 0,
                        "criteria_count": 0,
                        "llms": {},
                        "unassigned": {},
                    },
                )

                course_entry["llms"][llm.id] = llm

                for task_data in course_data["tasks"].values():
                    task = task_data["task"]
                    task_entry = course_entry["tasks"].setdefault(
                        task.id,
                        {
                            "task": task,
                            "criteria": [],
                        },
                    )

                    for entry in task_data["criteria"].values():
                        task_entry["criteria"].append(
                            {
                                "criterion": entry["criterion"],
                                "llm": llm,
                                "rank": entry.get("rank"),
                            }
                        )

                for criterion in course_data["unassigned"]:
                    existing = course_entry["unassigned"].setdefault(
                        criterion.id,
                        {
                            "criterion": criterion,
                            "llm": getattr(criterion, "llm_fk", None),
                        },
                    )
                    existing.setdefault("llm", getattr(criterion, "llm_fk", None))

        course_list = []
        for course_entry in course_map.values():
            tasks_list = []
            criteria_total = 0

            for task_entry in course_entry["tasks"].values():
                task_entry["criteria"].sort(
                    key=lambda value: (
                        value["rank"] if value["rank"] is not None else float("inf"),
                        (value["criterion"].title or "").lower(),
                    )
                )
                task_entry["criteria_count"] = len(task_entry["criteria"])
                criteria_total += task_entry["criteria_count"]
                tasks_list.append(task_entry)

            tasks_list.sort(
                key=lambda value: (value["task"].title or "").lower()
            )

            unassigned_list = sorted(
                course_entry["unassigned"].values(),
                key=lambda value: (value["criterion"].title or "").lower(),
            )

            criteria_total += len(unassigned_list)

            course_list.append(
                {
                    "course": course_entry["course"],
                    "tasks": tasks_list,
                    "task_count": len(tasks_list),
                    "criteria_count": criteria_total,
                    "llm_list": sorted(
                        course_entry["llms"].values(),
                        key=lambda llm_obj: (
                            (getattr(llm_obj.provider, "name", "") or "").lower(),
                            (llm_obj.name or "").lower(),
                        ),
                    ),
                    "unassigned": unassigned_list,
                }
            )

        course_list.sort(
            key=lambda value: (value["course"].course_name or "").lower()
        )

        return course_list
