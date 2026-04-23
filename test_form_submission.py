"""
Debug script - Actually call the course_create view with POST data
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduverse.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from accounts.models import TeacherProfile
from courses.models import Subject

User = get_user_model()

def test_course_form_submission():
    print("=" * 60)
    print("🧪 Testing Course Form Submission via POST")
    print("=" * 60)
    
    # Get a teacher user
    teacher_user = User.objects.filter(userrole__role__role_name='teacher').first()
    if not teacher_user:
        print("❌ No teacher user found!")
        return
    
    print(f"✅ Using teacher: {teacher_user.email}")
    
    # Ensure teacher profile exists
    teacher_profile, created = TeacherProfile.objects.get_or_create(
        user=teacher_user,
        defaults={'bio': 'Test', 'hourly_rate': 100}
    )
    
    # Get a subject
    subject = Subject.objects.first()
    if not subject:
        subject = Subject.objects.create(
            subject_name='Test Subject',
            subject_code='TEST'
        )
    
    # Create client and login
    client = Client()
    client.force_login(teacher_user)
    
    # Prepare POST data (simulating form submission)
    post_data = {
        'title': 'كورس اختبار من الفورم',
        'description': 'هذا وصف الكورس التجريبي',
        'subject': subject.subject_id,
        'course_type': 'recorded',
        'level': 'beginner',
        'price': '150.00',
        'currency': 'SAR',
        'duration_minutes': '90',
        'status': 'published',
        'objectives': 'هدف 1\\nهدف 2\\nهدف 3',
        'requirements': 'متطلب 1\\nمتطلب 2',
    }
    
    print(f"\n📝 POST Data:")
    for key, value in post_data.items():
        print(f"   {key}: {value}")
    
    # Submit form
    print(f"\n🚀 Submitting form to /courses/create/...")
    response = client.post('/courses/create/', post_data, follow=True)
    
    print(f"\n📊 Response Status: {response.status_code}")
    print(f"📊 Redirect Chain: {response.redirect_chain}")
    
    # Check messages
    messages = list(get_messages(response.wsgi_request))
    print(f"\n💬 Messages:")
    for message in messages:
        print(f"   [{message.level_tag}] {message}")
    
    # Check if course was created
    from courses.models import Course
    latest_course = Course.objects.filter(title='كورس اختبار من الفورم').first()
    
    if latest_course:
        print(f"\n✅ SUCCESS! Course created:")
        print(f"   ID: {latest_course.course_id}")
        print(f"   Title: {latest_course.title}")
        print(f"   Status: {latest_course.status}")
        print(f"   Teacher: {latest_course.teacher.user.email}")
    else:
        print(f"\n❌ FAILED! Course NOT found in database")
        print(f"\n📄 Response content preview:")
        content = response.content.decode('utf-8')[:1000]
        print(content)
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    test_course_form_submission()

