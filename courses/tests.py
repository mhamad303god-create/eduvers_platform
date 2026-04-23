from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal

from accounts.models import Role, UserRole, TeacherProfile, StudentProfile
from courses.models import Course, CourseLesson
import json


User = get_user_model()


class CourseVisibilityTests(TestCase):
    def setUp(self):
        self.teacher_role = Role.objects.create(role_name='teacher')
        self.student_role = Role.objects.create(role_name='student')

        self.teacher_user = User.objects.create_user(email='teacher1@test.com', password='pass12345', first_name='Teacher')
        UserRole.objects.create(user=self.teacher_user, role=self.teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(email='student1@test.com', password='pass12345', first_name='Student')
        UserRole.objects.create(user=self.student_user, role=self.student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student_user, grade_level='other')

    def test_student_sees_published_course_even_without_lessons(self):
        course = Course.objects.create(
            title='Visible Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        self.client.login(username='student1@test.com', password='pass12345')
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, course.title)

    def test_student_can_open_published_lesson_without_enrollment(self):
        course = Course.objects.create(
            title='Open Lesson Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        lesson = CourseLesson.objects.create(
            course=course,
            title='Lesson A',
            order_index=1,
            status='published',
            is_free=False
        )
        self.client.login(username='student1@test.com', password='pass12345')
        response = self.client.get(reverse('courses:lesson_view', args=[course.course_id, lesson.lesson_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, lesson.title)

    def test_teacher_can_create_batch_lessons_with_auto_order_and_metadata(self):
        course = Course.objects.create(
            title='Batch Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        self.client.login(username='teacher1@test.com', password='pass12345')

        poster_data_url = (
            'data:image/png;base64,'
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9lJawAAAAASUVORK5CYII='
        )
        payload = [
            {
                'fileName': '01_intro.mp4',
                'title': 'المقدمة',
                'durationSeconds': 125,
                'orderIndex': 1,
                'posterDataUrl': poster_data_url,
            },
            {
                'fileName': '02_setup.mp4',
                'title': 'التهيئة',
                'durationSeconds': 305,
                'orderIndex': 2,
                'posterDataUrl': poster_data_url,
            },
        ]

        response = self.client.post(
            reverse('courses:lesson_create', args=[course.course_id]),
            data={
                'upload_mode': 'batch',
                'batch_payload': json.dumps(payload),
                'batch_description': 'وصف موحد',
                'batch_content': 'محتوى موحد',
                'batch_is_free': 'on',
                'batch_videos': [
                    SimpleUploadedFile('01_intro.mp4', b'video-1', content_type='video/mp4'),
                    SimpleUploadedFile('02_setup.mp4', b'video-2', content_type='video/mp4'),
                ],
            },
        )

        self.assertEqual(response.status_code, 302)
        lessons = list(CourseLesson.objects.filter(course=course).order_by('order_index'))
        self.assertEqual(len(lessons), 2)
        self.assertEqual([lesson.title for lesson in lessons], ['المقدمة', 'التهيئة'])
        self.assertEqual([lesson.order_index for lesson in lessons], [1, 2])
        self.assertEqual(lessons[0].video_duration_seconds, 125)
        self.assertEqual(lessons[0].video_duration, 3)
        self.assertTrue(bool(lessons[0].poster_image))
        self.assertTrue(all(lesson.is_free for lesson in lessons))

    def test_course_list_orders_newest_courses_first(self):
        older = Course.objects.create(
            title='Older Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        newer = Course.objects.create(
            title='Newer Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        self.client.login(username='student1@test.com', password='pass12345')
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        courses = list(response.context['courses'])
        self.assertEqual(courses[0].course_id, newer.course_id)
        self.assertEqual(courses[1].course_id, older.course_id)

    def test_course_list_renders_all_published_courses_from_all_teachers(self):
        second_teacher_user = User.objects.create_user(email='teacher2@test.com', password='pass12345', first_name='Teacher Two')
        UserRole.objects.create(user=second_teacher_user, role=self.teacher_role)
        second_teacher_profile = TeacherProfile.objects.create(user=second_teacher_user)

        first_course = Course.objects.create(
            title='Teacher One Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        second_course = Course.objects.create(
            title='Teacher Two Course',
            teacher=second_teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )

        self.client.login(username='student1@test.com', password='pass12345')
        response = self.client.get(reverse('courses:course_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, first_course.title)
        self.assertContains(response, second_course.title)
        self.assertContains(response, 'كل الكورسات المنشورة من جميع الأساتذة')

    def test_course_detail_uses_correct_enrollment_button_label(self):
        free_course = Course.objects.create(
            title='Free Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published',
            price=Decimal('0.00')
        )
        paid_course = Course.objects.create(
            title='Paid Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published',
            price=Decimal('125.00')
        )
        self.client.login(username='student1@test.com', password='pass12345')
        free_response = self.client.get(reverse('courses:course_detail', args=[free_course.course_id]))
        paid_response = self.client.get(reverse('courses:course_detail', args=[paid_course.course_id]))
        self.assertContains(free_response, 'التسجيل فقط')
        self.assertNotContains(free_response, 'التسجيل والدفع')
        self.assertContains(paid_response, 'التسجيل والدفع')

    def test_student_can_download_lesson_video(self):
        course = Course.objects.create(
            title='Download Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        lesson = CourseLesson.objects.create(
            course=course,
            title='Video Lesson',
            order_index=1,
            status='published',
            video=SimpleUploadedFile('lesson.mp4', b'video-bytes', content_type='video/mp4'),
        )
        self.client.login(username='student1@test.com', password='pass12345')
        response = self.client.get(reverse('courses:download_lesson_video', args=[course.course_id, lesson.lesson_id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])

    def test_course_bundle_download_contains_all_lesson_videos(self):
        course = Course.objects.create(
            title='Bundle Course',
            teacher=self.teacher_profile,
            course_type='recorded',
            level='beginner',
            status='published'
        )
        CourseLesson.objects.create(
            course=course,
            title='First Lesson',
            order_index=1,
            status='published',
            video=SimpleUploadedFile('first.mp4', b'video-1', content_type='video/mp4'),
        )
        CourseLesson.objects.create(
            course=course,
            title='Second Lesson',
            order_index=2,
            status='published',
            video=SimpleUploadedFile('second.mp4', b'video-2', content_type='video/mp4'),
        )
        self.client.login(username='student1@test.com', password='pass12345')
        response = self.client.get(reverse('courses:download_course_lessons_bundle', args=[course.course_id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('.zip"', response['Content-Disposition'])
