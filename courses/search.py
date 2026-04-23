# ===== EduVerse Advanced Search System =====
# Intelligent search with filters, sorting, and recommendations

from django.db.models import Q, Count, Avg, F
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from .models import Course, Subject, TeacherSubjects
from accounts.models import TeacherProfile
import re


class CourseSearchEngine:
    """
    Advanced search engine for courses with intelligent filtering,
    ranking, and personalized recommendations.
    """
    
    def __init__(self):
        self.queryset = Course.objects.filter(status='published')
        self.filters = {}
        self.sort_by = '-created_at'
        
    def search(self, query_text='', **filters):
        """
        Main search method with text search and filters
        
        Args:
            query_text: Search text for courses
            filters: Dictionary of filters (subject, level, price_range, teacher, etc.)
        
        Returns:
            Filtered and sorted queryset
        """
        # Apply text search
        if query_text:
            self.queryset = self._text_search(query_text)
        
        # Apply filters
        self.queryset = self._apply_filters(**filters)
        
        # Apply sorting
        sort_by = filters.get('sort_by', self.sort_by)
        self.queryset = self._apply_sorting(sort_by)
        
        return self.queryset
    
    def _text_search(self, query):
        """
        Intelligent text search across multiple fields
        """
        # Clean query
        query = query.strip()
        
        # Search across title, description, and objectives
        search_filter = (
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(subject__subject_name__icontains=query) |
            Q(teacher__user__first_name__icontains=query) |
            Q(teacher__user__last_name__icontains=query)
        )
        
        return self.queryset.filter(search_filter).distinct()
    
    def _apply_filters(self, **filters):
        """Apply various filters to the queryset"""
        queryset = self.queryset
        
        # Subject filter
        if 'subject' in filters and filters['subject']:
            queryset = queryset.filter(subject_id=filters['subject'])
        
        # Level filter
        if 'level' in filters and filters['level']:
            queryset = queryset.filter(level=filters['level'])
        
        # Course type filter
        if 'course_type' in filters and filters['course_type']:
            queryset = queryset.filter(course_type=filters['course_type'])
        
        # Price range filter
        if 'price_min' in filters and filters['price_min']:
            queryset = queryset.filter(price__gte=filters['price_min'])
        
        if 'price_max' in filters and filters['price_max']:
            queryset = queryset.filter(price__lte=filters['price_max'])
        
        # Free courses filter
        if 'is_free' in filters and filters['is_free']:
            queryset = queryset.filter(Q(price=0) | Q(price__isnull=True))
        
        # Teacher filter
        if 'teacher' in filters and filters['teacher']:
            queryset = queryset.filter(teacher_id=filters['teacher'])
        
        # Featured courses
        if 'featured' in filters and filters['featured']:
            queryset = queryset.filter(is_featured=True)
        
        # Duration filter
        if 'duration_min' in filters and filters['duration_min']:
            queryset = queryset.filter(duration_minutes__gte=filters['duration_min'])
        
        if 'duration_max' in filters and filters['duration_max']:
            queryset = queryset.filter(duration_minutes__lte=filters['duration_max'])
        
        return queryset
    
    def _apply_sorting(self, sort_by):
        """Apply sorting to the queryset"""
        valid_sorts = {
            'newest': '-created_at',
            'oldest': 'created_at',
            'price_low': 'price',
            'price_high': '-price',
            'popular': '-enrollment_count',
            'rating': '-average_rating',
            'title_asc': 'title',
            'title_desc': '-title',
        }
        
        sort_field = valid_sorts.get(sort_by, '-created_at')
        
        # Annotate with enrollment count for popularity sorting
        if 'enrollment' in sort_field:
            from courses.models import Enrollment
            self.queryset = self.queryset.annotate(
                enrollment_count=Count('enrollment')
            )
        
        return self.queryset.order_by(sort_field)
    
    def get_facets(self):
        """
        Get faceted search data (aggregations)
        Returns counts for subjects, levels, price ranges, etc.
        """
        facets = {
            'subjects': self._get_subject_facets(),
            'levels': self._get_level_facets(),
            'course_types': self._get_course_type_facets(),
            'price_ranges': self._get_price_range_facets(),
        }
        return facets
    
    def _get_subject_facets(self):
        """Get course counts by subject"""
        return list(
            Course.objects.filter(status='published')
            .values('subject__subject_name', 'subject_id')
            .annotate(count=Count('course_id'))
            .order_by('-count')
        )
    
    def _get_level_facets(self):
        """Get course counts by level"""
        return list(
            Course.objects.filter(status='published')
            .values('level')
            .annotate(count=Count('course_id'))
            .order_by('-count')
        )
    
    def _get_course_type_facets(self):
        """Get course counts by type"""
        return list(
            Course.objects.filter(status='published')
            .values('course_type')
            .annotate(count=Count('course_id'))
            .order_by('-count')
        )
    
    def _get_price_range_facets(self):
        """Get course counts by price ranges"""
        from django.db.models import Case, When, IntegerField
        
        return list(
            Course.objects.filter(status='published')
            .annotate(
                price_range=Case(
                    When(price=0, then=0),
                    When(price__lt=100, then=1),
                    When(price__lt=500, then=2),
                    When(price__gte=500, then=3),
                    default=0,
                    output_field=IntegerField()
                )
            )
            .values('price_range')
            .annotate(count=Count('course_id'))
            .order_by('price_range')
        )


class TeacherSearchEngine:
    """Advanced search for teachers"""
    
    def __init__(self):
        self.queryset = TeacherProfile.objects.filter(
            verification_status='verified',
            user__status='active'
        )
    
    def search(self, query_text='', **filters):
        """Search teachers with filters"""
        if query_text:
            self.queryset = self._text_search(query_text)
        
        self.queryset = self._apply_filters(**filters)
        return self.queryset
    
    def _text_search(self, query):
        """Search teachers by name, bio, subjects"""
        search_filter = (
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(bio__icontains=query)
        )
        return self.queryset.filter(search_filter)
    
    def _apply_filters(self, **filters):
        """Apply teacher-specific filters"""
        queryset = self.queryset
        
        # Subject filter
        if 'subject' in filters and filters['subject']:
            queryset = queryset.filter(teachersubjects__subject_id=filters['subject'])
        
        # Hourly rate filter
        if 'rate_min' in filters and filters['rate_min']:
            queryset = queryset.filter(hourly_rate__gte=filters['rate_min'])
        
        if 'rate_max' in filters and filters['rate_max']:
            queryset = queryset.filter(hourly_rate__lte=filters['rate_max'])
        
        # Experience filter
        if 'experience_min' in filters and filters['experience_min']:
            queryset = queryset.filter(experience_years__gte=filters['experience_min'])
        
        return queryset.distinct()


class RecommendationEngine:
    """
    Intelligent recommendation system based on:
    - User's enrolled courses
    - User's browsing history
    - Similar students' choices
    - Popular courses in same subjects
    """
    
    @staticmethod
    def get_recommendations_for_student(student_profile, limit=10):
        """Get personalized course recommendations"""
        from courses.models import Enrollment
        
        # Get student's enrolled courses and subjects
        enrolled_courses = Enrollment.objects.filter(
            student=student_profile,
            status__in=['active', 'completed']
        ).values_list('course_id', flat=True)
        
        enrolled_subjects = Course.objects.filter(
            course_id__in=enrolled_courses
        ).values_list('subject_id', flat=True)
        
        # Recommend courses in same subjects (not enrolled)
        recommended = Course.objects.filter(
            status='published',
            subject_id__in=enrolled_subjects
        ).exclude(
            course_id__in=enrolled_courses
        ).annotate(
            enrollment_count=Count('enrollment')
        ).order_by('-enrollment_count', '-created_at')[:limit]
        
        return recommended
    
    @staticmethod
    def get_similar_courses(course, limit=5):
        """Get courses similar to given course"""
        return Course.objects.filter(
            status='published',
            subject=course.subject,
            level=course.level
        ).exclude(
            course_id=course.course_id
        ).order_by('-is_featured', '-created_at')[:limit]
    
    @staticmethod
    def get_trending_courses(limit=10):
        """Get trending courses based on recent enrollments"""
        from django.utils import timezone
        from datetime import timedelta
        from courses.models import Enrollment
        
        last_month = timezone.now() - timedelta(days=30)
        
        return Course.objects.filter(
            status='published'
        ).annotate(
            recent_enrollments=Count(
                'enrollment',
                filter=Q(enrollment__enrollment_date__gte=last_month)
            )
        ).order_by('-recent_enrollments', '-is_featured')[:limit]
