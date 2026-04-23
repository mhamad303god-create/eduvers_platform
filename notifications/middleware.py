from datetime import timedelta

from django.contrib import messages
from django.utils import timezone

from bookings.models import Booking
from notifications.models import Notification


class SessionDueNotificationMiddleware:
    """
    Create "session is due now" notifications for authenticated users.
    Runs at most once every 60 seconds per session to keep it lightweight.
    """

    CHECK_INTERVAL_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            self._maybe_create_due_notification(request)
        return self.get_response(request)

    def _maybe_create_due_notification(self, request):
        now = timezone.now()
        last_check = request.session.get("session_due_last_check")
        if last_check:
            try:
                last_dt = timezone.datetime.fromisoformat(last_check)
                if timezone.is_naive(last_dt):
                    last_dt = timezone.make_aware(last_dt, timezone.get_current_timezone())
                if (now - last_dt).total_seconds() < self.CHECK_INTERVAL_SECONDS:
                    return
            except ValueError:
                pass

        request.session["session_due_last_check"] = now.isoformat()

        roles = request.user.get_roles()
        if not roles:
            return

        start_window = now - timedelta(minutes=2)
        end_window = now + timedelta(minutes=5)

        if "student" in roles and hasattr(request.user, "studentprofile"):
            self._create_for_side(
                request=request,
                role_filter={"student": request.user.studentprofile},
                counterparty_field="teacher",
                role_label="المعلم",
                start_window=start_window,
                end_window=end_window,
            )

        if "teacher" in roles and hasattr(request.user, "teacherprofile"):
            self._create_for_side(
                request=request,
                role_filter={"teacher": request.user.teacherprofile},
                counterparty_field="student",
                role_label="الطالب",
                start_window=start_window,
                end_window=end_window,
            )

    def _create_for_side(self, request, role_filter, counterparty_field, role_label, start_window, end_window):
        due_bookings = Booking.objects.filter(
            **role_filter,
            scheduled_start__gte=start_window,
            scheduled_start__lte=end_window,
            status__in=["confirmed", "pending", "in_progress"],
        ).select_related(f"{counterparty_field}__user", "course")

        created = 0
        for booking in due_bookings:
            counterparty = getattr(booking, counterparty_field)
            exists = Notification.objects.filter(
                user=request.user,
                type="booking",
                data__event="session_start",
                data__booking_id=booking.booking_id,
            ).exists()
            if exists:
                continue

            Notification.objects.create(
                user=request.user,
                type="booking",
                title="حان وقت الجلسة الآن",
                content=(
                    f"جلسة {role_label} {counterparty.user.get_full_name() or counterparty.user.email} "
                    f"بدأت الآن ({booking.scheduled_start.strftime('%H:%M')})."
                ),
                data={
                    "event": "session_start",
                    "booking_id": booking.booking_id,
                    "booking_uuid": str(booking.uuid),
                    "course": booking.course.title if booking.course else None,
                },
            )
            created += 1

        if created:
            messages.info(request, f"لديك {created} جلسة حان وقتها الآن.")
        


