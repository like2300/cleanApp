#!/usr/bin/env python

import os
import sys
import django

# Setup Django
sys.path.append('/Users/omerlinks/Desktop/project/CLEAN')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.apps import apps
from accounts.models import User
from sync_engine.router import SyncRouter

def debug_problematic_users():
    """Debug the specific users that are failing to sync"""
    print("=== DEBUG DES UTILISATEURS PROBLÉMATIQUES ===")
    
    # Check connectivity
    router = SyncRouter()
    is_online = router._check_cloud_connectivity()
    print(f"Connectivité cloud: {'ONLINE' if is_online else 'OFFLINE'}")
    
    if not is_online:
        print("Impossible de déboguer sans connexion cloud")
        return
    
    # Get the problematic users
    problematic_uuids = [
        '852f56b0-c0d1-480f-bbb8-ef91d7c2022e',
        '440bc373-2982-4c1f-ba5e-49e72831153b'
    ]
    
    for uuid_str in problematic_uuids:
        try:
            # Get local user
            local_user = User.objects.using('default').filter(uuid=uuid_str).first()
            if not local_user:
                print(f"Utilisateur local {uuid_str} non trouvé")
                continue
            
            print(f"\n--- Utilisateur: {local_user} (UUID: {uuid_str}) ---")
            print(f"Nom d'utilisateur: {local_user.username}")
            print(f"Email: {local_user.email}")
            print(f"Rôle: {local_user.role}")
            print(f"Synchronisé: {local_user.synced}")
            print(f"Site ID: {local_user.site_id}")
            
            # Check if exists in cloud
            cloud_user = User.objects.using('cloud').filter(uuid=uuid_str).first()
            print(f"Existe dans le cloud: {cloud_user is not None}")
            
            if cloud_user:
                print(f"Cloud username: {cloud_user.username}")
                print(f"Cloud email: {cloud_user.email}")
                print(f"Cloud role: {cloud_user.role}")
                print(f"Cloud synced: {cloud_user.synced}")
                print(f"Cloud site_id: {cloud_user.site_id}")
                
                # Compare fields
                print("\nComparaison des champs:")
                for field in User._meta.fields:
                    if not field.primary_key and not field.name.startswith('_'):
                        local_val = getattr(local_user, field.name)
                        cloud_val = getattr(cloud_user, field.name)
                        if local_val != cloud_val:
                            print(f"  {field.name}: Local={local_val} vs Cloud={cloud_val}")
                
                # Check ManyToMany fields
                print("\nRelations ManyToMany:")
                for m2m_field in User._meta.many_to_many:
                    local_m2m = getattr(local_user, m2m_field.name).all()
                    cloud_m2m = getattr(cloud_user, m2m_field.name).all()
                    
                    local_uuids = set(getattr(item, 'uuid', None) for item in local_m2m)
                    cloud_uuids = set(getattr(item, 'uuid', None) for item in cloud_m2m)
                    
                    if local_uuids != cloud_uuids:
                        print(f"  {m2m_field.name}:")
                        print(f"    Local: {local_uuids}")
                        print(f"    Cloud: {cloud_uuids}")
                        print(f"    Différence: Ajouter {local_uuids - cloud_uuids}, Supprimer {cloud_uuids - local_uuids}")
                        
                        # Check if missing items exist in cloud
                        for uuid in local_uuids - cloud_uuids:
                            if uuid:
                                related_model = m2m_field.related_model
                                cloud_item = related_model.objects.using('cloud').filter(uuid=uuid).first()
                                print(f"      Item {uuid} dans cloud: {cloud_item is not None}")
            
        except Exception as e:
            print(f"Erreur avec {uuid_str}: {str(e)}")
            import traceback
            traceback.print_exc()

def main():
    debug_problematic_users()

if __name__ == '__main__':
    main()