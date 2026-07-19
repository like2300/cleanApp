from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import User, CompanySettings

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ('username', 'email', 'role', 'site_id', 'synced')
    list_filter = ('role', 'synced', 'site_id')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Sync & Role', {'fields': ('role', 'site_id', 'synced', 'uuid', 'zone')}),
    )
    readonly_fields = ('uuid', 'updated_at')

@admin.register(CompanySettings)
class CompanySettingsAdmin(ModelAdmin):
    list_display = ('name', 'email', 'phone')

    def has_add_permission(self, request):
        # Only one settings instance allowed
        return not CompanySettings.objects.exists()
