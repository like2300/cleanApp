#!/usr/bin/env python
"""
Test script to verify that ACCOUNTANT role has full access to expense management
and is not blocked by read-only restrictions.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/omerlinks/Desktop/project/CLEAN')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from accounts.models import User
from core.utils import read_only_role_blocked, block_read_only_role
from finance.models import Expense, ExpenseCategory

def test_read_only_role_blocked():
    """Test that ACCOUNTANT is not considered a read-only role"""
    print("Testing read-only role blocking...")
    
    # Create test users
    User = get_user_model()
    
    # Create users in database with unique usernames
    import uuid
    comptable = User.objects.create(
        username=f'test_comptable_{uuid.uuid4().hex[:8]}',
        role=User.Role.ACCOUNTANT
    )
    
    actionnaire = User.objects.create(
        username=f'test_actionnaire_{uuid.uuid4().hex[:8]}',
        role=User.Role.SHAREHOLDER
    )
    
    # Test the function
    comptable_is_blocked = read_only_role_blocked(comptable)
    actionnaire_is_blocked = read_only_role_blocked(actionnaire)
    
    if comptable_is_blocked:
        print("❌ FAIL: ACCOUNTANT is incorrectly blocked as read-only")
        return False
    else:
        print("✅ PASS: ACCOUNTANT is not blocked as read-only")
    
    if actionnaire_is_blocked:
        print("✅ PASS: SHAREHOLDER is correctly blocked as read-only")
    else:
        print("❌ FAIL: SHAREHOLDER should be blocked as read-only")
        return False
    
    return True

def test_block_read_only_role_function():
    """Test the block_read_only_role function with ACCOUNTANT"""
    print("\nTesting block_read_only_role function...")
    
    # Create a mock request for ACCOUNTANT
    class MockRequest:
        def __init__(self, user):
            self.user = user
            self.META = {'HTTP_REFERER': '/dashboard/'}
    
    # Create user in database with unique username
    import uuid
    User = get_user_model()
    comptable = User.objects.create(
        username=f'test_comptable_func_{uuid.uuid4().hex[:8]}',
        role=User.Role.ACCOUNTANT
    )
    
    request = MockRequest(comptable)
    response = block_read_only_role(request)
    
    if response is None:
        print("✅ PASS: block_read_only_role allows ACCOUNTANT access")
        return True
    else:
        print("❌ FAIL: block_read_only_role incorrectly blocks ACCOUNTANT")
        return False

def test_expense_views_access():
    """Test that ACCOUNTANT can access expense views"""
    print("\nTesting expense views access...")
    
    # Create a test client
    client = Client()
    
    # Create or get a comptable user
    User = get_user_model()
    comptable = User.objects.filter(role=User.Role.ACCOUNTANT).first()
    
    if not comptable:
        print("⚠️ No ACCOUNTANT user found, creating test user...")
        comptable = User.objects.create_user(
            username='test_comptable_user',
            password='testpass123',
            role=User.Role.ACCOUNTANT
        )
    
    # Login as comptable
    client.force_login(comptable)
    
    # Test access to expense list
    expense_list_url = reverse('expense_list')
    response = client.get(expense_list_url)
    
    if response.status_code == 200:
        print("✅ PASS: ACCOUNTANT can access expense list")
    else:
        print(f"❌ FAIL: ACCOUNTANT cannot access expense list (status: {response.status_code})")
        if response.status_code == 302:
            print(f"   Redirected to: {response.url}")
        return False
    
    # Test access to expense creation form
    expense_create_url = reverse('expense_create')
    response = client.get(expense_create_url)
    
    if response.status_code == 200:
        print("✅ PASS: ACCOUNTANT can access expense creation form")
    else:
        print(f"❌ FAIL: ACCOUNTANT cannot access expense creation form (status: {response.status_code})")
        return False
    
    return True

def test_expense_creation():
    """Test that ACCOUNTANT can actually create expenses"""
    print("\nTesting expense creation...")
    
    # Create test client
    client = Client()
    
    # Get or create comptable user
    User = get_user_model()
    comptable = User.objects.filter(role=User.Role.ACCOUNTANT).first()
    
    if not comptable:
        comptable = User.objects.create_user(
            username='test_comptable_creator',
            password='testpass123',
            role=User.Role.ACCOUNTANT
        )
    
    # Login as comptable
    client.force_login(comptable)
    
    # Get a category for the expense
    category = ExpenseCategory.objects.first()
    if not category:
        print("⚠️ No expense category found, creating one...")
        category = ExpenseCategory.objects.create(
            code='TEST',
            name='Test Category'
        )
    
    # Try to create an expense
    expense_create_url = reverse('expense_create')
    response = client.post(expense_create_url, {
        'title': 'Test Expense',
        'category': category.code,
        'amount': '1000',
        'expense_date': '2026-06-27',
        'description': 'Test expense creation'
    })
    
    if response.status_code == 302:  # Redirect after successful creation
        print("✅ PASS: ACCOUNTANT can successfully create expenses")
        
        # Check if expense was actually created
        expense_count = Expense.objects.filter(title='Test Expense').count()
        if expense_count > 0:
            print(f"✅ PASS: Expense was created in database ({expense_count} found)")
        else:
            print("⚠️ WARNING: Expense not found in database after creation")
        
        return True
    else:
        print(f"❌ FAIL: ACCOUNTANT cannot create expenses (status: {response.status_code})")
        if hasattr(response, 'context') and response.context and 'messages' in response.context:
            messages = list(response.context['messages'])
            for message in messages:
                print(f"   Error message: {message}")
        return False

def test_category_management():
    """Test that ACCOUNTANT can manage expense categories"""
    print("\nTesting category management...")
    
    # Create test client
    client = Client()
    
    # Get or create comptable user
    User = get_user_model()
    comptable = User.objects.filter(role=User.Role.ACCOUNTANT).first()
    
    if not comptable:
        comptable = User.objects.create_user(
            username='test_comptable_manager',
            password='testpass123',
            role=User.Role.ACCOUNTANT
        )
    
    # Login as comptable
    client.force_login(comptable)
    
    # Test category creation
    category_create_url = reverse('expense_category_create')
    response = client.post(category_create_url, {
        'name': 'Nouvelle Catégorie',
        'code': 'NOUVELLE'
    })
    
    if response.status_code == 302:
        print("✅ PASS: ACCOUNTANT can create expense categories")
        return True
    else:
        print(f"❌ FAIL: ACCOUNTANT cannot create categories (status: {response.status_code})")
        return False

if __name__ == "__main__":
    print("Running ACCOUNTANT access tests...\n")
    print("="*60)
    
    results = []
    results.append(test_read_only_role_blocked())
    results.append(test_block_read_only_role_function())
    results.append(test_expense_views_access())
    results.append(test_expense_creation())
    results.append(test_category_management())
    
    print("\n" + "="*60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed! ACCOUNTANT has full access to expense management.")
        sys.exit(0)
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        sys.exit(1)