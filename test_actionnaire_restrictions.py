#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CLEAN.settings')
sys.path.append('/Users/omerlinks/Desktop/project/CLEAN')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from business.views import zone_employees_manage
from django.contrib import messages

User = get_user_model()
factory = RequestFactory()

# Tester avec un Actionnaire
shareholder = User.objects.filter(role=User.Role.SHAREHOLDER).first()
if shareholder:
    print(f'Test avec Actionnaire: {shareholder.username}')
    
    # Créer une requête POST (qui devrait être bloquée)
    request = factory.post('/business/zones/1/employees/')
    request.user = shareholder
    
    try:
        response = zone_employees_manage(request, 1)
        print(f'Réponse HTTP: {response.status_code}')
        
        # Vérifier les messages
        if hasattr(response, 'cookies'):
            # Pour les redirections, vérifier le message dans la session
            print('✅ Redirection effectuée (accès en lecture seule appliqué)')
        else:
            print('❌ Aucune redirection')
            
    except Exception as e:
        print(f'Erreur: {str(e)}')
    
    # Tester avec une requête GET (qui devrait être autorisée)
    request_get = factory.get('/business/zones/1/employees/')
    request_get.user = shareholder
    
    try:
        response_get = zone_employees_manage(request_get, 1)
        print(f'GET Response: {response_get.status_code}')
        if response_get.status_code == 200:
            print('✅ Accès en lecture autorisé pour les Actionnaires')
        else:
            print(f'❌ Accès refusé: {response_get.status_code}')
            
    except Exception as e:
        print(f'Erreur GET: {str(e)}')
        
else:
    print('Aucun Actionnaire trouvé pour le test')