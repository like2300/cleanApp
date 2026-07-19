import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.apps import apps
from sync_engine.models import SyncBaseModel

def compare():
    sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]
    
    print(f"{'Model':<30} | {'Local':<10} | {'Cloud':<10} | {'Status'}")
    print("-" * 70)
    
    for model in sync_models:
        label = model._meta.label
        local_count = model.objects.using('default').count()
        try:
            cloud_count = model.objects.using('cloud').count()
            
            # Check for specific diffs
            local_uuids = set(model.objects.using('default').values_list('uuid', flat=True))
            cloud_uuids = set(model.objects.using('cloud').values_list('uuid', flat=True))
            
            only_local = len(local_uuids - cloud_uuids)
            only_cloud = len(cloud_uuids - local_uuids)
            
            status = "OK"
            if only_local > 0 or only_cloud > 0:
                status = f"DIFF: +{only_local} local, +{only_cloud} cloud"
            
            print(f"{label:<30} | {local_count:<10} | {cloud_count:<10} | {status}")
            
        except Exception as e:
            print(f"{label:<30} | {local_count:<10} | {'ERROR':<10} | {str(e)}")

if __name__ == "__main__":
    compare()
