from django.contrib import admin
from .models import Payment, Wallet, WalletTransaction


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'user', 'amount', 'currency', 'status', 'payment_method')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('uuid', 'user__email')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'currency', 'is_active')
    list_filter = ('is_active', 'currency')
    search_fields = ('user__email',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'type', 'amount', 'balance_after', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('wallet__user__email',)
