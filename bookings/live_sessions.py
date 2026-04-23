from django.conf import settings
from django.utils.text import slugify


def build_jitsi_room_name(booking):
    teacher_name = booking.teacher.user.get_full_name() or booking.teacher.user.email
    student_name = booking.student.user.get_full_name() or booking.student.user.email
    base_name = f"eduverse-{teacher_name}-{student_name}-{booking.booking_id}"
    slug = slugify(base_name)
    return slug or f"eduverse-session-{booking.booking_id}"


def build_jitsi_join_url(room_name):
    base_url = getattr(settings, "SITE_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base_url}/bookings/live/{room_name}/"
