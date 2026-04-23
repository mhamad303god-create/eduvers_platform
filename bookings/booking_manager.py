# ===== Booking Conflict Detection and Management =====
# Prevent overlapping bookings and scheduling conflicts

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Booking, TeacherAvailability
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

DAY_NAMES = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}


class BookingConflictDetector:
    """
    Detect and prevent booking conflicts
    Ensures no overlapping bookings for teachers
    """
    
    def __init__(self, teacher_profile):
        self.teacher = teacher_profile
    
    def check_availability(self, start_time, end_time):
        """
        Check if teacher is available for the given time slot
        
        Args:
            start_time: datetime
            end_time: datetime
        
        Returns:
            dict with 'available' boolean and 'reason' if not available
        """
        # Check for existing bookings
        conflict = self._check_booking_conflicts(start_time, end_time)
        if conflict:
            return {
                'available': False,
                'reason': 'Teacher has another booking at this time',
                'conflicting_booking': conflict
            }
        
        # Check teacher's availability schedule
        if not self._check_teacher_schedule(start_time, end_time):
            return {
                'available': False,
                'reason': 'Teacher is not available at this time'
            }
        
        # Check if time is in the past
        if start_time <= timezone.now():
            return {
                'available': False,
                'reason': 'Cannot book in the past'
            }
        
        # Check minimum advance booking time (e.g., 2 hours)
        min_advance = timezone.now() + timedelta(hours=2)
        if start_time < min_advance:
            return {
                'available': False,
                'reason': 'Bookings must be made at least 2 hours in advance'
            }
        
        return {'available': True}
    
    def _check_booking_conflicts(self, start_time, end_time):
        """Check for overlapping bookings"""
        conflicts = Booking.objects.filter(
            teacher=self.teacher,
            status__in=['confirmed', 'pending', 'in_progress']
        ).filter(
            Q(scheduled_start__lt=end_time, scheduled_end__gt=start_time) |
            Q(scheduled_start__gte=start_time, scheduled_start__lt=end_time) |
            Q(scheduled_end__gt=start_time, scheduled_end__lte=end_time)
        )
        
        return conflicts.first()
    
    def _check_teacher_schedule(self, start_time, end_time):
        """Check if time falls within teacher's availability"""
        day_of_week = DAY_NAMES[start_time.weekday()]

        availabilities = TeacherAvailability.objects.filter(
            teacher=self.teacher,
            day_of_week=day_of_week,
            status='available'
        )
        
        # If no availability set, allow all times
        if not availabilities.exists():
            return True
        
        # Check if requested time falls within any availability slot
        start_time_only = start_time.time()
        end_time_only = end_time.time()
        
        for availability in availabilities:
            if (availability.start_time <= start_time_only and 
                availability.end_time >= end_time_only):
                return True
        
        return False
    
    def get_available_slots(self, date, duration_minutes=60):
        """
        Get all available time slots for a specific date
        
        Args:
            date: datetime.date object
            duration_minutes: Session duration
        
        Returns:
            list of available time slots
        """
        day_of_week = DAY_NAMES[date.weekday()]
        
        # Get teacher's availability for this day
        availabilities = TeacherAvailability.objects.filter(
            teacher=self.teacher,
            day_of_week=day_of_week,
            status='available'
        ).order_by('start_time')
        
        if not availabilities.exists():
            return []
        
        available_slots = []
        
        for availability in availabilities:
            # Generate slots within this availability window
            current_time = datetime.combine(date, availability.start_time)
            end_boundary = datetime.combine(date, availability.end_time)
            
            while current_time + timedelta(minutes=duration_minutes) <= end_boundary:
                slot_start = current_time
                slot_end = current_time + timedelta(minutes=duration_minutes)
                
                # Check if this slot is available
                check_result = self.check_availability(slot_start, slot_end)
                
                if check_result['available']:
                    available_slots.append({
                        'start': slot_start,
                        'end': slot_end,
                        'duration': duration_minutes
                    })
                
                # Move to next slot (15-minute intervals)
                current_time += timedelta(minutes=15)
        
        return available_slots


class BookingManager:
    """
    Advanced booking management with atomic operations
    """
    
    @staticmethod
    @transaction.atomic
    def create_booking(student, teacher, start_time, end_time, **kwargs):
        """
        Create booking with conflict detection
        
        Uses database transaction to prevent race conditions
        """
        # Lock teacher's bookings for update
        existing_bookings = Booking.objects.filter(
            teacher=teacher,
            status__in=['confirmed', 'pending', 'in_progress']
        ).select_for_update()
        
        # Check for conflicts
        detector = BookingConflictDetector(teacher)
        availability = detector.check_availability(start_time, end_time)
        
        if not availability['available']:
            raise ValueError(availability['reason'])
        
        # Create booking
        booking = Booking.objects.create(
            student=student,
            teacher=teacher,
            scheduled_start=start_time,
            scheduled_end=end_time,
            status='pending',
            **kwargs
        )
        
        logger.info(f"Booking created: {booking.uuid}")
        
        # Trigger Zoom meeting creation (async)
        from .tasks import create_zoom_meeting
        create_zoom_meeting.delay(str(booking.uuid))
        
        return booking
    
    @staticmethod
    def cancel_booking(booking, cancelled_by, reason=None):
        """Cancel a booking"""
        if booking.status not in ['pending', 'confirmed']:
            raise ValueError("Cannot cancel this booking")
        
        booking.status = 'cancelled'
        booking.save()
        
        logger.info(f"Booking cancelled: {booking.uuid} by {cancelled_by.email}")
        
        # Send cancellation notifications
        from notifications.tasks import send_booking_cancellation_notification
        send_booking_cancellation_notification.delay(str(booking.uuid))
        
        return booking
    
    @staticmethod
    def reschedule_booking(booking, new_start_time, new_end_time):
        """Reschedule an existing booking"""
        if booking.status != 'confirmed':
            raise ValueError("Only confirmed bookings can be rescheduled")
        
        # Check availability for new time
        detector = BookingConflictDetector(booking.teacher)
        availability = detector.check_availability(new_start_time, new_end_time)
        
        if not availability['available']:
            raise ValueError(availability['reason'])
        
        # Update booking
        booking.scheduled_start = new_start_time
        booking.scheduled_end = new_end_time
        booking.save()
        
        logger.info(f"Booking rescheduled: {booking.uuid}")
        
        # Update Zoom meeting
        from .zoom_integration import ZoomIntegration
        zoom = ZoomIntegration()
        if booking.meeting_id and booking.meeting_provider == "zoom":
            zoom.update_meeting(booking.meeting_id, {
                'start_time': new_start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'duration': booking.duration_minutes
            })
        
        return booking


class BookingAnalytics:
    """Analytics for booking patterns and teacher performance"""
    
    def __init__(self, teacher=None, student=None):
        self.teacher = teacher
        self.student = student
    
    def get_teacher_booking_stats(self):
        """Get booking statistics for teacher"""
        if not self.teacher:
            return None
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        total_bookings = Booking.objects.filter(teacher=self.teacher).count()
        completed_bookings = Booking.objects.filter(
            teacher=self.teacher,
            status='completed'
        ).count()
        
        recent_bookings = Booking.objects.filter(
            teacher=self.teacher,
            scheduled_start__gte=thirty_days_ago
        ).count()
        
        cancelled_rate = 0
        if total_bookings > 0:
            cancelled = Booking.objects.filter(
                teacher=self.teacher,
                status='cancelled'
            ).count()
            cancelled_rate = round((cancelled / total_bookings) * 100, 1)
        
        return {
            'total_bookings': total_bookings,
            'completed_bookings': completed_bookings,
            'recent_bookings': recent_bookings,
            'cancelled_rate': cancelled_rate,
            'completion_rate': round((completed_bookings / total_bookings * 100) if total_bookings > 0 else 0, 1)
        }
    
    def get_peak_hours(self):
        """Get teacher's peak booking hours"""
        if not self.teacher:
            return []
        
        from django.db.models import Count
        from django.db.models.functions import ExtractHour
        
        bookings_by_hour = Booking.objects.filter(
            teacher=self.teacher,
            status='completed'
        ).annotate(
            hour=ExtractHour('scheduled_start')
        ).values('hour').annotate(
            count=Count('booking_id')
        ).order_by('-count')[:5]
        
        return list(bookings_by_hour)
