from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Invoice, Payment

@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ('uuid', 'client', 'amount', 'due_date', 'status', 'synced')
    list_filter = ('status', 'synced')
    search_fields = ('client__username', 'uuid')
    readonly_fields = ('uuid', 'updated_at')

@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('transaction_id', 'invoice', 'amount', 'paid_at', 'synced')
    list_filter = ('synced',)
    search_fields = ('transaction_id', 'invoice__uuid')
    readonly_fields = ('uuid', 'updated_at')
