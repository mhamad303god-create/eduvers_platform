from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from django.core.cache import cache
import logging
from .forms import CustomUserCreationForm, CustomAuthenticationForm, StudentProfileForm, TeacherProfileForm
from .models import UserRole, StudentProfile, TeacherProfile, Role
from .decorators import role_required, student_required, teacher_required, admin_required
from bookings.models import Booking
from courses.models import Course
from assessments.models import Assessment, AssessmentAttempt
from notifications.forms import ContactRequestForm, NewsletterSubscriptionForm
from notifications.models import ContactRequest, Message, Notification, NewsletterSubscription
from django.contrib.auth import get_user_model

User = get_user_model()

logger = logging.getLogger(__name__)


def home(request):
    """Home page view that redirects authenticated users to their dashboard"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == "POST" and request.POST.get("form_type") == "newsletter":
        newsletter_form = NewsletterSubscriptionForm(request.POST)
        if newsletter_form.is_valid():
            email = newsletter_form.cleaned_data["email"].strip().lower()
            defaults = {
                "is_active": True,
                "full_name": request.user.get_full_name().strip() if request.user.is_authenticated else "",
                "user": request.user if request.user.is_authenticated else None,
            }
            subscription, created = NewsletterSubscription.objects.update_or_create(
                email=email,
                defaults=defaults,
            )
            if created:
                messages.success(request, "تم الاشتراك في النشرة البريدية بنجاح.")
            else:
                messages.info(request, "هذا البريد مشترك بالفعل، وتم تحديث حالته.")
            return redirect(request.META.get("HTTP_REFERER") or reverse("home"))
        messages.error(request, "أدخل بريداً إلكترونياً صحيحاً للاشتراك في النشرة البريدية.")
        return redirect(request.META.get("HTTP_REFERER") or reverse("home"))

    if request.method == "POST":
        form = ContactRequestForm(request.POST)
        if form.is_valid():
            contact_request = form.save(commit=False)
            if request.user.is_authenticated:
                contact_request.sender = request.user
            contact_request.save()

            admin_users = User.objects.filter(
                Q(is_staff=True)
                | Q(is_superuser=True)
                | Q(userrole__role__role_name__in=["admin", "super_admin"])
            ).distinct()

            notification_content = (
                f"رسالة جديدة من {contact_request.full_name} "
                f"({contact_request.email}) بعنوان: {contact_request.subject}"
            )

            for admin_user in admin_users:
                Notification.objects.create(
                    user=admin_user,
                    type="message",
                    title="رسالة تواصل جديدة",
                    content=notification_content,
                    data={
                        "contact_request_id": contact_request.contact_id,
                        "sender_name": contact_request.full_name,
                        "sender_email": contact_request.email,
                        "subject": contact_request.subject,
                        "message": contact_request.message,
                    },
                )

                if contact_request.sender and admin_user != contact_request.sender:
                    Message.objects.create(
                        sender=contact_request.sender,
                        receiver=admin_user,
                        subject=contact_request.subject,
                        content=(
                            f"الاسم: {contact_request.full_name}\n"
                            f"البريد الإلكتروني: {contact_request.email}\n\n"
                            f"{contact_request.message}"
                        ),
                        attachment_urls=[],
                    )

            messages.success(request, "تم إرسال رسالتك بنجاح، وستصل إلى الإدارة على شكل إشعار.")
            return redirect(f"{reverse('home')}#contact")
        messages.error(request, "تعذر إرسال الرسالة. تأكد من تعبئة جميع الحقول بشكل صحيح.")
    else:
        form = ContactRequestForm()

    return render(request, 'index.html', {"contact_form": form, "newsletter_form": NewsletterSubscriptionForm()})


@login_required
def dashboard_redirect(request):
    """
    Central dispatch view to send users to their correct dashboard.
    Also Self-Heals accounts that are missing Roles or Profiles.
    """
    user = request.user
    
    # 0. Check Superuser/Admin First (Priority)
    if user.is_superuser or user.is_staff:
        # SUPERUSER CLEANUP: Remove any confused roles that might have been added by mistake
        UserRole.objects.filter(user=user).delete()
        return redirect('accounts:admin_dashboard')

    # 1. Role Hierarchy Enforcement (Fix conflicting roles)
    user_roles = user.get_roles()
    
    if 'admin' in user_roles or 'super_admin' in user_roles:
        # If Admin, shouldn't be Teacher or Student
        conflict_roles = Role.objects.filter(role_name__in=['teacher', 'student'])
        UserRole.objects.filter(user=user, role__in=conflict_roles).delete()
        
    elif 'teacher' in user_roles:
        # If Teacher, shouldn't be Student
        conflict_roles = Role.objects.filter(role_name='student')
        UserRole.objects.filter(user=user, role__in=conflict_roles).delete()

    # 2. Check & Fix Role (If no roles at all)
    if not user.get_roles():
        logger.warning(f"User {user.email} has no role. Self-healing to Student.")
        try:
            student_role, _ = Role.objects.get_or_create(role_name='student')
            UserRole.objects.get_or_create(user=user, role=student_role)
        except Exception as e:
            logger.error(f"Failed to auto-assign role: {e}")

    # 3. Check & Fix Profile
    if user.is_student() and not hasattr(user, 'studentprofile'):
        logger.warning(f"User {user.email} is student but missing profile. Creating one.")
        StudentProfile.objects.create(user=user, grade_level='other', learning_preferences={})
        
    # 4. Dispatch
    if user.is_student():
        return redirect('accounts:student_dashboard')
    elif user.is_teacher():
        return redirect('accounts:teacher_dashboard')
    elif user.is_admin():
        return redirect('accounts:admin_dashboard')
    
    # Fallback
    messages.error(request, "لم يتم تحديد صلاحيات لهذا الحساب. يرجى التواصل مع الدعم.")
    return redirect('home')


def login_view(request):
    """Handle standard user login"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                
                # Check for 'next' parameter
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                
                return redirect('accounts:dashboard_redirect')
            else:
                messages.error(request, "البريد الإلكتروني أو كلمة المرور غير صحيحة.")
        else:
            messages.error(request, "الرجاء التأكد من البيانات المدخلة.")
    else:
        form = CustomAuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"تم إنشاء الحساب بنجاح! مرحباً بك يا {user.first_name}")
                return redirect('accounts:dashboard_redirect')
            except Exception as e:
                logger.error(f"Registration Error: {e}")
                messages.error(request, f"حدث خطأ أثناء حفظ البيانات: {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})


def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.info(request, "تم تسجيل الخروج بنجاح.")
    return redirect('accounts:login') 


@login_required
def profile_view(request):
    """User profile management"""
    user_roles = UserRole.objects.filter(user=request.user).values_list('role__role_name', flat=True)

    if 'student' in user_roles:
        profile = get_object_or_404(StudentProfile, user=request.user)
        ProfileFormClass = StudentProfileForm
    elif 'teacher' in user_roles:
        profile = get_object_or_404(TeacherProfile, user=request.user)
        ProfileFormClass = TeacherProfileForm
    else:
        # Auto-fix if profile is missing for some reason
        return redirect('accounts:dashboard_redirect')

    from .forms import UserUpdateForm # Import here to avoid circular intent if any

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        # Pass request.FILES to profile_form too if needed, though mostly text
        profile_form = ProfileFormClass(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save()
            
            # Force refresh session/user to ensure templates see new data immediately
            # update_session_auth_hash(request, user) # Not needed unless password changes
            
            messages.success(request, "تم تحديث الملف الشخصي بنجاح.")
            return redirect('accounts:profile')
        else:
            # Debugging
            if user_form.errors:
                messages.error(request, f"خطأ في بيانات المستخدم: {user_form.errors}")
            if profile_form.errors:
                messages.error(request, f"خطأ في الملف الشخصي: {profile_form.errors}")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileFormClass(instance=profile)

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'profile': profile,
        'user_roles': user_roles
    })


@student_required
def student_dashboard(request):
    """Student dashboard view"""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        return redirect('accounts:dashboard_redirect') # Let the redirect view fix it

    cache_key = f"student_dashboard_metrics:{request.user.id}"
    cached_metrics = cache.get(cache_key) or {}

    # Get upcoming sessions
    upcoming_sessions = Booking.objects.filter(
        student=student_profile,
        scheduled_start__gte=timezone.now(),
        status__in=['confirmed', 'pending']
    ).select_related('teacher__user', 'course').order_by('scheduled_start')[:5]

    # Get recent assessment attempts
    recent_assessments = AssessmentAttempt.objects.filter(
        student=student_profile
    ).select_related('assessment__subject').order_by('-created_at')[:5]

    # Calculate stats
    total_sessions = cached_metrics.get("total_sessions")
    completed_sessions = cached_metrics.get("completed_sessions")
    if total_sessions is None or completed_sessions is None:
        total_sessions = Booking.objects.filter(student=student_profile).count()
        completed_sessions = Booking.objects.filter(
            student=student_profile,
            status='completed'
        ).count()
        cache.set(
            cache_key,
            {"total_sessions": total_sessions, "completed_sessions": completed_sessions},
            60,
        )

    # Get latest courses
    latest_courses = Course.objects.filter(
        status='published'
    ).select_related('teacher__user', 'subject').annotate(
        published_lessons_count=Count('courselesson', filter=Q(courselesson__status='published'), distinct=True)
    ).distinct().order_by('-created_at', '-course_id')[:6]

    context = {
        'upcoming_sessions': upcoming_sessions,
        'recent_assessments': recent_assessments,
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'progress_percentage': (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
        'latest_courses': latest_courses,
    }

    return render(request, 'accounts/student_dashboard.html', context)


@teacher_required
def teacher_dashboard(request):
    """Teacher dashboard view"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        return redirect('accounts:dashboard_redirect')

    cache_key = f"teacher_dashboard_metrics:{request.user.id}"
    cached_metrics = cache.get(cache_key) or {}

    # Get teacher's courses count
    total_courses = cached_metrics.get("total_courses")
    total_students = cached_metrics.get("total_students")
    total_bookings = cached_metrics.get("total_bookings")
    completed_sessions = cached_metrics.get("completed_sessions")
    if None in {total_courses, total_students, total_bookings, completed_sessions}:
        total_courses = Course.objects.filter(teacher=teacher_profile).count()
        total_students = Booking.objects.filter(teacher=teacher_profile).values('student').distinct().count()
        total_bookings = Booking.objects.filter(teacher=teacher_profile).count()
        completed_sessions = Booking.objects.filter(
            teacher=teacher_profile,
            status='completed'
        ).count()
        cache.set(
            cache_key,
            {
                "total_courses": total_courses,
                "total_students": total_students,
                "total_bookings": total_bookings,
                "completed_sessions": completed_sessions,
            },
            60,
        )

    # Get upcoming bookings
    upcoming_bookings = Booking.objects.filter(
        teacher=teacher_profile,
        scheduled_start__gte=timezone.now(),
        status__in=['confirmed', 'pending']
    ).select_related('student__user', 'course').order_by('scheduled_start')[:5]

    # Get courses
    courses = Course.objects.filter(teacher=teacher_profile).select_related('subject').order_by('-created_at')[:5]

    context = {
        'upcoming_bookings': upcoming_bookings,
        'courses': courses,
        'total_bookings': total_bookings,
        'completed_sessions': completed_sessions,
        'total_students': total_students,
        'total_courses': total_courses,
    }

    return render(request, 'accounts/teacher_dashboard.html', context)


@admin_required
def admin_dashboard(request):
    """Admin dashboard view"""
    # Get user statistics
    total_users = UserRole.objects.values('role__role_name').annotate(count=Count('user')).order_by('role__role_name')

    # Get recent bookings
    recent_bookings = Booking.objects.select_related(
        'student__user', 'teacher__user', 'course'
    ).order_by('-created_at')[:10]

    # Get system stats
    total_students = StudentProfile.objects.count()
    total_teachers = TeacherProfile.objects.count()
    total_bookings = Booking.objects.count()
    total_bookings = Booking.objects.count()
    active_bookings = Booking.objects.filter(status__in=['confirmed', 'in_progress']).count()

    # Get recent users with their primary role
    recent_users = User.objects.prefetch_related('userrole_set__role').order_by('-date_joined')[:5]
    recent_users_data = []
    for user in recent_users:
        roles = user.get_roles()
        if 'teacher' in roles:
            primary_role = 'teacher'
        elif 'student' in roles:
            primary_role = 'student'
        elif 'admin' in roles or 'super_admin' in roles or user.is_staff:
            primary_role = 'admin'
        else:
            primary_role = 'unknown'
        recent_users_data.append({
            'user': user,
            'role': primary_role,
        })

    recent_notifications = Notification.objects.filter(user=request.user).order_by("-created_at")[:5]
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).count()
    recent_admin_messages = Message.objects.filter(
        receiver=request.user,
        deleted_by_receiver=False,
    ).order_by("-created_at")[:5]
    unread_messages_count = Message.objects.filter(
        receiver=request.user,
        is_read=False,
        deleted_by_receiver=False,
    ).count()
    recent_contact_requests = ContactRequest.objects.all()[:5]
    new_contact_requests_count = ContactRequest.objects.filter(is_read=False).count()

    context = {
        'total_users': total_users,
        'recent_bookings': recent_bookings,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_bookings': total_bookings,
        'total_bookings': total_bookings,
        'active_bookings': active_bookings,
        'recent_users': recent_users_data,
        'recent_notifications': recent_notifications,
        'unread_notifications_count': unread_notifications_count,
        'recent_admin_messages': recent_admin_messages,
        'unread_messages_count': unread_messages_count,
        'recent_contact_requests': recent_contact_requests,
        'new_contact_requests_count': new_contact_requests_count,
    }

    return render(request, 'accounts/admin_dashboard.html', context)


# API Views

def api_user_profile(request, user_id):
    """API endpoint to get user profile data"""
    try:
        user = User.objects.select_related('studentprofile', 'teacherprofile').get(id=user_id)
        data = {
            'id': user.id,
            'uuid': str(user.uuid),
            'email': user.email,
            'full_name': f"{user.first_name} {user.last_name}",
            'phone': user.phone,
            'avatar_url': user.avatar.url if user.avatar else None,
            'status': user.status,
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }

        # Add profile-specific data
        if hasattr(user, 'studentprofile'):
            data['profile_type'] = 'student'
            data['grade_level'] = user.studentprofile.grade_level
            data['school_name'] = user.studentprofile.school_name
        elif hasattr(user, 'teacherprofile'):
            data['profile_type'] = 'teacher'
            data['bio'] = user.teacherprofile.bio
            data['hourly_rate'] = str(user.teacherprofile.hourly_rate)

        return JsonResponse(data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@admin_required
def admin_users_list(request, role_filter):
    """List users by role for admin with edit/delete actions."""
    valid_roles = {'student', 'teacher'}
    if role_filter not in valid_roles:
        messages.error(request, "نوع القائمة غير صالح.")
        return redirect('accounts:admin_dashboard')

    users = User.objects.filter(userrole__role__role_name=role_filter).distinct().order_by('-date_joined')
    users_data = []
    for user in users:
        users_data.append({
            'user': user,
            'roles': user.get_roles(),
            'password_hash': user.password,
        })

    return render(request, 'accounts/admin_user_list.html', {
        'users_data': users_data,
        'role_filter': role_filter,
        'title': 'قائمة الطلاب' if role_filter == 'student' else 'قائمة المعلمين',
    })


@admin_required
@require_POST
def admin_user_delete(request, user_id):
    """Delete a user from admin dashboard list."""
    user_to_delete = get_object_or_404(User, id=user_id)
    if user_to_delete == request.user:
        messages.error(request, "لا يمكنك حذف حسابك الحالي.")
        return redirect('accounts:admin_dashboard')
    if user_to_delete.is_superuser:
        messages.error(request, "لا يمكن حذف حساب المدير الأعلى.")
        return redirect('accounts:admin_dashboard')

    user_to_delete.delete()
    messages.success(request, "تم حذف المستخدم بنجاح.")
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer or 'accounts:admin_dashboard')
