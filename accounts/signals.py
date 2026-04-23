from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from .models import StudentProfile, UserRole, Role

User = get_user_model()

@receiver(user_signed_up)
def social_account_signup(request, user, **kwargs):
    """
    Signal handler to create a Student Profile and assign role 
    when a user signs up via Social Auth (Google/Facebook).
    """
    try:
        # Default to Student role for social signups
        student_role, _ = Role.objects.get_or_create(role_name='student')
        UserRole.objects.get_or_create(user=user, role=student_role)

        # Create Student Profile if it doesn't exist
        if not hasattr(user, 'studentprofile'):
            StudentProfile.objects.create(
                user=user,
                grade_level='other', # Default
                learning_preferences={}
            )
            print(f"Created Student Profile for Social User: {user.email}")
            
    except Exception as e:
        print(f"Error in social_account_signup signal: {e}")
