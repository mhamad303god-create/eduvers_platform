from functools import wraps
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from .models import UserRole


def role_required(*allowed_roles):
    """
    Decorator to check if user has one of the allowed roles.
    Redirects to appropriate dashboard if user doesn't have permission.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseRedirect(reverse('accounts:login'))

            user = request.user
            # Get roles from model method which now handles caching/logic better if we improved it, 
            # but here we use the helper we created/verified
            user_roles = user.get_roles()

            # Superuser/Staff override for Admin pages
            if (user.is_superuser or user.is_staff) and ('admin' in allowed_roles or 'super_admin' in allowed_roles):
                return view_func(request, *args, **kwargs)

            # Normal Check
            if any(role in allowed_roles for role in user_roles):
                return view_func(request, *args, **kwargs)
            
            # Access Denied - Redirect based on ACTUAL role
            messages.error(request, "ليس لديك صلاحية للوصول إلى هذه الصفحة.")
            
            if user.is_superuser or user.is_staff:
                return HttpResponseRedirect(reverse('accounts:admin_dashboard'))
                
            if 'admin' in user_roles:
                return HttpResponseRedirect(reverse('accounts:admin_dashboard'))
            elif 'teacher' in user_roles:
                return HttpResponseRedirect(reverse('accounts:teacher_dashboard'))
            elif 'student' in user_roles:
                return HttpResponseRedirect(reverse('accounts:student_dashboard'))
            else:
                return HttpResponseRedirect(reverse('home'))

        return _wrapped_view
    return decorator


def permission_required(permission):
    """
    Decorator to check if user has a specific permission.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseRedirect(reverse('accounts:login'))

            if not request.user.has_permission(permission):
                messages.error(request, "ليس لديك صلاحية للوصول إلى هذه الصفحة.")
                # Redirect to user's dashboard
                user_roles = request.user.get_roles()
                if 'student' in user_roles:
                    return HttpResponseRedirect(reverse('accounts:student_dashboard'))
                elif 'teacher' in user_roles:
                    return HttpResponseRedirect(reverse('accounts:teacher_dashboard'))
                elif 'admin' in user_roles or 'super_admin' in user_roles:
                    return HttpResponseRedirect(reverse('accounts:admin_dashboard'))
                else:
                    return HttpResponseRedirect(reverse('home'))

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def student_required(view_func):
    """Decorator for student-only views"""
    return role_required('student')(view_func)


def teacher_required(view_func):
    """Decorator for teacher-only views"""
    return role_required('teacher')(view_func)


def admin_required(view_func):
    """Decorator for admin-only views"""
    return role_required('admin', 'super_admin')(view_func)


def super_admin_required(view_func):
    """Decorator for super admin-only views"""
    return role_required('super_admin')(view_func)


# Specific permission decorators
def can_manage_users(view_func):
    """Require permission to manage users"""
    return permission_required('can_manage_users')(view_func)


def can_manage_courses(view_func):
    """Require permission to manage courses"""
    return permission_required('can_manage_courses')(view_func)


def can_manage_bookings(view_func):
    """Require permission to manage bookings"""
    return permission_required('can_manage_bookings')(view_func)


def can_view_reports(view_func):
    """Require permission to view reports"""
    return permission_required('can_view_reports')(view_func)


def can_access_admin_panel(view_func):
    """Require permission to access admin panel"""
    return permission_required('can_access_admin_panel')(view_func)