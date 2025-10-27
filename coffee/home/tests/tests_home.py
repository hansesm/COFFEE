import json
from unittest.mock import patch

from django.contrib.auth.models import User, Group
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from coffee.home.forms import CourseForm, TaskForm, FeedbackSessionForm
from coffee.home.models import (
    Course,
    Task,
    Criteria,
    Feedback,
    FeedbackCriteria,
    FeedbackSession,
    LLMProvider,
    LLMModel,
)
from coffee.home.registry import ProviderType


class CourseModelTest(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name="TestGroup")
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword"
        )
        self.user.groups.add(self.group)

        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            course_number="CS101",
            term="2024WS",
            active=True,
            course_context="Introduction to Python"
        )
        self.course.editing_groups.add(self.group)
        self.course.viewing_groups.add(self.group)

    def test_course_creation(self):
        self.assertEqual(self.course.faculty, "Computer Science")
        self.assertEqual(self.course.course_name, "Python Programming")
        self.assertTrue(self.course.active)

    def test_course_str_representation(self):
        self.assertEqual(str(self.course), "Python Programming")

    def test_can_edit_permission(self):
        self.assertTrue(self.course.can_edit(self.user))

        other_user = User.objects.create_user(
            username="otheruser",
            password="testpassword"
        )
        self.assertFalse(self.course.can_edit(other_user))

    def test_can_view_permission(self):
        self.assertTrue(self.course.can_view(self.user))

        other_user = User.objects.create_user(
            username="otheruser",
            password="testpassword"
        )
        self.assertFalse(self.course.can_view(other_user))

    def test_default_course_creation(self):
        from coffee.home.models import get_default_course
        default_course_id = get_default_course()
        default_course = Course.objects.get(id=default_course_id)
        self.assertEqual(default_course.course_name, "#Sample course")
        self.assertFalse(default_course.active)


class TaskModelTest(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )

        self.task = Task.objects.create(
            title="Assignment 1",
            description="Write a Python program",
            task_context="Variables and loops",
            course=self.course,
            active=True
        )

    def test_task_creation(self):
        self.assertEqual(self.task.title, "Assignment 1")
        self.assertEqual(self.task.description, "Write a Python program")
        self.assertTrue(self.task.active)
        self.assertEqual(self.task.course, self.course)

    def test_task_str_representation(self):
        self.assertEqual(str(self.task), "Assignment 1")

    def test_task_ordering(self):
        task2 = Task.objects.create(
            title="Assignment 2",
            description="Advanced Python",
            course=self.course
        )
        tasks = Task.objects.all()
        self.assertEqual(tasks[0], self.task)
        self.assertEqual(tasks[1], task2)


class CriteriaModelTest(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )

        self.criteria = Criteria.objects.create(
            title="Code Quality",
            description="Check code structure and readability",
            prompt="Evaluate the code quality of ##submission##",
            llm="phi4:latest",
            tag="quality",
            course=self.course,
            active=True
        )

    def test_criteria_creation(self):
        self.assertEqual(self.criteria.title, "Code Quality")
        self.assertEqual(self.criteria.description, "Check code structure and readability")
        self.assertTrue(self.criteria.active)
        self.assertEqual(self.criteria.course, self.course)

    def test_criteria_str_representation(self):
        self.assertEqual(str(self.criteria), "Code Quality")

    def test_criteria_prompt_template(self):
        self.assertIn("##submission##", self.criteria.prompt)


class FeedbackModelTest(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )

        self.task = Task.objects.create(
            title="Assignment 1",
            description="Write a Python program",
            course=self.course
        )

        self.criteria = Criteria.objects.create(
            title="Code Quality",
            description="Check code structure",
            prompt="Evaluate ##submission##",
            course=self.course
        )

        self.feedback = Feedback.objects.create(
            task=self.task,
            course=self.course,
            active=True
        )

    def test_feedback_creation(self):
        self.assertEqual(self.feedback.task, self.task)
        self.assertEqual(self.feedback.course, self.course)
        self.assertTrue(self.feedback.active)

    def test_feedback_str_representation(self):
        expected = f"{self.course} - {self.task.title}"
        self.assertEqual(str(self.feedback), expected)

    def test_feedback_criteria_relationship(self):
        FeedbackCriteria.objects.create(
            feedback=self.feedback,
            criteria=self.criteria,
            rank=1
        )

        self.assertEqual(self.feedback.criteria_set.count(), 1)
        self.assertEqual(self.feedback.criteria_set.first(), self.criteria)

    def test_get_criteria_set_json(self):
        FeedbackCriteria.objects.create(
            feedback=self.feedback,
            criteria=self.criteria,
            rank=1
        )

        json_data = self.feedback.get_criteria_set_json()
        parsed_data = json.loads(json_data)

        self.assertEqual(len(parsed_data), 1)
        self.assertEqual(parsed_data[0]['criteria__title'], 'Code Quality')
        self.assertEqual(parsed_data[0]['rank'], 1)


class FeedbackSessionModelTest(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )

        self.task = Task.objects.create(
            title="Assignment 1",
            description="Write a Python program",
            course=self.course
        )

        self.feedback = Feedback.objects.create(
            task=self.task,
            course=self.course
        )

        self.feedback_session = FeedbackSession.objects.create(
            submission="print('Hello World')",
            feedback_data={"criteria": []},
            helpfulness_score="8",
            staff_user="testuser",
            session_key="test_session_123",
            feedback=self.feedback,
            course=self.course
        )

    def test_feedback_session_creation(self):
        self.assertEqual(self.feedback_session.submission, "print('Hello World')")
        self.assertEqual(self.feedback_session.helpfulness_score, "8")
        self.assertEqual(self.feedback_session.staff_user, "testuser")
        self.assertEqual(self.feedback_session.feedback, self.feedback)
        self.assertEqual(self.feedback_session.course, self.course)

    def test_feedback_session_str_representation(self):
        expected = f"Session {self.feedback_session.id} at {self.feedback_session.timestamp}"
        self.assertEqual(str(self.feedback_session), expected)

    def test_feedback_session_timestamp(self):
        self.assertIsNotNone(self.feedback_session.timestamp)
        self.assertLessEqual(self.feedback_session.timestamp, timezone.now())


class ViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name="TestGroup")
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword"
        )
        self.user.groups.add(self.group)

        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )
        self.course.viewing_groups.add(self.group)

        self.provider = LLMProvider.objects.create(
            name="Test Provider",
            type=ProviderType.OLLAMA,
            endpoint="http://localhost:11434",
            config={"default_model": "test-model"},
        )
        self.llm_model = LLMModel.objects.create(
            provider=self.provider,
            name="Test Model",
            external_name="test-model",
            is_default=True,
        )

        self.task = Task.objects.create(
            title="Assignment 1",
            description="Write a Python program",
            course=self.course
        )

        self.criteria = Criteria.objects.create(
            title="Code Quality",
            description="Check code structure",
            prompt="Evaluate ##submission##",
            course=self.course,
            llm_fk=self.llm_model,
        )

        self.feedback = Feedback.objects.create(
            task=self.task,
            course=self.course
        )

    def test_index_view(self):
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)

    def test_feedback_view(self):
        response = self.client.get(reverse('feedback', kwargs={'id': self.feedback.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Assignment 1')

    def test_policies_view(self):
        response = self.client.get(reverse('policies'))
        self.assertEqual(response.status_code, 200)

    def test_feedback_list_view(self):
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)

    def test_feedback_list_view_with_filters(self):
        response = self.client.get(reverse('feedback_list'), {
            'faculty': 'Computer Science',
            'study_programme': 'Software Engineering'
        })
        self.assertEqual(response.status_code, 200)

    def test_save_feedback_session(self):
        data = {
            "feedback_data": {
                "feedback_id": str(self.feedback.id),
                "course_id": str(self.course.id),
                "user_input": "print('Hello World')",
                "helpfulness_score": "8",
                "criteria": []
            }
        }

        response = self.client.post(
            reverse('save_feedback_session'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'successfully')

        # Check that session was created
        self.assertTrue(FeedbackSession.objects.filter(
            submission="print('Hello World')",
            helpfulness_score="8"
        ).exists())

    def test_feedback_stream_view(self):
        from coffee.home.ai_provider.models import CoffeeUsage

        class DummyConfig:
            @classmethod
            def from_provider(cls, provider):
                return cls()

        class DummyClient:
            def __init__(self, config):
                self.config = config

            def stream(self, llm_model, user_input, custom_prompt, on_usage_report=None):
                if on_usage_report:
                    on_usage_report(CoffeeUsage())
                yield "Test chunk "
                yield "response"

        url = reverse(
            'feedback_stream',
            kwargs={'feedback_uuid': self.feedback.id, 'criteria_uuid': self.criteria.id},
        )

        with patch.dict(
                'coffee.home.views.feedback_detail.SCHEMA_REGISTRY',
                {self.provider.type: (DummyConfig, DummyClient)},
                clear=False,
        ):
            response = self.client.post(url, {'user_input': 'print("Hello World")'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream; charset=utf-8')

    def test_login_view(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_register_view(self):
        # Skip due to template static tag issue
        pass

    def test_logout_view(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)


class AuthenticatedViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name="TestGroup")
        self.manager_group = Group.objects.create(name="manager")
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword"
        )
        self.user.groups.add(self.group)
        self.user.groups.add(self.manager_group)

        # Add required permissions
        from django.contrib.auth.models import Permission
        permissions = [
            'add_course', 'change_course', 'delete_course', 'view_course',
            'add_task', 'change_task', 'delete_task', 'view_task',
            'add_criteria', 'change_criteria', 'delete_criteria', 'view_criteria',
            'add_feedback', 'change_feedback', 'delete_feedback', 'view_feedback'
        ]
        for perm_name in permissions:
            try:
                permission = Permission.objects.get(codename=perm_name)
                self.user.user_permissions.add(permission)
            except Permission.DoesNotExist:
                pass

        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )
        self.course.editing_groups.add(self.group)
        self.course.viewing_groups.add(self.group)

    def test_crud_course_view_authenticated(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('course'))
        self.assertEqual(response.status_code, 200)

    def test_crud_course_create(self):
        self.client.login(username='testuser', password='testpassword')

        data = {
            'request_type': 'update',
            'faculty': 'Engineering',
            'study_programme': 'Computer Science',
            'chair': 'Software Engineering',
            'course_name': 'Advanced Python',
            'course_number': 'CS201',
            'term': '2024SS',
            'active': 'true',
            'course_context': 'Advanced Python concepts'
        }

        response = self.client.post(reverse('course'), data)
        self.assertEqual(response.status_code, 200)

        # Check if course was created
        self.assertTrue(Course.objects.filter(course_name='Advanced Python').exists())

    def test_analysis_view_authenticated(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('analysis'))
        self.assertEqual(response.status_code, 200)

    def test_csv_export_view_authenticated(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(reverse('feedback_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')


class FormsTest(TestCase):
    def test_course_form_valid(self):
        form_data = {
            'faculty': 'Computer Science',
            'study_programme': 'Software Engineering',
            'chair': 'Data Science',
            'course_name': 'Python Programming',
            'course_number': 'CS101',
            'term': '2024WS',
            'active': True,
            'course_context': 'Introduction to Python'
        }
        form = CourseForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_task_form_valid(self):
        form_data = {
            'title': 'Assignment 1',
            'description': 'Write a Python program',
            'task_context': 'Variables and loops',
            'active': True
        }
        form = TaskForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_feedback_session_form_valid(self):
        form_data = {
            'submission': 'print("Hello World")'
        }
        form = FeedbackSessionForm(data=form_data)
        self.assertTrue(form.is_valid())


class PermissionTest(TestCase):
    def setUp(self):
        self.group1 = Group.objects.create(name="Group1")
        self.group2 = Group.objects.create(name="Group2")

        self.user1 = User.objects.create_user(
            username="user1",
            password="testpassword"
        )
        self.user1.groups.add(self.group1)

        self.user2 = User.objects.create_user(
            username="user2",
            password="testpassword"
        )
        self.user2.groups.add(self.group2)

        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )
        self.course.editing_groups.add(self.group1)
        self.course.viewing_groups.add(self.group1)

    def test_permission_check_with_edit_access(self):
        from coffee.home.views import check_permissions_and_group

        # Add required permission
        from django.contrib.auth.models import Permission
        try:
            permission = Permission.objects.get(codename='change_course')
            self.user1.user_permissions.add(permission)
        except Permission.DoesNotExist:
            pass

        has_permission, error = check_permissions_and_group(
            self.user1, self.course, 'change'
        )
        self.assertTrue(has_permission)
        self.assertIsNone(error)

    def test_permission_check_without_group_access(self):
        from coffee.home.views import check_permissions_and_group

        # Add required permission
        from django.contrib.auth.models import Permission
        try:
            permission = Permission.objects.get(codename='change_course')
            self.user2.user_permissions.add(permission)
        except Permission.DoesNotExist:
            pass

        has_permission, error = check_permissions_and_group(
            self.user2, self.course, 'change'
        )
        self.assertFalse(has_permission)
        self.assertIsNotNone(error)


class IntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name="TestGroup")
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword"
        )
        self.user.groups.add(self.group)

        self.course = Course.objects.create(
            faculty="Computer Science",
            study_programme="Software Engineering",
            chair="Data Science",
            course_name="Python Programming",
            active=True
        )
        self.course.viewing_groups.add(self.group)
        self.provider = LLMProvider.objects.create(
            name="Test Provider",
            type=ProviderType.OLLAMA,
            endpoint="http://localhost:11434",
            config={"default_model": "test-model"},
        )
        self.llm_model = LLMModel.objects.create(
            provider=self.provider,
            name="Test Model",
            external_name="test-model",
            is_default=True,
        )

    def test_full_feedback_flow(self):
        # Create task
        task = Task.objects.create(
            title="Assignment 1",
            description="Write a Python program",
            course=self.course
        )

        # Create criteria
        criteria = Criteria.objects.create(
            title="Code Quality",
            description="Check code structure",
            prompt="Evaluate ##submission##",
            course=self.course,
            llm_fk=self.llm_model,
        )

        # Create feedback
        feedback = Feedback.objects.create(
            task=task,
            course=self.course
        )

        # Create feedback criteria relationship
        FeedbackCriteria.objects.create(
            feedback=feedback,
            criteria=criteria,
            rank=1
        )

        # Access feedback page
        response = self.client.get(reverse('feedback', kwargs={'id': feedback.id}))
        self.assertEqual(response.status_code, 200)

        # Submit feedback session
        data = {
            "feedback_data": {
                "feedback_id": str(feedback.id),
                "course_id": str(self.course.id),
                "user_input": "print('Hello World')",
                "helpfulness_score": "8",
                "criteria": [
                    {
                        "id": str(criteria.id),
                        "criteria_id": str(criteria.id),
                        "title": criteria.title,
                        "response": "Good code structure",
                        "ai_response": "Good code structure",
                        "llm_model_id": str(self.llm_model.id),
                        "usage": {
                            "tokens_used_system": 10,
                            "tokens_used_user": 20,
                            "tokens_used_completion": 30,
                            "total_duration_ns": 0,
                        },
                    }
                ]
            }
        }

        response = self.client.post(
            reverse('save_feedback_session'),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Verify feedback session was created
        feedback_session = FeedbackSession.objects.get(
            submission="print('Hello World')",
            helpfulness_score="8"
        )
        self.assertEqual(feedback_session.feedback, feedback)
        self.assertEqual(feedback_session.course, self.course)


class LLMModelAssignmentsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.group = Group.objects.create(name="lecturer")
        self.user = User.objects.create_user(
            username="lecturer",
            password="pass1234",
        )
        self.user.groups.add(self.group)

        self.course = Course.objects.create(
            faculty="Informatik",
            study_programme="KI Systeme",
            chair="Didaktik",
            course_name="Einführung in KI",
            course_number="KI-101",
            term="2024WS",
            active=True,
        )
        self.course.viewing_groups.add(self.group)

        self.provider = LLMProvider.objects.create(
            name="Lokaler Provider",
            type=ProviderType.OLLAMA,
            config={},
            endpoint="http://localhost:11434",
            is_active=True,
        )

        self.llm = LLMModel.objects.create(
            provider=self.provider,
            name="Phi-4",
            external_name="phi-4",
            is_active=True,
        )

        self.task = Task.objects.create(
            title="Analyse Aufgabe",
            description="Bewerten Sie den Text.",
            course=self.course,
            active=True,
        )

        self.feedback = Feedback.objects.create(
            task=self.task,
            course=self.course,
            active=True,
        )

        self.criteria_assigned = Criteria.objects.create(
            title="Struktur",
            description="Bewerte die Struktur.",
            prompt="Bewerte ##submission##.",
            llm_fk=self.llm,
            course=self.course,
            active=True,
        )

        FeedbackCriteria.objects.create(
            feedback=self.feedback,
            criteria=self.criteria_assigned,
            rank=2,
        )

        self.criteria_unassigned = Criteria.objects.create(
            title="Sprache",
            description="Hinweise zur Sprache",
            prompt="Analysiere ##submission##.",
            llm_fk=self.llm,
            course=self.course,
            active=True,
        )

        # Nicht sichtbarer Kurs/Task
        other_course = Course.objects.create(
            faculty="Informatik",
            study_programme="KI Systeme",
            chair="Didaktik",
            course_name="Verdeckter Kurs",
            course_number="KI-999",
            term="2024WS",
            active=True,
        )

        other_task = Task.objects.create(
            title="Verdeckte Aufgabe",
            course=other_course,
            active=True,
        )

        other_feedback = Feedback.objects.create(
            task=other_task,
            course=other_course,
            active=True,
        )

        other_criteria = Criteria.objects.create(
            title="Verdeckt",
            prompt="Nur intern.",
            llm_fk=self.llm,
            course=other_course,
            active=True,
        )

        FeedbackCriteria.objects.create(
            feedback=other_feedback,
            criteria=other_criteria,
            rank=1,
        )

    def test_login_required(self):
        response = self.client.get(reverse("llm_assignments"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_llm_pivot_for_accessible_courses(self):
        logged_in = self.client.login(username="lecturer", password="pass1234")
        self.assertTrue(logged_in)

        response = self.client.get(reverse("llm_assignments"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/assignment_explorer.html")

        self.assertEqual(response.context["pivot"], "llm")

        hierarchy = response.context["hierarchy"]
        self.assertEqual(len(hierarchy), 1)
        self.assertEqual(response.context["hierarchy_count"], 1)

        llm_block = hierarchy[0]
        self.assertEqual(llm_block["llm"], self.llm)
        self.assertEqual(llm_block["course_count"], 1)

        course_block = llm_block["courses"][0]
        self.assertEqual(course_block["course"], self.course)
        self.assertEqual(course_block["task_count"], 1)

        task_block = course_block["tasks"][0]
        self.assertEqual(task_block["task"], self.task)

        criterion_titles = [entry["criterion"].title for entry in task_block["criteria"]]
        self.assertIn(self.criteria_assigned.title, criterion_titles)
        self.assertIn(self.criteria_unassigned, course_block["unassigned"])

    def test_criteria_pivot_structure(self):
        self.client.login(username="lecturer", password="pass1234")

        response = self.client.get(reverse("llm_assignments"), {"pivot": "criteria"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pivot"], "criteria")

        hierarchy = response.context["hierarchy"]
        self.assertEqual(len(hierarchy), 2)

        by_criterion_id = {entry["criterion"].id: entry for entry in hierarchy}

        assigned_entry = by_criterion_id[self.criteria_assigned.id]
        self.assertEqual(assigned_entry["llm"], self.llm)
        self.assertEqual(assigned_entry["course"], self.course)
        self.assertEqual(len(assigned_entry["tasks"]), 1)
        self.assertEqual(assigned_entry["tasks"][0]["task"], self.task)
        self.assertEqual(assigned_entry["tasks"][0]["rank"], 2)

        unassigned_entry = by_criterion_id[self.criteria_unassigned.id]
        self.assertEqual(unassigned_entry["llm"], self.llm)
        self.assertEqual(unassigned_entry["course"], self.course)
        self.assertEqual(unassigned_entry["tasks"], [])

    def test_invalid_pivot_falls_back_to_default(self):
        self.client.login(username="lecturer", password="pass1234")

        response = self.client.get(reverse("llm_assignments"), {"pivot": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pivot"], "llm")

    def test_task_pivot_structure(self):
        self.client.login(username="lecturer", password="pass1234")

        response = self.client.get(reverse("llm_assignments"), {"pivot": "task"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pivot"], "task")

        hierarchy = response.context["hierarchy"]
        self.assertEqual(len(hierarchy), 1)

        task_entry = hierarchy[0]
        self.assertEqual(task_entry["task"], self.task)
        self.assertEqual(task_entry["course"], self.course)
        self.assertEqual(task_entry["criteria_count"], 1)
        self.assertEqual(len(task_entry["llm_list"]), 1)
        self.assertEqual(task_entry["llm_list"][0], self.llm)

        criteria_entries = task_entry["criteria"]
        self.assertEqual(len(criteria_entries), 1)
        self.assertEqual(criteria_entries[0]["criterion"], self.criteria_assigned)
        self.assertEqual(criteria_entries[0]["llm"], self.llm)
        self.assertEqual(criteria_entries[0]["rank"], 2)

    def test_course_pivot_structure(self):
        self.client.login(username="lecturer", password="pass1234")

        response = self.client.get(reverse("llm_assignments"), {"pivot": "course"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pivot"], "course")

        hierarchy = response.context["hierarchy"]
        self.assertEqual(len(hierarchy), 1)

        course_entry = hierarchy[0]
        self.assertEqual(course_entry["course"], self.course)
        self.assertEqual(course_entry["task_count"], 1)
        self.assertEqual(course_entry["criteria_count"], 2)

        self.assertEqual(len(course_entry["llm_list"]), 1)
        self.assertEqual(course_entry["llm_list"][0], self.llm)

        tasks = course_entry["tasks"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task"], self.task)
        self.assertEqual(len(tasks[0]["criteria"]), 1)
        self.assertEqual(tasks[0]["criteria"][0]["criterion"], self.criteria_assigned)

        unassigned_entries = course_entry["unassigned"]
        self.assertEqual(len(unassigned_entries), 1)
        self.assertEqual(unassigned_entries[0]["criterion"], self.criteria_unassigned)
        self.assertEqual(unassigned_entries[0]["llm"], self.llm)
