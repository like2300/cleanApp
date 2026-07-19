from django.apps import apps
from sync_engine.models import SyncBaseModel
from django.conf import settings

site_id = getattr(settings, 'SITE_ID', 'LOCAL_SITE')
sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]

for model in sync_models:
    updated = model.objects.using('default').filter(site_id='LOCAL_SITE').update(site_id=site_id, synced=False)
    if updated:
        print(f"Updated {updated} records for {model._meta.label} with site_id={site_id}")
