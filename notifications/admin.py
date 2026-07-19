from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('title', 'user', 'is_read', 'created_at', 'synced')
    list_filter = ('is_read', 'synced')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('uuid', 'updated_at')
