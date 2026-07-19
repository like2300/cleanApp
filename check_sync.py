from django.apps import apps
from sync_engine.models import SyncBaseModel

sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]
total = 0
for m in sync_models:
    try:
        count = m.objects.using('default').filter(synced=False).count()
        total += count
        if count:
            print(f"{m._meta.label}: {count}")
    except Exception as e:
        print(f"Error checking {m._meta.label}: {e}")

print(f"Total unsynced: {total}")
