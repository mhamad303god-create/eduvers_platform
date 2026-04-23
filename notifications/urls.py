from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Messaging
    path('messages/', views.message_list, name='message_list'),
    path('messages/sent/', views.sent_messages, name='sent_messages'),
    path('messages/compose/', views.compose_message, name='compose_message'),
    path('messages/feed/', views.message_activity_feed, name='message_activity_feed'),
    path('messages/mark-all-read/', views.mark_all_messages_read, name='mark_all_messages_read'),
    path('messages/<int:message_id>/', views.message_detail, name='message_detail'),
    path('messages/<int:message_id>/reply/', views.reply_message, name='reply_message'),
    path('messages/<int:message_id>/forward/', views.forward_message, name='forward_message'),
    path('messages/<int:message_id>/download/', views.download_message_attachment, name='download_message_attachment'),
    path('messages/<int:message_id>/delete/', views.delete_message, name='delete_message'),

    # Notifications
    path('', views.notification_list, name='notification_list'),
    path('<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    path('mark_all_read/', views.mark_all_read, name='mark_all_read'),

    # AJAX endpoints
    path('unread_count/', views.unread_count, name='unread_count'),

    # Live calls
    path('live-calls/teacher/', views.teacher_live_calls, name='teacher_live_calls'),
    path('live-calls/student/', views.student_live_calls, name='student_live_calls'),
    path('live-calls/alerts/', views.incoming_call_alerts, name='incoming_call_alerts'),
    path('live-calls/<int:call_id>/status/', views.live_call_status, name='live_call_status'),
    path('live-calls/<int:call_id>/room/', views.live_call_room, name='live_call_room'),
    path('live-calls/<int:call_id>/archive/', views.archive_live_call, name='archive_live_call'),
    path('live-calls/<int:call_id>/<str:action>/', views.respond_live_call, name='respond_live_call'),
]
