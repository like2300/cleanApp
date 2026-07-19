from .models import CompanySettings
from django.apps import apps
from sync_engine.models import SyncBaseModel
from django.conf import settings

def company_settings(request):
    # Count unsynced items
    unsynced_count = 0
    if request.user.is_authenticated and request.user.is_staff:
        for model in [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]:
            try:
                unsynced_count += model.objects.filter(synced=False).count()
            except:
                pass
    
    # Check current mode and connectivity
    mode = getattr(settings, 'LIVE_MODE', 'LOCAL')
    from sync_engine.router import SyncRouter
    router = SyncRouter()
    is_online = router._check_cloud_connectivity()
                
    return {
        'company': CompanySettings.get_settings(),
        'sync_status': unsynced_count == 0,
        'unsynced_count': unsynced_count,
        'live_mode': mode,
        'is_online': is_online
    }
