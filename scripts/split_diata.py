#!/usr/bin/env python3
"""
Script de migration pour scinder la zone DIATA en 3 zones distinctes :
- DIATA ZONE A
- DIATA ZONE B
- DIATA ZONE C

Etapes :
1. Créer les 3 nouvelles zones
2. Réaffecter les clients selon leur source Excel (ou leur quartier/rue)
3. Déplacer les quartiers, abonnements, etc.
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from django.db import transaction
from django.db.models import Q

from accounts.models import User
from business.models import Quartier, Subscription, Zone

# Mapping des rues/quartiers vers les zones Diata
ZONE_MAPPING = {
    # Zone A : Av 5fevrier, Rue de la piscine, Rue du POOL
    "Av 5fevrier": "DIATA ZONE A",
    "La piscine": "DIATA ZONE A",
    "Rue du POOL": "DIATA ZONE A",
    "Rue Jacob BINAKI": "DIATA ZONE A",
    # Zone B : Rue Mont Fouary, Rue Mbongui, Dihesse
    "Rue Mont Fouary": "DIATA ZONE B",
    "Rue Mbongui": "DIATA ZONE B",
    "Dihesse": "DIATA ZONE B",
    "Rue Boupanda": "DIATA ZONE B",
    "Rue Makabana": "DIATA ZONE B",
    "Rue Makola": "DIATA ZONE B",
    "Nzambana jadot": "DIATA ZONE B",
    "Rue Mbila": "DIATA ZONE B",
    # Zone C : Avenue mpiaka, Ngabandzoko
    "Avenue mpiaka": "DIATA ZONE C",
    "Ngabandzoko": "DIATA ZONE C",
    "Avenue 5fevrier": "DIATA ZONE C",  # pour DIATA ZONE C.xlsx
}

# Clients connus dans les Excel avec leur zone source
EXCEL_SOURCES = {
    "DIATA ZONE A.xlsx": {
        "NGUIMBI Jean": "DIATA ZONE A",
        "DINANA Edwige": "DIATA ZONE A",
        "Premier bet ( Junior )": "DIATA ZONE A",
        "MBERYE Noel": "DIATA ZONE A",
        "HOTEL NYANGA": "DIATA ZONE A",
        "BOUNGUELE Ephiphanie": "DIATA ZONE A",
    },
    "DIATA ZONE B.xlsx": {
        "Bénie love": "DIATA ZONE B",
        "NGUIMBI Gildas": "DIATA ZONE B",
        "SAFOU": "DIATA ZONE B",
        "NGUEBE Serge": "DIATA ZONE B",
        "NGOUMA prince": "DIATA ZONE B",
    },
    "DIATA ZONE C.xlsx": {
        "BAHAMANI Eugenie": "DIATA ZONE C",
    },
}


def get_client_zone(user):
    """Déterminer la zone Diata A/B/C pour un client existant."""
    # 1. Par nom dans EXCEL_SOURCES
    for fname, mapping in EXCEL_SOURCES.items():
        for name, zone in mapping.items():
            if name.lower() in user.username.lower():
                return zone

    # 2. Par rue
    if user.address:
        for rue, zone in ZONE_MAPPING.items():
            if rue.lower() in user.address.lower():
                return zone

    # 3. Par quartier (si quartier existe)
    if user.quartier:
        q = user.quartier.name.lower()
        for qname, zone in ZONE_MAPPING.items():
            if qname.lower() in q:
                return zone

    # 4. Défaut : Zone A (à vérifier manuellement)
    return "DIATA ZONE A"


def main():
    print("🚀 Migration Diata → Diata A/B/C")

    # Créer les 3 nouvelles zones
    zones = {}
    for zname in ["DIATA ZONE A", "DIATA ZONE B", "DIATA ZONE C"]:
        zones[zname] = Zone.objects.get_or_create(name=zname)[0]
        print(f"  ✅ Zone {zname} (id={zones[zname].id})")

    # Récupérer l'ancienne zone DIATA
    old_diata = Zone.objects.get(name="DIATA")
    clients = User.objects.filter(zone=old_diata, role=User.Role.CLIENT)
    print(f"\n👥 Traitement de {clients.count()} clients...")

    # Réaffecter les clients
    moved = defaultdict(int)
    with transaction.atomic():
        for user in clients:
            new_zone_name = get_client_zone(user)
            user.zone = zones[new_zone_name]
            user.save()
            moved[new_zone_name] += 1

    print(f"\n📊 Migration terminée :")
    for z, count in moved.items():
        print(f"  {z} : {count} clients")

    # Vérifier les quartiers
    print("\n🏘️ Quartiers par zone :")
    for zname in ["DIATA ZONE A", "DIATA ZONE B", "DIATA ZONE C"]:
        zone = zones[zname]
        qs = zone.quartiers.all()
        print(f"  {zname} : {qs.count()} quartiers")

    print("\n⚠️ Vérifiez les affectations et archivez l'ancienne zone DIATA.")


if __name__ == "__main__":
    main()
