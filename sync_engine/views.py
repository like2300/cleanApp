from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .cron import SyncDataCronJob
from .router import SyncRouter

@login_required
def manual_sync(request):
    """Combined Sync (Push then Pull)"""
    try:
        SyncRouter.reset_cache()
        sync_job = SyncDataCronJob()
        sync_job.do()
        messages.success(request, "Synchronisation complète terminée.")
    except Exception as e:
        messages.error(request, f"Échec de la synchronisation : {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def push_to_cloud(request):
    """Only Push Local -> Cloud"""
    try:
        SyncRouter.reset_cache()
        sync_job = SyncDataCronJob()
        sync_job.push_local_changes()
        messages.success(request, "Données envoyées au cloud avec succès.")
    except Exception as e:
        messages.error(request, f"Échec de l'envoi : {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def pull_from_cloud(request):
    """Only Pull Cloud -> Local (Last Update Wins)"""
    try:
        SyncRouter.reset_cache()
        sync_job = SyncDataCronJob()
        sync_job.pull_cloud_changes()
        messages.success(request, "Données récupérées du cloud avec succès.")
    except Exception as e:
        messages.error(request, f"Échec de la récupération : {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def force_pull_from_cloud(request):
    """Force Pull Cloud -> Local (Overwrite everything)"""
    try:
        SyncRouter.reset_cache()
        sync_job = SyncDataCronJob()
        sync_job.pull_cloud_changes(force=True)
        messages.success(request, "Récupération forcée terminée. La base locale a été mise à jour avec les données du cloud.")
    except Exception as e:
        messages.error(request, f"Échec de la récupération forcée : {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

@login_required
def reconnect_cloud(request):
    """Manually trigger a connectivity re-check"""
    SyncRouter.reset_cache()
    from .router import SyncRouter as Router
    router = SyncRouter()
    is_online = router._check_cloud_connectivity()
    
    if is_online:
        messages.success(request, "Connexion au cloud rétablie !")
    else:
        messages.warning(request, "Le cloud est toujours injoignable. Mode hors-ligne maintenu.")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
