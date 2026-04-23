from collections import OrderedDict
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import FileResponse, Http404, JsonResponse
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.urls import reverse
from decouple import config
from accounts.decorators import student_required, teacher_required
from bookings.models import Booking
from courses.models import Enrollment
from accounts.models import StudentProfile, TeacherProfile
from .models import LiveCall, LiveCallParticipant, Message, Notification
from .forms import MessageForm, ReplyMessageForm
from accounts.models import User
import uuid
import os
from urllib.parse import urlencode, urlsplit, urlunsplit


def _message_inbox_queryset(user):
    return Message.objects.filter(
        receiver=user,
        deleted_by_receiver=False,
    ).select_related("sender", "receiver")


def _message_sent_queryset(user):
    return Message.objects.filter(
        sender=user,
        deleted_by_sender=False,
    ).select_related("sender", "receiver")


def _push_notification_to_user(user_id, payload):
    try:
        from .consumers import send_notification_to_user
        async_to_sync(send_notification_to_user)(user_id, payload)
    except Exception:
        pass


def _request_prefers_json(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")


def _build_pagination_query(request, page_param):
    params = request.GET.copy()
    params.pop(page_param, None)
    return urlencode(sorted(params.lists()), doseq=True)


def _paginate_queryset(request, queryset, *, per_page=12, page_param="page"):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get(page_param))
    return page_obj, _build_pagination_query(request, page_param)


def _send_system_message(sender, receiver, subject, content):
    message = Message.objects.create(
        sender=sender,
        receiver=receiver,
        subject=subject,
        content=content,
    )
    Notification.objects.create(
        user=receiver,
        type="message",
        title=subject,
        content=content,
        data={
            "message_id": message.message_id,
            "sender_name": sender.get_full_name() or sender.email,
            "sender_email": sender.email,
            "subject": subject,
            "message": content,
            "has_attachment": False,
        },
    )
    _push_notification_to_user(
        receiver.id,
        {
            "id": message.message_id,
            "type": "message",
            "title": subject,
            "message": content,
            "message_id": message.message_id,
        },
    )
    return message


def _message_original_filename(message):
    if not message.attachment_file:
        return ""
    return os.path.basename(message.attachment_file.name)


def _accessible_message_or_404(user, message_id):
    message = get_object_or_404(
        Message.objects.select_related("sender", "receiver"),
        Q(message_id=message_id),
        Q(receiver=user) | Q(sender=user),
    )
    if user == message.receiver and message.deleted_by_receiver:
        raise PermissionDenied("Hidden for receiver")
    if user == message.sender and message.deleted_by_sender:
        raise PermissionDenied("Hidden for sender")
    return message


def _message_file_response(message):
    if not message.attachment_file:
        raise Http404("No attachment")
    storage = message.attachment_file.storage
    if not storage.exists(message.attachment_file.name):
        raise Http404("Missing attachment")
    handle = storage.open(message.attachment_file.name, "rb")
    return FileResponse(handle, as_attachment=True, filename=_message_original_filename(message))


def _notify_message_receiver(message, title, notification_text):
    Notification.objects.create(
        user=message.receiver,
        type="message",
        title=title,
        content=notification_text,
        data={
            "message_id": message.message_id,
            "sender_name": message.sender.get_full_name() or message.sender.email,
            "sender_email": message.sender.email,
            "subject": message.subject,
            "message": message.content,
            "has_attachment": bool(message.attachment_file or message.attachment_urls),
        },
    )
    _push_notification_to_user(
        message.receiver_id,
        {
            "id": message.message_id,
            "type": "message",
            "title": title,
            "message": notification_text,
            "message_id": message.message_id,
        },
    )


def _localhost_room_hint(request):
    host = request.get_host()
    hostname = host.split(":")[0]
    if hostname in {"localhost", "127.0.0.1", "::1"} or request.is_secure():
        return None
    parts = urlsplit(request.build_absolute_uri())
    port = f":{parts.port}" if parts.port else ""
    replacement_netloc = f"127.0.0.1{port}"
    return urlunsplit((parts.scheme, replacement_netloc, parts.path, parts.query, parts.fragment))

@login_required
def message_list(request):
    filter_mode = request.GET.get("filter", "").strip()
    inbox_messages = _message_inbox_queryset(request.user)
    if filter_mode == "unread":
        inbox_messages = inbox_messages.filter(is_read=False)
    inbox_messages = inbox_messages.order_by("is_read", "-created_at")
    page_obj, pagination_query = _paginate_queryset(request, inbox_messages, per_page=10)
    unread_inbox_count = _message_inbox_queryset(request.user).filter(is_read=False).count()
    total_inbox_count = _message_inbox_queryset(request.user).count()
    context = {
        'inbox_messages': page_obj.object_list,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'unread_inbox_count': unread_inbox_count,
        'read_inbox_count': max(0, total_inbox_count - unread_inbox_count),
        'total_inbox_count': total_inbox_count,
        'filter_mode': filter_mode,
    }
    return render(request, 'notifications/message_list.html', context)

@login_required
def sent_messages(request):
    sent_messages_list = _message_sent_queryset(request.user).order_by('-created_at')
    page_obj, pagination_query = _paginate_queryset(request, sent_messages_list, per_page=10)
    return render(
        request,
        'notifications/sent_messages.html',
        {
            'sent_messages': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': pagination_query,
            'sent_total_count': sent_messages_list.count(),
        },
    )

@login_required
def compose_message(request):
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES, sender=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            _notify_message_receiver(
                message,
                "رسالة جديدة",
                f"وصلك رسالة جديدة من {request.user.get_full_name() or request.user.email}",
            )
            messages.success(request, 'تم إرسال الرسالة، وسيصل إشعار مباشر إلى الحساب المحدد.')
            return redirect('notifications:message_list')
    else:
        form = MessageForm(sender=request.user)
    return render(request, 'notifications/compose_message.html', {'form': form})

@login_required
def message_detail(request, message_id):
    try:
        message = _accessible_message_or_404(request.user, message_id)
    except PermissionDenied:
        messages.error(request, 'هذه الرسالة محذوفة من قائمتك.')
        return redirect('notifications:message_list')
    if request.user == message.receiver and not message.is_read:
        message.is_read = True
        message.read_at = timezone.now()
        message.save(update_fields=["is_read", "read_at"])
    return render(request, 'notifications/message_detail.html', {'message': message})

@login_required
def reply_message(request, message_id):
    parent_message = get_object_or_404(Message, message_id=message_id)
    # Ensure user can reply (either sender or receiver)
    if request.user not in [parent_message.sender, parent_message.receiver]:
        messages.error(request, 'لا يمكنك الرد على هذه الرسالة.')
        return redirect('notifications:message_list')

    if request.method == 'POST':
        form = ReplyMessageForm(request.POST, request.FILES, sender=request.user, parent=parent_message)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.sender = request.user
            reply.receiver = parent_message.sender if parent_message.receiver == request.user else parent_message.receiver
            reply.parent_message = parent_message
            reply.subject = f"Re: {parent_message.subject}"
            reply.save()
            _notify_message_receiver(
                reply,
                "رد على رسالة",
                f"وصلك رد جديد من {request.user.get_full_name() or request.user.email}",
            )
            messages.success(request, 'تم إرسال الرد، وتم إشعار المستلم به.')
            return redirect('notifications:message_detail', message_id=parent_message.message_id)
    else:
        form = ReplyMessageForm(sender=request.user, parent=parent_message)
    return render(request, 'notifications/reply_message.html', {'form': form, 'parent_message': parent_message})


@login_required
def forward_message(request, message_id):
    source_message = _accessible_message_or_404(request.user, message_id)
    initial = {
        "subject": f"إعادة إرسال: {source_message.subject or 'بدون موضوع'}",
        "content": source_message.content,
        "attachment_urls": source_message.attachment_urls,
        "receiver": source_message.receiver.id,
    }
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES, sender=request.user)
        if form.is_valid():
            forwarded = form.save(commit=False)
            forwarded.sender = request.user
            forwarded.parent_message = source_message.parent_message or source_message
            if not forwarded.attachment_file and source_message.attachment_file:
                forwarded.attachment_file = source_message.attachment_file.name
            if not forwarded.attachment_urls and source_message.attachment_urls:
                forwarded.attachment_urls = source_message.attachment_urls
            forwarded.save()
            _notify_message_receiver(
                forwarded,
                "رسالة معاد إرسالها",
                f"قام {request.user.get_full_name() or request.user.email} بإعادة إرسال رسالة إليك.",
            )
            messages.success(request, 'تمت إعادة إرسال الرسالة بنجاح.')
            return redirect('notifications:message_detail', message_id=forwarded.message_id)
    else:
        form = MessageForm(sender=request.user, initial=initial)
    return render(
        request,
        'notifications/compose_message.html',
        {
            'form': form,
            'forward_source': source_message,
        },
    )


@login_required
def download_message_attachment(request, message_id):
    message = _accessible_message_or_404(request.user, message_id)
    return _message_file_response(message)

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).exclude(type='message').order_by('is_read', '-created_at')
    message_notifications_count = Notification.objects.filter(user=request.user, type='message').count()
    page_obj, pagination_query = _paginate_queryset(request, notifications, per_page=12)
    return render(
        request,
        'notifications/notification_list.html',
        {
            'notifications': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': pagination_query,
            'notifications_total_count': notifications.count(),
            'message_notifications_count': message_notifications_count,
        },
    )

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, notification_id=notification_id, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
    if _request_prefers_json(request):
        return JsonResponse({"success": True, "notification_id": notification_id})
    return redirect('notifications:notification_list')

@login_required
def mark_all_read(request):
    updated = Notification.objects.filter(user=request.user, is_read=False).exclude(type='message').update(is_read=True, read_at=timezone.now())
    if _request_prefers_json(request):
        return JsonResponse({"success": True, "updated_count": updated})
    if updated:
        messages.success(request, 'تم تعليم كل الإشعارات المقروءة.')
    else:
        messages.info(request, 'لا توجد إشعارات جديدة لتعليمها كمقروءة.')
    return redirect('notifications:notification_list')


@login_required
@require_POST
def mark_all_messages_read(request):
    updated = _message_inbox_queryset(request.user).filter(is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    if _request_prefers_json(request):
        return JsonResponse({"success": True, "updated_count": updated})
    if updated:
        messages.success(request, f'تم تعليم {updated} رسالة كمقروءة.')
    else:
        messages.info(request, 'كل رسائلك مقروءة بالفعل.')
    return redirect('notifications:message_list')


@login_required
@require_POST
def delete_message(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("sender", "receiver"),
        Q(message_id=message_id),
        Q(receiver=request.user) | Q(sender=request.user),
    )
    redirect_name = 'notifications:message_list'
    updated_fields = []
    if request.user == message.receiver and not message.deleted_by_receiver:
        message.deleted_by_receiver = True
        updated_fields.append("deleted_by_receiver")
    if request.user == message.sender:
        redirect_name = 'notifications:sent_messages'
        if not message.deleted_by_sender:
            message.deleted_by_sender = True
            updated_fields.append("deleted_by_sender")

    if updated_fields:
        message.save(update_fields=updated_fields)
        if _request_prefers_json(request):
            return JsonResponse({"success": True, "message_id": message_id, "redirect_name": redirect_name})
        messages.success(request, 'تم حذف الرسالة من قائمتك.')
    else:
        if _request_prefers_json(request):
            return JsonResponse({"success": True, "message_id": message_id, "redirect_name": redirect_name})
        messages.info(request, 'هذه الرسالة محذوفة بالفعل من قائمتك.')
    return redirect(redirect_name)


@login_required
@require_POST
def delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, notification_id=notification_id, user=request.user)
    notification.delete()
    if _request_prefers_json(request):
        return JsonResponse({"success": True, "notification_id": notification_id})
    messages.success(request, 'تم حذف الإشعار.')
    return redirect('notifications:notification_list')


@login_required
def message_activity_feed(request):
    inbox_messages = _message_inbox_queryset(request.user).order_by("created_at")
    latest_messages = list(_message_inbox_queryset(request.user).order_by("-created_at")[:12])
    latest_messages.reverse()
    payload = {
        "unread_count": inbox_messages.filter(is_read=False).count(),
        "total_count": inbox_messages.count(),
        "messages": [
            {
                "id": message.message_id,
                "subject": message.subject or "بدون موضوع",
                "preview": (message.content or "")[:180],
                "sender_name": message.sender.get_full_name() or message.sender.email,
                "created_at": timezone.localtime(message.created_at).strftime("%Y-%m-%d %H:%M"),
                "detail_url": f"/notifications/messages/{message.message_id}/",
                "reply_url": f"/notifications/messages/{message.message_id}/reply/",
                "forward_url": f"/notifications/messages/{message.message_id}/forward/",
                "download_url": f"/notifications/messages/{message.message_id}/download/" if message.attachment_file else "",
                "is_read": message.is_read,
                "has_attachment": bool(message.attachment_file or message.attachment_urls),
            }
            for message in latest_messages
        ],
    }
    return JsonResponse(payload)

@login_required
def unread_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).exclude(type='message').count()
    return JsonResponse({'unread_count': count})


def _build_call_room(call_uuid):
    room_name = f"eduverse-call-{call_uuid.hex[:12]}"
    return room_name


def _build_local_call_urls(request, call):
    room_path = reverse("notifications:live_call_room", args=[call.call_id])
    room_url = request.build_absolute_uri(room_path)
    return room_path, room_url


def _webrtc_room_context(call):
    ice_servers = getattr(settings, "WEBRTC_ICE_SERVERS", [])
    return {
        "call_room_name": call.room_name,
        "call_ws_url": f"/ws/live-calls/{call.call_id}/",
        "webrtc_ice_servers": ice_servers,
        "cloudflare_url": config('CLOUDFLARE_TUNNEL_URL', default=''),
    }


def _candidate_students_for_teacher(teacher_profile):
    cache_key = f"teacher_call_candidates:{teacher_profile.user_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    students = OrderedDict()

    bookings = Booking.objects.filter(teacher=teacher_profile).select_related("student__user")
    for booking in bookings:
        students[booking.student.user_id] = booking.student

    enrollments = Enrollment.objects.filter(course__teacher=teacher_profile).select_related("student__user")
    for enrollment in enrollments:
        students[enrollment.student.user_id] = enrollment.student

    result = list(students.values())
    cache.set(cache_key, result, 60)
    return result


def _candidate_teachers_for_student(student_profile):
    cache_key = f"student_call_candidates:{student_profile.user_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    teachers = OrderedDict()

    bookings = Booking.objects.filter(student=student_profile).select_related("teacher__user")
    for booking in bookings:
        teachers[booking.teacher.user_id] = booking.teacher

    enrollments = Enrollment.objects.filter(student=student_profile).select_related("course__teacher__user")
    for enrollment in enrollments:
        if enrollment.course and enrollment.course.teacher:
            teachers[enrollment.course.teacher.user_id] = enrollment.course.teacher

    result = list(teachers.values())
    cache.set(cache_key, result, 60)
    return result


def _create_call_notification(user, title, content, call, extra_data=None):
    payload = {
        "call_id": call.call_id,
        "call_uuid": str(call.uuid),
        "room_url": call.room_url,
        "room_path": call.room_path,
        "topic": call.topic,
        "message": call.message,
        "teacher_id": call.teacher_id,
        "status": call.status,
        "is_emergency": call.is_emergency,
    }
    if extra_data:
        payload.update(extra_data)

    notification = Notification.objects.create(
        user=user,
        type="call",
        title=title,
        content=content,
        data=payload,
    )
    try:
        from .consumers import send_notification_to_user
        async_to_sync(send_notification_to_user)(
            user.id,
            {
                "id": notification.notification_id,
                "type": "call",
                "title": title,
                "message": content,
                "icon": "phone-volume",
                "call_id": call.call_id,
                "room_url": call.room_url,
                "room_path": call.room_path,
            },
        )
    except Exception:
        pass
    return notification


def _user_has_busy_call(user):
    return LiveCallParticipant.objects.filter(
        user=user,
        status__in=["invited", "accepted"],
        live_call__status__in=["pending", "active"],
    ).exists()


def _call_status_meta(call, participant):
    accepted_count = call.participants.filter(status="accepted").count()
    invited_count = call.participants.filter(status="invited").count()
    rejected_count = call.participants.filter(status="rejected").count()
    is_other_side_joined = call.participants.exclude(user=participant.user).filter(status="accepted").exists()

    if call.status == "pending":
        if participant.role == "teacher" and invited_count:
            state_message = "تم إرسال الدعوة. النظام ينتظر رد الطلاب الآن."
        elif participant.role == "student" and is_other_side_joined:
            state_message = "الطرف الآخر جاهز. سيتم فتح الغرفة فور تثبيت الجلسة."
        else:
            state_message = "جارٍ الرنين للطرف الآخر الآن."
    elif call.status == "active":
        if is_other_side_joined:
            state_message = "الطرف الآخر داخل الاتصال الآن."
        else:
            state_message = "تم تفعيل الاتصال، والنظام ينتظر دخول باقي الأطراف."
    elif call.status == "ended":
        state_message = "انتهى الاتصال."
    elif call.status == "cancelled":
        state_message = "تم إلغاء الاتصال."
    elif call.status == "rejected":
        state_message = "تم رفض الاتصال."
    else:
        state_message = "حالة الاتصال قيد التحديث."

    return {
        "status_label": call.get_status_display(),
        "state_message": state_message,
        "accepted_count": accepted_count,
        "invited_count": invited_count,
        "rejected_count": rejected_count,
        "is_other_side_joined": is_other_side_joined,
    }


@teacher_required
def teacher_live_calls(request):
    teacher_profile = get_object_or_404(TeacherProfile, user=request.user)
    candidate_students = _candidate_students_for_teacher(teacher_profile)

    if request.method == "POST":
        selected_ids = request.POST.getlist("student_ids")
        topic = request.POST.get("topic", "").strip()
        message_text = request.POST.get("message", "").strip()

        if not selected_ids:
            messages.error(request, "اختر طالباً واحداً على الأقل لبدء الاتصال المباشر.")
            return redirect("notifications:teacher_live_calls")

        selected_students = [student for student in candidate_students if str(student.user_id) in selected_ids]
        if not selected_students:
            messages.error(request, "الطلاب المحددون غير متاحين لهذا المعلم.")
            return redirect("notifications:teacher_live_calls")

        available_students = []
        busy_students = []
        for student in selected_students:
            if _user_has_busy_call(student.user):
                busy_students.append(student.user.get_full_name() or student.user.email)
            else:
                available_students.append(student)

        if not available_students:
            messages.error(request, "كل الطلاب المحددين مشغولون حالياً باتصالات أخرى.")
            return redirect("notifications:teacher_live_calls")

        with transaction.atomic():
            call_uuid = uuid.uuid4()
            room_name = _build_call_room(call_uuid)
            call = LiveCall.objects.create(
                uuid=call_uuid,
                initiated_by=request.user,
                teacher=request.user,
                topic=topic or "اتصال مباشر طارئ",
                message=message_text or "يرجى الانضمام إلى الاتصال المباشر حالاً.",
                room_name=room_name,
                room_url="http://local-call-pending.invalid/",
                status="pending",
                is_emergency=True,
            )
            room_path, room_url = _build_local_call_urls(request, call)
            call.room_path = room_path
            call.room_url = room_url
            call.save(update_fields=["room_path", "room_url"])

            LiveCallParticipant.objects.create(
                live_call=call,
                user=request.user,
                role="teacher",
                status="accepted",
                responded_at=timezone.now(),
            )

            for student in available_students:
                LiveCallParticipant.objects.create(
                    live_call=call,
                    user=student.user,
                    role="student",
                    status="invited",
                )
                _create_call_notification(
                    student.user,
                    "اتصال مباشر وارد",
                    f"لديك اتصال مباشر طارئ من المعلم {request.user.get_full_name() or request.user.email}.",
                    call,
                    extra_data={
                        "direction": "incoming",
                        "caller_name": request.user.get_full_name() or request.user.email,
                        "redirect_path": room_path,
                    },
                )

        if busy_students:
            messages.warning(request, f"تم تجاوز الطلاب المشغولين حالياً: {', '.join(busy_students)}")

        messages.success(request, "تم إرسال دعوة الاتصال المباشر إلى الطلاب المحددين.")
        return redirect("notifications:live_call_room", call_id=call.call_id)

    participant_prefetch = Prefetch(
        "participants",
        queryset=LiveCallParticipant.objects.select_related("user").order_by("role", "created_at"),
    )
    live_calls_queryset = LiveCall.objects.filter(
        teacher=request.user,
        archived_by_initiator=False,
    ).prefetch_related(participant_prefetch).order_by("-created_at")
    page_obj, pagination_query = _paginate_queryset(request, live_calls_queryset, per_page=8, page_param="calls_page")
    return render(
        request,
        "notifications/teacher_live_calls.html",
        {
            "candidate_students": candidate_students,
            "live_calls": page_obj.object_list,
            "live_calls_page_obj": page_obj,
            "live_calls_pagination_query": pagination_query,
            "live_calls_total_count": live_calls_queryset.count(),
        },
    )


@student_required
def student_live_calls(request):
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    candidate_teachers = _candidate_teachers_for_student(student_profile)

    if request.method == "POST":
        teacher_id = request.POST.get("teacher_id")
        topic = request.POST.get("topic", "").strip()
        message_text = request.POST.get("message", "").strip()

        selected_teacher = next((teacher for teacher in candidate_teachers if str(teacher.user_id) == str(teacher_id)), None)
        if not selected_teacher:
            messages.error(request, "اختر أستاذاً واحداً صحيحاً لبدء الاتصال.")
            return redirect("notifications:student_live_calls")

        if _user_has_busy_call(request.user):
            messages.error(request, "لديك اتصال مباشر قائم أو وارد حالياً. أنهِه أولاً قبل بدء اتصال جديد.")
            return redirect("notifications:student_live_calls")

        if _user_has_busy_call(selected_teacher.user):
            messages.error(request, "الأستاذ المحدد مشغول حالياً باتصال مباشر آخر.")
            return redirect("notifications:student_live_calls")

        with transaction.atomic():
            call_uuid = uuid.uuid4()
            room_name = _build_call_room(call_uuid)
            call = LiveCall.objects.create(
                uuid=call_uuid,
                initiated_by=request.user,
                teacher=selected_teacher.user,
                topic=topic or "طلب اتصال مباشر",
                message=message_text or "أحتاج إلى تواصل مباشر عاجل.",
                room_name=room_name,
                room_url="http://local-call-pending.invalid/",
                status="pending",
                is_emergency=True,
            )
            room_path, room_url = _build_local_call_urls(request, call)
            call.room_path = room_path
            call.room_url = room_url
            call.save(update_fields=["room_path", "room_url"])

            LiveCallParticipant.objects.create(
                live_call=call,
                user=request.user,
                role="student",
                status="accepted",
                responded_at=timezone.now(),
            )
            LiveCallParticipant.objects.create(
                live_call=call,
                user=selected_teacher.user,
                role="teacher",
                status="invited",
            )

            _create_call_notification(
                selected_teacher.user,
                "طلب اتصال مباشر من طالب",
                f"لديك طلب اتصال مباشر من الطالب {request.user.get_full_name() or request.user.email}.",
                call,
                extra_data={
                    "direction": "incoming",
                    "caller_name": request.user.get_full_name() or request.user.email,
                    "redirect_path": room_path,
                },
            )

        messages.success(request, "تم إرسال طلب الاتصال إلى الأستاذ المحدد.")
        return redirect("notifications:student_live_calls")

    incoming_calls_queryset = LiveCallParticipant.objects.filter(
        user=request.user,
        status="invited",
        live_call__status__in=["pending", "active"],
    ).select_related("live_call", "live_call__initiated_by", "live_call__teacher")
    incoming_page_obj, incoming_pagination_query = _paginate_queryset(
        request,
        incoming_calls_queryset.order_by("-live_call__created_at"),
        per_page=6,
        page_param="incoming_page",
    )
    outgoing_calls_queryset = LiveCall.objects.filter(
        initiated_by=request.user,
        archived_by_initiator=False,
    ).prefetch_related(
        Prefetch(
            "participants",
            queryset=LiveCallParticipant.objects.select_related("user").order_by("role", "created_at"),
        )
    ).order_by("-created_at")
    outgoing_page_obj, outgoing_pagination_query = _paginate_queryset(
        request,
        outgoing_calls_queryset,
        per_page=8,
        page_param="outgoing_page",
    )

    return render(
        request,
        "notifications/student_live_calls.html",
        {
            "candidate_teachers": candidate_teachers,
            "incoming_calls": incoming_page_obj.object_list,
            "outgoing_calls": outgoing_page_obj.object_list,
            "incoming_page_obj": incoming_page_obj,
            "outgoing_page_obj": outgoing_page_obj,
            "incoming_pagination_query": incoming_pagination_query,
            "outgoing_pagination_query": outgoing_pagination_query,
            "incoming_total_count": incoming_calls_queryset.count(),
            "outgoing_total_count": outgoing_calls_queryset.count(),
        },
    )


@login_required
@require_POST
def respond_live_call(request, call_id, action):
    call = get_object_or_404(LiveCall, call_id=call_id)
    participant = get_object_or_404(LiveCallParticipant, live_call=call, user=request.user)
    redirect_url = redirect("notifications:teacher_live_calls" if request.user.is_teacher() else "notifications:student_live_calls").url

    if action not in {"accept", "reject", "cancel", "end"}:
        if _request_prefers_json(request):
            return JsonResponse({"success": False, "error": "إجراء غير صالح."}, status=400)
        messages.error(request, "إجراء غير صالح.")
        return redirect("notifications:notification_list")

    if action == "accept":
        if request.user.is_student():
            other_active_teacher_calls = LiveCallParticipant.objects.filter(
                user=request.user,
                role="student",
                status="accepted",
                live_call__status__in=["pending", "active"],
            ).exclude(live_call=call).exists()
            if other_active_teacher_calls:
                if _request_prefers_json(request):
                    return JsonResponse({"success": False, "error": "لا يمكنك قبول أكثر من اتصال أستاذ واحد في الوقت نفسه."}, status=400)
                messages.error(request, "لا يمكنك قبول أكثر من اتصال أستاذ واحد في الوقت نفسه.")
                return redirect("notifications:student_live_calls")
        participant.status = "accepted"
        participant.responded_at = timezone.now()
        participant.left_at = None
        participant.save(update_fields=["status", "responded_at", "left_at"])
        if call.status == "pending":
            call.status = "active"
            call.answered_at = timezone.now()
            call.save(update_fields=["status", "answered_at"])
        Notification.objects.filter(user=request.user, type="call", data__call_id=call.call_id, is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )
        _create_call_notification(
            call.initiated_by,
            "تم قبول الاتصال",
            f"قام {request.user.get_full_name() or request.user.email} بقبول الاتصال المباشر.",
            call,
            extra_data={"direction": "update", "redirect_path": call.room_path},
        )
        if _request_prefers_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "action": "accept",
                    "redirect_url": reverse("notifications:live_call_room", args=[call.call_id]),
                    "message": "تم قبول الاتصال. يمكنك الانضمام الآن.",
                }
            )
        messages.success(request, "تم قبول الاتصال. يمكنك الانضمام الآن.")
        return redirect("notifications:live_call_room", call_id=call.call_id)

    if action == "reject":
        participant.status = "rejected"
        participant.responded_at = timezone.now()
        participant.left_at = timezone.now()
        participant.save(update_fields=["status", "responded_at", "left_at"])
        Notification.objects.filter(user=request.user, type="call", data__call_id=call.call_id).delete()
        remaining_open_participants = call.participants.exclude(user=call.initiated_by).exclude(user=request.user).filter(
            status__in=["invited", "accepted"]
        ).exists()
        if not remaining_open_participants:
            call.status = "rejected"
            call.end_reason = "تم رفض الاتصال من الطرف الآخر."
            call.ended_at = timezone.now()
            call.save(update_fields=["status", "end_reason", "ended_at"])
        _create_call_notification(
            call.initiated_by,
            "تم رفض الاتصال",
            f"قام {request.user.get_full_name() or request.user.email} برفض الاتصال المباشر.",
            call,
            extra_data={
                "direction": "update",
                "redirect_path": redirect_url,
                "actor_name": request.user.get_full_name() or request.user.email,
                "reason": "تم رفض الاتصال من الطرف الآخر.",
            },
        )
        _send_system_message(
            request.user,
            call.initiated_by,
            "تم رفض الاتصال المباشر",
            f"قام {request.user.get_full_name() or request.user.email} برفض الاتصال المباشر على موضوع: {call.topic or 'بدون عنوان'}.",
        )
        if _request_prefers_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "action": "reject",
                    "redirect_url": redirect_url,
                    "message": "تم رفض الاتصال.",
                    "remove_call_id": call.call_id,
                }
            )
        messages.info(request, "تم رفض الاتصال.")
        return redirect(redirect_url)

    if action == "cancel":
        if request.user != call.initiated_by:
            if _request_prefers_json(request):
                return JsonResponse({"success": False, "error": "فقط منشئ الاتصال يمكنه إلغاءه."}, status=403)
            messages.error(request, "فقط منشئ الاتصال يمكنه إلغاءه.")
            return redirect("notifications:notification_list")
        reason = (request.POST.get("reason") or "تم إلغاء الاتصال من الطرف الآخر.").strip()
        participant.status = "cancelled"
        participant.responded_at = timezone.now()
        participant.left_at = timezone.now()
        participant.save(update_fields=["status", "responded_at", "left_at"])
        call.status = "cancelled"
        call.ended_at = timezone.now()
        call.end_reason = reason
        call.save(update_fields=["status", "ended_at", "end_reason"])
        call.participants.exclude(user=request.user).update(status="cancelled", responded_at=timezone.now(), left_at=timezone.now())
        for participant_user_id in call.participants.exclude(user=request.user).values_list("user_id", flat=True):
            _create_call_notification(
                User.objects.get(id=participant_user_id),
                "تم إنهاء الاتصال",
                f"تم إنهاء الاتصال من الطرف الآخر. السبب: {reason}",
                call,
                extra_data={"direction": "ended", "reason": reason, "redirect_path": redirect_url},
            )
        if _request_prefers_json(request):
            return JsonResponse({"success": True, "action": "cancel", "redirect_url": redirect_url, "reason": reason})
        messages.info(request, "تم إلغاء الاتصال.")
        return redirect(redirect_url)

    if action == "end":
        reason = (request.POST.get("reason") or "تم إنهاء الاتصال من الطرف الآخر.").strip()
        participant.status = "cancelled"
        participant.responded_at = timezone.now()
        participant.left_at = timezone.now()
        participant.save(update_fields=["status", "responded_at", "left_at"])
        call.status = "ended"
        call.ended_at = timezone.now()
        call.end_reason = reason
        call.save(update_fields=["status", "ended_at", "end_reason"])
        call.participants.exclude(user=request.user).update(status="cancelled", responded_at=timezone.now(), left_at=timezone.now())
        for participant_user_id in call.participants.exclude(user=request.user).values_list("user_id", flat=True):
            _create_call_notification(
                User.objects.get(id=participant_user_id),
                "تم قطع الاتصال",
                f"لقد تم قطع الاتصال بسبب: {reason}",
                call,
                extra_data={"direction": "ended", "reason": reason, "redirect_path": redirect_url},
            )
        if _request_prefers_json(request):
            return JsonResponse({"success": True, "action": "end", "redirect_url": redirect_url, "reason": reason})
        messages.info(request, "تم إنهاء الاتصال المباشر.")
        return redirect(redirect_url)


@login_required
def live_call_room(request, call_id):
    call = get_object_or_404(LiveCall.objects.select_related("initiated_by", "teacher"), call_id=call_id)
    participant = get_object_or_404(LiveCallParticipant, live_call=call, user=request.user)
    redirect_url = redirect("notifications:teacher_live_calls" if request.user.is_teacher() else "notifications:student_live_calls").url

    if participant.status not in ["accepted", "invited"] and request.user != call.initiated_by:
        messages.error(request, "لا يمكنك الانضمام إلى هذه الغرفة.")
        return redirect("notifications:notification_list")

    if participant.status == "invited":
        participant.status = "accepted"
        participant.responded_at = timezone.now()
        participant.save(update_fields=["status", "responded_at"])
        if call.status == "pending":
            call.status = "active"
            call.answered_at = timezone.now()
            call.save(update_fields=["status", "answered_at"])

    return render(
        request,
        "notifications/live_call_room.html",
        {
            "call": call,
            "participants": call.participants.select_related("user").order_by("role", "created_at"),
            **_webrtc_room_context(call),
            "redirect_url": redirect_url,
            "current_user_id": request.user.id,
            "localhost_room_hint_url": _localhost_room_hint(request),
        },
    )


@login_required
def incoming_call_alerts(request):
    pending_calls = LiveCallParticipant.objects.filter(
        user=request.user,
        status="invited",
        live_call__status__in=["pending", "active"],
    ).select_related("live_call", "live_call__initiated_by")

    data = []
    for participant in pending_calls:
        call = participant.live_call
        data.append(
            {
                "call_id": call.call_id,
                "title": call.topic or "اتصال مباشر",
                "message": call.message or "",
                "caller_name": call.initiated_by.get_full_name() or call.initiated_by.email,
                "caller_avatar": call.initiated_by.avatar.url if call.initiated_by.avatar else "",
                "created_at": timezone.localtime(call.created_at).strftime("%Y-%m-%d %H:%M"),
                "accept_url": redirect("notifications:respond_live_call", call_id=call.call_id, action="accept").url,
                "reject_url": redirect("notifications:respond_live_call", call_id=call.call_id, action="reject").url,
                "room_url": redirect("notifications:live_call_room", call_id=call.call_id).url,
            }
        )
    return JsonResponse({"calls": data})


@login_required
def live_call_status(request, call_id):
    call = get_object_or_404(LiveCall, call_id=call_id)
    participant = get_object_or_404(LiveCallParticipant, live_call=call, user=request.user)
    meta = _call_status_meta(call, participant)
    connected_count = call.participants.filter(joined_at__isnull=False).count()

    # Ensure the current accepted participant is not shown as zero before WebSocket presence is established.
    if connected_count == 0 and participant.status == "accepted":
        connected_count = 1

    return JsonResponse(
        {
            "call_id": call.call_id,
            "status": call.status,
            "status_label": meta["status_label"],
            "state_message": meta["state_message"],
            "reason": call.end_reason or "",
            "redirect_url": redirect(
                "notifications:teacher_live_calls" if request.user.is_teacher() else "notifications:student_live_calls"
            ).url,
            "participant_status": participant.status,
            "accepted_count": meta["accepted_count"],
            "invited_count": meta["invited_count"],
            "rejected_count": meta["rejected_count"],
            "is_other_side_joined": meta["is_other_side_joined"],
            "connected_count": connected_count,
        }
    )


@login_required
@require_POST
def archive_live_call(request, call_id):
    call = get_object_or_404(LiveCall, call_id=call_id)
    if request.user != call.initiated_by:
        if _request_prefers_json(request):
            return JsonResponse({"success": False, "error": "فقط منشئ الاتصال يمكنه حذف السجل من قائمته."}, status=403)
        messages.error(request, "فقط منشئ الاتصال يمكنه حذف السجل من قائمته.")
        return redirect("notifications:notification_list")

    if call.status in {"pending", "active"}:
        if _request_prefers_json(request):
            return JsonResponse({"success": False, "error": "لا يمكن حذف سجل اتصال ما زال نشطاً."}, status=400)
        messages.error(request, "لا يمكن حذف سجل اتصال ما زال نشطاً.")
        return redirect("notifications:teacher_live_calls" if request.user.is_teacher() else "notifications:student_live_calls")

    call.archived_by_initiator = True
    call.save(update_fields=["archived_by_initiator"])
    if _request_prefers_json(request):
        return JsonResponse({"success": True, "call_id": call.call_id, "message": "تم حذف سجل الاتصال من قائمتك."})
    messages.success(request, "تم حذف سجل الاتصال من قائمتك.")
    return redirect("notifications:teacher_live_calls" if request.user.is_teacher() else "notifications:student_live_calls")
