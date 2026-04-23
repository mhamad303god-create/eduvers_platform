from django.contrib import admin
from .models import ContactRequest, LiveCall, LiveCallParticipant, Message, Notification, ActivityLog, SystemSetting, Attachment, Certificate


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "subject", "status", "is_read", "created_at")
    list_filter = ("status", "is_read", "created_at")
    search_fields = ("full_name", "email", "subject", "message")
    readonly_fields = ("created_at", "read_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__email', 'receiver__email', 'subject')


@admin.register(LiveCall)
class LiveCallAdmin(admin.ModelAdmin):
    list_display = ("call_id", "initiated_by", "teacher", "status", "is_emergency", "created_at")
    list_filter = ("status", "is_emergency", "created_at")
    search_fields = ("initiated_by__email", "teacher__email", "topic", "message")


@admin.register(LiveCallParticipant)
class LiveCallParticipantAdmin(admin.ModelAdmin):
    list_display = ("live_call", "user", "role", "status", "responded_at")
    list_filter = ("role", "status", "created_at")
    search_fields = ("user__email", "live_call__room_name")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'title', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('user__email', 'title')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'resource_type', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__email', 'action')


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('setting_key', 'setting_type', 'is_public', 'updated_at')
    list_filter = ('setting_type', 'is_public')
    search_fields = ('setting_key',)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'user', 'filename', 'file_size', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'filename')


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_id', 'student', 'title', 'issued_date', 'status')
    list_filter = ('status', 'issued_date')
    search_fields = ('student__user__email', 'title')
    readonly_fields = ('certificate_id', 'uuid', 'issued_date')
