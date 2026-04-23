# ===== Background Tasks for Bookings =====

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Booking
from datetime import timedelta
import logging
from notifications.models import Notification
from .live_sessions import build_jitsi_join_url, build_jitsi_room_name

logger = logging.getLogger(__name__)


@shared_task
def check_booking_statuses():
    """Check and update booking statuses based on time"""
    logger.info("Checking booking statuses...")
    
    now = timezone.now()
    
    # Mark bookings as 'in_progress' if they've started
    starting_bookings = Booking.objects.filter(
        status='confirmed',
        scheduled_start__lte=now,
        scheduled_end__gt=now
    )
    
    for booking in starting_bookings:
        booking.status = 'in_progress'
        booking.save()
        logger.info(f"Booking {booking.uuid} marked as in progress")
    
    # Mark bookings as 'completed' if they've ended
    ending_bookings = Booking.objects.filter(
        status='in_progress',
        scheduled_end__lte=now
    )
    
    for booking in ending_bookings:
        booking.status = 'completed'
        booking.save()
        logger.info(f"Booking {booking.uuid} marked as completed")
    
    # Mark as 'no_show' if 30 minutes past start and still pending
    no_show_threshold = now - timedelta(minutes=30)
    no_shows = Booking.objects.filter(
        status='confirmed',
        scheduled_start__lte=no_show_threshold
    )
    
    for booking in no_shows:
        booking.status = 'no_show'
        booking.save()
        logger.info(f"Booking {booking.uuid} marked as no-show")


@shared_task
def send_booking_reminders():
    """Send reminders for upcoming bookings"""
    logger.info("Sending booking reminders...")
    
    # Remind 1 hour before
    one_hour_later = timezone.now() + timedelta(hours=1)
    one_hour_fifteen = one_hour_later + timedelta(minutes=15)
    
    upcoming_bookings = Booking.objects.filter(
        status='confirmed',
        scheduled_start__gte=one_hour_later,
        scheduled_start__lt=one_hour_fifteen,
        reminder_sent=False
    ).select_related('student__user', 'teacher__user')
    
    for booking in upcoming_bookings:
        try:
            if not booking.meeting_url:
                room_name = build_jitsi_room_name(booking)
                booking.meeting_id = room_name
                booking.meeting_url = build_jitsi_join_url(room_name)
                booking.meeting_provider = "jitsi"

            # Send to student
            send_mail(
                'تذكير: موعدك القادم خلال ساعة ⏰',
                f'''
                مرحباً {booking.student.user.get_full_name()},
                
                لديك موعد مع {booking.teacher.user.get_full_name()}
                خلال ساعة واحدة.
                
                التاريخ: {booking.scheduled_start.strftime("%Y-%m-%d")}
                الوقت: {booking.scheduled_start.strftime("%I:%M %p")}
                المدة: {booking.duration_minutes} دقيقة
                
                {'رابط الجلسة: ' + booking.meeting_url if booking.meeting_url else ''}
                
                كن مستعداً! 📚
                
                فريق EduVerse
                ''',
                settings.DEFAULT_FROM_EMAIL,
                [booking.student.user.email],
                fail_silently=True,
            )
            
            # Send to teacher
            send_mail(
                'تذكير: لديك حجز خلال ساعة ⏰',
                f'''
                مرحباً {booking.teacher.user.get_full_name()},
                
                لديك حجز مع {booking.student.user.get_full_name()}
                خلال ساعة واحدة.
                
                التاريخ: {booking.scheduled_start.strftime("%Y-%m-%d")}
                الوقت: {booking.scheduled_start.strftime("%I:%M %p")}
                المدة: {booking.duration_minutes} دقيقة
                
                {'رابط الجلسة: ' + booking.meeting_url if booking.meeting_url else ''}
                
                استعد للجلسة! 👨‍🏫
                
                فريق EduVerse
                ''',
                settings.DEFAULT_FROM_EMAIL,
                [booking.teacher.user.email],
                fail_silently=True,
            )
            
            Notification.objects.create(
                user=booking.student.user,
                type="booking",
                title="تذكير بالجلسة القادمة",
                content=f"لديك جلسة خلال ساعة بتاريخ {booking.scheduled_start.strftime('%Y-%m-%d')} الساعة {booking.scheduled_start.strftime('%I:%M %p')}.",
                data={"booking_id": booking.booking_id, "meeting_url": booking.meeting_url or ""},
            )
            Notification.objects.create(
                user=booking.teacher.user,
                type="booking",
                title="تذكير بجلسة قادمة",
                content=f"لديك جلسة خلال ساعة بتاريخ {booking.scheduled_start.strftime('%Y-%m-%d')} الساعة {booking.scheduled_start.strftime('%I:%M %p')}.",
                data={"booking_id": booking.booking_id, "meeting_url": booking.meeting_url or ""},
            )

            booking.reminder_sent = True
            booking.reminder_sent_at = timezone.now()
            booking.save()
            
            logger.info(f"Reminder sent for booking {booking.uuid}")
            
        except Exception as e:
            logger.error(f"Failed to send reminder for {booking.uuid}: {str(e)}")


@shared_task(bind=True, max_retries=3)
def create_zoom_meeting(self, booking_id):
    """Create Zoom meeting for a booking"""
    try:
        booking = Booking.objects.select_related(
            'teacher__user', 'student__user'
        ).get(uuid=booking_id)

        if not booking.meeting_url:
            room_name = build_jitsi_room_name(booking)
            booking.meeting_id = room_name
            booking.meeting_url = build_jitsi_join_url(room_name)
            booking.meeting_provider = "jitsi"
            booking.save()

            logger.info(f"Live classroom created for booking {booking_id}")
            _send_zoom_link_email(booking)
        
    except Booking.DoesNotExist:
        logger.error(f"Booking not found: {booking_id}")
    except Exception as e:
        logger.error(f"Failed to create Zoom meeting: {str(e)}")
        raise self.retry(exc=e, countdown=300)


def _send_zoom_link_email(booking):
    """Internal: Send Zoom meeting link via email"""
    subject = 'رابط الجلسة المباشرة للحجز'
    message = f'''
    مرحباً,
    
    تم إنشاء رابط الجلسة المباشرة لحجزك:
    
    📅 التاريخ: {booking.scheduled_start.strftime("%Y-%m-%d")}
    ⏰ الوقت: {booking.scheduled_start.strftime("%I:%M %p")}
    🔗 رابط الجلسة: {booking.meeting_url}
    
    انضم في الوقت المحدد!
    
    فريق EduVerse
    '''
    
    # Send to both student and teacher
    recipients = [
        booking.student.user.email,
        booking.teacher.user.email
    ]
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=True,
    )


@shared_task
def cleanup_old_bookings():
    """Archive or cleanup very old completed bookings"""
    logger.info("Cleaning up old bookings...")
    
    six_months_ago = timezone.now() - timedelta(days=180)
    
    old_bookings = Booking.objects.filter(
        status__in=['completed', 'cancelled', 'no_show'],
        scheduled_start__lt=six_months_ago
    )
    
    count = old_bookings.count()
    # Instead of deleting, you might want to archive them
    # old_bookings.update(archived=True)
    
    logger.info(f"Found {count} old bookings to archive")
