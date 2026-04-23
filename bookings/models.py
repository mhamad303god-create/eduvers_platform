from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from accounts.models import StudentProfile, TeacherProfile
from courses.models import Course
import uuid


class TeacherAvailability(models.Model):
    availability_id = models.AutoField(primary_key=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    day_of_week = models.CharField(
        max_length=10,
        choices=[
            ('sunday', 'Sunday'),
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
        ]
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=50, default='Asia/Riyadh')
    is_recurring = models.BooleanField(default=True)
    recurrence_pattern = models.JSONField(default=dict)
    specific_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('available', 'Available'),
            ('booked', 'Booked'),
            ('cancelled', 'Cancelled'),
        ],
        default='available'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Teacher Availability')
        verbose_name_plural = _('Teacher Availabilities')

    def __str__(self):
        return f"{self.teacher.user.email} - {self.day_of_week} {self.start_time}-{self.end_time}"


class Booking(models.Model):
    booking_id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, blank=True, null=True)
    availability = models.ForeignKey(TeacherAvailability, on_delete=models.SET_NULL, blank=True, null=True)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(blank=True, null=True)
    actual_end = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('no_show', 'No Show'),
        ],
        default='pending'
    )
    meeting_url = models.URLField(blank=True, null=True)
    meeting_id = models.CharField(max_length=100, blank=True, null=True)
    meeting_provider = models.CharField(
        max_length=20,
        choices=[
            ("jitsi", "Jitsi Meet"),
            ("zoom", "Zoom"),
            ("external", "External"),
        ],
        default="jitsi",
    )
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Booking')
        verbose_name_plural = _('Bookings')

    def __str__(self):
        return f"Booking {self.uuid} - {self.student.user.email} with {self.teacher.user.email}"

    @property
    def duration_minutes(self):
        if self.scheduled_start and self.scheduled_end:
            return int((self.scheduled_end - self.scheduled_start).total_seconds() / 60)
        return 0

    @property
    def is_joinable(self):
        if not self.meeting_url:
            return False
        now = timezone.now()
        join_window_start = self.scheduled_start - timezone.timedelta(minutes=15)
        join_window_end = self.scheduled_end + timezone.timedelta(minutes=30)
        return join_window_start <= now <= join_window_end
