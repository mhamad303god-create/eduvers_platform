"""
Test script to verify lesson creation functionality
Run: python test_lesson_creation.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduverse.settings')
django.setup()

from courses.models import Course, CourseLesson
from accounts.models import TeacherProfile, User

print("=" * 70)
print("🧪 Testing Lesson Creation")
print("=" * 70)

# Find a course to add lesson to
try:
    # Get a teacher course
    teacher_profile = TeacherProfile.objects.first()
    if not teacher_profile:
        print("❌ No teacher found!")
        exit(1)
    
    teacher_user = teacher_profile.user
    print(f"✅ Using teacher: {teacher_user.email}")
    
    # Get a course
    course = Course.objects.filter(teacher=teacher_profile).first()
    if not course:
        print("❌ No course found for this teacher!")
        exit(1)
    
    print(f"✅ Found course: {course.title} (ID: {course.course_id})")
    
    # Count existing lessons
    existing_lessons = CourseLesson.objects.filter(course=course).count()
    print(f"📊 Existing lessons: {existing_lessons}")
    
    # Create a new lesson
    print("\n📝 Creating new lesson...")
    lesson = CourseLesson.objects.create(
        course=course,
        title="درس تجريبي - اختبار الحفظ",
        description="هذا درس تجريبي للتحقق من أن الدروس تحفظ في قاعدة البيانات",
        content="محتوى الدرس التجريبي",
        order_index=existing_lessons + 1,
        is_free=False,
        status='draft'
    )
    
    print(f"✅ Lesson created successfully!")
    print(f"   ID: {lesson.lesson_id}")
    print(f"   Title: {lesson.title}")
    print(f"   Course: {lesson.course.title}")
    print(f"   Order: {lesson.order_index}")
    print(f"   Status: {lesson.status}")
    
    # Verify it's in the database
    print("\n🔍 Verifying lesson in database...")
    saved_lesson = CourseLesson.objects.get(lesson_id=lesson.lesson_id)
    print(f"✅ Lesson verified in database!")
    print(f"   Retrieved: {saved_lesson.title}")
    
    # Count lessons again
    new_count = CourseLesson.objects.filter(course=course).count()
    print(f"\n📊 Total lessons now: {new_count}")
    print(f"   Change: +{new_count - existing_lessons}")
    
    print("\n" + "=" * 70)
    print(" SUCCESS! Lesson creation works correctly! ✅")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
