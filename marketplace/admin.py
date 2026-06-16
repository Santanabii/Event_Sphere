from django.contrib import admin
from .models import Listing, ResaleOrder


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ['seller', 'ticket', 'asking_price', 'status', 'listed_at']
    list_filter = ['status']
    search_fields = ['seller__email']


@admin.register(ResaleOrder)
class ResaleOrderAdmin(admin.ModelAdmin):
    list_display = ['buyer', 'amount_paid', 'platform_fee', 'seller_payout', 'completed_at']