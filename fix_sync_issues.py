#!/usr/bin/env python

import os
import sys
import django

# Setup Django
sys.path.append('/Users/omerlinks/Desktop/project/CLEAN')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.apps import apps
from sync_engine.models import SyncBaseModel
from sync_engine.cron import SyncDataCronJob
from sync_engine.router import SyncRouter
import logging

logger = logging.getLogger(__name__)

def diagnose_sync_issues():
    """Diagnose synchronization issues"""
    print("=== DIAGNOSTIC DE SYNCHRONISATION ===")
    
    # Check connectivity
    router = SyncRouter()
    is_online = router._check_cloud_connectivity()
    print(f"Connectivité cloud: {'ONLINE' if is_online else 'OFFLINE'}")
    
    if not is_online:
        print("Impossible de diagnostiquer sans connexion cloud")
        return
    
    # Get all sync models
    sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]
    
    for model in sync_models:
        # Check for unsynced items
        unsynced_items = model.objects.using('default').filter(synced=False)
        print(f"\n{model._meta.verbose_name_plural} ({model._meta.label}):")
        print(f"  Non synchronisés: {unsynced_items.count()}")
        
        if unsynced_items.count() > 0:
            print(f"  Exemples: {[str(item) for item in unsynced_items[:3]]}")
            
            # Check if they exist in cloud
            for item in unsynced_items[:3]:
                cloud_exists = model.objects.using('cloud').filter(uuid=item.uuid).exists()
                print(f"    {item} -> Cloud: {'EXISTE' if cloud_exists else 'MANQUANT'}")
                
                # Check dependencies
                for field in model._meta.fields:
                    if field.is_relation and not field.many_to_many:
                        value = getattr(item, field.name)
                        if value and hasattr(value, 'uuid'):
                            related_model = field.related_model
                            related_uuid = value.uuid
                            cloud_related_exists = related_model.objects.using('cloud').filter(uuid=related_uuid).exists()
                            if not cloud_related_exists:
                                print(f"      Dépendance manquante: {related_model._meta.label} {related_uuid}")

def fix_missing_dependencies():
    """Fix missing dependencies by syncing them first"""
    print("\n=== CORRECTION DES DÉPENDANCES MANQUANTES ===")
    
    # Order matters: sync simpler models first
    sync_order = [
        'business.Zone',
        'business.Quartier', 
        'business.Position',
        'business.SubscriptionPlan',
        'accounts.User',
        'business.Subscription',
        'finance.Invoice',
        'finance.Payment',
        'notifications.Notification'
    ]
    
    router = SyncRouter()
    if not router._check_cloud_connectivity():
        print("Impossible de corriger sans connexion cloud")
        return
    
    for model_label in sync_order:
        try:
            model = apps.get_model(model_label)
            if issubclass(model, SyncBaseModel):
                unsynced_items = model.objects.using('default').filter(synced=False)
                if unsynced_items.exists():
                    print(f"Synchronisation de {model._meta.verbose_name_plural}...")
                    
                    for item in unsynced_items:
                        try:
                            # Check if all dependencies exist in cloud
                            dependencies_ok = True
                            for field in model._meta.fields:
                                if field.is_relation and not field.many_to_many:
                                    value = getattr(item, field.name)
                                    if value and hasattr(value, 'uuid'):
                                        related_model = field.related_model
                                        related_uuid = value.uuid
                                        cloud_related_exists = related_model.objects.using('cloud').filter(uuid=related_uuid).exists()
                                        if not cloud_related_exists:
                                            dependencies_ok = False
                                            print(f"  Dépendance manquante pour {item}: {related_model._meta.label} {related_uuid}")
                                            break
                            
                            if dependencies_ok:
                                # Try to sync this item
                                cloud_item = model.objects.using('cloud').filter(uuid=item.uuid).first()
                                
                                if cloud_item:
                                    # Update existing
                                    for f in model._meta.fields:
                                        if not f.primary_key:
                                            setattr(cloud_item, f.name, getattr(item, f.name))
                                    cloud_item.save(using='cloud')
                                    print(f"  Mis à jour: {item}")
                                else:
                                    # Create new
                                    data = {}
                                    for f in model._meta.fields:
                                        if not f.primary_key:
                                            data[f.name] = getattr(item, f.name)
                                    
                                    # Handle foreign keys
                                    for f in model._meta.fields:
                                        if f.is_relation and not f.many_to_many:
                                            value = getattr(item, f.name)
                                            if value and hasattr(value, 'uuid'):
                                                related_model = f.related_model
                                                cloud_related = related_model.objects.using('cloud').filter(uuid=value.uuid).first()
                                                if cloud_related:
                                                    data[f.name] = cloud_related
                                    
                                    cloud_item = model.objects.using('cloud').create(**data)
                                    print(f"  Créé: {item}")
                                
                                # Mark as synced
                                item.synced = True
                                item.save(using='default')
                                
                        except Exception as e:
                            print(f"  Échec pour {item}: {str(e)}")
        
        except Exception as e:
            print(f"Erreur avec {model_label}: {str(e)}")

def main():
    print("Démarrage du diagnostic et correction des problèmes de synchronisation...")
    
    diagnose_sync_issues()
    fix_missing_dependencies()
    
    print("\n=== SYNCHRONISATION COMPLÈTE ===")
    print("Veuillez vérifier les logs ci-dessus pour les erreurs résiduelles.")

if __name__ == '__main__':
    main()