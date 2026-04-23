from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import StudentProfile, TeacherProfile
from courses.models import Subject, Course
import uuid


class Assessment(models.Model):
    assessment_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(
        max_length=20,
        choices=[
            ("placement", "Placement"),
            ("quiz", "Quiz"),
            ("exam", "Exam"),
            ("assignment", "Assignment"),
        ],
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.SET_NULL, blank=True, null=True
    )
    teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.SET_NULL, blank=True, null=True
    )
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, blank=True, null=True)
    duration_minutes = models.IntegerField(blank=True, null=True)
    total_points = models.IntegerField(default=100)
    passing_score = models.IntegerField(default=60)
    max_attempts = models.IntegerField(default=3)
    is_randomized = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        default="draft",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Assessment")
        verbose_name_plural = _("Assessments")

    def __str__(self):
        return self.title


class AssessmentQuestion(models.Model):
    question_id = models.AutoField(primary_key=True)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=[
            ("multiple_choice", "Multiple Choice"),
            ("true_false", "True/False"),
            ("short_answer", "Short Answer"),
            ("essay", "Essay"),
            ("fill_blank", "Fill in the Blank"),
        ],
    )
    points = models.IntegerField(default=1)
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
        ],
        default="medium",
    )
    explanation = models.TextField(blank=True, null=True)
    order_index = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Assessment Question")
        verbose_name_plural = _("Assessment Questions")
        ordering = ["order_index"]

    def __str__(self):
        return f"Q{self.order_index}: {self.question_text[:50]}"


class QuestionChoice(models.Model):
    choice_id = models.AutoField(primary_key=True)
    question = models.ForeignKey(AssessmentQuestion, on_delete=models.CASCADE)
    choice_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order_index = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Question Choice")
        verbose_name_plural = _("Question Choices")
        ordering = ["order_index"]

    def __str__(self):
        return f"Choice {self.order_index}: {self.choice_text[:30]}"


class AssessmentAttempt(models.Model):
    attempt_id = models.AutoField(primary_key=True)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    attempt_number = models.IntegerField()
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)
    time_taken = models.IntegerField(blank=True, null=True)  # in seconds
    score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    max_score = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )
    passed = models.BooleanField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("abandoned", "Abandoned"),
            ("expired", "Expired"),
        ],
        default="in_progress",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Assessment Attempt")
        verbose_name_plural = _("Assessment Attempts")
        unique_together = ("assessment", "student", "attempt_number")

    def __str__(self):
        return f"{self.student.user.email} - {self.assessment.title} (Attempt {self.attempt_number})"


class AssessmentAnswer(models.Model):
    answer_id = models.AutoField(primary_key=True)
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE)
    question = models.ForeignKey(AssessmentQuestion, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(
        QuestionChoice, on_delete=models.SET_NULL, blank=True, null=True
    )
    text_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(blank=True, null=True)
    points_earned = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    time_spent = models.IntegerField(default=0)  # in seconds
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Assessment Answer")
        verbose_name_plural = _("Assessment Answers")
        unique_together = ("attempt", "question")

    def __str__(self):
        return f"Answer for {self.question.question_text[:30]}"


class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    booking = models.ForeignKey("bookings.Booking", on_delete=models.CASCADE)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )
    admin_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Review")
        verbose_name_plural = _("Reviews")
        unique_together = ("booking",)

    def __str__(self):
        return f"Review by {self.student.user.email} for {self.teacher.user.email}"
