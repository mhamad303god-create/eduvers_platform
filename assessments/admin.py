from django.contrib import admin
from .models import Assessment, AssessmentQuestion, QuestionChoice, AssessmentAttempt, AssessmentAnswer, Review


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'subject', 'teacher', 'status')
    list_filter = ('type', 'status')
    search_fields = ('title', 'teacher__user__email')


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_text', 'assessment', 'question_type', 'points', 'difficulty')
    list_filter = ('question_type', 'difficulty')
    search_fields = ('question_text',)


@admin.register(QuestionChoice)
class QuestionChoiceAdmin(admin.ModelAdmin):
    list_display = ('choice_text', 'question', 'is_correct', 'order_index')
    list_filter = ('is_correct',)
    search_fields = ('choice_text',)


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ('assessment', 'student', 'attempt_number', 'score', 'passed', 'status')
    list_filter = ('status', 'passed')
    search_fields = ('student__user__email', 'assessment__title')


@admin.register(AssessmentAnswer)
class AssessmentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct', 'points_earned')
    list_filter = ('is_correct',)
    search_fields = ('attempt__student__user__email',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('student', 'teacher', 'rating', 'is_public', 'status')
    list_filter = ('rating', 'is_public', 'status')
    search_fields = ('student__user__email', 'teacher__user__email')

