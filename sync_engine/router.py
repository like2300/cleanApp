from django.conf import settings
import socket
import logging

logger = logging.getLogger(__name__)

class SyncRouter:
    """
    A router to control database operations.
    If settings.LIVE_MODE is 'CLOUD', it uses the cloud database.
    If 'AUTO', it tries cloud and falls back to local.
    """
    
    _is_cloud_reachable_cache = None
    _last_check_time = 0

    def _check_cloud_connectivity(self):
        import time
        now = time.time()

        # Re-check every 10 seconds if we were online, 30 if we were offline
        cache_ttl = 10 if SyncRouter._is_cloud_reachable_cache else 30

        if SyncRouter._is_cloud_reachable_cache is not None and (now - SyncRouter._last_check_time) < cache_ttl:
            return SyncRouter._is_cloud_reachable_cache

        SyncRouter._last_check_time = now
        cloud_db = settings.DATABASES.get('cloud', {})
        host = cloud_db.get('HOST')
        port = int(cloud_db.get('PORT', 3306))

        if not host:
            SyncRouter._is_cloud_reachable_cache = False
            return False

        try:
            # Try to resolve and connect with a very short timeout
            # We use a 1s timeout to keep the UI responsive
            sock = socket.create_connection((host, port), timeout=1.0)
            sock.close()
            SyncRouter._is_cloud_reachable_cache = True
            return True
        except (socket.timeout, socket.error, Exception):
            # Any error means we are probably offline or can't reach the DB
            SyncRouter._is_cloud_reachable_cache = False
            return False
    @classmethod
    def reset_cache(cls):
        cls._is_cloud_reachable_cache = None

    def db_for_read(self, model, **hints):
        # Always respect explicit .using()
        if 'using' in hints:
            return hints['using']
            
        # DeletedRecord must always be local
        if model._meta.model_name == 'deletedrecord':
            return 'default'

        # Local-First: Always use local database for the application logic.
        # This ensures maximum speed and offline capability.
        # The sync engine will use .using('cloud') to pull/push data.
        return 'default'

    def db_for_write(self, model, **hints):
        if 'using' in hints:
            return hints['using']
            
        if model._meta.model_name == 'deletedrecord':
            return 'default'

        # Local-First: Always save locally first.
        # Our AutoSyncMiddleware will detect the change and push it to cloud if online.
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations between objects regardless of which DB they are in
        # (This is risky but necessary for the sync engine's temporary states)
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True
