import os
import sys
import django
import time
import io
from pathlib import Path

# Fix Windows console encoding (cp1252 can't handle emojis)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from sync_engine.router import SyncRouter
from sync_engine.models import SyncBaseModel
from django.apps import apps
from django.conf import settings
from sync_engine.cron import SyncDataCronJob

def run_test():
    print("=" * 70)
    print("🚀 DÉBUT DU TEST DE SYNCHRONISATION CLOUD")
    print("=" * 70)

    # 1. Tester la connectivité Cloud
    router = SyncRouter()
    SyncRouter.reset_cache()
    t0 = time.time()
    is_online = router._check_cloud_connectivity()
    latency = (time.time() - t0) * 1000
    
    print(f"📡 Connexion Cloud : {'✅ EN LIGNE' if is_online else '❌ HORS LIGNE'} ({latency:.1f}ms)")
    
    if not is_online:
        print("\n❌ Impossible de continuer car le serveur Cloud n'est pas joignable.")
        print("Veuillez vérifier votre connexion Internet et les paramètres de base de données (settings.py).")
        return

    # 2. État initial (Avant sync)
    print("\n📊 État de synchronisation initial (Avant sync) :")
    sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]
    initial_unsynced = 0
    
    for model in sync_models:
        try:
            local_count = model.objects.using('default').count()
            cloud_count = model.objects.using('cloud').count()
            unsynced_count = model.objects.using('default').filter(synced=False).count()
            initial_unsynced += unsynced_count
            
            status = "✅ Synch." if unsynced_count == 0 else f"⚠️ {unsynced_count} en attente"
            print(f"  • {model._meta.label:<40} Local: {local_count:<4} | Cloud: {cloud_count:<4} | {status}")
        except Exception as e:
            print(f"  • ❌ Erreur pour {model._meta.label} : {e}")

    # 3. Exécution du Push (Local -> Cloud)
    print("\n📤 Exécution du PUSH (Local -> Cloud)...")
    cron = SyncDataCronJob()
    try:
        cron.push_local_changes()
        print("✅ Exécution du PUSH terminée sans erreur bloquante.")
    except Exception as e:
        import traceback
        print("❌ Erreur critique lors du PUSH :")
        traceback.print_exc()

    # 4. Exécution du Pull (Cloud -> Local)
    print("\n📥 Exécution du PULL (Cloud -> Local)...")
    try:
        cron.pull_cloud_changes()
        print("✅ Exécution du PULL terminée sans erreur bloquante.")
    except Exception as e:
        import traceback
        print("❌ Erreur critique lors du PULL :")
        traceback.print_exc()

    # 5. État final (Après sync)
    print("\n📊 État de synchronisation final (Après sync) :")
    final_unsynced = 0
    for model in sync_models:
        try:
            local_count = model.objects.using('default').count()
            cloud_count = model.objects.using('cloud').count()
            unsynced_count = model.objects.using('default').filter(synced=False).count()
            final_unsynced += unsynced_count
            
            status = "✅ Synch." if unsynced_count == 0 else f"⚠️ {unsynced_count} en attente"
            print(f"  • {model._meta.label:<40} Local: {local_count:<4} | Cloud: {cloud_count:<4} | {status}")
        except Exception as e:
            print(f"  • ❌ Erreur pour {model._meta.label} : {e}")

    print("\n" + "=" * 70)
    if final_unsynced == 0:
        print("🎉 RÉSULTAT : SYNCHRONISATION COMPLÈTE ET OPÉRATIONNELLE !")
    else:
        print(f"⚠️ RÉSULTAT : SYNCHRONISATION PARTIELLE ({final_unsynced} éléments restants).")
    print("=" * 70)

if __name__ == '__main__':
    run_test()
