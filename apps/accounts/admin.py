from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, SafetyInfo, TrustedContact, Pet, OTPVerification, BlacklistedToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'name', 'phone_number', 'is_active', 'is_staff', 'created_at']
    list_filter = ['is_active', 'is_staff', 'is_superuser']
    search_fields = ['email', 'name', 'phone_number']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )


@admin.register(SafetyInfo)
class SafetyInfoAdmin(admin.ModelAdmin):
    list_display = ['user', 'living_status', 'check_in_time', 'created_at']
    list_filter = ['living_status']
    search_fields = ['user__email', 'home_address']


@admin.register(TrustedContact)
class TrustedContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'relationship', 'phone_number', 'user', 'created_at']
    search_fields = ['name', 'phone_number', 'user__email']


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ['pet_name', 'breed', 'age', 'user', 'created_at']
    search_fields = ['pet_name', 'breed', 'user__email']


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'otp', 'is_verified', 'created_at', 'expires_at']
    list_filter = ['is_verified']
    search_fields = ['email']


@admin.register(BlacklistedToken)
class BlacklistedTokenAdmin(admin.ModelAdmin):
    list_display = ['blacklisted_at']
    list_filter = ['blacklisted_at']
