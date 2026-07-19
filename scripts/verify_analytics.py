#!/usr/bin/env python3
"""
Vérifie que les données affichées par la vue analytics_dashboard correspondent
à la réalité de la base SQLite.

Reproduit la logique de finance/views.py::analytics_dashboard (sans filtres
de zone/quartier/période, comme si on affichait tout) et affiche les valeurs
réelles de la base pour comparaison avec l'écran.

Usage (depuis la racine du projet, env activé) :
  python scripts/verify_analytics.py
"""

import os
import sys

import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from business.models import Zone
from finance.models import Expense, Invoice, Payment

# --- Reproduction de la logique de la vue (sans filtres utilisateur) ---
invoices_qs = Invoice.objects.all()
payments_qs = Payment.objects.filter(is_validated=True)

total_invoiced = invoices_qs.aggregate(Sum("amount"))["amount__sum"] or 0
total_paid = payments_qs.aggregate(Sum("amount"))["amount__sum"] or 0
recovery_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0

print("=" * 60)
print("STATS GLOBALES (toutes zones, sans filtre)")
print("=" * 60)
print(f"Total facturé      : {total_invoiced}")
print(f"Total encaissé (validé) : {total_paid}")
print(f"Taux de recouvrement : {recovery_rate:.1f}%")
print(f"Reste à recouvrer   : {total_invoiced - total_paid}")

# --- Détail par zone ---
print("\n" + "=" * 60)
print("PAR ZONE")
print("=" * 60)
for zone in Zone.objects.all():
    z_inv = (
        invoices_qs.filter(client__zone=zone).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )
    z_pay = (
        payments_qs.filter(invoice__client__zone=zone).aggregate(Sum("amount"))[
            "amount__sum"
        ]
        or 0
    )
    rate = (float(z_pay) / float(z_inv) * 100) if z_inv > 0 else 0
    print(
        f"  {zone.name:<20} facturé={float(z_inv):>12.1f}  encaissé={float(z_pay):>12.1f}  taux={rate:>5.1f}%"
    )

# --- Paiements non validés (pour expliquer un encaissé à 0) ---
unvalidated = Payment.objects.filter(is_validated=False)
unvalidated_sum = unvalidated.aggregate(Sum("amount"))["amount__sum"] or 0
print("\n" + "=" * 60)
print("PAIEMENTS NON VALIDÉS (is_validated=False)")
print("=" * 60)
print(f"Nombre : {unvalidated.count()}")
print(f"Montant total non validé : {unvalidated_sum}")
print("=> Si > 0, c'est la raison pour laquelle 'Encaissé' affiche 0 FCFA.")

# --- Dépenses par catégorie ---
print("\n" + "=" * 60)
print("DÉPENSES PAR CATÉGORIE")
print("=" * 60)
for cat_val, cat_label in Expense.DEFAULT_CATEGORIES.items():
    amt = (
        Expense.objects.filter(category=cat_val).aggregate(Sum("amount"))["amount__sum"]
        or 0
    )
    if amt:
        print(f"  {cat_label:<15} : {float(amt):.1f}")

# --- Vérif : factures sans client.zone (exclues du découpage par zone) ---
orphan_inv = invoices_qs.filter(client__zone__isnull=True)
orphan_sum = orphan_inv.aggregate(Sum("amount"))["amount__sum"] or 0
print("\n" + "=" * 60)
print("COHÉRENCE")
print("=" * 60)
zones_sum = sum(
    (invoices_qs.filter(client__zone=z).aggregate(Sum("amount"))["amount__sum"] or 0)
    for z in Zone.objects.all()
)
print(f"Somme facturé par zone : {zones_sum}")
print(f"Total facturé global   : {total_invoiced}")
print(f"Facturé 'orphelin' (sans zone) : {orphan_sum}")
if float(zones_sum) != float(total_invoiced):
    print("  /!\\ Écart : certaines factures ne sont pas rattachées à une zone.")
