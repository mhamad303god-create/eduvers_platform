from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Max, Prefetch
from django.db import models, transaction
from django.http import FileResponse, Http404, JsonResponse
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from asgiref.sync import async_to_sync
from accounts.decorators import role_required, student_required, teacher_required, permission_required, can_manage_courses
from accounts.models import UserRole, StudentProfile, TeacherProfile
from .models import Course, CourseLesson, Enrollment, LessonProgress, Subject
from .forms import CourseForm, CourseLessonForm, CourseFilterForm
from .search import CourseSearchEngine, TeacherSearchEngine, RecommendationEngine
from .analytics import StudentAnalytics, TeacherAnalytics, AdminAnalytics
import base64
import binascii
import json
import os
import re
import shutil
import tempfile
import zipfile
from math import ceil


def _add_form_errors_as_notifications(request, form):
    """Push form errors as readable toast messages."""
    for field_name, error_list in form.errors.items():
        if field_name == '__all__':
            label = "النموذج"
        else:
            label = form.fields.get(field_name).label if field_name in form.fields else field_name
        for error in error_list:
            messages.error(request, f"{label}: {error}")


def _broadcast_course_to_students(course):
    try:
        from notifications.consumers import send_notification_to_user
    except Exception:
        return

    payload = {
        "type": "course_published",
        "course": {
            "id": course.course_id,
            "title": course.title,
            "description": course.description or "",
            "subject_id": course.subject_id,
            "subject_name": course.subject.subject_name if course.subject else "بدون مادة",
            "level": course.level,
            "level_display": course.get_level_display(),
            "price": float(course.price) if course.price else 0,
            "currency": course.currency,
            "duration_minutes": course.duration_minutes or 0,
            "thumbnail_url": course.thumbnail.url if course.thumbnail else "",
            "preview_video_url": course.preview_video.url if course.preview_video else "",
            "teacher_name": course.teacher.user.get_full_name() or course.teacher.user.email,
            "teacher_avatar_url": course.teacher.user.avatar.url if course.teacher.user.avatar else "",
            "detail_url": reverse("courses:course_detail", args=[course.course_id]),
            "published_lessons_count": 0,
            "is_featured": course.is_featured,
        },
    }
    student_ids = UserRole.objects.filter(role__role_name="student").values_list("user_id", flat=True)
    for student_id in student_ids.iterator():
        async_to_sync(send_notification_to_user)(student_id, payload)


def _next_lesson_order(course):
    max_order = CourseLesson.objects.filter(course=course).aggregate(max_order=Max('order_index'))['max_order'] or 0
    return max_order + 1


def _resolve_user_roles(user):
    return set(UserRole.objects.filter(user=user).values_list('role__role_name', flat=True))


def _can_view_course_material(user, course, user_roles=None):
    user_roles = user_roles or _resolve_user_roles(user)
    return course.status == 'published' or ('teacher' in user_roles and course.teacher.user == user)


def _can_view_lesson_material(user, course, lesson, user_roles=None):
    user_roles = user_roles or _resolve_user_roles(user)
    if 'teacher' in user_roles and course.teacher.user == user:
        return True
    return 'student' in user_roles and course.status == 'published' and lesson.status == 'published'


def _safe_download_name(raw_name, fallback_stem):
    _, ext = os.path.splitext(raw_name or "")
    stem = slugify(fallback_stem or "") or "download"
    return f"{stem}{ext or ''}"


def _field_file_download_response(field_file, filename):
    if not field_file:
        raise Http404("Missing file")
    storage = field_file.storage
    if not storage.exists(field_file.name):
        raise Http404("Missing file")
    handle = storage.open(field_file.name, "rb")
    return FileResponse(handle, as_attachment=True, filename=filename)


def _duration_minutes_from_seconds(duration_seconds):
    if not duration_seconds:
        return None
    return ceil(int(duration_seconds) / 60)


def _parse_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _title_from_filename(filename):
    name, _ext = os.path.splitext(filename or "")
    normalized = re.sub(r'[_\-]+', ' ', name)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized or 'درس جديد'


def _decode_data_url_file(data_url, filename_stub):
    if not data_url or not data_url.startswith('data:image/'):
        return None
    try:
        header, encoded = data_url.split(',', 1)
        extension = header.split('/')[1].split(';')[0]
        binary = base64.b64decode(encoded)
    except (ValueError, binascii.Error):
        return None
    safe_name = slugify(filename_stub) or 'lesson-poster'
    return ContentFile(binary, name=f"{safe_name}.{extension}")


def _apply_video_artifacts(lesson, duration_seconds=None, poster_data_url=None, poster_stub=None):
    updated_fields = []
    duration_seconds = _parse_positive_int(duration_seconds)

    if duration_seconds:
        lesson.video_duration_seconds = int(duration_seconds)
        lesson.video_duration = _duration_minutes_from_seconds(duration_seconds)
        updated_fields.extend(['video_duration_seconds', 'video_duration'])

    if poster_data_url:
        poster_file = _decode_data_url_file(poster_data_url, poster_stub or lesson.title)
        if poster_file:
            lesson.poster_image.save(poster_file.name, poster_file, save=False)
            updated_fields.append('poster_image')

    if updated_fields:
        lesson.save(update_fields=updated_fields)


def _load_batch_payload(request):
    raw_payload = request.POST.get('batch_payload', '').strip()
    if not raw_payload:
        return []
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _create_batch_lessons(request, course):
    uploaded_videos = request.FILES.getlist('batch_videos')
    if not uploaded_videos:
        return 0

    payload_items = _load_batch_payload(request)
    payload_by_name = {
        item.get('fileName'): item
        for item in payload_items
        if isinstance(item, dict) and item.get('fileName')
    }
    base_order = _next_lesson_order(course)
    shared_description = request.POST.get('batch_description', '').strip()
    shared_content = request.POST.get('batch_content', '').strip()
    status = request.POST.get('batch_status', 'published') or 'published'
    is_free = request.POST.get('batch_is_free') == 'on'
    created_lessons = []

    with transaction.atomic():
        for offset, video_file in enumerate(uploaded_videos):
            item = payload_by_name.get(video_file.name, {})
            title = (item.get('title') or _title_from_filename(video_file.name)).strip()
            duration_seconds = _parse_positive_int(item.get('durationSeconds'))
            order_index = item.get('orderIndex') or (base_order + offset)

            lesson = CourseLesson.objects.create(
                course=course,
                title=title,
                description=shared_description,
                content=shared_content,
                video=video_file,
                order_index=int(order_index),
                is_free=is_free,
                status=status,
                video_duration_seconds=duration_seconds,
                video_duration=_duration_minutes_from_seconds(duration_seconds) if duration_seconds else None,
            )
            poster_stub = f"{title}-{lesson.order_index}"
            _apply_video_artifacts(
                lesson,
                duration_seconds=duration_seconds,
                poster_data_url=item.get('posterDataUrl'),
                poster_stub=poster_stub,
            )
            created_lessons.append(lesson)

    return len(created_lessons)


@login_required
def course_list(request):
    """Display all published courses with filtering"""
    published_lessons_prefetch = Prefetch(
        'courselesson_set',
        queryset=CourseLesson.objects.filter(status='published').order_by('order_index'),
        to_attr='published_lessons'
    )
    courses = Course.objects.filter(
        status='published'
    ).annotate(
        published_lessons_count=Count('courselesson', filter=Q(courselesson__status='published'), distinct=True)
    ).select_related(
        'subject', 'teacher__user'
    ).prefetch_related(
        published_lessons_prefetch
    ).distinct().order_by('-created_at', '-course_id')

    # Apply filters
    subject_id = request.GET.get('subject')
    level = request.GET.get('level')
    teacher_search = request.GET.get('teacher')
    search_query = request.GET.get('search')

    if subject_id:
        courses = courses.filter(subject_id=subject_id)
    if level:
        courses = courses.filter(level=level)
    if teacher_search:
        courses = courses.filter(
            Q(teacher__user__first_name__icontains=teacher_search) |
            Q(teacher__user__last_name__icontains=teacher_search) |
            Q(teacher__user__email__icontains=teacher_search)
        )
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Get user roles for template
    user_roles = UserRole.objects.filter(user=request.user).values_list('role__role_name', flat=True)

    # Get enrolled courses for students
    enrolled_course_ids = []
    if 'student' in user_roles:
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
            enrolled_course_ids = Enrollment.objects.filter(
                student=student_profile,
                status__in=['active', 'completed']
            ).values_list('course_id', flat=True)
        except StudentProfile.DoesNotExist:
            pass

    context = {
        'courses': courses,
        'user_roles': user_roles,
        'enrolled_course_ids': enrolled_course_ids,
        'filter_form': CourseFilterForm(request.GET),
        'subjects': Subject.objects.filter(is_active=True),
    }
    return render(request, 'courses/course_list.html', context)


@login_required
def course_detail(request, course_id):
    """Show course information, lessons, enrollment status"""
    course = get_object_or_404(Course.objects.select_related('subject', 'teacher__user'), course_id=course_id)
    user_roles = UserRole.objects.filter(user=request.user).values_list('role__role_name', flat=True)

    # Check if user can view this course
    can_view = course.status == 'published' or ('teacher' in user_roles and course.teacher.user == request.user)

    if not can_view:
        messages.error(request, "ليس لديك صلاحية لعرض هذا الكورس")
        return redirect('courses:course_list')

    can_edit = 'teacher' in user_roles and course.teacher.user == request.user

    if can_edit:
        lessons = CourseLesson.objects.filter(course=course).order_by('order_index')
    else:
        lessons = CourseLesson.objects.filter(course=course, status='published').order_by('order_index')
    published_lessons_count = CourseLesson.objects.filter(course=course, status='published').count()
    draft_lessons_count = CourseLesson.objects.filter(course=course, status='draft').count()

    # Get enrollment status for students
    enrollment = None
    is_enrolled = False
    if 'student' in user_roles:
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
            enrollment = Enrollment.objects.filter(student=student_profile, course=course).first()
            is_enrolled = enrollment is not None and enrollment.status in ['active', 'completed']
        except StudentProfile.DoesNotExist:
            pass

    # Get progress for enrolled students
    progress_data = {}
    completed_lesson_ids = set()
    if is_enrolled and enrollment:
        progress_records = LessonProgress.objects.filter(
            student=student_profile,
            lesson__course=course
        ).select_related('lesson')
        progress_data = {record.lesson_id: record for record in progress_records}
        completed_lesson_ids = {
            record.lesson_id for record in progress_records if record.completed
        }

    context = {
        'course': course,
        'lessons': lessons,
        'user_roles': user_roles,
        'is_enrolled': is_enrolled,
        'enrollment': enrollment,
        'progress_data': progress_data,
        'completed_lesson_ids': completed_lesson_ids,
        'can_edit': 'teacher' in user_roles and course.teacher.user == request.user,
        'draft_lessons_count': draft_lessons_count,
        'published_lessons_count': published_lessons_count,
        'has_paid_price': bool(course.price and course.price > 0),
        'downloadable_lessons_count': sum(1 for lesson in lessons if lesson.video),
    }
    return render(request, 'courses/course_detail.html', context)


@login_required
def download_course_preview(request, course_id):
    course = get_object_or_404(Course.objects.select_related('teacher__user'), course_id=course_id)
    user_roles = _resolve_user_roles(request.user)
    if not _can_view_course_material(request.user, course, user_roles):
        raise PermissionDenied
    if not course.preview_video:
        raise Http404("No preview video")
    return _field_file_download_response(
        course.preview_video,
        _safe_download_name(course.preview_video.name, f"{course.title}-preview"),
    )


@permission_required('can_manage_courses')
def course_create(request):
    """Create a new course"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, "يجب إنشاء ملف تعريف معلم أولاً")
        return redirect('accounts:teacher_dashboard')

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = teacher_profile
            course.status = 'published'
            course.save()
            _broadcast_course_to_students(course)
            messages.success(request, f"تم إنشاء الكورس بنجاح! (ID: {course.course_id})")
            return redirect('courses:course_detail', course_id=course.course_id)
        else:
            _add_form_errors_as_notifications(request, form)
    else:
        form = CourseForm()

    return render(request, 'courses/course_create.html', {'form': form})


@permission_required('can_manage_courses')
def course_edit(request, course_id):
    """Edit an existing course"""
    course = get_object_or_404(Course, course_id=course_id, teacher__user=request.user)

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            updated_course = form.save(commit=False)
            updated_course.status = 'published'
            updated_course.save()
            messages.success(request, "تم تحديث الكورس بنجاح")
            return redirect('courses:course_detail', course_id=course.course_id)
        _add_form_errors_as_notifications(request, form)
    else:
        form = CourseForm(instance=course)

    return render(request, 'courses/course_edit.html', {'form': form, 'course': course})


@teacher_required
def teacher_course_list(request):
    """List courses created by the teacher"""
    try:
        teacher_profile = TeacherProfile.objects.get(user=request.user)
        courses = Course.objects.filter(teacher=teacher_profile).prefetch_related('subject')
    except TeacherProfile.DoesNotExist:
        courses = Course.objects.none()

    # Add enrollment counts
    courses_with_counts = courses.annotate(
        enrollment_count=Count('enrollment', filter=Q(enrollment__status__in=['active', 'completed']))
    )

    return render(request, 'courses/teacher_course_list.html', {
        'courses': courses_with_counts
    })


@student_required
def enroll_course(request, course_id):
    """Enroll student in a course"""
    course = get_object_or_404(Course, course_id=course_id, status='published')

    if course.price and course.price > 0:
        return redirect("payments:course_checkout", course_id=course.course_id)

    try:
        student_profile = StudentProfile.objects.get(user=request.user)

        # Check if already enrolled
        existing_enrollment = Enrollment.objects.filter(
            student=student_profile,
            course=course,
            status__in=['active', 'completed']
        ).exists()

        if existing_enrollment:
            messages.warning(request, "أنت مسجل بالفعل في هذا الكورس")
            return redirect('courses:course_detail', course_id=course_id)

        # Create enrollment
        enrollment = Enrollment.objects.create(
            student=student_profile,
            course=course,
            payment_status='paid' if course.price == 0 or course.price is None else 'pending'
        )

        messages.success(request, "تم التسجيل في الكورس بنجاح")
        return redirect('courses:course_detail', course_id=course_id)

    except StudentProfile.DoesNotExist:
        messages.error(request, "يجب إنشاء ملف تعريف طالب أولاً")
        return redirect('accounts:student_dashboard')


@login_required
def lesson_view(request, course_id, lesson_id):
    """View lesson content and track progress"""
    course = get_object_or_404(Course, course_id=course_id)
    lesson = get_object_or_404(CourseLesson, lesson_id=lesson_id, course=course)

    user_roles = UserRole.objects.filter(user=request.user).values_list('role__role_name', flat=True)

    # Check permissions
    can_view = False
    enrollment = None

    if 'teacher' in user_roles and course.teacher.user == request.user:
        can_view = True
    elif 'student' in user_roles:
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
            enrollment = Enrollment.objects.filter(
                student=student_profile,
                course=course,
                status__in=['active', 'completed']
            ).first()
            can_view = course.status == 'published' and lesson.status == 'published'
        except StudentProfile.DoesNotExist:
            pass

    if not can_view:
        messages.error(request, "ليس لديك صلاحية لعرض هذا الدرس")
        return redirect('courses:course_detail', course_id=course_id)

    # Get or create progress record for students
    progress = None
    if enrollment and 'student' in user_roles:
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
            progress, created = LessonProgress.objects.get_or_create(
                student=student_profile,
                lesson=lesson,
                defaults={'completed': False}
            )
        except StudentProfile.DoesNotExist:
            pass

    # Get next and previous lessons
    lessons = list(CourseLesson.objects.filter(course=course, status='published').order_by('order_index'))
    current_index = next((i for i, l in enumerate(lessons) if l.lesson_id == lesson_id), -1)
    prev_lesson = lessons[current_index - 1] if current_index > 0 else None
    next_lesson = lessons[current_index + 1] if current_index < len(lessons) - 1 else None

    context = {
        'course': course,
        'lesson': lesson,
        'progress': progress,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
        'user_roles': user_roles,
        'is_enrolled': enrollment is not None,
    }
    return render(request, 'courses/lesson_view.html', context)


@login_required
def download_lesson_video(request, course_id, lesson_id):
    course = get_object_or_404(Course.objects.select_related('teacher__user'), course_id=course_id)
    lesson = get_object_or_404(CourseLesson, lesson_id=lesson_id, course=course)
    user_roles = _resolve_user_roles(request.user)
    if not _can_view_lesson_material(request.user, course, lesson, user_roles):
        raise PermissionDenied
    if not lesson.video:
        raise Http404("No lesson video")
    return _field_file_download_response(
        lesson.video,
        _safe_download_name(lesson.video.name, f"{course.title}-{lesson.order_index}-{lesson.title}"),
    )


@login_required
def download_course_lessons_bundle(request, course_id):
    course = get_object_or_404(Course.objects.select_related('teacher__user'), course_id=course_id)
    user_roles = _resolve_user_roles(request.user)
    if not _can_view_course_material(request.user, course, user_roles):
        raise PermissionDenied

    if 'teacher' in user_roles and course.teacher.user == request.user:
        lessons = CourseLesson.objects.filter(course=course).order_by('order_index')
    else:
        lessons = CourseLesson.objects.filter(course=course, status='published').order_by('order_index')

    lessons_with_video = [lesson for lesson in lessons if lesson.video]
    if not lessons_with_video:
        raise Http404("No downloadable lessons")

    archive_buffer = tempfile.SpooledTemporaryFile(max_size=25 * 1024 * 1024, mode='w+b')
    with zipfile.ZipFile(archive_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            'README.txt',
            f"Course: {course.title}\nLessons: {len(lessons_with_video)}\nGenerated by EduVerse.\n",
        )
        for lesson in lessons_with_video:
            extension = os.path.splitext(lesson.video.name or '')[1] or '.mp4'
            archive_name = f"{lesson.order_index:02d}-{slugify(lesson.title) or 'lesson'}{extension}"
            with lesson.video.storage.open(lesson.video.name, 'rb') as source_file:
                with archive.open(archive_name, 'w') as archive_entry:
                    shutil.copyfileobj(source_file, archive_entry, length=1024 * 1024)
    archive_buffer.seek(0)
    return FileResponse(
        archive_buffer,
        as_attachment=True,
        filename=f"{slugify(course.title) or 'course'}-lessons.zip",
    )


@login_required
def mark_lesson_complete(request, lesson_id):
    """Mark lesson as completed via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        lesson = CourseLesson.objects.get(lesson_id=lesson_id)
        student_profile = StudentProfile.objects.get(user=request.user)

        # Check enrollment
        enrollment = Enrollment.objects.filter(
            student=student_profile,
            course=lesson.course,
            status__in=['active', 'completed']
        ).exists()

        if not enrollment:
            return JsonResponse({'success': False, 'error': 'Not enrolled'})

        progress, created = LessonProgress.objects.get_or_create(
            student=student_profile,
            lesson=lesson,
            defaults={'completed': True, 'completion_date': timezone.now()}
        )

        if not created and not progress.completed:
            progress.completed = True
            progress.completion_date = timezone.now()
            progress.save()

            # Update enrollment progress
            total_lessons = CourseLesson.objects.filter(course=lesson.course, status='published').count()
            completed_lessons = LessonProgress.objects.filter(
                student=student_profile,
                lesson__course=lesson.course,
                completed=True
            ).count()

            if total_lessons > 0:
                progress_percentage = (completed_lessons / total_lessons) * 100
                enrollment_obj = Enrollment.objects.get(student=student_profile, course=lesson.course)
                enrollment_obj.progress_percentage = progress_percentage
                if progress_percentage == 100:
                    enrollment_obj.status = 'completed'
                    enrollment_obj.completion_date = timezone.now()
                enrollment_obj.save()

        return JsonResponse({'success': True})

    except (CourseLesson.DoesNotExist, StudentProfile.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Invalid request'})


@teacher_required
def lesson_create(request, course_id):
    """Create a new lesson for a course"""
    course = get_object_or_404(Course, course_id=course_id, teacher__user=request.user)

    if request.method == 'POST':
        if request.POST.get('upload_mode') == 'batch':
            created_count = _create_batch_lessons(request, course)
            if created_count:
                messages.success(request, f"تم رفع {created_count} درس وترتيبها تلقائياً داخل الكورس")
                return redirect('courses:course_detail', course_id=course_id)
            messages.error(request, "لم يتم العثور على فيديوهات صالحة للرفع الجماعي")
            form = CourseLessonForm(initial={'order_index': _next_lesson_order(course)})
            return render(request, 'courses/lesson_create.html', {'form': form, 'course': course})

        form = CourseLessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.status = 'published'
            duration_seconds = _parse_positive_int(request.POST.get('video_duration_seconds'))
            if duration_seconds:
                lesson.video_duration_seconds = duration_seconds
                lesson.video_duration = _duration_minutes_from_seconds(duration_seconds)
            lesson.save()
            _apply_video_artifacts(
                lesson,
                duration_seconds=duration_seconds,
                poster_data_url=request.POST.get('video_poster_data_url'),
                poster_stub=lesson.title,
            )
            messages.success(request, "تم إنشاء الدرس بنجاح")
            return redirect('courses:course_detail', course_id=course_id)
        _add_form_errors_as_notifications(request, form)
    else:
        # Set default order_index
        form = CourseLessonForm(initial={'order_index': _next_lesson_order(course)})

    return render(request, 'courses/lesson_create.html', {'form': form, 'course': course})


@teacher_required
def lesson_edit(request, course_id, lesson_id):
    """Edit an existing lesson"""
    course = get_object_or_404(Course, course_id=course_id, teacher__user=request.user)
    lesson = get_object_or_404(CourseLesson, lesson_id=lesson_id, course=course)

    if request.method == 'POST':
        form = CourseLessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            updated_lesson = form.save(commit=False)
            updated_lesson.status = 'published'
            duration_seconds = _parse_positive_int(request.POST.get('video_duration_seconds'))
            if duration_seconds:
                updated_lesson.video_duration_seconds = duration_seconds
                updated_lesson.video_duration = _duration_minutes_from_seconds(duration_seconds)
            updated_lesson.save()
            _apply_video_artifacts(
                updated_lesson,
                duration_seconds=duration_seconds,
                poster_data_url=request.POST.get('video_poster_data_url'),
                poster_stub=updated_lesson.title,
            )
            messages.success(request, "تم تحديث الدرس بنجاح")
            return redirect('courses:course_detail', course_id=course_id)
    else:
        form = CourseLessonForm(instance=lesson)

    return render(request, 'courses/lesson_edit.html', {'form': form, 'course': course, 'lesson': lesson})


@teacher_required
def lesson_delete(request, course_id, lesson_id):
    """Delete a lesson"""
    course = get_object_or_404(Course, course_id=course_id, teacher__user=request.user)
    lesson = get_object_or_404(CourseLesson, lesson_id=lesson_id, course=course)
    
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, "تم حذف الدرس بنجاح")
        return redirect('courses:course_detail', course_id=course_id)
        
    return render(request, 'courses/lesson_confirm_delete.html', {'lesson': lesson, 'course': course})


@teacher_required
@require_http_methods(["POST"])
def publish_all_lessons(request, course_id):
    """Publish all draft lessons for a course owned by the current teacher."""
    course = get_object_or_404(Course, course_id=course_id, teacher__user=request.user)
    updated = CourseLesson.objects.filter(course=course, status='draft').update(status='published')

    if updated:
        messages.success(request, f"تم نشر {updated} درس بنجاح.")
    else:
        messages.info(request, "لا توجد دروس مسودة للنشر.")

    return redirect('courses:course_detail', course_id=course_id)


# API Views for AJAX

def api_courses_list(request):
    """API endpoint to get courses list"""
    courses = Course.objects.filter(status='published').select_related('subject', 'teacher__user').values(
        'course_id', 'title', 'description', 'price', 'currency', 'level', 'thumbnail', 'created_at'
    )
    return JsonResponse(list(courses), safe=False)


def api_course_detail(request, course_id):
    """API endpoint to get course details"""
    try:
        course = Course.objects.select_related('subject', 'teacher__user').get(course_id=course_id, status='published')
        data = {
            'course_id': course.course_id,
            'title': course.title,
            'description': course.description,
            'subject': course.subject.subject_name if course.subject else None,
            'teacher': f"{course.teacher.user.first_name} {course.teacher.user.last_name}",
            'level': course.level,
            'price': str(course.price),
            'currency': course.currency,
            'duration_minutes': course.duration_minutes,
            'max_students': course.max_students,
            'is_featured': course.is_featured,
        }
        return JsonResponse(data)
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)


# ===== Advanced Search Views =====

@login_required
@require_http_methods(["GET"])
def advanced_search(request):
    """
    Advanced search view with filters, facets, and pagination
    """
    # Get search parameters
    query = request.GET.get('q', '')
    subject = request.GET.get('subject', '')
    level = request.GET.get('level', '')
    course_type = request.GET.get('course_type', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    is_free = request.GET.get('is_free', '') == 'true'
    teacher = request.GET.get('teacher', '')
    sort_by = request.GET.get('sort_by', 'newest')
    page = request.GET.get('page', 1)
    
    # Initialize search engine
    search_engine = CourseSearchEngine()
    
    # Build filters
    filters = {
        'subject': subject,
        'level': level,
        'course_type': course_type,
        'sort_by': sort_by,
    }
    
    if price_min:
        filters['price_min'] = float(price_min)
    if price_max:
        filters['price_max'] = float(price_max)
    if is_free:
        filters['is_free'] = True
    if teacher:
        filters['teacher'] = teacher
    
    # Perform search
    results = search_engine.search(query, **filters)
    
    # Get facets for filtering
    facets = search_engine.get_facets()
    
    # Paginate results
    paginator = Paginator(results, 12)  # 12 courses per page
    courses_page = paginator.get_page(page)
    
    # Get recommendations if user is student
    recommendations = []
    user_roles = request.user.get_roles()
    if 'student' in user_roles:
        try:
            student_profile = StudentProfile.objects.get(user=request.user)
            recommendations = RecommendationEngine.get_recommendations_for_student(student_profile, limit=6)
        except StudentProfile.DoesNotExist:
            pass
    
    context = {
        'query': query,
        'courses': courses_page,
        'facets': facets,
        'filters': filters,
        'recommendations': recommendations,
        'user_roles': user_roles,
        'subjects': Subject.objects.filter(is_active=True),
    }
    
    return render(request, 'courses/advanced_search.html', context)


@login_required
@require_http_methods(["GET"])
def api_search_courses(request):
    """
    API endpoint for course search (AJAX)
    Returns JSON with courses, facets, and pagination info
    """
    query = request.GET.get('q', '')
    filters = {
        'subject': request.GET.get('subject', ''),
        'level': request.GET.get('level', ''),
        'course_type': request.GET.get('course_type', ''),
        'sort_by': request.GET.get('sort_by', 'newest'),
    }
    
    # Remove empty filters
    filters = {k: v for k, v in filters.items() if v}
    
    search_engine = CourseSearchEngine()
    results = search_engine.search(query, **filters)
    
    # Paginate
    page = int(request.GET.get('page', 1))
    paginator = Paginator(results, 12)
    courses_page = paginator.get_page(page)
    
    # Serialize courses
    courses_data = []
    for course in courses_page:
        courses_data.append({
            'id': course.course_id,
            'title': course.title,
            'description': course.description[:150] if course.description else '',
            'subject': course.subject.subject_name if course.subject else None,
            'level': course.get_level_display(),
            'price': float(course.price) if course.price else 0,
            'currency': course.currency,
            'thumbnail': course.thumbnail.url if course.thumbnail else None,
            'teacher': {
                'name': f"{course.teacher.user.first_name} {course.teacher.user.last_name}",
                'id': course.teacher.teacher_id,
            },
            'is_featured': course.is_featured,
        })
    
    # Get facets
    facets = search_engine.get_facets()
    
    return JsonResponse({
        'courses': courses_data,
        'facets': facets,
        'pagination': {
            'current_page': courses_page.number,
            'total_pages': paginator.num_pages,
            'has_next': courses_page.has_next(),
            'has_previous': courses_page.has_previous(),
            'total_count': paginator.count,
        }
    })


@login_required
@require_http_methods(["GET"])
def api_search_teachers(request):
    """
    API endpoint for teacher search
    """
    query = request.GET.get('q', '')
    filters = {
        'subject': request.GET.get('subject', ''),
        'rate_min': request.GET.get('rate_min', ''),
        'rate_max': request.GET.get('rate_max', ''),
    }
    
    # Remove empty filters
    filters = {k: v for k, v in filters.items() if v}
    
    search_engine = TeacherSearchEngine()
    results = search_engine.search(query, **filters)
    
    # Paginate
    page = int(request.GET.get('page', 1))
    paginator = Paginator(results, 12)
    teachers_page = paginator.get_page(page)
    
    # Serialize teachers
    teachers_data = []
    for teacher in teachers_page:
        teachers_data.append({
            'id': teacher.teacher_id,
            'name': f"{teacher.user.first_name} {teacher.user.last_name}",
            'bio': teacher.bio[:200] if teacher.bio else '',
            'hourly_rate': float(teacher.hourly_rate) if teacher.hourly_rate else None,
            'experience_years': teacher.experience_years,
            'avatar': teacher.user.avatar.url if teacher.user.avatar else None,
        })
    
    return JsonResponse({
        'teachers': teachers_data,
        'pagination': {
            'current_page': teachers_page.number,
            'total_pages': paginator.num_pages,
            'has_next': teachers_page.has_next(),
            'has_previous': teachers_page.has_previous(),
            'total_count': paginator.count,
        }
    })


@login_required
@require_http_methods(["GET"])
def api_recommendations(request):
    """
    API endpoint for personalized recommendations
    """
    user_roles = request.user.get_roles()
    
    if 'student' not in user_roles:
        return JsonResponse({'error': 'Only students can get recommendations'}, status=403)
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
        recommendations = RecommendationEngine.get_recommendations_for_student(student_profile, limit=10)
        
        courses_data = []
        for course in recommendations:
            courses_data.append({
                'id': course.course_id,
                'title': course.title,
                'description': course.description[:150] if course.description else '',
                'subject': course.subject.subject_name if course.subject else None,
                'level': course.get_level_display(),
                'price': float(course.price) if course.price else 0,
                'thumbnail': course.thumbnail.url if course.thumbnail else None,
            })
        
        return JsonResponse({'recommendations': courses_data})
        
    except StudentProfile.DoesNotExist:
        return JsonResponse({'error': 'Student profile not found'}, status=404)


@require_http_methods(["GET"])
def api_trending_courses(request):
    """
    API endpoint for trending courses
    """
    limit = int(request.GET.get('limit', 10))
    trending = RecommendationEngine.get_trending_courses(limit=limit)
    
    courses_data = []
    for course in trending:
        courses_data.append({
            'id': course.course_id,
            'title': course.title,
            'description': course.description[:150] if course.description else '',
            'subject': course.subject.subject_name if course.subject else None,
            'price': float(course.price) if course.price else 0,
            'thumbnail': course.thumbnail.url if course.thumbnail else None,
            'is_featured': course.is_featured,
        })
    
    return JsonResponse({'trending_courses': courses_data})


# ===== FRONTEND INTEGRATED VIEWS =====

@login_required
@student_required
def analytics_dashboard(request):
    """Student analytics dashboard"""
    student_profile = StudentProfile.objects.get(user=request.user)
    analytics = StudentAnalytics(student_profile)
    
    overview = analytics.get_overview()
    progress_by_course = analytics.get_progress_by_course()
    heatmap_data = analytics.get_activity_heatmap(days=90)
    
    progress_labels = []
    progress_data = []
    for i in range(7):
        date = timezone.now() - timezone.timedelta(days=6-i)
        progress_labels.append(date.strftime('%a'))
        progress_data.append(overview['learning_hours'] / 7)
    
    subject_labels = []
    subject_data = []
    for course in progress_by_course[:5]:
        subject_labels.append(course['course_title'][:20])
        subject_data.append(course['progress'])
    
    context = {
        'overview': overview,
        'progress_by_course': progress_by_course,
        'heatmap_data': json.dumps(heatmap_data),
        'progress_labels': json.dumps(progress_labels),
        'progress_data': json.dumps(progress_data),
        'subject_labels': json.dumps(subject_labels),
        'subject_data': json.dumps(subject_data),
    }
    
    return render(request, 'courses/analytics_dashboard.html', context)


@login_required
def certificate_view(request, certificate_id):
    """View certificate"""
    from courses.models import Certificate
    certificate = get_object_or_404(Certificate, certificate_id=certificate_id)
    
    if certificate.enrollment.student.user != request.user and not request.user.is_staff:
        messages.error(request, 'Permission denied')
        return redirect('accounts:dashboard_redirect')
    
    return render(request, 'courses/certificate_view.html', {'certificate': certificate})


@require_http_methods(["GET"])
def verify_certificate(request, certificate_id):
    """Public certificate verification"""
    from .certificate_generator import CertificateGenerator
    generator = CertificateGenerator()
    verification = generator.verify_certificate(certificate_id)
    
    return render(request, 'courses/certificate_verify.html', {
        'verification': verification,
        'certificate_id': certificate_id
    })
