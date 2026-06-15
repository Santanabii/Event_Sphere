from django.contrib import admin
from .models import Event, TicketTier


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'organiser', 'venue', 'date', 'status']
    list_filter = ['status', 'resale_allowed']
    search_fields = ['title', 'venue']


@admin.register(TicketTier)
class TicketTierAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'price', 'quantity', 'quantity_sold']
