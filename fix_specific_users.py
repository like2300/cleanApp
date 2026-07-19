#!/usr/bin/env python

import os
import sys
import django

# Setup Django
sys.path.append('/Users/omerlinks/Desktop/project/CLEAN')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import User
from sync_engine.router import SyncRouter
from django.db import transaction

def fix_specific_users():
    """Fix the specific users that are failing to sync"""
    print("=== CORRECTION DES UTILISATEURS SPÉCIFIQUES ===")
    
    # Check connectivity
    router = SyncRouter()
    is_online = router._check_cloud_connectivity()
    print(f"Connectivité cloud: {'ONLINE' if is_online else 'OFFLINE'}")
    
    if not is_online:
        print("Impossible de corriger sans connexion cloud")
        return
    
    # Get the problematic users
    problematic_uuids = [
        '852f56b0-c0d1-480f-bbb8-ef91d7c2022e',
        '440bc373-2982-4c1f-ba5e-49e72831153b'
    ]
    
    for uuid_str in problematic_uuids:
        try:
            print(f"\n--- Traitement de l'utilisateur {uuid_str} ---")
            
            # Get local user
            local_user = User.objects.using('default').filter(uuid=uuid_str).first()
            if not local_user:
                print(f"Utilisateur local {uuid_str} non trouvé")
                continue
            
            # Get cloud user
            cloud_user = User.objects.using('cloud').filter(uuid=uuid_str).first()
            if not cloud_user:
                print(f"Utilisateur cloud {uuid_str} non trouvé - création...")
                # Create the user in cloud
                cloud_user_data = {
                    'username': local_user.username,
                    'email': local_user.email,
                    'role': local_user.role,
                    'registration_number': local_user.registration_number,
                    'phone_number': local_user.phone_number,
                    'phone_number_2': local_user.phone_number_2,
                    'address': local_user.address,
                    'uses_momo_payment': local_user.uses_momo_payment,
                    'fixed_due_date': local_user.fixed_due_date,
                    'is_active': local_user.is_active,
                    'first_name': local_user.first_name,
                    'last_name': local_user.last_name,
                    'date_joined': local_user.date_joined,
                    'uuid': local_user.uuid,
                    'site_id': local_user.site_id,
                    'synced': True  # Mark as synced immediately
                }
                
                # Handle foreign keys
                if local_user.quartier:
                    cloud_quartier = local_user.quartier.__class__.objects.using('cloud').filter(uuid=local_user.quartier.uuid).first()
                    if cloud_quartier:
                        cloud_user_data['quartier'] = cloud_quartier
                
                if local_user.zone:
                    cloud_zone = local_user.zone.__class__.objects.using('cloud').filter(uuid=local_user.zone.uuid).first()
                    if cloud_zone:
                        cloud_user_data['zone'] = cloud_zone
                
                # Create the user in cloud
                cloud_user = User.objects.using('cloud').create_user(**cloud_user_data)
                print(f"Utilisateur {uuid_str} créé dans le cloud")
            else:
                print(f"Utilisateur {uuid_str} existe déjà dans le cloud")
                
            # Now sync ManyToMany relationships
            print("Synchronisation des relations ManyToMany...")
            
            # Sync zones
            local_zones = local_user.zones.all()
            cloud_zones_to_add = []
            for zone in local_zones:
                cloud_zone = zone.__class__.objects.using('cloud').filter(uuid=zone.uuid).first()
                if cloud_zone:
                    cloud_zones_to_add.append(cloud_zone)
            
            if cloud_zones_to_add:
                cloud_user.zones.set(cloud_zones_to_add)
                print(f"Zones synchronisées: {[z.name for z in cloud_zones_to_add]}")
            
            # Mark both as synced
            local_user.synced = True
            local_user.save(using='default')
            
            cloud_user.synced = True
            cloud_user.save(using='cloud')
            
            print(f"✓ Utilisateur {uuid_str} synchronisé avec succès")
            
        except Exception as e:
            print(f"✗ Erreur avec {uuid_str}: {str(e)}")
            import traceback
            traceback.print_exc()

def main():
    fix_specific_users()

if __name__ == '__main__':
    main()