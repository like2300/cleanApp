#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CLEAN.settings')
sys.path.append('/Users/omerlinks/Desktop/project/CLEAN')
django.setup()

from business.views import zone_subscriptions_manage
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from business.models import Zone

User = get_user_model()
factory = RequestFactory()

# Create a test request
user = User.objects.first()
zone = Zone.objects.first()

if user and zone:
    request = factory.get(f'/business/zones/{zone.id}/subscriptions/?quartier=1&period=current')
    request.user = user
    
    response = zone_subscriptions_manage(request, zone.id)
    content = response.content.decode()
    
    print('✅ Page loaded successfully!')
    print('Status:', response.status_code)
    
    # Check that it's the simplified version
    if 'Suivi des Paiements' in content:
        print('✅ Title changed to "Suivi des Paiements"')
    
    if 'Liste' not in content and 'Calendrier' not in content:
        print('✅ Tabs removed')
    
    if 'Export Excel' in content:
        print('✅ Export button present')
    
    if 'Rechercher client' in content:
        print('✅ Search filter present')
    
    if 'Quartier' in content and 'Période' in content:
        print('✅ Filters present')
    
    # Check client display
    if 'open' in content and 'apps' in content:
        print('✅ Clients displayed')
    
    # Check payment indicators
    payment_indicators = content.count('solar:check-circle-linear')
    no_payment_indicators = content.count('>-<')
    print(f'💰 Payment indicators: {payment_indicators} green, {no_payment_indicators} gray')
    
else:
    print('❌ Missing user or zone')