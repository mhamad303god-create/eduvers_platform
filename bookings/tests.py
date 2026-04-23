from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, StudentProfile, TeacherProfile, UserRole
from bookings.models import Booking


User = get_user_model()


class BookingLiveClassroomTests(TestCase):
    def setUp(self):
        self.teacher_role = Role.objects.create(role_name="teacher")
        self.student_role = Role.objects.create(role_name="student")

        self.teacher_user = User.objects.create_user(email="teacher-booking@test.com", password="pass12345", first_name="Teacher")
        self.student_user = User.objects.create_user(email="student-booking@test.com", password="pass12345", first_name="Student")

        UserRole.objects.create(user=self.teacher_user, role=self.teacher_role)
        UserRole.objects.create(user=self.student_user, role=self.student_role)

        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user)
        self.student_profile = StudentProfile.objects.create(user=self.student_user, grade_level="other")

        self.booking = Booking.objects.create(
            student=self.student_profile,
            teacher=self.teacher_profile,
            scheduled_start=timezone.now() + timezone.timedelta(minutes=10),
            scheduled_end=timezone.now() + timezone.timedelta(minutes=40),
            status="confirmed",
        )

    def test_student_live_classroom_renders_local_room(self):
        self.client.login(username="student-booking@test.com", password="pass12345")
        response = self.client.get(reverse("bookings:student_live_classroom", args=[self.booking.booking_id]))
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertContains(response, f"/ws/live-classrooms/{self.booking.meeting_id}/")
        self.assertContains(response, "فصل محلي داخل المنصة")

    def test_student_live_classroom_shows_localhost_hint_for_non_secure_host(self):
        self.client.login(username="student-booking@test.com", password="pass12345")
        response = self.client.get(
            reverse("bookings:student_live_classroom", args=[self.booking.booking_id]),
            HTTP_HOST="localhost:8000",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "يبدو أن هذا الفصل فُتح عبر رابط غير آمن للأجهزة")
