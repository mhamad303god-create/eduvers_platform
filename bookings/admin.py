from django.contrib import admin
from .models import TeacherAvailability, Booking


@admin.register(TeacherAvailability)
class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'day_of_week', 'start_time', 'end_time', 'status')
    list_filter = ('day_of_week', 'status', 'is_recurring')
    search_fields = ('teacher__user__email',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'student', 'teacher', 'scheduled_start', 'status')
    list_filter = ('status', 'scheduled_start')
    search_fields = ('student__user__email', 'teacher__user__email', 'uuid')
