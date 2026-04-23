from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from accounts.models import StudentProfile, TeacherProfile
import json
import os
from math import ceil


def course_thumbnail_upload_path(instance, filename):
    course_ref = instance.course_id or f"teacher-{instance.teacher_id or 'new'}"
    return f'courses/thumbnails/{course_ref}/{filename}'


def lesson_video_upload_path(instance, filename):
    lesson_ref = instance.lesson_id or f"pending-{instance.order_index or 'new'}"
    return f'courses/lessons/{instance.course.course_id}/{lesson_ref}/{filename}'


def lesson_poster_upload_path(instance, filename):
    lesson_ref = instance.lesson_id or f"pending-{instance.order_index or 'new'}"
    return f'courses/lessons/{instance.course.course_id}/{lesson_ref}/posters/{filename}'


class Subject(models.Model):
    subject_id = models.AutoField(primary_key=True)
    subject_name = models.CharField(max_length=255, unique=True)
    subject_code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    grade_levels = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Subject')
        verbose_name_plural = _('Subjects')

    def __str__(self):
        return self.subject_name


class Course(models.Model):
    course_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    course_type = models.CharField(
        max_length=20,
        choices=[
            ('individual', 'Individual'),
            ('group', 'Group'),
            ('recorded', 'Recorded'),
        ]
    )
    level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ]
    )
    max_students = models.IntegerField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default='SAR')
    duration_minutes = models.IntegerField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to=course_thumbnail_upload_path, blank=True, null=True, max_length=255)
    preview_video = models.FileField(upload_to=course_thumbnail_upload_path, blank=True, null=True, max_length=255)
    requirements = models.JSONField(default=list)
    objectives = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('archived', 'Archived'),
        ],
        default='draft'
    )
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Course')
        verbose_name_plural = _('Courses')

    def __str__(self):
        return self.title


class CourseLesson(models.Model):
    lesson_id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    video = models.FileField(upload_to=lesson_video_upload_path, blank=True, null=True)
    video_duration = models.IntegerField(blank=True, null=True)
    video_duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    poster_image = models.ImageField(upload_to=lesson_poster_upload_path, blank=True, null=True, max_length=255)
    order_index = models.IntegerField()
    is_free = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('published', 'Published'),
        ],
        default='draft'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Course Lesson')
        verbose_name_plural = _('Course Lessons')
        ordering = ['order_index']

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    @property
    def duration_seconds(self):
        if self.video_duration_seconds:
            return self.video_duration_seconds
        if self.video_duration:
            return self.video_duration * 60
        return None

    @property
    def duration_display(self):
        total_seconds = self.duration_seconds
        if not total_seconds:
            return ""
        hours, remainder = divmod(int(total_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def sync_duration_minutes(self):
        if self.video_duration_seconds:
            self.video_duration = ceil(self.video_duration_seconds / 60)


class Enrollment(models.Model):
    enrollment_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrollment_date = models.DateTimeField(auto_now_add=True)
    completion_date = models.DateTimeField(blank=True, null=True)
    progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('dropped', 'Dropped'),
            ('refunded', 'Refunded'),
        ],
        default='active'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('refunded', 'Refunded'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Enrollment')
        verbose_name_plural = _('Enrollments')
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.user.email} - {self.course.title}"


class TeacherSubjects(models.Model):
    id = models.AutoField(primary_key=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    proficiency_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        default='intermediate'
    )
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Teacher Subject')
        verbose_name_plural = _('Teacher Subjects')
        unique_together = ('teacher', 'subject')

    def __str__(self):
        return f"{self.teacher.user.email} - {self.subject.subject_name}"


class LessonProgress(models.Model):
    progress_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    lesson = models.ForeignKey(CourseLesson, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(blank=True, null=True)
    time_spent = models.IntegerField(default=0)  # in seconds
    last_position = models.IntegerField(default=0)  # in seconds
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Lesson Progress')
        verbose_name_plural = _('Lesson Progress')
        unique_together = ('student', 'lesson')

    def __str__(self):
        return f"{self.student.user.email} - {self.lesson.title}"
