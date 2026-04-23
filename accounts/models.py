from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
import uuid
import json
import logging
logger = logging.getLogger(__name__)


from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(_('email address'), unique=True)
    username = models.CharField(_('username'), max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
            ('pending', 'Pending'),
        ],
        default='pending'
    )
    last_login_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.email

    def has_permission(self, permission):
        """Check if user has a specific permission"""
        try:
            user_roles = UserRole.objects.filter(user=self).select_related('role')
            for user_role in user_roles:
                if user_role.role.permissions.get(permission, False):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking permission {permission} for user {self.email}: {e}")
            return False

    def get_roles(self):
        """Get list of user's role names"""
        try:
            return list(UserRole.objects.filter(user=self).values_list('role__role_name', flat=True))
        except Exception as e:
            logger.error(f"Error getting roles for user {self.email}: {e}")
            return []

    def is_student(self):
        return 'student' in self.get_roles()

    def is_teacher(self):
        return 'teacher' in self.get_roles()

    def is_admin(self):
        return self.is_superuser or self.is_staff or 'admin' in self.get_roles() or 'super_admin' in self.get_roles()

    def is_super_admin(self):
        return self.is_superuser or 'super_admin' in self.get_roles()


class Role(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(
        max_length=20,
        choices=[
            ('super_admin', 'Super Admin'),
            ('admin', 'Admin'),
            ('teacher', 'Teacher'),
            ('student', 'Student'),
        ],
        unique=True
    )
    description = models.TextField(blank=True, null=True)
    permissions = models.JSONField(default=dict)

    def get_default_permissions(self):
        """Return default permissions for each role"""
        if self.role_name == 'super_admin':
            return {
                'can_manage_users': True,
                'can_manage_roles': True,
                'can_manage_courses': True,
                'can_manage_bookings': True,
                'can_manage_payments': True,
                'can_view_reports': True,
                'can_manage_system': True,
                'can_delete_data': True,
                'can_access_admin_panel': True,
            }
        elif self.role_name == 'admin':
            return {
                'can_manage_users': True,
                'can_manage_roles': False,
                'can_manage_courses': True,
                'can_manage_bookings': True,
                'can_manage_payments': True,
                'can_view_reports': True,
                'can_manage_system': False,
                'can_delete_data': False,
                'can_access_admin_panel': True,
            }
        elif self.role_name == 'teacher':
            return {
                'can_manage_users': False,
                'can_manage_roles': False,
                'can_manage_courses': True,  # Only their own courses
                'can_manage_bookings': True,  # Only their bookings
                'can_manage_payments': False,
                'can_view_reports': True,  # Only their reports
                'can_manage_system': False,
                'can_delete_data': False,
                'can_access_admin_panel': False,
            }
        elif self.role_name == 'student':
            return {
                'can_manage_users': False,
                'can_manage_roles': False,
                'can_manage_courses': False,
                'can_manage_bookings': True,  # Only their bookings
                'can_manage_payments': False,
                'can_view_reports': True,  # Only their progress
                'can_manage_system': False,
                'can_delete_data': False,
                'can_access_admin_panel': False,
            }
        return {}

    def save(self, *args, **kwargs):
        """Set default permissions if not set"""
        if not self.permissions:
            self.permissions = self.get_default_permissions()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Role')
        verbose_name_plural = _('Roles')

    def __str__(self):
        return self.get_role_name_display()


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_roles')

    class Meta:
        unique_together = ('user', 'role')
        verbose_name = _('User Role')
        verbose_name_plural = _('User Roles')

    def __str__(self):
        return f"{self.user.email} - {self.role.role_name}"


class StudentProfile(models.Model):
    student_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    grade_level = models.CharField(
        max_length=20,
        choices=[
            ('elementary', 'Elementary'),
            ('middle', 'Middle'),
            ('high', 'High'),
            ('university', 'University'),
            ('other', 'Other'),
        ],
        blank=True, null=True
    )
    grade = models.CharField(max_length=50, blank=True, null=True)
    school_name = models.CharField(max_length=255, blank=True, null=True)
    parent_name = models.CharField(max_length=255, blank=True, null=True)
    parent_phone = models.CharField(max_length=20, blank=True, null=True)
    parent_email = models.EmailField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female')],
        blank=True, null=True
    )
    learning_preferences = models.JSONField(default=dict)

    class Meta:
        verbose_name = _('Student Profile')
        verbose_name_plural = _('Student Profiles')

    def __str__(self):
        return f"Student: {self.user.email}"


class TeacherProfile(models.Model):
    teacher_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    subjects = models.JSONField(default=list, blank=True)  # List of subject IDs
    education = models.JSONField(default=dict, blank=True)
    experience_years = models.IntegerField(default=0)
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    verification_documents = models.JSONField(default=dict, blank=True)
    bank_account_info = models.JSONField(default=dict, blank=True)
    tax_info = models.JSONField(default=dict, blank=True)
    availability_settings = models.JSONField(default=dict, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        verbose_name = _('Teacher Profile')
        verbose_name_plural = _('Teacher Profiles')

    def __str__(self):
        return f"Teacher: {self.user.email}"
