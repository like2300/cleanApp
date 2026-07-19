from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Zone, Employee, SubscriptionPlan, Subscription

@admin.register(Zone)
class ZoneAdmin(ModelAdmin):
    list_display = ('name', 'site_id', 'synced', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('uuid', 'updated_at')

@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = ('first_name', 'last_name', 'position', 'zone', 'salary', 'synced')
    list_filter = ('zone', 'synced', 'position')
    search_fields = ('first_name', 'last_name', 'position')
    readonly_fields = ('uuid', 'updated_at')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'synced')
    readonly_fields = ('uuid', 'updated_at')

@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('client', 'plan', 'start_date', 'end_date', 'is_active', 'synced')
    list_filter = ('is_active', 'synced', 'plan')
    readonly_fields = ('uuid', 'updated_at')
