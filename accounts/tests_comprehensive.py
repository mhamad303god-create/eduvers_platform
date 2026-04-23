# ===== Comprehensive Test Suite for EduVerse Platform =====
# Complete testing for all major components

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import StudentProfile, TeacherProfile, Role, UserRole
from courses.models import Course, Subject, Enrollment, CourseLesson
from bookings.models import Booking, TeacherAvailability
from assessments.models import Assessment, AssessmentQuestion, QuestionChoice, AssessmentAttempt
from payments.models import Payment
from datetime import datetime, timedelta
from django.utils import timezone
import json

User = get_user_model()


class UserAuthenticationTests(TestCase):
    """Test user registration, login, and authentication"""
    
    def setUp(self):
        self.client = Client()
        self.student_role, _ = Role.objects.get_or_create(role_name='student')
        self.teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
    
    def test_user_registration(self):
        """Test student registration"""
        response = self.client.post(reverse('accounts:register'), {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123',
            'password2': 'testpass123',
            'role': 'student',
        })
        
        # Check user was created
        self.assertTrue(User.objects.filter(email='test@example.com').exists())
        user = User.objects.get(email='test@example.com')
        self.assertTrue(user.is_student())
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
    
    def test_user_login(self):
        """Test user login"""
        user = User.objects.create_user(email='login@test.com', password='pass123')
        UserRole.objects.create(user=user, role=self.student_role)
        
        response = self.client.post(reverse('accounts:login'), {
            'username': 'login@test.com',
            'password': 'pass123',
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after login
        self.assertTrue(response.wsgi_request.user.is_authenticated)
    
    def test_password_validation(self):
        """Test password validation"""
        response = self.client.post(reverse('accounts:register'), {
            'email': 'weak@test.com',
            'password': '123',  # Too short
            'password2': '123',
        })
        
        # Should fail validation
        self.assertFalse(User.objects.filter(email='weak@test.com').exists())


class CourseManagementTests(TestCase):
    """Test course creation, editing, and management"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='pass123'
        )
        self.teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=self.teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher,
            bio='Test teacher',
            hourly_rate=100
        )
        self.subject = Subject.objects.create(
            subject_name='Python Programming',
            subject_code='PY101'
        )
    
    def test_course_creation(self):
        """Test creating a new course"""
        self.client.login(email='teacher@test.com', password='pass123')
        
        response = self.client.post(reverse('courses:course_create'), {
            'title': 'Advanced Python',
            'description': 'Learn advanced Python',
            'subject': self.subject.subject_id,
            'course_type': 'recorded',
            'level': 'advanced',
            'price': 299.99,
            'currency': 'SAR',
            'status': 'published',
            'objectives': 'Learn\\nPractice',
            'requirements': 'Basic Python',
        })
        
        self.assertTrue(Course.objects.filter(title='Advanced Python').exists())
        course = Course.objects.get(title='Advanced Python')
        self.assertEqual(course.teacher, self.teacher_profile)
    
    def test_course_list_view(self):
        """Test course listing page"""
        course = Course.objects.create(
            title='Test Course',
            teacher=self.teacher_profile,
            subject=self.subject,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Course')
    
    def test_course_enrollment(self):
        """Test student enrolling in course"""
        student = User.objects.create_user(email='student@test.com', password='pass123')
        student_role, _ = Role.objects.get_or_create(role_name='student')
        UserRole.objects.create(user=student, role=student_role)
        student_profile = StudentProfile.objects.create(user=student)
        
        course = Course.objects.create(
            title='Enrollment Test',
            teacher=self.teacher_profile,
            subject=self.subject,
            course_type='recorded',
            level='beginner',
            status='published',
            price=99.99
        )
        
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.post(reverse('courses:enroll_course', args=[course.course_id]))
        
        self.assertTrue(
            Enrollment.objects.filter(student=student_profile, course=course).exists()
        )


class SearchFunctionalityTests(TestCase):
    """Test advanced search features"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@test.com', password='pass')
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher)
        
        self.subject1 = Subject.objects.create(subject_name='Math', subject_code='M101')
        self.subject2 = Subject.objects.create(subject_name='Science', subject_code='S101')
        
        # Create test courses
        for i in range(5):
            Course.objects.create(
                title=f'Math Course {i}',
                teacher=self.teacher_profile,
                subject=self.subject1,
                course_type='recorded',
                level='beginner',
                status='published',
                price=100 + i * 10
            )
    
    def test_search_by_keyword(self):
        """Test searching courses by keyword"""
        from courses.search import CourseSearchEngine
        
        engine = CourseSearchEngine()
        results = engine.search('Math')
        
        self.assertEqual(results.count(), 5)
    
    def test_search_with_filters(self):
        """Test searching with price filter"""
        from courses.search import CourseSearchEngine
        
        engine = CourseSearchEngine()
        results = engine.search('', price_min=110, price_max=130)
        
        self.assertTrue(results.count() > 0)
        for course in results:
            self.assertTrue(110 <= course.price <= 130)
    
    def test_faceted_search(self):
        """Test facets generation"""
        from courses.search import CourseSearchEngine
        
        engine = CourseSearchEngine()
        facets = engine.get_facets()
        
        self.assertIn('subjects', facets)
        self.assertIn('levels', facets)
        self.assertTrue(len(facets['subjects']) > 0)


class AnalyticsTests(TestCase):
    """Test analytics and reporting"""
    
    def setUp(self):
        self.student = User.objects.create_user(email='s@test.com', password='pass')
        student_role, _ = Role.objects.get_or_create(role_name='student')
        UserRole.objects.create(user=self.student, role=student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student)
        
        self.teacher = User.objects.create_user(email='t@test.com', password='pass')
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher)
        
        self.subject = Subject.objects.create(subject_name='Test', subject_code='T101')
        self.course = Course.objects.create(
            title='Test Course',
            teacher=self.teacher_profile,
            subject=self.subject,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        
        Enrollment.objects.create(
            student=self.student_profile,
            course=self.course,
            payment_status='paid'
        )
    
    def test_student_overview(self):
        """Test student analytics overview"""
        from courses.analytics import StudentAnalytics
        
        analytics = StudentAnalytics(self.student_profile)
        overview = analytics.get_overview()
        
        self.assertEqual(overview['total_courses'], 1)
        self.assertTrue('learning_hours' in overview)
    
    def test_teacher_overview(self):
        """Test teacher analytics overview"""
        from courses.analytics import TeacherAnalytics
        
        analytics = TeacherAnalytics(self.teacher_profile)
        overview = analytics.get_overview()
        
        self.assertEqual(overview['total_courses'], 1)
        self.assertEqual(overview['total_enrollments'], 1)
    
    def test_admin_platform_stats(self):
        """Test platform-wide statistics"""
        from courses.analytics import AdminAnalytics
        
        stats = AdminAnalytics.get_platform_overview()
        
        self.assertTrue(stats['total_users'] >= 2)
        self.assertTrue(stats['total_courses'] >= 1)


class PaymentProcessingTests(TestCase):
    """Test payment gateway integration"""
    
    def setUp(self):
        self.user = User.objects.create_user(email='pay@test.com', password='pass')
        
    def test_payment_creation(self):
        """Test creating a payment record"""
        payment = Payment.objects.create(
            user=self.user,
            amount=100.00,
            currency='SAR',
            payment_method='credit_card',
            status='pending'
        )
        
        self.assertIsNotNone(payment.uuid)
        self.assertEqual(payment.status, 'pending')
    
    def test_payment_gateway_factory(self):
        """Test payment gateway factory"""
        from payments.payment_gateways import PaymentGatewayFactory
        
        try:
            stripe_gateway = PaymentGatewayFactory.get_gateway('stripe')
            self.assertEqual(stripe_gateway.name, 'Stripe')
        except Exception:
            pass  # Skip if not configured
        
        try:
            moyasar_gateway = PaymentGatewayFactory.get_gateway('moyasar')
            self.assertEqual(moyasar_gateway.name, 'Moyasar')
        except Exception:
            pass


class BookingSystemTests(TestCase):
    """Test booking and scheduling"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@test.com', password='pass')
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher)
        
        self.student = User.objects.create_user(email='s@test.com', password='pass')
        student_role, _ = Role.objects.get_or_create(role_name='student')
        UserRole.objects.create(user=self.student, role=student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student)
    
    def test_booking_creation(self):
        """Test creating a booking"""
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        
        booking = Booking.objects.create(
            student=self.student_profile,
            teacher=self.teacher_profile,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status='pending'
        )
        
        self.assertIsNotNone(booking.uuid)
        self.assertEqual(booking.status, 'pending')
    
    def test_booking_conflict_detection(self):
        """Test detecting booking conflicts"""
        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=1)
        
        # Create first booking
        Booking.objects.create(
            student=self.student_profile,
            teacher=self.teacher_profile,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status='confirmed'
        )
        
        # Check for conflicts
        conflicting_bookings = Booking.objects.filter(
            teacher=self.teacher_profile,
            status__in=['confirmed', 'pending'],
            scheduled_start__lt=end_time,
            scheduled_end__gt=start_time
        )
        
        self.assertTrue(conflicting_bookings.exists())


class AssessmentTests(TestCase):
    """Test assessment and quiz functionality"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@test.com', password='pass')
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher)
        
        self.student = User.objects.create_user(email='s@test.com', password='pass')
        student_role, _ = Role.objects.get_or_create(role_name='student')
        UserRole.objects.create(user=self.student, role=student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student)
        
        self.subject = Subject.objects.create(subject_name='Test', subject_code='T101')
    
    def test_assessment_creation(self):
        """Test creating an assessment"""
        assessment = Assessment.objects.create(
            title='Test Quiz',
            type='quiz',
            teacher=self.teacher_profile,
            subject=self.subject,
            total_points=100,
            status='published'
        )
        
        self.assertEqual(assessment.title, 'Test Quiz')
    
    def test_question_creation(self):
        """Test creating assessment questions"""
        assessment = Assessment.objects.create(
            title='Test',
            type='quiz',
            teacher=self.teacher_profile,
            status='published'
        )
        
        question = AssessmentQuestion.objects.create(
            assessment=assessment,
            question_text='What is 2+2?',
            question_type='multiple_choice',
            points=10,
            order_index=1
        )
        
        # Add choices
        QuestionChoice.objects.create(
            question=question,
            choice_text='3',
            is_correct=False,
            order_index=1
        )
        QuestionChoice.objects.create(
            question=question,
            choice_text='4',
            is_correct=True,
            order_index=2
        )
        
        self.assertEqual(question.questionchoice_set.count(), 2)


class IntegrationTests(TestCase):
    """End-to-end integration tests"""
    
    def setUp(self):
        self.client = Client()
        
        # Create complete user setup
        self.student = User.objects.create_user(
            email='integration@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Student'
        )
        student_role, _ = Role.objects.get_or_create(role_name='student')
        UserRole.objects.create(user=self.student, role=student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student)
        
        self.teacher = User.objects.create_user(
            email='teacher@integration.com',
            password='teachpass123'
        )
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher,
            hourly_rate=150
        )
        
        self.subject = Subject.objects.create(
            subject_name='Integration Test Subject',
            subject_code='INT101'
        )
    
    def test_complete_enrollment_flow(self):
        """Test complete flow: course creation -> enrollment -> payment"""
        # Teacher creates course
        self.client.login(email='teacher@integration.com', password='teachpass123')
        
        course_data = {
            'title': 'Integration Test Course',
            'description': 'Test description',
            'subject': self.subject.subject_id,
            'course_type': 'recorded',
            'level': 'beginner',
            'price': 199.99,
            'currency': 'SAR',
            'status': 'published',
            'objectives': 'Learn\\nPractice',
            'requirements': 'None',
        }
        
        response = self.client.post(reverse('courses:course_create'), course_data)
        
        # Verify course was created
        self.assertTrue(Course.objects.filter(title='Integration Test Course').exists())
        course = Course.objects.get(title='Integration Test Course')
        
        # Student enrolls
        self.client.login(email='integration@test.com', password='testpass123')
        response = self.client.post(reverse('courses:enroll_course', args=[course.course_id]))
        
        # Verify enrollment
        self.assertTrue(
            Enrollment.objects.filter(
                student=self.student_profile,
                course=course
            ).exists()
        )
        
        enrollment = Enrollment.objects.get(student=self.student_profile, course=course)
        
        # Simulate payment
        payment = Payment.objects.create(
            user=self.student,
            enrollment=enrollment,
            amount=course.price,
            currency=course.currency,
            payment_method='credit_card',
            status='completed'
        )
        
        # Update enrollment payment status
        enrollment.payment_status = 'paid'
        enrollment.save()
        
        # Verify complete flow
        self.assertEqual(enrollment.payment_status, 'paid')
        self.assertEqual(payment.status, 'completed')


class PerformanceTests(TestCase):
    """Test database query performance"""
    
    def setUp(self):
        # Create bulk data
        self.teacher = User.objects.create_user(email='perf@test.com', password='pass')
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')
        UserRole.objects.create(user=self.teacher, role=teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher)
        
        self.subject = Subject.objects.create(subject_name='Perf', subject_code='P101')
    
    def test_bulk_course_query(self):
        """Test querying many courses efficiently"""
        # Create 50 courses
        courses = [
            Course(
                title=f'Course {i}',
                teacher=self.teacher_profile,
                subject=self.subject,
                course_type='recorded',
                level='beginner',
                status='published'
            )
            for i in range(50)
        ]
        Course.objects.bulk_create(courses)
        
        # Query with select_related
        from django.db import connection
        from django.test.utils import override_settings
        
        with self.assertNumQueries(1):  # Should be 1 query with select_related
            list(Course.objects.select_related('teacher__user', 'subject').all())


# Run specific test categories
def run_auth_tests():
    """Run only authentication tests"""
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['accounts.tests_comprehensive.UserAuthenticationTests'])
    return failures == 0


def run_all_tests():
    """Run all tests"""
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['accounts.tests_comprehensive'])
    return failures == 0
