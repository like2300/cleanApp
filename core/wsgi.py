"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import threading
import time

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

application = get_wsgi_application()


def _background_sync_loop(interval=30):
    """
    Synchronisation automatique en arrière-plan pour la version web (serveur WSGI).

    Comme le serveur web ne lance pas `runcrons`, cette boucle assure que la
    base cloud et la base locale du serveur restent synchronisées en continu,
    indépendamment des requêtes HTTP. Elle réutilise le même verrou que le
    middleware AutoSyncMiddleware pour éviter deux syncs concurrents.
    """
    import logging

    from sync_engine.cron import SyncDataCronJob
    from sync_engine.middleware import AutoSyncMiddleware

    logger = logging.getLogger(__name__)

    while True:
        try:
            if getattr(AutoSyncMiddleware, "_is_syncing", False):
                time.sleep(interval)
                continue

            AutoSyncMiddleware._is_syncing = True
            try:
                # do() vérifie la connectivité et ne fait rien si hors-ligne.
                SyncDataCronJob().do()
            finally:
                AutoSyncMiddleware._is_syncing = False
        except Exception as e:
            logger.debug(f"Synchro arrière-plan (web) ignorée : {e}")
        time.sleep(interval)


# Lancer la boucle de synchro en arrière-plan (une seule fois au démarrage du
# serveur WSGI). Le thread est daemon : il s'arrête avec le process serveur.
_sync_interval = int(os.environ.get("SYNC_INTERVAL", "30"))
_sync_thread = threading.Thread(
    target=_background_sync_loop, args=(_sync_interval,), daemon=True
)
_sync_thread.start()
