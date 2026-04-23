import json
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Payment
from .forms import PaymentForm
from .payment_gateways import PaymentProcessor
from bookings.models import Booking
from courses.models import Course, Enrollment
from accounts.models import StudentProfile

@login_required
def payment_list(request):
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'payments': payments,
        'payment_count': payments.count(),
        'completed_count': payments.filter(status='completed').count(),
        'latest_payment_at': payments.first().created_at if payments.exists() else None,
    }
    return render(request, 'payments/payment_list.html', context)


@login_required
def course_checkout(request, course_id):
    course = get_object_or_404(Course.objects.select_related("teacher__user"), course_id=course_id, status="published")

    if not course.price or Decimal(course.price) <= 0:
        return redirect("courses:enroll_course", course_id=course.course_id)

    student_profile = get_object_or_404(StudentProfile, user=request.user)
    enrollment, _ = Enrollment.objects.get_or_create(
        student=student_profile,
        course=course,
        defaults={
            "payment_status": "pending",
            "status": "active",
        },
    )

    if enrollment.payment_status == "paid":
        messages.info(request, "هذا الكورس مدفوع بالفعل ومفعل على حسابك.")
        return redirect("courses:course_detail", course_id=course.course_id)

    context = {
        "course": course,
        "amount": course.price,
        "currency": course.currency,
        "discount": None,
        "enrollment_id": enrollment.enrollment_id,
        "booking_id": "",
        "stripe_publishable_key": getattr(settings, "STRIPE_PUBLISHABLE_KEY", ""),
        "moyasar_publishable_key": getattr(settings, "MOYASAR_PUBLISHABLE_KEY", ""),
    }
    return render(request, "payments/payment_checkout.html", context)

@login_required
def payment_detail(request, payment_uuid):
    payment = get_object_or_404(Payment, uuid=payment_uuid, user=request.user)
    return render(request, 'payments/payment_detail.html', {'payment': payment})


@login_required
@require_POST
def create_intent(request):
    payload = json.loads(request.body or "{}")
    gateway_name = payload.get("gateway", "stripe")
    enrollment_id = payload.get("enrollment_id")
    booking_id = payload.get("booking_id")

    enrollment = None
    booking = None
    amount = Decimal(str(payload.get("amount", "0")))
    currency = payload.get("currency", "SAR")

    if enrollment_id:
        enrollment = get_object_or_404(
            Enrollment.objects.select_related("course", "student__user"),
            enrollment_id=enrollment_id,
            student__user=request.user,
        )
        amount = enrollment.course.price or amount
        currency = enrollment.course.currency or currency
    elif booking_id:
        booking = get_object_or_404(Booking, booking_id=booking_id, student__user=request.user)

    processor = PaymentProcessor(gateway_name)

    if not processor.gateway.is_configured:
        payment = Payment.objects.create(
            user=request.user,
            booking=booking,
            enrollment=enrollment,
            amount=amount,
            currency=currency,
            payment_method="credit_card",
            payment_gateway=f"{gateway_name}_demo",
            transaction_id=f"demo_{timezone.now().timestamp()}",
            status="processing",
        )
        return JsonResponse(
            {
                "success": True,
                "payment_id": str(payment.uuid),
                "demo_mode": True,
                "message": "بوابة الدفع غير مهيأة، تم تفعيل وضع الاختبار المحلي.",
            }
        )

    result = processor.process_payment(
        user=request.user,
        amount=amount,
        currency=currency,
        payment_method="credit_card",
        metadata={
            "enrollment_id": enrollment.enrollment_id if enrollment else None,
            "booking_id": booking.booking_id if booking else None,
            "description": f"EduVerse payment for {enrollment.course.title if enrollment else 'booking'}",
            "callback_url": request.build_absolute_uri("/payments/success/"),
        },
    )

    if not result.get("success"):
        return JsonResponse({"success": False, "error": result.get("error", "تعذر إنشاء عملية الدفع.")}, status=400)

    payment = result["payment"]
    gateway_response = result["gateway_response"]
    return JsonResponse(
        {
            "success": True,
            "payment_id": str(payment.uuid),
            "client_secret": gateway_response.get("client_secret", ""),
            "payment_url": gateway_response.get("payment_url", ""),
            "demo_mode": False,
        }
    )


@login_required
@require_POST
def confirm_payment(request, payment_id):
    payment = get_object_or_404(Payment, uuid=payment_id, user=request.user)

    if payment.payment_gateway and payment.payment_gateway.endswith("_demo"):
        payment.status = "completed"
        payment.save(update_fields=["status", "updated_at"])
        if payment.enrollment:
            payment.enrollment.payment_status = "paid"
            payment.enrollment.amount_paid = payment.amount
            payment.enrollment.save(update_fields=["payment_status", "amount_paid"])
        return JsonResponse({"success": True, "redirect_url": _payment_redirect_url(payment)})

    processor = PaymentProcessor(payment.payment_gateway or "stripe")
    result = processor.confirm_payment_completion(payment.uuid)

    if not result.get("success"):
        return JsonResponse({"success": False, "error": result.get("error", "فشل تأكيد الدفع.")}, status=400)

    return JsonResponse({"success": True, "redirect_url": _payment_redirect_url(result["payment"])})

@login_required
def process_payment(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.user = request.user
            # For demo, assume it's for a booking or enrollment
            booking_id = request.POST.get('booking_id')
            enrollment_id = request.POST.get('enrollment_id')
            if booking_id:
                payment.booking = get_object_or_404(Booking, booking_id=booking_id, student__user=request.user)
            elif enrollment_id:
                payment.enrollment = get_object_or_404(Enrollment, enrollment_id=enrollment_id, student__user=request.user)
            payment.status = 'completed'  # Simulate successful payment
            payment.transaction_id = f"txn_{payment.uuid}"
            payment.save()
            messages.success(request, 'Payment processed successfully.')
            return redirect('payments:payment_detail', payment_uuid=payment.uuid)
    else:
        form = PaymentForm()
    return render(request, 'payments/process_payment.html', {'form': form})

@login_required
def payment_success(request):
    payment_id = request.GET.get("payment_id")
    if payment_id:
        payment = get_object_or_404(Payment, uuid=payment_id, user=request.user)
        if payment.status != "completed":
            processor = PaymentProcessor((payment.payment_gateway or "stripe").replace("_demo", ""))
            result = processor.confirm_payment_completion(payment.uuid)
            if result.get("success"):
                payment = result["payment"]
                messages.success(request, "تم الدفع بنجاح وتم تفعيل وصولك.")
            else:
                messages.error(request, result.get("error", "تعذر تأكيد عملية الدفع."))
                return redirect("payments:payment_failure")
        else:
            messages.success(request, "تم الدفع بنجاح.")
        return redirect(_payment_redirect_url(payment))

    messages.success(request, 'Payment was successful.')
    return redirect('payments:payment_list')

@login_required
def payment_failure(request):
    # Handle payment failure callback
    messages.error(request, 'Payment failed.')
    return redirect('payments:payment_list')

@login_required
def request_refund(request, payment_uuid):
    payment = get_object_or_404(Payment, uuid=payment_uuid, user=request.user)
    if payment.status == 'completed':
        payment.status = 'refunded'
        payment.refunded_amount = payment.amount
        payment.refund_date = timezone.now()
        payment.save()
        messages.success(request, 'Refund requested successfully.')
    return redirect('payments:payment_detail', payment_uuid=payment.uuid)


def _payment_redirect_url(payment):
    if payment.enrollment:
        return redirect("courses:course_detail", course_id=payment.enrollment.course.course_id).url
    if payment.booking:
        return redirect("bookings:student_booking_detail", booking_id=payment.booking.booking_id).url
    return redirect("payments:payment_list").url
