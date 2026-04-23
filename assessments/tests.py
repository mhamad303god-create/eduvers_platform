from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from accounts.models import Role, UserRole, StudentProfile, TeacherProfile
from courses.models import Course
from assessments.models import Assessment, AssessmentQuestion, QuestionChoice, AssessmentAttempt


User = get_user_model()


class AssessmentFlowTests(TestCase):
    def setUp(self):
        self.student_role = Role.objects.create(role_name='student')
        self.teacher_role = Role.objects.create(role_name='teacher')

        self.teacher_user = User.objects.create_user(email='teacher2@test.com', password='pass12345')
        UserRole.objects.create(user=self.teacher_user, role=self.teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(email='student2@test.com', password='pass12345')
        UserRole.objects.create(user=self.student_user, role=self.student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student_user, grade_level='other')

        self.course = Course.objects.create(
            title='Assessment Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        self.assessment = Assessment.objects.create(
            title='Quiz 1',
            type='quiz',
            teacher=self.teacher_profile,
            course=self.course,
            status='published',
            duration_minutes=10
        )

    def test_student_list_access(self):
        self.client.login(username='student2@test.com', password='pass12345')
        response = self.client.get(reverse('assessments:student_assessment_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quiz 1')

    def test_start_attempt_fails_without_questions(self):
        self.client.login(username='student2@test.com', password='pass12345')
        response = self.client.post(reverse('assessments:start_attempt', args=[self.assessment.assessment_id]), data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_take_and_submit_assessment(self):
        q = AssessmentQuestion.objects.create(
            assessment=self.assessment,
            question_text='2 + 2 = ?',
            question_type='multiple_choice',
            points=1,
            difficulty='easy',
            order_index=1
        )
        c1 = QuestionChoice.objects.create(question=q, choice_text='3', is_correct=False, order_index=1)
        c2 = QuestionChoice.objects.create(question=q, choice_text='4', is_correct=True, order_index=2)

        self.client.login(username='student2@test.com', password='pass12345')
        start = self.client.post(reverse('assessments:start_attempt', args=[self.assessment.assessment_id]), data='{}', content_type='application/json')
        self.assertEqual(start.status_code, 200)

        submit = self.client.post(
            reverse('assessments:assessment_take', args=[self.assessment.assessment_id]),
            data={f'question_{q.question_id}': str(c2.choice_id)}
        )
        self.assertEqual(submit.status_code, 302)
        attempt = AssessmentAttempt.objects.get(assessment=self.assessment, student=self.student_profile, attempt_number=1)
        self.assertEqual(attempt.status, 'completed')
        self.assertTrue(float(attempt.percentage) >= 100.0)
