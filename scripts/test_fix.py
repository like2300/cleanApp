#!/usr/bin/env python3
"""
Test script to check if the fix script works.
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

print("Testing fix script...")

# Check if we can access the cloud database
try:
    # Try to query the cloud database
    users = User.objects.using("cloud").all()
    print(f"✅ Successfully connected to cloud database")
    print(f"Total users on cloud: {users.count()}")

    # Check for duplicates
    duplicates = (
        User.objects.using("cloud")
        .values("username")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    print(f"Duplicate usernames on cloud: {len(duplicates)}")

    for dup in duplicates[:5]:
        print(f"  - {dup['username']}: {dup['count']} occurrences")

except Exception as e:
    print(f"❌ Error accessing cloud database: {e}")
    import traceback

    traceback.print_exc()
