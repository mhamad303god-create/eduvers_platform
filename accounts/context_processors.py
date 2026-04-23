from django.conf import settings
from django.core.cache import cache
from accounts.models import UserRole
from notifications.models import Message, Notification


def user_roles_processor(request):
    """
    Context processor to add user_roles to all templates
    """
    user_roles = []
    unread_notifications_count = 0
    unread_messages_count = 0
    if request.user.is_authenticated:
        user_roles = list(UserRole.objects.filter(user=request.user).values_list('role__role_name', flat=True))
        cache_key = f"nav_badges:{request.user.id}"
        cached_counts = cache.get(cache_key)
        if cached_counts is None:
            cached_counts = {
                "unread_notifications_count": Notification.objects.filter(
                    user=request.user,
                    is_read=False,
                ).exclude(type='message').count(),
                "unread_messages_count": Message.objects.filter(
                    receiver=request.user,
                    is_read=False,
                    deleted_by_receiver=False,
                ).count(),
            }
            cache.set(cache_key, cached_counts, 30)
        unread_notifications_count = cached_counts["unread_notifications_count"]
        unread_messages_count = cached_counts["unread_messages_count"]

    return {
        'user_roles': user_roles,
        'unread_notifications_count': unread_notifications_count,
        'unread_messages_count': unread_messages_count,
    }
