#!/usr/bin/env python3
"""
Script pour corriger les doublons de usernames sur le cloud.
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

from django.db.models import Count

from accounts.models import User


def generate_unique_username(base_name):
    """Génère un username unique en ajoutant un suffixe si nécessaire."""
    if not base_name:
        return None

    name = " ".join(base_name.split()).title()
    username = name.replace(" ", "_")

    # Vérifier si le username existe déjà sur le cloud
    counter = 1
    while User.objects.using("cloud").filter(username=username).exists():
        username = f"{name.replace(' ', '_')}_{counter}"
        counter += 1

    return username


def fix_cloud_duplicate_usernames():
    print("🔍 Correction des doublons de usernames sur le cloud...")

    # Récupérer les usernames en doublon sur le cloud
    duplicate_usernames = (
        User.objects.using("cloud")
        .values("username")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )

    print(f"⚠️ {len(duplicate_usernames)} usernames en doublon détectés sur le cloud.")

    for dup in duplicate_usernames:
        username = dup["username"]
        users = User.objects.using("cloud").filter(username=username)
        print(f"  ❌ {username} (trouvé {users.count()} fois)")

        for i, user in enumerate(users, 1):
            if i > 1:  # Ne pas modifier le premier
                new_username = generate_unique_username(user.username)
                if new_username and new_username != user.username:
                    print(f"    ✅ {user.username} → {new_username}")
                    user.username = new_username
                    user.save(using="cloud")

    print("✅ Correction terminée !")


if __name__ == "__main__":
    fix_cloud_duplicate_usernames()
