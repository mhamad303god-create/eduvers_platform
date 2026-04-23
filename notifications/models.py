from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from accounts.models import User, StudentProfile
from courses.models import Course
from assessments.models import Assessment
import uuid


class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="received_messages"
    )
    subject = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField()
    attachment_urls = models.JSONField(default=list)
    attachment_file = models.FileField(upload_to="messages/attachments/%Y/%m/", blank=True, null=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    parent_message = models.ForeignKey(
        "self", on_delete=models.SET_NULL, blank=True, null=True
    )
    deleted_by_sender = models.BooleanField(default=False)
    deleted_by_receiver = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        indexes = [
            models.Index(fields=['receiver', 'deleted_by_receiver', 'is_read']),
            models.Index(fields=['sender', 'deleted_by_sender', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Message from {self.sender.email} to {self.receiver.email}"


class ContactRequest(models.Model):
    contact_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="contact_requests",
    )
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("resolved", "Resolved"),
        ],
        default="new",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Contact Request")
        verbose_name_plural = _("Contact Requests")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} - {self.subject}"


class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(
        max_length=20,
        choices=[
            ("booking", "Booking"),
            ("message", "Message"),
            ("call", "Call"),
            ("payment", "Payment"),
            ("assessment", "Assessment"),
            ("system", "System"),
            ("promotion", "Promotion"),
        ],
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    data = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class LiveCall(models.Model):
    call_id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    initiated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="initiated_calls")
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="teacher_live_calls",
    )
    topic = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    room_name = models.CharField(max_length=255, unique=True)
    room_url = models.URLField()
    room_path = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("active", "Active"),
            ("ended", "Ended"),
            ("cancelled", "Cancelled"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    is_emergency = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    end_reason = models.TextField(blank=True, null=True)
    archived_by_initiator = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Live Call")
        verbose_name_plural = _("Live Calls")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.call_id} - {self.initiated_by.email}"


class LiveCallParticipant(models.Model):
    participant_id = models.AutoField(primary_key=True)
    live_call = models.ForeignKey(LiveCall, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="live_call_participations")
    role = models.CharField(
        max_length=20,
        choices=[
            ("teacher", "Teacher"),
            ("student", "Student"),
        ],
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("invited", "Invited"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("missed", "Missed"),
        ],
        default="invited",
    )
    responded_at = models.DateTimeField(blank=True, null=True)
    joined_at = models.DateTimeField(blank=True, null=True)
    left_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Live Call Participant")
        verbose_name_plural = _("Live Call Participants")
        unique_together = ("live_call", "user")
        indexes = [
            models.Index(fields=['live_call', 'user']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.live_call_id} - {self.user.email}"


class ActivityLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50, blank=True, null=True)
    resource_id = models.IntegerField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Activity Log")
        verbose_name_plural = _("Activity Logs")

    def __str__(self):
        return f"{self.user.email if self.user else 'System'} - {self.action}"


class SystemSetting(models.Model):
    setting_id = models.AutoField(primary_key=True)
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField(blank=True, null=True)
    setting_type = models.CharField(
        max_length=20,
        choices=[
            ("string", "String"),
            ("number", "Number"),
            ("boolean", "Boolean"),
            ("json", "JSON"),
        ],
        default="string",
    )
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("System Setting")
        verbose_name_plural = _("System Settings")

    def __str__(self):
        return self.setting_key


class Attachment(models.Model):
    attachment_id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource_type = models.CharField(max_length=50)
    resource_id = models.IntegerField(blank=True, null=True)
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.IntegerField(blank=True, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Attachment")
        verbose_name_plural = _("Attachments")

    def __str__(self):
        return self.original_filename


class Certificate(models.Model):
    certificate_id = models.CharField(max_length=100, unique=True, primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    enrollment = models.ForeignKey('courses.Enrollment', on_delete=models.CASCADE, related_name='certificates', null=True, blank=True)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, blank=True, null=True)
    assessment = models.ForeignKey(
        Assessment, on_delete=models.SET_NULL, blank=True, null=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    issued_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(blank=True, null=True)
    certificate_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    qr_code = models.ImageField(upload_to='certificates/qr/', blank=True, null=True)
    certificate_url = models.URLField(blank=True, null=True)
    template_id = models.IntegerField(blank=True, null=True)
    is_verified = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("revoked", "Revoked"),
        ],
        default="issued",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Certificate")
        verbose_name_plural = _("Certificates")

    def __str__(self):
        return f"{self.student.user.email} - {self.title}"


class NewsletterSubscription(models.Model):
    subscription_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Newsletter Subscription")
        verbose_name_plural = _("Newsletter Subscriptions")
        ordering = ["-subscribed_at"]

    def __str__(self):
        return self.email
