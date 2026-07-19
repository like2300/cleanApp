#!/usr/bin/env python3
"""
Script pour corriger les doublons de usernames lors de l'import des clients.
Ajoute un suffixe unique si le username existe déjà.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from accounts.models import User
from business.models import Zone


def generate_unique_username(base_name):
    """Génère un username unique en ajoutant un suffixe si nécessaire."""
    if not base_name:
        return None

    # Nettoyer le nom
    name = " ".join(base_name.split()).title()
    username = name.replace(" ", "_")

    # Vérifier si le username existe déjà
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{name.replace(' ', '_')}_{counter}"
        counter += 1

    return username


from django.db.models import Count


def fix_duplicate_usernames():
    print("🔍 Correction des doublons de usernames...")

    # Récupérer tous les clients avec des doublons
    duplicate_users = (
        User.objects.values("username").annotate(count=Count("id")).filter(count__gt=1)
    )
    print(f"⚠️ {len(duplicate_users)} usernames en doublon détectés.")

    # Corriger les doublons
    for dup in duplicate_users:
        username = dup["username"]
        users = User.objects.filter(username=username)
        print(f"  ❌ {username} (trouvé {users.count()} fois)")

        for i, user in enumerate(users, 1):
            if i > 1:  # Ne pas modifier le premier
                new_username = generate_unique_username(user.username)
                if new_username and new_username != user.username:
                    print(f"    ✅ {user.username} → {new_username}")
                    user.username = new_username
                    user.save()

    # Vérifier les zones avec des clients
    for zone in Zone.objects.all():
        clients = User.objects.filter(zone=zone, role="CLIENT")
        print(f"\n📍 Zone {zone.name}: {clients.count()} clients")

        # Vérifier les doublons dans cette zone
        zone_duplicates = (
            clients.values("username").annotate(count=Count("id")).filter(count__gt=1)
        )
        if zone_duplicates.exists():
            print(f"  ⚠️ {len(zone_duplicates)} doublons dans cette zone")
            for dup in zone_duplicates:
                print(f"    ❌ {dup['username']} (trouvé {dup['count']} fois)")

    print("\n✅ Correction terminée !")


if __name__ == "__main__":
    fix_duplicate_usernames()
