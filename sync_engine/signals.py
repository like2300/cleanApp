from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import SyncBaseModel, DeletedRecord

@receiver(post_delete)
def track_deletions(sender, instance, **kwargs):
    if issubclass(sender, SyncBaseModel):
        # Skip if we are deleting locally as part of a PULL from cloud
        if getattr(instance, '_syncing', False):
            return

        if instance._state.db == 'default':
            DeletedRecord.objects.create(
                model_label=sender._meta.label,
                uuid=instance.uuid
            )
