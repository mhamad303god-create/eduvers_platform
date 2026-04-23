# ===== WebSocket Routing for Django Channels =====

from django.urls import re_path
from . import consumers
from bookings.consumers import BookingClassroomConsumer

websocket_urlpatterns = [
    # Notifications WebSocket
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/live-calls/(?P<call_id>\d+)/$', consumers.LiveCallConsumer.as_asgi()),
    re_path(r'ws/live-classrooms/(?P<room_name>[^/]+)/$', BookingClassroomConsumer.as_asgi()),
]
