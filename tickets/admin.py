from django.contrib import admin
from .models import Ticket, MpesaTransaction


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['qr_token', 'owner', 'tier', 'status', 'purchase_price', 'issued_at']
    list_filter = ['status']
    search_fields = ['owner__email', 'qr_token']


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'amount', 'status', 'mpesa_receipt', 'created_at']
    list_filter = ['status']