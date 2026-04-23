from django.contrib import admin
from .models import Subject, Course, CourseLesson, Enrollment, LessonProgress


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('subject_name', 'subject_code', 'category', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('subject_name', 'subject_code')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'subject', 'level', 'price', 'status', 'is_featured')
    list_filter = ('status', 'level', 'is_featured', 'course_type')
    search_fields = ('title', 'teacher__user__email')


@admin.register(CourseLesson)
class CourseLessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order_index', 'is_free', 'status')
    list_filter = ('is_free', 'status')
    search_fields = ('title', 'course__title')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrollment_date', 'status', 'progress_percentage')
    list_filter = ('status', 'enrollment_date')
    search_fields = ('student__user__email', 'course__title')


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'lesson', 'completed', 'completion_date', 'time_spent')
    list_filter = ('completed', 'completion_date')
    search_fields = ('student__user__email', 'lesson__title')
