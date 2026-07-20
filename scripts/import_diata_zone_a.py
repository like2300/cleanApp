#!/usr/bin/env python3
"""
Importe les clients de la DIATA ZONE A et les synchronise (local + web via cloud).

- Cree la zone DIATA et les quartiers (derives des adresses).
- Cree les clients (User, role=CLIENT) et leurs abonnements.
- Pousse tout vers le cloud pour que la version web (AlwaysData) recupere
  les donnees via sa synchro.

Les plans sont normalises depuis les libelles du tableau (fautes de frappe
corrigees : Bsic->Basic, Entrprise->Entreprise, Standare->Standard, etc.).

Usage :
  python scripts/import_diata_zone_a.py            # import local + push cloud
  python scripts/import_diata_zone_a.py --no-push  # import local seulement
  python scripts/import_diata_zone_a.py --dry-run # simulation
"""

import io
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.db.models import Q

from accounts.models import User
from business.models import Quartier, Subscription, SubscriptionPlan, Zone
from sync_engine.cron import SyncDataCronJob
from sync_engine.router import SyncRouter

ZONE_NAME = "DIATA"

# Donnees du tableau (N°, Nom, Email, Tel1, Tel2, Quartier, Plan, Echeance, Adresse)
RAW = """1	NGUIMBI Jean	NC	06 579 66 39	NC	DIATA	Basic	le 15	Av 5fevrier
2	DINANA Edwige	NC	06 636 55 30	NC	DIATA	Basic	le 30	Av 5fevrier
3	Andre	NC	06 404 79 71	NC	DIATA	Basic	le 30	la piscine
4	Kadie	NC	06 877 09 39	NC	DIATA	Basic	le 15	la piscine
5	MGOUALA Jojo Mavy	NC	06 955 42 09	06 634 41 05	DIATA	Basic+bac 30L	le 15	Rue Mossedjo
6	BUETUENA Emilienne	NC	05 380 54 62	NC	DIATA	Basic	le 05	Rue Mossedjo
7	Premier bet ( Junior )	NC	06 623 67 23	NC	DIATA	Basic	le 05	Rue Mossedjo
8	Pharmacie Galien Diata	NC	56560087	NC	DIATA	Basic	le 05	Rue Mossedjo
9	MBERYE Noel	NC	06 931 01 15	NC	DIATA	Basic	le 15	Rue Mossedjo
10	KOMBO	NC	06 666 50 25	06 964 35 7	DIATA	Standard+bac60L	le 15	Rue Mossedjo
11	Niko	NC	NC	NC	DIATA	Basic	le 05	Rue Mossedjo
12	Destar	NC	06 869 01 73	NC	DIATA	Basic	le 05	Rue Mossedjo
13	HOTEL NYANGA	NC	06 917 61 81	NC	DIATA	Entrprise	le 15	Rue du POOL
14	Amelia	NC	05 655 52 52	NC	DIATA	standard	le 30	Rue du POOL
15	kadele le safoutie	NC	06 941 98 86	NC	DIATA	standard	le 30	Rue du POOL
16	MAKAYA Dodo	NC	06 955 28 75	NC	DIATA	3plus	le 30	Rue du POOL
17	GAMA paul sandy	NC	06 949 74 69	NC	DIATA	Basic	le 30	Rue du POOL
18	KAYE firlene	NC	06 982 19 67	NC	DIATA	Basic	le 30	Rue du POOL
19	MAKIBI Ramaldine	NC	06 952 90 13	NC	DIATA	Basic	le 30	Rue du POOL
20	KOUNSOU Heleine	NC	06 952 89 94	NC	DIATA	Bsic	le 05	Rue du POOL
21	PANZA Joel	NC	06955 17 98	NC	DIATA	Bsic	le 05	Rue du POOL
22	MIKOLO Huguette	NC	05 300 15 06	NC	DIATA	Bsic	le 05	Rue du POOL
23	BIKAWA Théophile	NC	06 689 69 27	05 532 62 04	DIATA	Bsic	le 15	Rue du POOL
24	CASE	NC	06 467 00 59	NC	DIATA	Entreprise	le 30	Rue du POOL
25	NSONDE Marie	NC	06 886 83 20	NC	DIATA	Standard	le 30	Rue Jacob BINAKI
26	YIMBOU	NC	06 918 55 24	NC	DIATA	standard	le 15	Rue Jacob BINAKI
27	DILOU	NC	06 967 40 82	NC	DIATA	Basic	le 15	Rue Jacob BINAKI
28	NIAMBA Marceline	NC	06 782 13 04	NC	DIATA	Basic	le 30	Rue Jacob BINAKI
29	MABOULOU Bertine	NC	06 450 71 64	NC	DIATA	Basic	le 05	Rue Jacob BINAKI
30	NGOMA Rodevine	NC	06 934 14 72	NC	DIATA	Basic	le 05	Rue Jacob BINAKI
31	MOUELLET Nadège	NC	06 557 32 80	NC	DIATA	Basic	le 30	Rue Jacob BINAKI
32	OLONGO cladisse	NC	06 441 75 98	NC	DIATA	Basic	le 15	Rue Jacob BINAKI
33	Elodie (à vérifier)	NC	06 902 28 10	NC	DIATA	Standard	le 30	Rue Jacob BINAKI
34	ETS DM	NC	06 577 00 88	NC	DIATA	Entreprise	le 05	Rue Jacob BINAKI
35	Garance	NC	05 559 56 25	NC	DIATA	Basic	le 15	Rue Jacob BINAKI
36	Reine	NC	06 863 77 56	NC	DIATA	Basic	le 30	Rue marie bella
37	DIAYOKA Leslie	NC	06 650 89 05	NC	DIATA	Basic	le 05	Rue marie bella
38	GOMA Yolande	NC	06 517 21 64	NC	DIATA	Basic+bac 30L	le 05	Rue marie bella
39	MOUANOU Aude	NC	06 475 78 90	NC	DIATA	Basic	le 05	Rue marie bella
40	MBENDI	NC	06 817 57 68	NC	DIATA	Basic	le 05	Rue marie bella
41	(Nom manquant)	NC	NC	NC	DIATA	Basic	le 30	Rue marie bella
42	NKAMBELIE Mavina	NC	06 935 23 03	06 631 68 17	DIATA	Standard	le 30	Rue marie bella
43	BONGO	NC	06 637 95 13	NC	DIATA	Standard+bac 60L	le 05	Rue Hinda
44	NGOMA Clarisse	NC	06 657 98 94	NC	DIATA	3plus	le 30	Rue Hinda
45	KANYA Jirisse	NC	06 530 57 65	06 978 77 86	DIATA	Standard	le 30	Rue Hinda
46	MOUKALA Garcia	NC	06 975 19 15	NC	DIATA	Basic	le 15	Rue Hinda
47	NKONDOLO Luis	NC	06 611 62 51	NC	DIATA	Basic	le 15	Rue Hinda
48	Enock	NC	06 352 55 55	NC	DIATA	Basic+bac 30L	le 05	Rue Nianga
49	ECOLE Aimé Blaise	NC	06 758 40 97	NC	DIATA	Entreprise tj	le 05	Rue Nianga
50	LETEMBET Syvia	NC	06 512 51 17	NC	DIATA	Basic	le 05	Rue Nianga
51	ginelle	NC	NC	NC	DIATA	Basic	le 05	Rue Nianga
52	BALA Chantalle	NC	06 655 95 62	06 695 60 76	DIATA	Standare	le 05	rue Kimbenza
53	KASTANE-BIAGNEF Mabel	NC	06 658 98 76	NC	DIATA	Basic	le 05	rue Kimbenza
54	NGAMIYI Irge	NC	06 851 70 97	NC	DIATA	Standar	le 15	rue Kimbenza
55	SENGUE Sarha	NC	06 920 20 21	NC	DIATA	Standar	le 30	rue Kimbenza
56	Brice	NC	06 930 02 59	NC	DIATA	Basic	le 15	rue Kimbenza
57	SEKOU Paulaie	NC	05 034 16 53	NC	DIATA	Basic	le 30	Bihani sivory
58	KAYA Loinel	NC	06 954 31 34	NC	DIATA	Standard	le 30	Bihani sivory
59	GUERNICHTE	NC	06 885 97 19	NC	DIATA	Standard	le 30	Bihani sivory
60	MBELE Leopold	NC	06 405 26 46	NC	DIATA	Standard	le 05	Rue loualou
61	NGOUA Daniel	NC	NC	NC	DIATA	Standard	le 05	Rue loualou
62	Rolande	NC	06 690 79 55	NC	DIATA	Basic	le 30	Rue sambaJoseph
63	SOUNGHA Gael	NC	06 677 50 04	NC	DIATA	Standard	le 30	Rue sambaJoseph
64	MBERI Judicel	NC	06 668 30 87	NC	DIATA	Standard	le 30	Rue sambaJoseph
65	YAMBA Adivine	NC	06 651 36 65	NC	DIATA	Standard+bac 30L	le 05	Mbanza Ndounga
66	Lolo	NC	06 671 10 47	NC	DIATA	Basic	le 05	Rue de la fraternite
67	Grace	NC	06 512 78 57	NC	DIATA	Basic+bac 30L	le 05	Rue marie bella
68	Chrysante sauvernier	NC	06 845 65 70	05 707 06 46	DIATA	Basic+bac 30L	le 15	Rue Nianga
69	IKAMA Gladice	NC	06 503 48 25	NC	DIATA	Basic	le 05	Rue Mossedjo
70	KAYA Ken	NC	06 830 10 60	NC	DIATA	Basic	le 15	Rue Nianga
71	SAMBA Christopher	NC	06 927 83 84	NC	DIATA	Standard	le 05	Rue Nianga
72	BOUNGUELE Ephiphanie	NC	06 986 25 03	NC	DIATA	Basic	le 30	Rue Mossedjo
73	Clissan	NC	06 288 55 81	NC	DIATA	Basic+bac 30L	le 15	Rue marie bella
74	Est foure tout (Caroline)	NC	06 500 26 00	NC	DIATA	Entreprise	le 15	Rue du POOL
75	GASPARD	NC	NC	NC	DIATA	Basic +bac 30L	le 05	la piscine
76	Naomie cave	NC	06 677 47 87	NC	DIATA	Basic	le 15	Rue Jacob BINAKI
77	MASSIKA Valentine	NC	06 654 58 89	NC	DIATA	Standard	le 05	Rue sambaJoseph
78	BOUNDA MIDOU Chanelle	NC	06 405 62 48	NC	DIATA	Basic	le 30	Av 5fevrier
79	Gesica	NC	06 838 23 08	NC	DIATA	Standard	le 05	la piscine"""


def clean_phone(phone):
    if phone is None:
        return None
    s = str(phone).strip()
    if s.upper() in ["NC", ""]:
        return None
    # Garde uniquement les chiffres et espaces
    cleaned = "".join(c for c in s if c.isdigit() or c.isspace())
    cleaned = cleaned.replace(" ", "")
    return cleaned or None


def clean_name(name):
    if name is None:
        return None
    s = str(name).strip()
    if not s or s.upper() == "NC":
        return None
    return " ".join(s.split())


def normalize_plan(raw_plan):
    """Normalise les libelles du tableau vers les plans existants."""
    if not raw_plan:
        return "Basic"
    p = raw_plan.lower().replace(" ", "").replace("+", "+")
    # Cas avec bac
    if "bac60" in p or "bac 60" in p:
        return "Standard + bac 60L"
    if "bac30" in p or "bac 30" in p:
        return "Basic + bac 30L"
    # Cas simples (corrige les fautes)
    if "3plus" in p or "3 plus" in p:
        return "3plus"
    if "entreprise" in p:
        return "Entreprise"
    if "standard" in p:
        return "Standard"
    if "basic" in p or "bsic" in p or "basique" in p:
        return "Basic"
    return "Basic"


def normalize_quartier(address, default="DIATA"):
    """Derive un nom de quartier lisible depuis l'adresse."""
    if not address:
        return default
    a = address.strip()
    # Prendre la fin de l'adresse comme quartier (ex: 'Rue Mossedjo' -> 'Mossedjo')
    parts = re.split(
        r"(rue|av|avenue|rte|route|à|la|le|de|du)\s+", a, flags=re.IGNORECASE
    )
    last = parts[-1].strip() if parts else a
    last = re.sub(r"[^A-Za-z0-9 '\-]", "", last).strip()
    if not last:
        return default
    return last[:50]


def parse_due_day(token):
    """'le 15' -> 15 ; defaut 15."""
    if not token:
        return 15
    m = re.search(r"(\d+)", str(token))
    if m:
        d = int(m.group(1))
        return max(1, min(28, d))
    return 15


def get_or_create_zone(name):
    zone, _ = Zone.objects.get_or_create(
        name__iexact=name, defaults={"name": name, "description": f"Zone {name}"}
    )
    return zone


def get_or_create_quartier(name, zone):
    if not name:
        return None
    q, _ = Quartier.objects.get_or_create(
        name__iexact=name, zone=zone, defaults={"name": name, "zone": zone}
    )
    return q


def get_or_create_plan(name):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name__iexact=name,
        defaults={
            "name": name,
            "price": 2000,
            "duration_days": 30,
            "description": f"Plan {name}",
        },
    )
    return plan


def get_or_create_client(name, phone, phone2, quartier, zone, address):
    # Deux clients peuvent avoir le meme nom : on ne deduit JAMAIS par nom seul.
    # La distinction reelle se fait par uuid (ID de sync). On deduit par
    # telephone si disponible ; sinon on cree toujours un nouveau client.
    # Le vrai nom est stocke dans display_name ; username est genere (uuid).
    if not name:
        name = f"Client_{phone[-4:]}" if phone else f"Client_{Quartier.objects.count()}"
    if phone:
        existing = User.objects.filter(
            Q(phone_number=phone) | Q(phone_number_2=phone), role=User.Role.CLIENT
        ).first()
        if existing:
            return existing
    # Pas de dedoublonnage par nom : on cree un client par ligne.
    import uuid as uuid_lib

    u = uuid_lib.uuid4()
    temp_username = f"u{str(u).replace('-', '')[:12]}"
    return User.objects.create_user(
        username=temp_username,
        uuid=u,
        first_name=name,
        display_name=name,
        phone_number=phone,
        phone_number_2=phone2,
        quartier=quartier,
        zone=zone,
        address=address,
        role=User.Role.CLIENT,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Importe DIATA ZONE A et pousse au cloud."
    )
    parser.add_argument(
        "--no-push", action="store_true", help="Import local seulement."
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulation.")
    args = parser.parse_args()

    if args.dry_run:
        print("⚠️  DRY RUN — aucune ecriture")
        return

    zone = get_or_create_zone(ZONE_NAME)
    print(f"✅ Zone '{zone.name}' prete")

    stats = {"created": 0, "skipped": 0, "errors": 0}
    today = date.today()

    for line in RAW.strip().splitlines():
        cols = line.split("\t")
        if len(cols) < 9:
            continue
        _n, nom, _email, tel1, tel2, _zone, plan_raw, due_raw, address = cols[:9]

        nom = clean_name(nom)
        if not nom:
            stats["skipped"] += 1
            continue
        tel1 = clean_phone(tel1)
        tel2 = clean_phone(tel2)
        plan_name = normalize_plan(plan_raw)
        quartier_name = normalize_quartier(address, default=ZONE_NAME)
        due_day = parse_due_day(due_raw)

        try:
            quartier = get_or_create_quartier(quartier_name, zone)
            plan = get_or_create_plan(plan_name)
            client = get_or_create_client(nom, tel1, tel2, quartier, zone, address)

            # Date d'echeance : ce mois-ci au jour due_day
            try:
                end_date = today.replace(day=due_day)
            except ValueError:
                end_date = today
            if end_date < today:
                # mois prochain
                from dateutil.relativedelta import relativedelta

                end_date = today + relativedelta(months=1, day=due_day)

            sub, created = Subscription.objects.get_or_create(
                client=client,
                plan=plan,
                defaults={"end_date": end_date, "is_active": True},
            )
            if created:
                stats["created"] += 1
                print(f"   ✅ {nom} | {plan_name} | echeance jour {due_day}")
            else:
                stats["skipped"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"   ❌ {nom}: {e}")

    print(
        f"\n📊 Abonnements crees: {stats['created']} | ignores: {stats['skipped']} | erreurs: {stats['errors']}"
    )
    print(
        f"   👥 Clients DIATA: {User.objects.filter(zone=zone, role=User.Role.CLIENT).count()}"
    )

    if args.no_push:
        print("\n⏭️  --no-push : donnees en base locale uniquement.")
        return

    print("\n☁️  Push vers le cloud (version web)...")
    router = SyncRouter()
    if not router._check_cloud_connectivity():
        print("❌ Cloud injoignable. Relance plus tard pour pousser.")
        sys.exit(1)
    try:
        SyncDataCronJob().do()
        print("✅ DIATA ZONE A synchronisee (local + web via cloud).")
    except Exception as e:
        print(f"❌ Erreur push: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
