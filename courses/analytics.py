# ===== EduVerse Analytics & Reporting System =====
# Advanced analytics for students, teachers, and admins

from django.db.models import Count, Sum, Avg, F, Q, ExpressionWrapper, DurationField
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Course, Enrollment, LessonProgress, CourseLesson
from bookings.models import Booking
from assessments.models import AssessmentAttempt, Assessment
from accounts.models import StudentProfile, TeacherProfile, User
import json


class StudentAnalytics:
    """
    Comprehensive analytics for student performance and progress
    """
    
    def __init__(self, student_profile):
        self.student = student_profile
        self.user = student_profile.user
    
    def get_overview(self):
        """Get overall student statistics"""
        enrollments = Enrollment.objects.filter(student=self.student)
        
        total_courses = enrollments.count()
        active_courses = enrollments.filter(status='active').count()
        completed_courses = enrollments.filter(status='completed').count()
        
        # Learning hours
        total_lesson_time = LessonProgress.objects.filter(
            student=self.student
        ).aggregate(total=Sum('time_spent'))['total'] or 0
        
        # Convert seconds to hours
        learning_hours = round(total_lesson_time / 3600, 1)
        
        # Bookings stats
        total_bookings = Booking.objects.filter(student=self.student).count()
        completed_bookings = Booking.objects.filter(
            student=self.student,
            status='completed'
        ).count()
        
        # Assessment stats
        assessments_taken = AssessmentAttempt.objects.filter(
            student=self.student,
            status='completed'
        ).count()
        
        avg_score = AssessmentAttempt.objects.filter(
            student=self.student,
            status='completed'
        ).aggregate(avg=Avg('percentage'))['avg'] or 0
        
        return {
            'total_courses': total_courses,
            'active_courses': active_courses,
            'completed_courses': completed_courses,
            'completion_rate': round((completed_courses / total_courses * 100) if total_courses > 0 else 0, 1),
            'learning_hours': learning_hours,
            'total_bookings': total_bookings,
            'completed_bookings': completed_bookings,
            'assessments_taken': assessments_taken,
            'average_score': round(avg_score, 1),
        }
    
    def get_progress_by_course(self):
        """Get detailed progress for each enrolled course"""
        enrollments = Enrollment.objects.filter(
            student=self.student,
            status__in=['active', 'completed']
        ).select_related('course', 'course__subject')
        
        progress_data = []
        
        for enrollment in enrollments:
            course = enrollment.course
            total_lessons = CourseLesson.objects.filter(
                course=course,
                status='published'
            ).count()
            
            completed_lessons = LessonProgress.objects.filter(
                student=self.student,
                lesson__course=course,
                completed=True
            ).count()
            
            time_spent = LessonProgress.objects.filter(
                student=self.student,
                lesson__course=course
            ).aggregate(total=Sum('time_spent'))['total'] or 0
            
            progress_data.append({
                'course_id': course.course_id,
                'course_title': course.title,
                'subject': course.subject.subject_name if course.subject else None,
                'total_lessons': total_lessons,
                'completed_lessons': completed_lessons,
                'progress_percentage': enrollment.progress_percentage,
                'time_spent_hours': round(time_spent / 3600, 1),
                'status': enrollment.status,
                'enrollment_date': enrollment.enrollment_date,
            })
        
        return progress_data
    
    def get_learning_streak(self):
        """Calculate current learning streak in days"""
        # Get lesson progress dates
        progress_dates = LessonProgress.objects.filter(
            student=self.student,
            completed=True
        ).values_list('completion_date', flat=True).order_by('-completion_date')
        
        if not progress_dates:
            return 0
        
        # Calculate streak
        streak = 1
        current_date = progress_dates[0].date()
        
        for date in progress_dates[1:]:
            date = date.date()
            if (current_date - date).days == 1:
                streak += 1
                current_date = date
            elif (current_date - date).days > 1:
                break
        
        return streak
    
    def get_activity_heatmap(self, days=90):
        """Get learning activity for heatmap visualization"""
        start_date = timezone.now() - timedelta(days=days)
        
        activities = LessonProgress.objects.filter(
            student=self.student,
            updated_at__gte=start_date
        ).annotate(
            date=TruncDate('updated_at')
        ).values('date').annotate(
            count=Count('progress_id'),
            total_time=Sum('time_spent')
        ).order_by('date')
        
        # Format for frontend
        heatmap_data = []
        for activity in activities:
            heatmap_data.append({
                'date': activity['date'].strftime('%Y-%m-%d'),
                'count': activity['count'],
                'hours': round(activity['total_time'] / 3600, 1),
            })
        
        return heatmap_data
    
    def get_assessment_performance(self):
        """Get detailed assessment performance"""
        attempts = AssessmentAttempt.objects.filter(
            student=self.student,
            status='completed'
        ).select_related('assessment').order_by('-created_at')
        
        performance_data = []
        
        for attempt in attempts:
            performance_data.append({
                'assessment_title': attempt.assessment.title,
                'subject': attempt.assessment.subject.subject_name if attempt.assessment.subject else None,
                'score': float(attempt.score) if attempt.score else 0,
                'max_score': float(attempt.max_score) if attempt.max_score else 100,
                'percentage': float(attempt.percentage) if attempt.percentage else 0,
                'passed': attempt.passed,
                'time_taken_minutes': round(attempt.time_taken / 60) if attempt.time_taken else 0,
                'date': attempt.created_at,
                'attempt_number': attempt.attempt_number,
            })
        
        return performance_data
    
    def get_learning_recommendations(self):
        """Get personalized learning recommendations"""
        # Analyze weak subjects
        weak_assessments = AssessmentAttempt.objects.filter(
            student=self.student,
            status='completed',
            passed=False
        ).values('assessment__subject').annotate(
            fail_count=Count('attempt_id')
        ).order_by('-fail_count')[:3]
        
        weak_subjects = [item['assessment__subject'] for item in weak_assessments if item['assessment__subject']]
        
        # Get courses in weak subjects
        from .search import RecommendationEngine
        recommendations = RecommendationEngine.get_recommendations_for_student(self.student, limit=5)
        
        return {
            'weak_subjects': weak_subjects,
            'recommended_courses': recommendations,
        }


class TeacherAnalytics:
    """
    Comprehensive analytics for teacher performance and earnings
    """
    
    def __init__(self, teacher_profile):
        self.teacher = teacher_profile
        self.user = teacher_profile.user
    
    def get_overview(self):
        """Get overall teacher statistics"""
        # Course stats
        total_courses = Course.objects.filter(teacher=self.teacher).count()
        published_courses = Course.objects.filter(
            teacher=self.teacher,
            status='published'
        ).count()
        
        # Student stats
        total_enrollments = Enrollment.objects.filter(
            course__teacher=self.teacher
        ).count()
        
        unique_students = Enrollment.objects.filter(
            course__teacher=self.teacher
        ).values('student').distinct().count()
        
        # Booking stats
        total_bookings = Booking.objects.filter(teacher=self.teacher).count()
        completed_bookings = Booking.objects.filter(
            teacher=self.teacher,
            status='completed'
        ).count()
        
        # Teaching hours (from completed bookings)
        teaching_hours = Booking.objects.filter(
            teacher=self.teacher,
            status='completed',
            actual_start__isnull=False,
            actual_end__isnull=False
        ).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('actual_end') - F('actual_start'),
                    output_field=DurationField()
                )
            )
        )['total']
        
        teaching_hours_value = teaching_hours.total_seconds() / 3600 if teaching_hours else 0
        
        # Revenue calculation (approximate)
        revenue = Enrollment.objects.filter(
            course__teacher=self.teacher,
            payment_status='paid'
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
        return {
            'total_courses': total_courses,
            'published_courses': published_courses,
            'total_enrollments': total_enrollments,
            'unique_students': unique_students,
            'total_bookings': total_bookings,
            'completed_bookings': completed_bookings,
            'teaching_hours': round(teaching_hours_value, 1),
            'total_revenue': float(revenue),
        }
    
    def get_course_performance(self):
        """Get detailed performance for each course"""
        courses = Course.objects.filter(teacher=self.teacher).annotate(
            enrollment_count=Count('enrollment'),
            completed_count=Count('enrollment', filter=Q(enrollment__status='completed')),
            revenue=Sum('enrollment__amount_paid', filter=Q(enrollment__payment_status='paid'))
        )
        
        performance_data = []
        
        for course in courses:
            # Calculate average progress
            avg_progress = Enrollment.objects.filter(
                course=course,
                status__in=['active', 'completed']
            ).aggregate(avg=Avg('progress_percentage'))['avg'] or 0
            
            performance_data.append({
                'course_id': course.course_id,
                'course_title': course.title,
                'status': course.status,
                'enrollment_count': course.enrollment_count,
                'completed_count': course.completed_count,
                'completion_rate': round(
                    (course.completed_count / course.enrollment_count * 100)
                    if course.enrollment_count > 0 else 0,
                    1
                ),
                'average_progress': round(avg_progress, 1),
                'revenue': float(course.revenue) if course.revenue else 0,
            })
        
        return performance_data
    
    def get_earnings_timeline(self, days=30):
        """Get earnings over time for charts"""
        start_date = timezone.now() - timedelta(days=days)
        
        earnings = Enrollment.objects.filter(
            course__teacher=self.teacher,
            payment_status='paid',
            created_at__gte=start_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            daily_revenue=Sum('amount_paid'),
            enrollments=Count('enrollment_id')
        ).order_by('date')
        
        timeline_data = []
        for earning in earnings:
            timeline_data.append({
                'date': earning['date'].strftime('%Y-%m-%d'),
                'revenue': float(earning['daily_revenue']),
                'enrollments': earning['enrollments'],
            })
        
        return timeline_data
    
    def get_student_engagement(self):
        """Analyze student engagement in teacher's courses"""
        # Get students with their progress
        students = Enrollment.objects.filter(
            course__teacher=self.teacher,
            status__in=['active', 'completed']
        ).select_related('student__user').values(
            'student__user__first_name',
            'student__user__last_name',
            'student__student_id'
        ).annotate(
            courses_count=Count('enrollment_id'),
            avg_progress=Avg('progress_percentage')
        ).order_by('-avg_progress')[:20]
        
        return list(students)
    
    def get_booking_calendar(self, year=None, month=None):
        """Get booking schedule for calendar view"""
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
        
        bookings = Booking.objects.filter(
            teacher=self.teacher,
            scheduled_start__year=year,
            scheduled_start__month=month
        ).select_related('student__user', 'course').order_by('scheduled_start')
        
        calendar_data = []
        for booking in bookings:
            calendar_data.append({
                'id': booking.booking_id,
                'student_name': f"{booking.student.user.first_name} {booking.student.user.last_name}",
                'course_title': booking.course.title if booking.course else 'Session',
                'start': booking.scheduled_start.isoformat(),
                'end': booking.scheduled_end.isoformat(),
                'status': booking.status,
            })
        
        return calendar_data


class AdminAnalytics:
    """
    Platform-wide analytics for administrators
    """
    
    @staticmethod
    def get_platform_overview():
        """Get overall platform statistics"""
        # User stats
        total_users = User.objects.filter(is_active=True).count()
        total_students = StudentProfile.objects.count()
        total_teachers = TeacherProfile.objects.filter(verification_status='verified').count()
        
        # Course stats
        total_courses = Course.objects.count()
        published_courses = Course.objects.filter(status='published').count()
        
        # Enrollment stats
        total_enrollments = Enrollment.objects.count()
        active_enrollments = Enrollment.objects.filter(status='active').count()
        
        # Booking stats
        total_bookings = Booking.objects.count()
        completed_bookings = Booking.objects.filter(status='completed').count()
        
        # Revenue
        total_revenue = Enrollment.objects.filter(
            payment_status='paid'
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
        return {
            'total_users': total_users,
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_courses': total_courses,
            'published_courses': published_courses,
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'total_bookings': total_bookings,
            'completed_bookings': completed_bookings,
            'total_revenue': float(total_revenue),
        }
    
    @staticmethod
    def get_growth_metrics(days=30):
        """Get growth metrics over time"""
        start_date = timezone.now() - timedelta(days=days)
        
        # New users
        new_users = User.objects.filter(
            date_joined__gte=start_date
        ).annotate(
            date=TruncDate('date_joined')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # New enrollments
        new_enrollments = Enrollment.objects.filter(
            enrollment_date__gte=start_date
        ).annotate(
            date=TruncDate('enrollment_date')
        ).values('date').annotate(
            count=Count('enrollment_id')
        ).order_by('date')
        
        # Revenue
        daily_revenue = Enrollment.objects.filter(
            created_at__gte=start_date,
            payment_status='paid'
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            revenue=Sum('amount_paid')
        ).order_by('date')
        
        return {
            'new_users': list(new_users),
            'new_enrollments': list(new_enrollments),
            'daily_revenue': list(daily_revenue),
        }
    
    @staticmethod
    def get_popular_subjects():
        """Get most popular subjects by enrollment"""
        from courses.models import Subject
        
        popular = Subject.objects.annotate(
            course_count=Count('course'),
            enrollment_count=Count('course__enrollment')
        ).order_by('-enrollment_count')[:10]
        
        return list(popular.values('subject_name', 'course_count', 'enrollment_count'))
    
    @staticmethod
    def get_top_teachers(limit=10):
        """Get top performing teachers"""
        teachers = TeacherProfile.objects.annotate(
            student_count=Count('course__enrollment__student', distinct=True),
            course_count=Count('course'),
            revenue=Sum('course__enrollment__amount_paid', filter=Q(course__enrollment__payment_status='paid'))
        ).order_by('-student_count')[:limit]
        
        top_teachers = []
        for teacher in teachers:
            top_teachers.append({
                'name': f"{teacher.user.first_name} {teacher.user.last_name}",
                'student_count': teacher.student_count,
                'course_count': teacher.course_count,
                'revenue': float(teacher.revenue) if teacher.revenue else 0,
            })
        
        return top_teachers
