"""
Test script to create a course and verify it's saved to database
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduverse.settings')
django.setup()

from courses.models import Course, Subject
from accounts.models import TeacherProfile, User

def test_course_creation():
    print("=" * 50)
    print("🧪 Testing Course Creation")
    print("=" * 50)
    
    # Find a teacher
    try:
        teacher_profile = TeacherProfile.objects.first()
        if not teacher_profile:
            print("❌ No teacher profile found. Creating one...")
            # Try to find a user with teacher role
            teacher_user = User.objects.filter(userrole__role__role_name='teacher').first()
            if not teacher_user:
                print("❌ No teacher user found!")
                return
            teacher_profile = TeacherProfile.objects.create(
                user=teacher_user,
                bio="Test bio",
                hourly_rate=100
            )
            print(f"✅ Created teacher profile for {teacher_user.email}")
    except Exception as e:
        print(f"❌ Error finding teacher: {e}")
        return
    
    # Get or create a subject
    subject, created = Subject.objects.get_or_create(
        subject_code='TEST',
        defaults={
            'subject_name': 'Test Subject',
            'description': 'Test description'
        }
    )
    if created:
        print(f"✅ Created test subject: {subject.subject_name}")
    else:
        print(f"✅ Using existing subject: {subject.subject_name}")
    
    # Count courses بefore
    before_count = Course.objects.count()
    print(f"\n📊 Courses before: {before_count}")
    
    # Create a course
    try:
        course = Course.objects.create(
            title="دورة اختبار البرمجة",
            description="هذا كورس تجريبي لاختبار النظام",
            subject=subject,
            teacher=teacher_profile,
            course_type='recorded',
            level='beginner',
            price=100.00,
            currency='SAR',
            duration_minutes=120,
            status='published',
            objectives=['تعلم البرمجة', 'تطوير المهارات'],
            requirements=['حاسوب', 'اتصال بالإنترنت']
        )
        print(f"✅ Course created successfully!")
        print(f"   ID: {course.course_id}")
        print(f"   Title: {course.title}")
        print(f"   Teacher: {course.teacher.user.email}")
        print(f"   Status: {course.status}")
        print(f"   Price: {course.price} {course.currency}")
    except Exception as e:
        print(f"❌ Error creating course: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Count courses after
    after_count = Course.objects.count()
    print(f"\n📊 Courses after: {after_count}")
    print(f"✅ Difference: +{after_count - before_count}")
    
    # List all courses
    print(f"\n📚 All Courses in Database:")
    for c in Course.objects.all()[:10]:
        print(f"   - [{c.course_id}] {c.title} (Status: {c.status}, Teacher: {c.teacher.user.email})")
    
    print("\n" + "=" * 50)
    print("✅ Test completed successfully!")
    print ("=" * 50)

if __name__ == '__main__':
    test_course_creation()
