from django.db import models
import uuid

class SyncBaseModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    synced = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    site_id = models.CharField(max_length=50, default='LOCAL_SITE')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from django.conf import settings
        if not self.site_id or self.site_id == 'LOCAL_SITE':
            self.site_id = getattr(settings, 'SITE_ID', 'LOCAL_SITE')
            
        if not kwargs.get('update_fields') or 'synced' not in kwargs.get('update_fields'):
            if not getattr(self, '_syncing', False):
                self.synced = False
        super().save(*args, **kwargs)

class DeletedRecord(models.Model):
    model_label = models.CharField(max_length=100)
    uuid = models.UUIDField()
    deleted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Deleted {self.model_label} - {self.uuid}"
