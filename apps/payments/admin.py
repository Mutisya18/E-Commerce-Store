from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'amount', 'currency', 'status', 'flutterwave_tx_ref', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('order__order_number', 'flutterwave_tx_ref', 'flutterwave_tx_id')
    readonly_fields = ('created_at', 'updated_at', 'raw_webhook_payload')
