"""
Test script to verify lesson form submission
Run: python test_lesson_form.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduverse.settings')
django.setup()

from django.test import Client
from courses.models import Course, CourseLesson
from accounts.models import TeacherProfile, User

print("=" * 70)
print("🧪 Testing Lesson Form Submission")
print("=" * 70)

# Setup
client = Client()

try:
    # Get a teacher
    teacher_profile = TeacherProfile.objects.first()
    if not teacher_profile:
        print("❌ No teacher found!")
        exit(1)
    
    teacher_user = teacher_profile.user
    print(f"✅ Using teacher: {teacher_user.email}")
    
    # Get their course
    course = Course.objects.filter(teacher=teacher_profile).first()
    if not course:
        print("❌ No course found!")
        exit(1)
    
    print(f"✅ Found course: {course.title} (ID: {course.course_id})")
    
    # Login as teacher
    client.force_login(teacher_user)
    print(f"✅ Logged in as teacher")
    
    # Count existing lessons
    before_count = CourseLesson.objects.filter(course=course).count()
    print(f"📊 Lessons before: {before_count}")
    
    # Prepare form data
    form_data = {
        'title': 'درس اختبار من Form',
        'description': 'هذا درس تجريبي عبر POST request',
        'content': 'محتوى الدرس التجريبي',
        'order_index': before_count + 1,
        'is_free': False,
        'status': 'draft'
    }
    
    print("\n📝 Form Data:")
    for key, value in form_data.items():
        print(f"   {key}: {value}")
    
    # Submit form
    print(f"\n🚀 Submitting form to /courses/{course.course_id}/lessons/create/...")
    response = client.post(
        f'/courses/{course.course_id}/lessons/create/',
        data=form_data,
        follow=True
    )
    
    print(f"📊 Response Status: {response.status_code}")
    
    if response.redirect_chain:
        print(f"📊 Redirect Chain: {response.redirect_chain}")
    
    # Check for messages
    if hasattr(response, 'context') and response.context and 'messages' in response.context:
        messages = list(response.context['messages'])
        if messages:
            print("\n💬 Messages:")
            for message in messages:
                print(f"   [{message.tags}] {message.message}")
    
    # Count lessons after
    after_count = CourseLesson.objects.filter(course=course).count()
    print(f"\n📊 Lessons after: {after_count}")
    print(f"   Change: +{after_count - before_count}")
    
    if after_count > before_count:
        # Get the newest lesson
        newest_lesson = CourseLesson.objects.filter(course=course).order_by('-lesson_id').first()
        print(f"\n✅ SUCCESS! Lesson created:")
        print(f"   ID: {newest_lesson.lesson_id}")
        print(f"   Title: {newest_lesson.title}")
        print(f"   Course: {newest_lesson.course.title}")
        print(f"   Status: {newest_lesson.status}")
    else:
        print("\n❌ FAILED! Lesson was not created!")
        
        # Check for form errors in response
        if hasattr(response, 'context') and response.context and 'form' in response.context:
            form = response.context['form']
            if form.errors:
                print("\n📋 Form Errors:")
                for field, errors in form.errors.items():
                    print(f"   {field}: {errors}")
    
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
