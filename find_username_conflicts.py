#!/usr/bin/env python
"""
Script to find username conflicts between local and cloud databases.
Run this to identify users that need to be resolved.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from accounts.models import User
from django.db import connection

def get_usernames(db_alias):
    """Get all usernames from a specific database"""
    try:
        users = User.objects.using(db_alias).all()
        return {u.username.lower(): u for u in users if u.username}
    except Exception as e:
        print(f"Error accessing {db_alias} database: {e}")
        return {}

def main():
    print("Checking for username conflicts between local and cloud databases...")
    print("=" * 70)
    
    # Get usernames from both databases
    local_usernames = get_usernames('default')
    cloud_usernames = get_usernames('cloud')
    
    print(f"\nLocal database: {len(local_usernames)} users")
    print(f"Cloud database: {len(cloud_usernames)} users")
    
    # Find conflicts (same username, different UUID)
    conflicts = []
    for username_lower, local_user in local_usernames.items():
        if username_lower in cloud_usernames:
            cloud_user = cloud_usernames[username_lower]
            if local_user.uuid != cloud_user.uuid:
                conflicts.append({
                    'username': local_user.username,
                    'local_uuid': local_user.uuid,
                    'local_id': local_user.id,
                    'cloud_uuid': cloud_user.uuid,
                    'cloud_id': cloud_user.id,
                    'local_synced': local_user.synced,
                })
    
    print(f"\nFound {len(conflicts)} username conflicts:")
    print("-" * 70)
    
    for i, conflict in enumerate(conflicts, 1):
        print(f"\n{i}. Username: '{conflict['username']}'")
        print(f"   Local:  UUID={conflict['local_uuid']}, ID={conflict['local_id']}, Synced={conflict['local_synced']}")
        print(f"   Cloud:  UUID={conflict['cloud_uuid']}, ID={conflict['cloud_id']}")
        print(f"   → ACTION NEEDED: Merge or rename one of these users")
    
    if conflicts:
        print("\n" + "=" * 70)
        print("RECOMMENDED ACTIONS:")
        print("1. For each conflict, decide which user to keep")
        print("2. Either:")
        print("   a. Update the username on one user (e.g., add suffix)")
        print("   b. Delete the duplicate user")
        print("   c. If same person, update UUIDs to match")
        print("3. After resolving, run sync again")
    else:
        print("\n✓ No username conflicts found!")

if __name__ == '__main__':
    main()
