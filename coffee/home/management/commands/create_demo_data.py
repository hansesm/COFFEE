from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from coffee.home.models import Course, Task, Criteria, Feedback, FeedbackCriteria, FeedbackSession
from django.utils import timezone


class Command(BaseCommand):
    help = "Create demo data for the COFFEE application including courses, tasks, criteria, feedback, and users"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before creating new data',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.clear_demo_data()

        with transaction.atomic():
            self.create_demo_groups()
            self.create_demo_users()
            self.create_demo_courses()
            self.create_demo_tasks_and_criteria()
            self.create_demo_feedback()
            self.create_demo_sessions()

        self.stdout.write(
            self.style.SUCCESS('Demo data created successfully!')
        )

    def clear_demo_data(self):
        """Clear existing demo data"""
        self.stdout.write('Clearing existing demo data...')
        
        # Delete in proper order to handle protected foreign keys
        from coffee.home.models import FeedbackSession, FeedbackCriteria, Feedback, Task, Criteria
        
        # Delete feedback sessions first
        demo_courses = Course.objects.filter(course_name__startswith='Demo Course')
        session_count = FeedbackSession.objects.filter(course__in=demo_courses).count()
        FeedbackSession.objects.filter(course__in=demo_courses).delete()
        
        # Delete feedback criteria relationships
        feedback_criteria_count = FeedbackCriteria.objects.filter(feedback__course__in=demo_courses).count()
        FeedbackCriteria.objects.filter(feedback__course__in=demo_courses).delete()
        
        # Delete feedback entries
        feedback_count = Feedback.objects.filter(course__in=demo_courses).count()
        Feedback.objects.filter(course__in=demo_courses).delete()
        
        # Delete tasks and criteria
        task_count = Task.objects.filter(course__in=demo_courses).count()
        Task.objects.filter(course__in=demo_courses).delete()
        
        criteria_count = Criteria.objects.filter(course__in=demo_courses).count()
        Criteria.objects.filter(course__in=demo_courses).delete()
        
        # Finally delete courses
        course_count = demo_courses.count()
        demo_courses.delete()
        
        # Delete demo users
        demo_users = User.objects.filter(username__startswith='demo_')
        user_count = demo_users.count()
        demo_users.delete()
        
        # Delete demo groups (but keep manager group)
        demo_groups = Group.objects.filter(name__in=['Demo Viewers', 'Demo Editors'])
        group_count = demo_groups.count()
        demo_groups.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Cleared {course_count} courses, {task_count} tasks, {criteria_count} criteria, {feedback_count} feedback entries, {session_count} sessions, {user_count} users, and {group_count} groups')
        )

    def create_demo_groups(self):
        """Create demo groups for permissions"""
        self.stdout.write('Creating demo groups...')
        
        # Get or create the manager group (needed for management functions)
        self.manager_group, created = Group.objects.get_or_create(name="manager")
        if created:
            self.stdout.write(self.style.SUCCESS('Created "manager" group'))
        
        # Create viewing and editing groups
        self.viewer_group, created = Group.objects.get_or_create(name="Demo Viewers")
        if created:
            self.stdout.write(self.style.SUCCESS('Created "Demo Viewers" group'))
        
        self.editor_group, created = Group.objects.get_or_create(name="Demo Editors")
        if created:
            self.stdout.write(self.style.SUCCESS('Created "Demo Editors" group'))

    def create_demo_users(self):
        """Create 3 demo users with appropriate groups"""
        self.stdout.write('Creating demo users...')
        
        # Demo viewer users (2) - add to both manager and viewer groups
        for i in range(1, 3):
            username = f"demo_viewer_{i}"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f"viewer{i}@demo.com",
                    password="demopassword123",
                    first_name=f"Demo",
                    last_name=f"Viewer {i}"
                )
                user.groups.add(self.manager_group)  # For management access
                user.groups.add(self.viewer_group)   # For course viewing permissions
                self.stdout.write(
                    self.style.SUCCESS(f'Created demo viewer user: {username}')
                )
        
        # Demo editor user (1) - add to both manager and editor groups
        username = "demo_editor"
        if not User.objects.filter(username=username).exists():
            user = User.objects.create_user(
                username=username,
                email="editor@demo.com",
                password="demopassword123",
                first_name="Demo",
                last_name="Editor"
            )
            user.groups.add(self.manager_group)  # For management access
            user.groups.add(self.editor_group)   # For course editing permissions
            self.stdout.write(
                self.style.SUCCESS(f'Created demo editor user: {username}')
            )

    def create_demo_courses(self):
        """Create 3 demo courses with proper permissions"""
        self.stdout.write('Creating demo courses...')
        
        course_data = [
            {
                'course_name': 'Demo Course: Machine Learning Fundamentals',
                'faculty': 'Computer Science',
                'study_programme': 'B.Sc. Computer Science',
                'chair': 'Chair of Artificial Intelligence',
                'course_number': 'CS-ML-101',
                'term': 'Winter 2024/25',
                'course_context': 'This course introduces students to the fundamental concepts of machine learning, including supervised and unsupervised learning algorithms, neural networks, and practical applications.'
            },
            {
                'course_name': 'Demo Course: Data Structures and Algorithms',
                'faculty': 'Computer Science',
                'study_programme': 'B.Sc. Computer Science',
                'chair': 'Chair of Software Engineering',
                'course_number': 'CS-DSA-201',
                'term': 'Winter 2024/25',
                'course_context': 'An advanced course covering fundamental data structures and algorithms, with emphasis on complexity analysis, optimization techniques, and practical problem-solving skills.'
            },
            {
                'course_name': 'Demo Course: Web Development with Django',
                'faculty': 'Computer Science',
                'study_programme': 'M.Sc. Software Engineering',
                'chair': 'Chair of Web Technologies',
                'course_number': 'CS-WEB-301',
                'term': 'Winter 2024/25',
                'course_context': 'A practical course focusing on modern web development using the Django framework, covering backend development, database design, and deployment strategies.'
            }
        ]
        
        self.demo_courses = []
        for course_info in course_data:
            course = Course.objects.create(**course_info)
            course.viewing_groups.add(self.viewer_group)
            course.editing_groups.add(self.editor_group)
            self.demo_courses.append(course)
            self.stdout.write(
                self.style.SUCCESS(f'Created course: {course.course_name}')
            )
            self.stdout.write(
                f'  - Added viewing permissions for: {self.viewer_group.name}'
            )
            self.stdout.write(
                f'  - Added editing permissions for: {self.editor_group.name}'
            )

    def create_demo_tasks_and_criteria(self):
        """Create 5 tasks and 5 criteria for each course"""
        self.stdout.write('Creating demo tasks and criteria...')
        
        for course in self.demo_courses:
            # Create tasks based on course type
            if 'Machine Learning' in course.course_name:
                self.create_ml_tasks_and_criteria(course)
            elif 'Data Structures' in course.course_name:
                self.create_dsa_tasks_and_criteria(course)
            elif 'Web Development' in course.course_name:
                self.create_web_tasks_and_criteria(course)

    def create_ml_tasks_and_criteria(self, course):
        """Create ML-specific tasks and criteria"""
        tasks_data = [
            {
                'title': 'Linear Regression Implementation',
                'description': 'Implement a linear regression algorithm from scratch using Python and NumPy.',
                'task_context': 'Students should demonstrate understanding of gradient descent and cost functions.'
            },
            {
                'title': 'Classification with Decision Trees',
                'description': 'Build a decision tree classifier and evaluate its performance on a given dataset.',
                'task_context': 'Focus on feature selection, pruning techniques, and performance metrics.'
            },
            {
                'title': 'Neural Network Basics',
                'description': 'Create a simple feedforward neural network for image classification.',
                'task_context': 'Implement backpropagation and experiment with different activation functions.'
            },
            {
                'title': 'Clustering Analysis',
                'description': 'Apply K-means clustering to customer segmentation data and analyze results.',
                'task_context': 'Students should justify their choice of K and interpret the clusters.'
            },
            {
                'title': 'Model Evaluation and Validation',
                'description': 'Compare multiple ML algorithms using cross-validation and statistical tests.',
                'task_context': 'Demonstrate understanding of bias-variance tradeoff and overfitting.'
            }
        ]
        
        criteria_data = [
            {
                'title': 'Code Quality and Documentation',
                'description': 'Evaluation of code structure, comments, and documentation',
                'prompt': 'Evaluate the code quality, including proper variable naming, code structure, comments, and documentation. Provide specific feedback on areas for improvement.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Algorithm Implementation Correctness',
                'description': 'Assessment of correct algorithm implementation',
                'prompt': 'Check if the algorithm is implemented correctly according to the theoretical foundations. Identify any logical errors or deviations from standard implementations.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Mathematical Understanding',
                'description': 'Evaluation of mathematical concepts and formulations',
                'prompt': 'Assess the student\'s understanding of the mathematical concepts behind the implementation. Check for correct use of formulas and mathematical reasoning.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Performance Analysis',
                'description': 'Assessment of model performance evaluation',
                'prompt': 'Evaluate how well the student analyzed the performance of their model, including appropriate metrics, validation techniques, and interpretation of results.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Experimental Design',
                'description': 'Evaluation of experimental methodology',
                'prompt': 'Assess the experimental design, including data preprocessing, parameter tuning, and comparison methodology. Provide feedback on scientific rigor.',
                'llm': 'phi4:latest'
            }
        ]
        
        self.create_tasks_and_criteria_for_course(course, tasks_data, criteria_data)

    def create_dsa_tasks_and_criteria(self, course):
        """Create DSA-specific tasks and criteria"""
        tasks_data = [
            {
                'title': 'Binary Search Tree Implementation',
                'description': 'Implement a complete binary search tree with insertion, deletion, and search operations.',
                'task_context': 'Include tree balancing considerations and time complexity analysis.'
            },
            {
                'title': 'Graph Algorithms',
                'description': 'Implement Dijkstra\'s algorithm and demonstrate its use in finding shortest paths.',
                'task_context': 'Students should handle edge cases and provide complexity analysis.'
            },
            {
                'title': 'Dynamic Programming Solutions',
                'description': 'Solve the knapsack problem using dynamic programming approach.',
                'task_context': 'Compare with brute force approach and analyze space-time tradeoffs.'
            },
            {
                'title': 'Sorting Algorithm Comparison',
                'description': 'Implement and compare the performance of quicksort, mergesort, and heapsort.',
                'task_context': 'Provide empirical analysis with different input sizes and data distributions.'
            },
            {
                'title': 'Hash Table Design',
                'description': 'Design and implement a hash table with collision resolution strategies.',
                'task_context': 'Compare different hash functions and collision resolution methods.'
            }
        ]
        
        criteria_data = [
            {
                'title': 'Algorithm Correctness',
                'description': 'Verification of algorithm implementation correctness',
                'prompt': 'Verify that the algorithm is implemented correctly and handles all edge cases. Check for logical errors and adherence to algorithmic principles.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Time and Space Complexity',
                'description': 'Analysis of computational complexity',
                'prompt': 'Evaluate the time and space complexity analysis provided by the student. Check if the analysis is correct and complete.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Code Efficiency',
                'description': 'Assessment of code optimization and efficiency',
                'prompt': 'Assess the efficiency of the implementation. Identify potential optimizations and inefficient code patterns.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Data Structure Design',
                'description': 'Evaluation of data structure choice and design',
                'prompt': 'Evaluate the appropriateness of data structure choices and their design. Consider scalability and maintainability.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Testing and Validation',
                'description': 'Assessment of testing methodology',
                'prompt': 'Evaluate the testing approach, including test cases, edge case handling, and validation methods used.',
                'llm': 'phi4:latest'
            }
        ]
        
        self.create_tasks_and_criteria_for_course(course, tasks_data, criteria_data)

    def create_web_tasks_and_criteria(self, course):
        """Create Web Development-specific tasks and criteria"""
        tasks_data = [
            {
                'title': 'Django Model Design',
                'description': 'Design and implement Django models for a blog application with user authentication.',
                'task_context': 'Include proper relationships, validation, and database optimization considerations.'
            },
            {
                'title': 'RESTful API Development',
                'description': 'Create a RESTful API using Django REST Framework for a task management system.',
                'task_context': 'Implement proper HTTP methods, status codes, and authentication mechanisms.'
            },
            {
                'title': 'Frontend Integration',
                'description': 'Develop a responsive frontend interface that consumes the Django API.',
                'task_context': 'Use modern JavaScript frameworks and ensure mobile compatibility.'
            },
            {
                'title': 'User Authentication System',
                'description': 'Implement a complete user authentication system with registration, login, and permissions.',
                'task_context': 'Include password security, session management, and role-based access control.'
            },
            {
                'title': 'Deployment and Production Setup',
                'description': 'Deploy the Django application to a production environment with proper configuration.',
                'task_context': 'Include database setup, static file handling, and security considerations.'
            }
        ]
        
        criteria_data = [
            {
                'title': 'Django Best Practices',
                'description': 'Adherence to Django conventions and best practices',
                'prompt': 'Evaluate adherence to Django best practices, including project structure, naming conventions, and framework utilization.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Database Design',
                'description': 'Quality of database schema and model design',
                'prompt': 'Assess the database design, including model relationships, normalization, and query optimization considerations.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Security Implementation',
                'description': 'Security measures and vulnerability prevention',
                'prompt': 'Evaluate security implementations, including authentication, authorization, CSRF protection, and input validation.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'API Design and Documentation',
                'description': 'Quality of API design and documentation',
                'prompt': 'Assess the API design quality, including RESTful principles, response formats, error handling, and documentation completeness.',
                'llm': 'phi4:latest'
            },
            {
                'title': 'Frontend User Experience',
                'description': 'User interface design and user experience',
                'prompt': 'Evaluate the frontend implementation, including responsiveness, user interface design, accessibility, and user experience considerations.',
                'llm': 'phi4:latest'
            }
        ]
        
        self.create_tasks_and_criteria_for_course(course, tasks_data, criteria_data)

    def create_tasks_and_criteria_for_course(self, course, tasks_data, criteria_data):
        """Helper method to create tasks and criteria for a specific course"""
        # Create tasks
        course_tasks = []
        for task_info in tasks_data:
            task = Task.objects.create(course=course, **task_info)
            course_tasks.append(task)
            self.stdout.write(f'  Created task: {task.title}')
        
        # Create criteria
        course_criteria = []
        for criteria_info in criteria_data:
            criteria = Criteria.objects.create(course=course, **criteria_info)
            course_criteria.append(criteria)
            self.stdout.write(f'  Created criteria: {criteria.title}')
        
        # Store for feedback creation
        if not hasattr(self, 'course_tasks'):
            self.course_tasks = {}
            self.course_criteria = {}
        
        self.course_tasks[course.id] = course_tasks
        self.course_criteria[course.id] = course_criteria

    def create_demo_feedback(self):
        """Create feedback entries linking tasks with criteria"""
        self.stdout.write('Creating demo feedback entries...')
        
        for course in self.demo_courses:
            tasks = self.course_tasks[course.id]
            criteria = self.course_criteria[course.id]
            
            for task in tasks:
                # Create feedback for each task
                feedback = Feedback.objects.create(
                    task=task,
                    course=course,
                    active=True
                )
                
                # Add all criteria to this feedback with ranks
                for rank, criterion in enumerate(criteria, 1):
                    FeedbackCriteria.objects.create(
                        feedback=feedback,
                        criteria=criterion,
                        rank=rank
                    )
                
                self.stdout.write(f'  Created feedback for: {task.title}')

    def create_demo_sessions(self):
        """Create some demo feedback sessions"""
        self.stdout.write('Creating demo feedback sessions...')
        
        sample_submissions = [
            "I implemented the algorithm according to the specifications. Here's my code and analysis...",
            "My solution uses the approach discussed in class. I've included test cases and performance analysis.",
            "This implementation focuses on efficiency and readability. I've documented all major functions.",
            "I compared multiple approaches and selected the most appropriate one based on the requirements.",
            "The solution handles edge cases and includes comprehensive error checking."
        ]
        
        helpfulness_score = ['1', '2', '3', '4', '5']
        
        for course in self.demo_courses:
            feedbacks = Feedback.objects.filter(course=course)
            
            for i, feedback in enumerate(feedbacks[:3]):  # Create sessions for first 3 feedbacks
                session = FeedbackSession.objects.create(
                    feedback=feedback,
                    course=course,
                    submission=sample_submissions[i % len(sample_submissions)],
                    feedback_data={
                        'criteria_1': {'response': 'Good implementation with clear structure.', 'score': 8},
                        'criteria_2': {'response': 'Algorithm is correct but could be optimized.', 'score': 7},
                        'criteria_3': {'response': 'Mathematical concepts are well understood.', 'score': 9}
                    },
                    helpfulness_score=helpfulness_score[i % len(helpfulness_score)],
                    session_key=f"demo_session_{i}",
                    timestamp=timezone.now()
                )
                self.stdout.write(f'  Created feedback session for: {feedback.task.title}')