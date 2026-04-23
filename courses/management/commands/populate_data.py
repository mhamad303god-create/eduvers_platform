from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, TeacherProfile
from courses.models import Course, Subject
from bookings.models import Booking
import random
from datetime import timedelta

class Command(BaseCommand):
    help = 'Populates the database with dummy data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating dummy data...')

        # Create Subjects
        subjects = ['Mathematics', 'Physics', 'Chemistry', 'English', 'Computer Science']
        subject_objs = []
        for sub_name in subjects:
            code = sub_name[:3].upper()
            subject, created = Subject.objects.get_or_create(
                subject_name=sub_name,
                defaults={'subject_code': code}
            )
            subject_objs.append(subject)
            if created:
                self.stdout.write(f'Created subject: {sub_name}')

        # Ensure Roles exist
        from accounts.models import Role, UserRole
        teacher_role, _ = Role.objects.get_or_create(role_name='teacher')

        # Create Teachers
        teachers = []
        for i in range(5):
            username = f'teacher{i}'
            email = f'teacher{i}@example.com'
            user, created = User.objects.get_or_create(username=username, email=email)
            if created:
                user.set_password('password123')
                user.save()
                # Assign Role
                UserRole.objects.get_or_create(user=user, role=teacher_role)
                TeacherProfile.objects.create(user=user, bio="Expert teacher", hourly_rate=50.00)
                self.stdout.write(f'Created teacher: {username}')
            
            if hasattr(user, 'teacherprofile'):
                teachers.append(user.teacherprofile)
            elif hasattr(user, 'teacher_profile'):
                 teachers.append(user.teacher_profile)

        # Create Courses
        for i in range(10):
            teacher = random.choice(teachers)
            subject = random.choice(subject_objs)
            title = f'{subject.subject_name} 10{i}'
            course, created = Course.objects.get_or_create(
                title=title,
                teacher=teacher,
                defaults={
                    'subject': subject,
                    'description': f'A comprehensive course on {subject.subject_name}.',
                    'price': random.randint(100, 500),
                    'level': 'beginner', # Adjust based on your choices
                    'duration_minutes': 60
                }
            )
            if created:
                self.stdout.write(f'Created course: {title}')

        self.stdout.write(self.style.SUCCESS('Successfully populated database'))
