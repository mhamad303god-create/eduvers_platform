# ===== Background Tasks for Courses App =====

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg
from .models import Course, Enrollment, CourseLesson, LessonProgress, Certificate
from accounts.models import StudentProfile
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_enrollment_confirmation_email(self, enrollment_id):
    """Send confirmation email after course enrollment"""
    try:
        enrollment = Enrollment.objects.select_related(
            'student__user', 'course__teacher__user'
        ).get(enrollment_id=enrollment_id)
        
        subject = f'تأكيد التسجيل في: {enrollment.course.title}'
        message = f'''
        مرحباً {enrollment.student.user.get_full_name()},
        
        تم تسجيلك بنجاح في الكورس:
        📚 {enrollment.course.title}
        
        المعلم: {enrollment.course.teacher.user.get_full_name()}
        
        يمكنك البدء بالتعلم الآن!
        
        بالتوفيق،
        فريق EduVerse
        '''
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [enrollment.student.user.email],
            fail_silently=False,
        )
        
        logger.info(f"Enrollment email sent for: {enrollment_id}")
        
    except Enrollment.DoesNotExist:
        logger.error(f"Enrollment not found: {enrollment_id}")
    except Exception as e:
        logger.error(f"Failed to send enrollment email: {str(e)}")
        raise self.retry(exc=e, countdown=60)


@shared_task
def generate_weekly_reports():
    """Generate weekly progress reports for all students"""
    logger.info("Starting weekly report generation...")
    
    week_ago = timezone.now() - timedelta(days=7)
    
    # Get students with activity in the last week
    active_students = StudentProfile.objects.filter(
        enrollment__enrolled_date__gte=week_ago
    ).distinct()
    
    for student in active_students:
        try:
            _generate_student_weekly_report(student)
        except Exception as e:
            logger.error(f"Failed to generate report for {student.user.email}: {str(e)}")
    
    logger.info(f"Weekly reports generated for {active_students.count()} students")


def _generate_student_weekly_report(student):
    """Internal: Generate report for a single student"""
    week_ago = timezone.now() - timedelta(days=7)
    
    # Get week's progress
    progress = LessonProgress.objects.filter(
        student=student,
        last_accessed__gte=week_ago
    ).select_related('lesson__course')
    
    lessons_completed = progress.filter(completed=True).count()
    time_spent = progress.aggregate(total=sum('time_spent'))['total'] or 0
    hours = round(time_spent / 3600, 1)
    
    if lessons_completed == 0 and hours == 0:
        return  # No activity, skip report
    
    # Send email
    subject = '📊 تقريرك الأسبوعي - EduVerse'
    message = f'''
    مرحباً {student.user.get_full_name()},
    
    هذا تقريرك الأسبوعي:
    
    ✅ دروس مكتملة: {lessons_completed}
    ⏱️ ساعات التعلم: {hours}
    
    استمر في التقدم! 💪
    
    بالتوفيق،
    فريق EduVerse
    '''
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [student.user.email],
        fail_silently=True,
    )


@shared_task
def update_popularity_scores():
    """Update course popularity scores based on enrollments"""
    logger.info("Updating course popularity scores...")
    
    # Calculate popularity (recent enrollments weighted more)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    seven_days_ago = timezone.now() - timedelta(days=7)
    
    courses = Course.objects.all()
    
    for course in courses:
        recent_7d = Enrollment.objects.filter(
            course=course,
            enrolled_date__gte=seven_days_ago
        ).count()
        
        recent_30d = Enrollment.objects.filter(
            course=course,
            enrolled_date__gte=thirty_days_ago
        ).count()
        
        # Weighted popularity score
        popularity = (recent_7d * 3) + (recent_30d * 1)
        
        # Save to course metadata or custom field
        # (You can add a popularity_score field to Course model)
        logger.info(f"Course {course.title}: popularity = {popularity}")
    
    logger.info("Popularity scores updated")


@shared_task
def process_certificate_queue():
    """Process pending certificate generation requests"""
    from .certificate_generator import CertificateGenerator
    
    logger.info("Processing certificate queue...")
    
    # Find enrollments that completed but don't have certificates
    completed_enrollments = Enrollment.objects.filter(
        status='completed',
        certificate__isnull=True
    ).select_related('student__user', 'course')
    
    generator = CertificateGenerator()
    
    for enrollment in completed_enrollments[:10]:  # Process 10 at a time
        try:
            certificate = generator.generate_certificate(enrollment)
            logger.info(f"Certificate generated: {certificate.certificate_id}")
        except Exception as e:
            logger.error(f"Failed to generate certificate for {enrollment.enrollment_id}: {str(e)}")
    
    logger.info("Certificate queue processed")


@shared_task(bind=True, max_retries=3)
def send_lesson_completion_notification(self, lesson_progress_id):
    """Send notification when student completes a lesson"""
    try:
        progress = LessonProgress.objects.select_related(
            'student__user', 'lesson__course'
        ).get(id=lesson_progress_id)
        
        if not progress.completed:
            return
        
        # Check if this completes the entire course
        total_lessons = CourseLesson.objects.filter(course=progress.lesson.course).count()
        completed_lessons = LessonProgress.objects.filter(
            student=progress.student,
            lesson__course=progress.lesson.course,
            completed=True
        ).count()
        
        if total_lessons == completed_lessons:
            # Course completed!
            _handle_course_completion(progress.student, progress.lesson.course)
        
    except Exception as e:
        logger.error(f"Lesson completion notification failed: {str(e)}")
        raise self.retry(exc=e, countdown=60)


def _handle_course_completion(student, course):
    """Internal: Handle course completion"""
    # Update enrollment status
    enrollment = Enrollment.objects.get(student=student, course=course)
    enrollment.status = 'completed'
    enrollment.completion_date = timezone.now()
    enrollment.save()
    
    # Send congratulations email
    subject = f'🎉 مبروك! أكملت: {course.title}'
    message = f'''
    عزيزنا {student.user.get_full_name()},
    
    تهانينا! لقد أكملت بنجاح:
    📚 {course.title}
    
    سيتم إصدار شهادتك قريباً.
    
    نفخر بإنجازك! 🎓
    
    فريق EduVerse
    '''
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [student.user.email],
        fail_silently=True,
    )
    
    # Trigger certificate generation
    from .certificate_generator import CertificateGenerator
    generator = CertificateGenerator()
    generator.generate_certificate(enrollment)


@shared_task
def cleanup_draft_courses():
    """Remove old draft courses that were never published"""
    logger.info("Cleaning up old draft courses...")
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    old_drafts = Course.objects.filter(
        status='draft',
        created_at__lt=thirty_days_ago
    )
    
    count = old_drafts.count()
    old_drafts.delete()
    
    logger.info(f"Deleted {count} old draft courses")


@shared_task
def update_course_statistics():
    """Update course statistics and metrics"""
    logger.info("Updating course statistics...")
    
    courses = Course.objects.annotate(
        enrollment_count=Count('enrollment'),
        avg_progress=Avg('enrollment__progress_percentage')
    )
    
    for course in courses:
        # You can store these in a CourseStatistics model
        logger.info(f"Course {course.title}: {course.enrollment_count} enrollments, "
                   f"{course.avg_progress:.1f}% avg progress")
    
    logger.info("Course statistics updated")
