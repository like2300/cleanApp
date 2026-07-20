#!/usr/bin/env python3
"""
Cree les plans tarifaires (offres) DIRECTEMENT dans la base en ligne (cloud),
sans passer par la base locale.

Les plans sont cree avec un UUID constant (par nom) et synced=True, afin
d'etre immediatement disponibles pour la version web (AlwaysData) qui lit le
cloud. La version locale (desktop) les recuperera automatiquement via le pull
du moteur de synchronisation.

Plans creees :
  Basic            -> 2 000 FCFA
  Basic + bac 30L  -> 3 000 FCFA
  Standard         -> 3 000 FCFA
  Standard + bac 30L -> 3 500 FCFA
  Standard + bac 60L -> 5 000 FCFA
  3plus            -> 3 500 FCFA
  Entreprise       -> 3 500 FCFA

Usage :
  python scripts/create_plans_cloud.py            # cree/met a jour dans le cloud
  python scripts/create_plans_cloud.py --dry-run  # affiche sans ecrire
"""

import os
import sys
import uuid as uuid_lib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from business.models import SubscriptionPlan

# UUID constants par plan (evite les doublons si le script est relance)
PLANS = [
    {"key": "basic", "name": "Basic", "price": 2000, "desc": "Basic - 2000 FCFA"},
    {
        "key": "basic_bac30",
        "name": "Basic + bac 30L",
        "price": 3000,
        "desc": "Basic + bac 30L - 3000 FCFA",
    },
    {
        "key": "standard",
        "name": "Standard",
        "price": 3000,
        "desc": "Standard - 3000 FCFA",
    },
    {
        "key": "standard_bac30",
        "name": "Standard + bac 30L",
        "price": 3500,
        "desc": "Standard + bac 30L - 3500 FCFA",
    },
    {
        "key": "standard_bac60",
        "name": "Standard + bac 60L",
        "price": 5000,
        "desc": "Standard + bac 60L - 5000 FCFA",
    },
    {"key": "3plus", "name": "3plus", "price": 3500, "desc": "3plus - 3500 FCFA"},
    {
        "key": "entreprise",
        "name": "Entreprise",
        "price": 3500,
        "desc": "Entreprise - 3500 FCFA",
    },
]


# UUID deterministe derive du nom (stable entre executions)
def plan_uuid(key):
    return uuid_lib.uuid5(uuid_lib.NAMESPACE_DNS, f"clean-plan-{key}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Cree les plans tarifaires dans le cloud."
    )
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans ecrire.")
    args = parser.parse_args()

    try:
        from django.db import connections

        connections["cloud"].ensure_connection()
    except Exception as e:
        print(f"❌ Cloud injoignable : {e}")
        sys.exit(1)

    print("☁️  Creation des plans dans le cloud (base en ligne)...")
    for plan in PLANS:
        uid = plan_uuid(plan["key"])
        if args.dry_run:
            print(f"   [DRY] {plan['name']} -> {plan['price']} FCFA (uuid={uid})")
            continue

        obj, created = SubscriptionPlan.objects.using("cloud").update_or_create(
            uuid=uid,
            defaults={
                "name": plan["name"],
                "price": plan["price"],
                "duration_days": 30,
                "description": plan["desc"],
                "synced": True,
                "site_id": "CLOUD_SITE",
            },
        )
        verb = "CREE" if created else "MIS A JOUR"
        print(f"   ✅ {verb} : {obj.name} ({obj.price} FCFA)")

    print("\n✅ Plans tarifaires prets dans le cloud.")
    print("   La version web (AlwaysData) les verra immediatement (elle lit le cloud).")
    print(
        "   La version locale les recuperera via le prochain pull de synchronisation."
    )


if __name__ == "__main__":
    main()
