from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, StudentProfile, TeacherProfile, UserRole
from notifications.models import LiveCall, LiveCallParticipant, NewsletterSubscription, Notification, Message
from bookings.models import Booking


User = get_user_model()


class LiveCallFlowTests(TestCase):
    def setUp(self):
        self.teacher_role = Role.objects.create(role_name="teacher")
        self.student_role = Role.objects.create(role_name="student")

        self.teacher_user = User.objects.create_user(
            email="teacher-call@test.com",
            password="pass12345",
            first_name="Teacher",
        )
        UserRole.objects.create(user=self.teacher_user, role=self.teacher_role)
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            email="student-call@test.com",
            password="pass12345",
            first_name="Student",
        )
        UserRole.objects.create(user=self.student_user, role=self.student_role)
        self.student_profile = StudentProfile.objects.create(user=self.student_user, grade_level="other")

    def _create_pending_call(self):
        call = LiveCall.objects.create(
            initiated_by=self.teacher_user,
            teacher=self.teacher_user,
            topic="اختبار اتصال",
            message="يرجى الرد",
            room_name="eduverse-call-test-1",
            room_url="http://testserver/notifications/live-calls/1/room/",
            room_path="/notifications/live-calls/1/room/",
            status="pending",
        )
        LiveCallParticipant.objects.create(
            live_call=call,
            user=self.teacher_user,
            role="teacher",
            status="accepted",
        )
        LiveCallParticipant.objects.create(
            live_call=call,
            user=self.student_user,
            role="student",
            status="invited",
        )
        return call

    def _link_teacher_and_student(self):
        Booking.objects.create(
            student=self.student_profile,
            teacher=self.teacher_profile,
            scheduled_start=timezone.now() + timezone.timedelta(days=1),
            scheduled_end=timezone.now() + timezone.timedelta(days=1, minutes=30),
            status="confirmed",
        )

    def test_teacher_call_creation_uses_local_room_url(self):
        self._link_teacher_and_student()
        self.client.login(username="teacher-call@test.com", password="pass12345")
        response = self.client.post(
            reverse("notifications:teacher_live_calls"),
            data={
                "student_ids": [self.student_user.id],
                "topic": "اتصال عاجل",
                "message": "اختبار غرفة محلية",
            },
        )
        self.assertEqual(response.status_code, 302)
        call = LiveCall.objects.latest("call_id")
        self.assertTrue(call.room_path.endswith(f"/notifications/live-calls/{call.call_id}/room/"))
        self.assertTrue(call.room_url.endswith(call.room_path))

    def test_student_can_accept_call_via_ajax(self):
        call = self._create_pending_call()
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.post(
            reverse("notifications:respond_live_call", args=[call.call_id, "accept"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        call.refresh_from_db()
        participant = LiveCallParticipant.objects.get(live_call=call, user=self.student_user)
        self.assertTrue(payload["success"])
        self.assertEqual(call.status, "active")
        self.assertEqual(participant.status, "accepted")
        self.assertIn(f"/notifications/live-calls/{call.call_id}/room/", payload["redirect_url"])

    def test_student_reject_notifies_initiator_and_redirects_to_list(self):
        call = self._create_pending_call()
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.post(
            reverse("notifications:respond_live_call", args=[call.call_id, "reject"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        call.refresh_from_db()
        participant = LiveCallParticipant.objects.get(live_call=call, user=self.student_user)
        self.assertTrue(payload["success"])
        self.assertEqual(participant.status, "rejected")
        self.assertEqual(call.status, "rejected")
        self.assertTrue(Notification.objects.filter(user=self.teacher_user, type="call", title="تم رفض الاتصال").exists())
        self.assertTrue(Message.objects.filter(receiver=self.teacher_user, subject="تم رفض الاتصال المباشر").exists())
        self.assertEqual(payload["remove_call_id"], call.call_id)
        self.assertEqual(payload["redirect_url"], reverse("notifications:student_live_calls"))

    def test_live_call_room_renders_local_signaling_context(self):
        call = self._create_pending_call()
        participant = LiveCallParticipant.objects.get(live_call=call, user=self.student_user)
        participant.status = "accepted"
        participant.save(update_fields=["status"])
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.get(reverse("notifications:live_call_room", args=[call.call_id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"/ws/live-calls/{call.call_id}/")
        self.assertContains(response, "WebRTC")

    def test_live_call_room_shows_localhost_hint_for_non_secure_host(self):
        call = self._create_pending_call()
        participant = LiveCallParticipant.objects.get(live_call=call, user=self.student_user)
        participant.status = "accepted"
        participant.save(update_fields=["status"])
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.get(
            reverse("notifications:live_call_room", args=[call.call_id]),
            HTTP_HOST="localhost:8000",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "يبدو أنك فتحت الغرفة عبر رابط غير آمن للأجهزة")

    def test_notification_list_excludes_message_type_notifications(self):
        Notification.objects.create(
            user=self.student_user,
            type="message",
            title="رسالة جديدة",
            content="يجب ألا تظهر في صفحة الإشعارات.",
            data={},
        )
        Notification.objects.create(
            user=self.student_user,
            type="call",
            title="اتصال جديد",
            content="هذا إشعار فعلي.",
            data={},
        )
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.get(reverse("notifications:notification_list"))
        self.assertEqual(response.status_code, 200)
        notification_titles = [item.title for item in response.context["notifications"]]
        self.assertIn("اتصال جديد", notification_titles)
        self.assertNotIn("رسالة جديدة", notification_titles)

    def test_notification_list_shows_message_notification_hint_when_no_general_notifications_exist(self):
        Notification.objects.create(
            user=self.student_user,
            type="message",
            title="رسالة جديدة",
            content="هذه رسالة إشعار.",
            data={
                "message_id": 1,
                "sender_name": "Teacher",
                "sender_email": "teacher-call@test.com",
                "subject": "اختبار",
                "message": "نص الرسالة.",
            },
        )
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.get(reverse("notifications:notification_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "لا توجد إشعارات عامة حالياً")
        self.assertContains(response, "صفحة الرسائل")

    def test_message_attachment_can_be_downloaded_by_receiver(self):
        message = Message.objects.create(
            sender=self.teacher_user,
            receiver=self.student_user,
            subject="ملف",
            content="مرفق للتنزيل",
            attachment_file=SimpleUploadedFile("notes.pdf", b"pdf-content", content_type="application/pdf"),
        )
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.get(reverse("notifications:download_message_attachment", args=[message.message_id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response["Content-Disposition"])
        self.assertIn('.pdf"', response["Content-Disposition"])

    def test_forward_message_reuses_existing_attachment(self):
        source = Message.objects.create(
            sender=self.teacher_user,
            receiver=self.student_user,
            subject="المصدر",
            content="رسالة أصلية",
            attachment_file=SimpleUploadedFile("brief.pdf", b"brief", content_type="application/pdf"),
        )
        self.client.login(username="student-call@test.com", password="pass12345")
        response = self.client.post(
            reverse("notifications:forward_message", args=[source.message_id]),
            data={
                "receiver": self.teacher_user.id,
                "subject": "إعادة إرسال",
                "content": "أعيد إرسالها",
                "attachment_urls": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        forwarded = Message.objects.exclude(message_id=source.message_id).latest("message_id")
        self.assertEqual(forwarded.sender, self.student_user)
        self.assertEqual(forwarded.receiver, self.teacher_user)
        self.assertTrue(bool(forwarded.attachment_file))

    def test_initiator_can_archive_finished_call(self):
        call = self._create_pending_call()
        call.status = "rejected"
        call.save(update_fields=["status"])
        self.client.login(username="teacher-call@test.com", password="pass12345")
        response = self.client.post(
            reverse("notifications:archive_live_call", args=[call.call_id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        call.refresh_from_db()
        self.assertTrue(call.archived_by_initiator)

    def test_newsletter_subscription_can_be_created_from_home(self):
        response = self.client.post(
            reverse("home"),
            data={"form_type": "newsletter", "email": "subscriber@example.com"},
            HTTP_REFERER=reverse("home"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(NewsletterSubscription.objects.filter(email="subscriber@example.com", is_active=True).exists())
