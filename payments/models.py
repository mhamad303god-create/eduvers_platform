from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from accounts.models import User
from bookings.models import Booking
from courses.models import Enrollment
import uuid


class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, blank=True, null=True)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='SAR')
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('credit_card', 'Credit Card'),
            ('bank_transfer', 'Bank Transfer'),
            ('wallet', 'Wallet'),
            ('apple_pay', 'Apple Pay'),
            ('google_pay', 'Google Pay'),
        ]
    )
    payment_gateway = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    failure_reason = models.TextField(blank=True, null=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refund_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')

    def __str__(self):
        return f"Payment {self.uuid} - {self.amount} {self.currency}"


class Wallet(models.Model):
    wallet_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='SAR')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Wallet')
        verbose_name_plural = _('Wallets')

    def __str__(self):
        return f"{self.user.email} - {self.balance} {self.currency}"


class WalletTransaction(models.Model):
    transaction_id = models.AutoField(primary_key=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    type = models.CharField(
        max_length=20,
        choices=[
            ('credit', 'Credit'),
            ('debit', 'Debit'),
            ('refund', 'Refund'),
            ('bonus', 'Bonus'),
        ]
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    reference_type = models.CharField(
        max_length=20,
        choices=[
            ('payment', 'Payment'),
            ('refund', 'Refund'),
            ('booking_payout', 'Booking Payout'),
            ('bonus', 'Bonus'),
            ('withdrawal', 'Withdrawal'),
        ],
        blank=True, null=True
    )
    reference_id = models.IntegerField(blank=True, null=True)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Wallet Transaction')
        verbose_name_plural = _('Wallet Transactions')

    def __str__(self):
        return f"{self.wallet.user.email} - {self.type} {self.amount}"
