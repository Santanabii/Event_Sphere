from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'username', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('EventSphere', {'fields': ('role', 'phone_number')}),
    )