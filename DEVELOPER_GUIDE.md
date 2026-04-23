# 👨‍💻 EduVerse Platform - Developer Guide

## 🏗️ Architecture Overview

### System Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Templates + JS)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Dashboard │  │ Courses  │  │Assessments│  │ Bookings │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                      Django Application Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Views    │  │  Forms   │  │Serializers│  │  APIs    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                      Business Logic Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Analytics │  │  Search  │  │ Payment  │  │  Booking │       │
│  │  Engine  │  │  Engine  │  │ Gateway  │  │ Manager  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                         Data Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │PostgreSQL│  │  Redis   │  │   AWS    │  │  Celery  │       │
│  │    DB    │  │  Cache   │  │   S3     │  │  Queue   │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Stripe  │  │ Moyasar  │  │   Zoom   │  │  Email   │       │
│  │  Payment │  │  Payment │  │   API    │  │  SMTP    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema

### Core Models

#### User Model (Accounts)
```python
User (extends AbstractUser)
├── email (unique)
├── first_name
├── last_name
├── is_active
└── roles (ManyToMany with Role)
    ├── StudentProfile
    │   ├── date_of_birth
    │   ├── grade_level
    │   └── interests
    └── TeacherProfile
        ├── bio
        ├── hourly_rate
        ├── expertise
        └── subjects (ManyToMany)
```

#### Course Model
```python
Course
├── course_id (UUID, PK)
├── title
├── description
├── teacher (FK -> TeacherProfile)
├── subject (FK -> Subject)
├── course_type (recorded/live/hybrid)
├── level (beginner/intermediate/advanced)
├── price & currency
├── status (draft/published/archived)
└── timestamps
    └── Lessons (related)
        ├── title
        ├── content
        ├── video_url
        ├── order_index
        └── duration_minutes
```

#### Enrollment Model
```python
Enrollment
├── enrollment_id (UUID, PK)
├── student (FK -> StudentProfile)
├── course (FK -> Course)
├── enrolled_date
├── progress_percentage
├── payment_status
└── status (active/completed/refunded)
```

#### Booking Model
```python
Booking
├── uuid (PK)
├── student (FK -> StudentProfile)
├── teacher (FK -> TeacherProfile)
├── scheduled_start
├── scheduled_end
├── duration_minutes
├── status (pending/confirmed/ongoing/completed/cancelled)
├── zoom_meeting_id
└── zoom_meeting_url
```

#### Payment Model
```python
Payment
├── uuid (PK)
├── user (FK -> User)
├── amount & currency
├── payment_method
├── payment_gateway (stripe/moyasar)
├── transaction_id
├── status (pending/processing/completed/failed/refunded)
├── enrollment (FK, optional)
└── booking (FK, optional)
```

---

## 🔄 Data Flow Examples

### Course Enrollment Flow
```
1. Student browses courses → CourseListView
2. Student clicks "Enroll" → enroll_course view
3. Creates Enrollment (status='pending')
4. Redirects to Payment → create_payment_intent
5. Payment Gateway (Stripe/Moyasar) processes
6. Webhook confirms payment → update Enrollment
7. Celery task sends confirmation email
8. Student can access course content
```

### Booking Flow with Conflict Detection
```
1. Student selects teacher & time → book_session view
2. BookingConflictDetector.check_availability()
   ├── Check existing bookings (DB lock)
   ├── Check teacher schedule
   └── Validate minimum advance time
3. If available:
   ├── Create Booking (status='pending')
   ├── Trigger Zoom meeting creation (Celery task)
   ├── Send confirmation email
   └── Schedule reminder (Celery beat)
4. If conflict: Return error with suggestions
```

### Real-time Notification Flow
```
1. Event occurs (enrollment, message, etc.)
2. Create Notification record in DB
3. Celery task calls send_notification_to_user()
4. Channel layer broadcasts to user's WebSocket group
5. NotificationConsumer.notification_message() receives
6. Frontend JavaScript displays toast notification
7. Updates notification badge count
```

---

## 🛠️ Key Components Deep Dive

### 1. Search Engine (`courses/search.py`)

```python
class CourseSearchEngine:
    def search(self, query_text='', **filters):
        """
        Multi-field search with filters:
        - Text search: title, description
        - Filters: subject, level, price range, type
        - Sorting: relevance, price, date, rating
        """
        # Implementation uses Django Q objects
        # Combines text search with filter conditions
        # Returns optimized queryset with select_related
```

**Usage:**
```python
engine = CourseSearchEngine()
results = engine.search(
    query_text='Python',
    level='beginner',
    price_min=100,
    price_max=500,
    sort_by='price'
)
facets = engine.get_facets()  # For filter UI
```

---

### 2. Analytics Engine (`courses/analytics.py`)

```python
class StudentAnalytics:
    def get_overview(self):
        """
        Returns:
        - Total/active/completed courses
        - Learning hours
        - Completion rate
        - Assessment scores
        - Current streak
        """
        # Uses Django ORM aggregations
        # Optimized with select_related/prefetch_related
```

**Usage:**
```python
analytics = StudentAnalytics(student_profile)
overview = analytics.get_overview()
progress = analytics.get_progress_by_course()
heatmap = analytics.get_activity_heatmap(days=90)
```

---

### 3. Payment Gateway (`payments/payment_gateways.py`)

**Factory Pattern:**
```python
class PaymentGatewayFactory:
    @staticmethod
    def get_gateway(gateway_name):
        # Returns StripeGateway or MoyasarGateway
```

**Processor:**
```python
class PaymentProcessor:
    def process_payment(self, user, amount, currency, metadata):
        """
        1. Create Payment record (status='pending')
        2. Create intent with gateway
        3. Return client_secret for frontend
        """
    
    def confirm_payment_completion(self, payment_uuid):
        """
        1. Verify with gateway
        2. Update Payment status
        3. Update related objects (Enrollment/Booking)
        4. Trigger confirmation email
        """
```

---

### 4. Booking Manager (`bookings/booking_manager.py`)

**Conflict Detection:**
```python
class BookingConflictDetector:
    def check_availability(self, start_time, end_time):
        """
        Checks:
        1. Overlapping bookings (DB query with time range)
        2. Teacher availability schedule
        3. Minimum advance booking (2 hours)
        4. Not in the past
        
        Returns: {'available': bool, 'reason': str}
        """
    
    def get_available_slots(self, date, duration=60):
        """
        Returns list of available time slots:
        - Based on teacher availability
        - Excludes booked slots
        - 15-minute intervals
        """
```

**Atomic Booking Creation:**
```python
@transaction.atomic
def create_booking(student, teacher, start, end):
    # Uses select_for_update() to lock rows
    # Prevents race conditions
```

---

### 5. Certificate Generator (`courses/certificate_generator.py`)

**PDF Generation:**
```python
class CertificateGenerator:
    def generate_certificate(self, enrollment):
        """
        1. Generate unique certificate ID
        2. Create Certificate record
        3. Generate PDF with ReportLab
           - Custom design
           - Student name, course title
           - Teacher signature
           - QR code for verification
        4. Upload to S3 (or local media)
        5. Return Certificate instance
        """
    
    def _generate_qr_code(self, certificate):
        """
        Creates QR code pointing to verification URL:
        https://eduverse.com/certificates/verify/{cert_id}/
        """
```

---

### 6. Zoom Integration (`bookings/zoom_integration.py`)

```python
class ZoomIntegration:
    def create_meeting(self, topic, start_time, duration):
        """
        1. Generate JWT token
        2. POST to Zoom API /users/me/meetings
        3. Returns meeting_id, join_url, start_url
        """
    
    def update_meeting(self, meeting_id, updates):
        """Update existing meeting (reschedule)"""
    
    def delete_meeting(self, meeting_id):
        """Cancel Zoom meeting"""
```

**Webhook Handler:**
```python
class ZoomWebhookHandler:
    @staticmethod
    def handle_meeting_started(event_data):
        # Update Booking status to 'ongoing'
    
    @staticmethod
    def handle_meeting_ended(event_data):
        # Update Booking status to 'completed'
```

---

### 7. WebSocket Consumers (`notifications/consumers.py`)

```python
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join user's personal notification channel
        self.notification_group_name = f'notifications_{user.id}'
    
    async def notification_message(self, event):
        # Send notification to WebSocket client
        await self.send(json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
```

**Frontend Integration:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/notifications/');

ws.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.type === 'notification') {
        showNotificationToast(data.notification);
    }
};
```

---

## ⚙️ Celery Tasks

### Periodic Tasks (Celery Beat)

**Daily Tasks:**
```python
# Send daily digest emails (8 AM)
@shared_task
def send_daily_digest():
    # Aggregate user activity
    # Send personalized email

# Clean expired payments (2 AM)
@shared_task
def cleanup_expired_payments():
    # Delete old pending payments
```

**Frequent Tasks:**
```python
# Check booking statuses (every 5 min)
@shared_task
def check_booking_statuses():
    # Mark ongoing/completed bookings

# Send booking reminders (every 10 min)
@shared_task
def send_booking_reminders():
    # Remind 1 hour before
```

### On-Demand Tasks

```python
# Send enrollment email (triggered by enrollment)
@shared_task(bind=True, max_retries=3)
def send_enrollment_confirmation_email(self, enrollment_id):
    # Sends confirmation
    # Retries on failure with exponential backoff

# Create Zoom meeting (triggered by booking)
@shared_task
def create_zoom_meeting(booking_id):
    # Creates Zoom meeting
    # Saves meeting_url to Booking
    # Sends email with link
```

---

## 🧪 Testing Strategy

### Test Structure

```python
# Unit Tests
class CourseSearchEngineTests(TestCase):
    def test_text_search(self):
        # Test search returns correct results
    
    def test_filters(self):
        # Test price, level, subject filters
    
    def test_facets(self):
        # Test facet generation

# Integration Tests
class EnrollmentFlowTests(TestCase):
    def test_complete_enrollment_flow(self):
        # 1. Create course
        # 2. Enroll student
        # 3. Process payment
        # 4. Verify enrollment status
        # 5. Check email sent

# Performance Tests
class PerformanceTests(TestCase):
    def test_bulk_course_query(self):
        # Test query count with select_related
        with self.assertNumQueries(1):
            list(Course.objects.select_related(...).all())
```

### Running Tests

```bash
# All tests
python manage.py test

# Specific app
python manage.py test courses

# With coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report

# Specific test class
python manage.py test accounts.tests_comprehensive.UserAuthenticationTests

# Parallel execution
python manage.py test --parallel
```

---

## 🔍 Debugging Tips

### Django Debug Toolbar
```python
# Add to INSTALLED_APPS
'debug_toolbar',

# Middleware
'debug_toolbar.middleware.DebugToolbarMiddleware',

# Shows:
# - SQL queries (count, time, duplicates)
# - Template rendering
# - Cache hits/misses
# - Signal calls
```

### Logging Configuration
```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
        },
        'courses': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
```

### Common Issues

**Issue: N+1 Query Problem**
```python
# Bad (N+1 queries)
courses = Course.objects.all()
for course in courses:
    print(course.teacher.user.email)  # Triggers query each time

# Good (2 queries)
courses = Course.objects.select_related('teacher__user').all()
for course in courses:
    print(course.teacher.user.email)
```

**Issue: Race Conditions in Bookings**
```python
# Bad (race condition)
if not Booking.objects.filter(...).exists():
    Booking.objects.create(...)

# Good (atomic with lock)
@transaction.atomic
def create_booking():
    Booking.objects.select_for_update().filter(...)
    # Creates booking safely
```

---

## 📊 Performance Optimization

### Database Optimization

1. **Use select_related for ForeignKey**
```python
# Single query instead of N+1
Course.objects.select_related('teacher', 'subject').all()
```

2. **Use prefetch_related for ManyToMany**
```python
Course.objects.prefetch_related('lessons').all()
```

3. **Index Important Fields**
```python
class Meta:
    indexes = [
        models.Index(fields=['status', 'created_at']),
        models.Index(fields=['teacher', 'status']),
    ]
```

4. **Database-level Aggregations**
```python
# Better than Python loops
Course.objects.aggregate(
    total_students=Count('enrollment'),
    avg_rating=Avg('rating')
)
```

### Caching Strategy

```python
from django.core.cache import cache

# Cache course list for 5 minutes
def get_popular_courses():
    cache_key = 'popular_courses'
    courses = cache.get(cache_key)
    
    if not courses:
        courses = Course.objects.filter(
            status='published'
        ).order_by('-enrollment_count')[:10]
        cache.set(cache_key, courses, 300)  # 5 minutes
    
    return courses

# Invalidate cache on course update
@receiver(post_save, sender=Course)
def invalidate_course_cache(sender, instance, **kwargs):
    cache.delete('popular_courses')
```

### Async Tasks for Heavy Operations

```python
# Don't block request-response cycle
@shared_task
def process_video_upload(video_file_path):
    # Transcode video
    # Generate thumbnails
    # Upload to S3
    # This runs in background
```

---

## 🔐 Security Best Practices

### 1. Input Validation
```python
from django.core.validators import MinValueValidator, MaxValueValidator

class Course(models.Model):
    price = models.DecimalField(
        validators=[MinValueValidator(0), MaxValueValidator(10000)]
    )
```

### 2. Permission Checks
```python
@login_required
def edit_course(request, course_id):
    course = get_object_or_404(Course, course_id=course_id)
    
    # Check if user is course teacher
    if course.teacher.user != request.user:
        raise PermissionDenied
```

### 3. Secure File Uploads
```python
def validate_file_extension(value):
    valid_extensions = ['.pdf', '.docx', '.mp4']
    if not any(value.name.endswith(ext) for ext in valid_extensions):
        raise ValidationError('Invalid file type')

class CourseLesson(models.Model):
    material = models.FileField(
        validators=[validate_file_extension],
        upload_to='course_materials/'
    )
```

### 4. Rate Limiting
```python
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

@method_decorator(ratelimit(key='ip', rate='10/m'), name='dispatch')
class CreateCourseView(View):
    # Limited to 10 requests per minute per IP
```

---

## 📝 Code Style Guide

### Naming Conventions
- Models: `PascalCase` (e.g., `CourseLesson`)
- Functions/methods: `snake_case` (e.g., `get_user_courses`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`)
- Private methods: `_leading_underscore` (e.g., `_calculate_total`)

### Docstrings
```python
def process_payment(user, amount, currency, metadata=None):
    """
    Process a payment transaction through payment gateway.
    
    Args:
        user (User): User making the payment
        amount (Decimal): Payment amount
        currency (str): ISO currency code (e.g., 'SAR')
        metadata (dict, optional): Additional payment data
    
    Returns:
        dict: Payment result with 'success' key and payment details
    
    Raises:
        ValueError: If amount is negative
        PaymentGatewayError: If gateway communication fails
    
    Example:
        >>> result = process_payment(user, 100.00, 'SAR')
        >>> if result['success']:
        ...     print(f"Payment ID: {result['payment_id']}")
    """
```

### Import Organization
```python
# Standard library
import json
import logging
from datetime import datetime, timedelta

# Django
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

# Third-party
import stripe
from celery import shared_task

# Local
from .models import Course, Enrollment
from .forms import CourseForm
```

---

## 🚀 Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Database migrations created
- [ ] Static files collected
- [ ] Environment variables set
- [ ] Backup current database
- [ ] Security scan completed

### Deployment Steps
1. Pull latest code
2. Activate virtual environment
3. Install/update requirements
4. Run migrations
5. Collect static files
6. Restart services (Gunicorn, Celery)
7. Test critical flows
8. Monitor logs

### Post-Deployment
- [ ] Smoke tests passed
- [ ] Monitor error rates (Sentry)
- [ ] Check performance metrics
- [ ] Verify scheduled tasks running
- [ ] Confirm webhooks working

---

## 📚 Additional Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **DRF Documentation**: https://www.django-rest-framework.org/
- **Celery Documentation**: https://docs.celeryproject.org/
- **Stripe API**: https://stripe.com/docs/api
- **Zoom API**: https://marketplace.zoom.us/docs/api-reference/

---

**Happy Coding! 🎉**
