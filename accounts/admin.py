from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AdminUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = AdminUserCreationForm
    ordering = ['email']
    list_display = ['email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_filter = ['is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Google sign-in', {'fields': ('google_id',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
