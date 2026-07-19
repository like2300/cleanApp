#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CLEAN.settings')
sys.path.append('/Users/omerlinks/Desktop/project/CLEAN')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
c = Client()

try:
    user = User.objects.first()
    if user:
        c.force_login(user)
        response = c.get('/business/zones/1/subscriptions/?quartier=1&period=current')
        print('Status:', response.status_code)
        
        if response.status_code == 200:
            content = response.content.decode()
            if 'Aucun client trouvé' in content:
                print('❌ No clients found message displayed')
            else:
                print('✅ Clients are being displayed')
                # Count client rows
                client_rows = content.count('<tr class="hover:bg-slate-50')
                print(f'📊 Number of client rows: {client_rows}')
                
                # Check for payment indicators
                if 'solar:check-circle-linear' in content:
                    payment_indicators = content.count('solar:check-circle-linear')
                    print(f'💰 Payment indicators found: {payment_indicators}')
        else:
            print('❌ Error occurred')
            print('Content:', content[:500] if hasattr(response, 'content') else 'No content')
    else:
        print('❌ No users found in database')
except Exception as e:
    print('❌ Error:', str(e))
    import traceback
    traceback.print_exc()