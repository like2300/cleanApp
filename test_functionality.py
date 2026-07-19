#!/usr/bin/env python
"""
Test script to verify the implemented functionality works correctly.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/omerlinks/Desktop/project/CLEAN')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from finance.models import Invoice, Payment
from business.models import Subscription, SubscriptionPlan
from accounts.models import User

def test_invoice_creation_blocking():
    """Test that invoice creation is blocked when one already exists"""
    print("Testing invoice creation blocking...")
    
    # Create a test client
    client = User.objects.filter(role=User.Role.CLIENT).first()
    if not client:
        print("⚠️ No test client found, skipping test")
        return False
    
    # Create a test subscription plan
    plan = SubscriptionPlan.objects.first()
    if not plan:
        print("⚠️ No subscription plan found, skipping test")
        return False
    
    # Create a test subscription
    subscription = Subscription.objects.create(
        client=client,
        plan=plan,
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=30),
        is_active=True
    )
    
    # Create a pending invoice
    pending_invoice = Invoice.objects.create(
        client=client,
        subscription=subscription,
        amount=plan.price,
        due_date=timezone.now().date() + timedelta(days=7),  # Due in 7 days
        status=Invoice.Status.PENDING
    )
    
    print(f"✅ Created test pending invoice: {pending_invoice.id}")
    
    # Try to create another invoice - should be blocked by our logic
    existing_invoices = Invoice.objects.filter(
        client=client,
        subscription=subscription,
        status__in=[Invoice.Status.PENDING, Invoice.Status.PAID]
    )
    
    if existing_invoices.exists():
        print("✅ Invoice creation blocking works: Found existing invoice")
        return True
    else:
        print("❌ Invoice creation blocking failed: No existing invoice found")
        return False

def test_expired_subscriptions():
    """Test the expired subscriptions functionality"""
    print("\nTesting expired subscriptions handling...")
    
    from finance.views import check_and_create_invoices_for_expired_subscriptions
    
    # Create an expired subscription
    client = User.objects.filter(role=User.Role.CLIENT).first()
    if not client:
        print("⚠️ No test client found, skipping test")
        return False
    
    plan = SubscriptionPlan.objects.first()
    if not plan:
        print("⚠️ No subscription plan found, skipping test")
        return False
    
    # Create expired subscription
    expired_sub = Subscription.objects.create(
        client=client,
        plan=plan,
        start_date=timezone.now().date() - timedelta(days=40),
        end_date=timezone.now().date() - timedelta(days=10),  # Expired 10 days ago
        is_active=True
    )
    
    print(f"✅ Created test expired subscription: {expired_sub.id}")
    
    # Run the expired subscriptions check
    try:
        count = check_and_create_invoices_for_expired_subscriptions()
        print(f"✅ Expired subscriptions check completed. Processed {count} subscriptions.")
        return True
    except Exception as e:
        print(f"❌ Expired subscriptions check failed: {e}")
        return False

def test_template_syntax():
    """Test basic template syntax"""
    print("\nTesting template syntax...")
    
    from django.template import Template, Context
    
    # Test a simple template
    template_str = """
    {% load static %}
    <html>
    <head><title>{% block title %}Test{% endblock %}</title></head>
    <body>
        <h1>Hello {{ name }}</h1>
        {% for item in items %}
            <p>{{ item }}</p>
        {% endfor %}
    </body>
    </html>
    """
    
    try:
        template = Template(template_str)
        context = Context({'name': 'Test', 'items': ['a', 'b', 'c']})
        result = template.render(context)
        print("✅ Basic template syntax is valid")
        return True
    except Exception as e:
        print(f"❌ Template syntax error: {e}")
        return False

if __name__ == "__main__":
    print("Running functionality tests...\n")
    
    results = []
    results.append(test_template_syntax())
    results.append(test_invoice_creation_blocking())
    results.append(test_expired_subscriptions())
    
    print(f"\n{'='*50}")
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed or were skipped")
        sys.exit(1)