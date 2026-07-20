#!/usr/bin/env python3
"""
Vide les DONNÉES des bases locale (default) et en ligne (cloud).

ATTENTION : supprime TOUTES les données métier (users, zones, abonnements,
factures, paiements, etc.) des DEUX bases. Les paramètres CompanySettings et
les catégories de dépense par défaut sont conservés sauf option --full.

Usage :
  python scripts/reset_databases.py                 # vide les deux bases
  python scripts/reset_databases.py --dry-run        # liste ce qui serait supprimé
  python scripts/reset_databases.py --local-only     # seulement la base locale
  python scripts/reset_databases.py --cloud-only     # seulement le cloud
  python scripts/reset_databases.py --full           # vide aussi CompanySettings
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django

django.setup()

from django.db import connection

from accounts.models import CompanySettings, User
from business.models import (
    Employee,
    Position,
    Quartier,
    Subscription,
    SubscriptionPlan,
    Zone,
)
from finance.models import Expense, ExpenseCategory, Invoice, Payment
from notifications.models import Notification, Reclamation
from sync_engine.models import DeletedRecord


def _empty(model, using, dry_run):
    """Supprime tous les objets d'un modèle sur une base donnée."""
    qs = model.objects.using(using).all()
    count = qs.count()
    if dry_run:
        if count:
            print(f"   [DRY] {model._meta.label} ({using}): {count} supprimé(s)")
        return count
    qs.delete()
    print(f"   🗑️  {model._meta.label} ({using}): {count} supprimé(s)")
    return count


def reset_db(using, dry_run, full):
    print(f"\n{'=' * 60}")
    print(f"🧹 Base : {using}")
    print(f"{'=' * 60}")

    # Ordre : enfants avant parents (respecte les FK)
    # 1. Finance
    _empty(Payment, using, dry_run)
    _empty(Invoice, using, dry_run)
    _empty(Subscription, using, dry_run)
    _empty(SubscriptionPlan, using, dry_run)
    # 2. Notifications
    _empty(Notification, using, dry_run)
    _empty(Reclamation, using, dry_run)
    # 3. Business
    _empty(Employee, using, dry_run)
    _empty(Quartier, using, dry_run)
    _empty(Zone, using, dry_run)
    _empty(Position, using, dry_run)
    # 4. Users (clients + staff)
    _empty(User, using, dry_run)
    # 5. Dépenses
    _empty(Expense, using, dry_run)
    if full:
        _empty(CompanySettings, using, dry_run)
        _empty(ExpenseCategory, using, dry_run)
    else:
        # Conserve CompanySettings et les catégories de dépense par défaut
        print(
            f"   ℹ️  CompanySettings et ExpenseCategory conservés (utilisez --full pour tout vider)"
        )

    # Nettoyage de la table de suivi des suppressions
    _empty(DeletedRecord, using, dry_run)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Vide les bases locale et cloud.")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans supprimer.")
    parser.add_argument(
        "--local-only", action="store_true", help="Base locale seulement."
    )
    parser.add_argument("--cloud-only", action="store_true", help="Cloud seulement.")
    parser.add_argument(
        "--full", action="store_true", help="Vide aussi CompanySettings."
    )
    args = parser.parse_args()

    if args.dry_run:
        print("⚠️  MODE DRY RUN — aucune suppression réelle")

    if not args.cloud_only:
        reset_db("default", args.dry_run, args.full)
    if not args.local_only:
        # Vérifie que le cloud est configuré avant de tenter
        try:
            connection.ensure_connection() if using_is_cloud() else None
        except Exception:
            pass
        reset_db("cloud", args.dry_run, args.full)

    print("\n✅ Reset terminé.")
    if not args.dry_run:
        print(
            "   Relance l'import Excel puis le push : python scripts/import_to_cloud.py"
        )


def using_is_cloud():
    from django.conf import settings

    return "cloud" in settings.DATABASES


if __name__ == "__main__":
    main()
