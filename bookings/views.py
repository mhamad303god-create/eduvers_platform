from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.conf import settings
from accounts.decorators import student_required, teacher_required
from .models import TeacherAvailability, Booking
from .forms import TeacherAvailabilityForm, BookingForm
from accounts.models import TeacherProfile, StudentProfile
from notifications.models import Notification
from .live_sessions import build_jitsi_join_url, build_jitsi_room_name
from urllib.parse import urlsplit, urlunsplit


def _localhost_room_hint(request):
    host = request.get_host()
    hostname = host.split(":")[0]
    if hostname in {"localhost", "127.0.0.1", "::1"} or request.is_secure():
        return None
    parts = urlsplit(request.build_absolute_uri())
    port = f":{parts.port}" if parts.port else ""
    replacement_netloc = f"127.0.0.1{port}"
    return urlunsplit((parts.scheme, replacement_netloc, parts.path, parts.query, parts.fragment))


def _ensure_booking_meeting(booking):
    if booking.meeting_url and booking.meeting_id:
        return

    room_name = build_jitsi_room_name(booking)
    booking.meeting_id = room_name
    booking.meeting_url = build_jitsi_join_url(room_name)
    booking.meeting_provider = "external"
    booking.save(update_fields=["meeting_id", "meeting_url", "meeting_provider", "updated_at"])


def _build_booking_live_context(request, booking, role_label, back_url):
    return {
        "booking": booking,
        "role_label": role_label,
        "back_url": back_url,
        "call_room_name": booking.meeting_id,
        "call_ws_url": f"/ws/live-classrooms/{booking.meeting_id}/",
        "current_user_id": request.user.id,
        "peer_name": (
            booking.teacher.user.get_full_name() or booking.teacher.user.email
            if request.user == booking.student.user else booking.student.user.get_full_name() or booking.student.user.email
        ),
        "peer_role": "المعلم" if request.user == booking.student.user else "الطالب",
        "localhost_room_hint_url": _localhost_room_hint(request),
        "webrtc_ice_servers": getattr(settings, 'WEBRTC_ICE_SERVERS', []),
    }


def _create_booking_notification(user, title, content, booking):
    Notification.objects.create(
        user=user,
        type="booking",
        title=title,
        content=content,
        data={
            "booking_id": booking.booking_id,
            "scheduled_start": booking.scheduled_start.isoformat(),
            "meeting_url": booking.meeting_url or "",
        },
    )

# Teacher availability management
@teacher_required
def teacher_availability_list(request):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    availabilities = TeacherAvailability.objects.filter(teacher=teacher_profile)
    return render(request, 'bookings/teacher_availability_list.html', {'availabilities': availabilities})

@teacher_required
def teacher_availability_create(request):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    if request.method == 'POST':
        form = TeacherAvailabilityForm(request.POST)
        if form.is_valid():
            availability = form.save(commit=False)
            availability.teacher = teacher_profile
            availability.save()
            messages.success(request, 'تم إنشاء الوقت المتاح بنجاح! ✅')
            return redirect('bookings:teacher_availability_list')
        else:
            messages.error(request, 'يرجى تصحيح الأخطاء في النموذج.')
    else:
        form = TeacherAvailabilityForm()
    return render(request, 'bookings/teacher_availability_form.html', {'form': form, 'action': 'Create'})

@teacher_required
def teacher_availability_edit(request, availability_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    availability = get_object_or_404(TeacherAvailability, availability_id=availability_id, teacher=teacher_profile)
    if request.method == 'POST':
        form = TeacherAvailabilityForm(request.POST, instance=availability)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الوقت المتاح بنجاح! ✅')
            return redirect('bookings:teacher_availability_list')
        else:
            messages.error(request, 'يرجى تصحيح الأخطاء في النموذج.')
    else:
        form = TeacherAvailabilityForm(instance=availability)
    return render(request, 'bookings/teacher_availability_form.html', {'form': form, 'action': 'Edit'})

@teacher_required
def teacher_availability_delete(request, availability_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    availability = get_object_or_404(TeacherAvailability, availability_id=availability_id, teacher=teacher_profile)
    if request.method == 'POST':
        availability.delete()
        messages.success(request, 'Availability deleted successfully.')
        return redirect('bookings:teacher_availability_list')
    return render(request, 'bookings/teacher_availability_confirm_delete.html', {'availability': availability})

# Booking management for teachers
@teacher_required
def teacher_booking_list(request):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    bookings = Booking.objects.filter(teacher=teacher_profile).order_by('-scheduled_start', '-created_at')
    context = {
        'bookings': bookings,
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'active_bookings': bookings.filter(status__in=['confirmed', 'in_progress']).count(),
    }
    return render(request, 'bookings/teacher_booking_list.html', context)

@teacher_required
def teacher_booking_detail(request, booking_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, teacher=teacher_profile)
    return render(request, 'bookings/teacher_booking_detail.html', {'booking': booking})

@teacher_required
def confirm_booking(request, booking_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, teacher=teacher_profile)
    if booking.status == 'pending':
        booking.status = 'confirmed'
        booking.save()
        _ensure_booking_meeting(booking)
        start_label = timezone.localtime(booking.scheduled_start).strftime("%Y-%m-%d %I:%M %p")
        _create_booking_notification(
            booking.student.user,
            "تم تأكيد الحجز",
            f"تم تأكيد جلستك مع {booking.teacher.user.get_full_name() or booking.teacher.user.email} بتاريخ {start_label}.",
            booking,
        )
        _create_booking_notification(
            booking.teacher.user,
            "الجلسة جاهزة",
            f"تم تجهيز رابط الفصل المباشر لجلسة {start_label}.",
            booking,
        )
        messages.success(request, 'Booking confirmed.')
    return redirect('bookings:teacher_booking_detail', booking_id=booking_id)

@teacher_required
def cancel_booking(request, booking_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, teacher=teacher_profile)
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '')
        booking.status = 'cancelled'
        booking.cancellation_reason = reason
        booking.save()
        messages.success(request, 'Booking cancelled.')
        return redirect('bookings:teacher_booking_detail', booking_id=booking_id)
    return render(request, 'bookings/cancel_booking.html', {'booking': booking})

@teacher_required
def complete_booking(request, booking_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, teacher=teacher_profile)
    if booking.status == 'confirmed':
        booking.status = 'completed'
        booking.actual_end = timezone.now()
        booking.save()
        messages.success(request, 'Booking completed.')
    return redirect('bookings:teacher_booking_detail', booking_id=booking_id)

# Student booking views
@student_required
def student_teacher_list(request):
    teachers = TeacherProfile.objects.all()
    return render(request, 'bookings/student_teacher_list.html', {'teachers': teachers})

@student_required
def teacher_availability_view(request, teacher_id):
    teacher = get_object_or_404(TeacherProfile, pk=teacher_id)
    availabilities = TeacherAvailability.objects.filter(teacher=teacher, status='available').order_by('specific_date', 'day_of_week', 'start_time')
    return render(request, 'bookings/teacher_availability_view.html', {'teacher': teacher, 'availabilities': availabilities})

@student_required
def student_book_session(request):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    if request.method == 'POST':
        form = BookingForm(request.POST, student=student_profile)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.student = student_profile
            # Assume teacher is selected somehow, perhaps from previous page
            teacher_id = request.POST.get('teacher_id')
            if not teacher_id:
                messages.error(request, "حدث خطأ: لم يتم تحديد المعلم.")
                return render(request, 'bookings/student_book_session.html', {
                    'form': form,
                    'teacher_id': teacher_id
                })

            booking.teacher = get_object_or_404(TeacherProfile, pk=teacher_id)
            booking.save()
            messages.success(request, 'تم إرسال طلب الحجز بنجاح.')
            return redirect('bookings:student_booking_list')
    else:
        teacher_id = request.GET.get('teacher_id')
        teacher = None
        if teacher_id:
            teacher = get_object_or_404(TeacherProfile, pk=teacher_id)
        form = BookingForm(student=student_profile, teacher=teacher)
        
    return render(request, 'bookings/student_book_session.html', {
        'form': form, 
        'teacher': teacher if 'teacher' in locals() else None,
        'teacher_id': teacher_id if 'teacher_id' in locals() else request.POST.get('teacher_id')
    })

@student_required
def student_booking_list(request):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    bookings = Booking.objects.filter(student=student_profile).order_by('-scheduled_start', '-created_at')
    context = {
        'bookings': bookings,
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'active_bookings': bookings.filter(status__in=['confirmed', 'in_progress']).count(),
    }
    return render(request, 'bookings/student_booking_list.html', context)

@student_required
def student_booking_detail(request, booking_id):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, student=student_profile)
    if booking.status == "confirmed":
        _ensure_booking_meeting(booking)
    return render(request, 'bookings/student_booking_detail.html', {'booking': booking})

@student_required
def student_cancel_booking(request, booking_id):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, student=student_profile)
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '')
        booking.status = 'cancelled'
        booking.cancellation_reason = reason
        booking.save()
        messages.success(request, 'Booking cancelled.')
        return redirect('bookings:student_booking_detail', booking_id=booking_id)
    return render(request, 'bookings/cancel_booking.html', {'booking': booking})


@student_required
def student_live_classroom(request, booking_id):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, student=student_profile)
    if booking.status not in ["confirmed", "in_progress", "completed"]:
        messages.error(request, "الفصل المباشر غير متاح قبل تأكيد الحجز.")
        return redirect("bookings:student_booking_detail", booking_id=booking.booking_id)

    _ensure_booking_meeting(booking)
    return render(
        request,
        "bookings/live_classroom.html",
        _build_booking_live_context(
            request,
            booking,
            "الطالب",
            reverse("bookings:student_booking_detail", args=[booking.booking_id]),
        ),
    )


@teacher_required
def teacher_live_classroom(request, booking_id):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    booking = get_object_or_404(Booking, booking_id=booking_id, teacher=teacher_profile)
    if booking.status not in ["confirmed", "in_progress", "completed"]:
        messages.error(request, "الفصل المباشر غير متاح قبل تأكيد الحجز.")
        return redirect("bookings:teacher_booking_detail", booking_id=booking.booking_id)

    _ensure_booking_meeting(booking)
    return render(
        request,
        "bookings/live_classroom.html",
        _build_booking_live_context(
            request,
            booking,
            "المعلم",
            reverse("bookings:teacher_booking_detail", args=[booking.booking_id]),
        ),
    )


@login_required
def booking_live_room_entry(request, room_name):
    booking = get_object_or_404(Booking.objects.select_related("student__user", "teacher__user"), meeting_id=room_name)
    if request.user == booking.student.user:
        return redirect("bookings:student_live_classroom", booking_id=booking.booking_id)
    if request.user == booking.teacher.user:
        return redirect("bookings:teacher_live_classroom", booking_id=booking.booking_id)
    messages.error(request, "لا يمكنك الوصول إلى هذا الفصل المباشر.")
    return redirect("accounts:dashboard_redirect")
