from django.conf import settings
from .router import SyncRouter
from .cron import SyncDataCronJob
import threading
import time

class AutoSyncMiddleware:
    """
    Middleware that manages data synchronization between Local and Cloud.
    - Pushes local changes after every POST when online.
    - Performs a Full Sync (Push + Pull) on reconnection.
    - Performs a Full Sync periodically while online.
    """
    _last_online_status = None
    _is_syncing = False
    _last_full_sync_time = 0

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        now = time.time()
        
        # Always check connectivity
        router = SyncRouter()
        is_online = router._check_cloud_connectivity()
        
        # 1. RECONNECTION TRIGGER: Offline -> Online
        if is_online and self._last_online_status == False:
            print("AUTO-SYNC: Reconnection detected. Triggering full sync...")
            self.__class__._last_full_sync_time = now
            threading.Thread(target=self._run_auto_sync, args=(2, True)).start()
        
        # 2. PERIODIC PULL: If online and no full sync in the last 10 minutes
        elif is_online and (now - self._last_full_sync_time) > 600: # 10 minutes
            print("AUTO-SYNC: Periodic sync trigger...")
            self.__class__._last_full_sync_time = now
            threading.Thread(target=self._run_auto_sync, args=(5, True)).start()

        self.__class__._last_online_status = is_online

        response = self.get_response(request)

        # 3. IMMEDIATE PUSH: After a successful POST request when online
        if request.method == 'POST' and is_online and response.status_code in [200, 201, 204, 302]:
            threading.Thread(target=self._run_auto_sync, args=(0.5, False)).start()

        return response

    def _run_auto_sync(self, delay=1, full_sync=False):
        try:
            if delay > 0:
                time.sleep(delay)
            
            if getattr(self.__class__, '_is_syncing', False):
                return
            
            self.__class__._is_syncing = True
            try:
                sync_job = SyncDataCronJob()
                if full_sync:
                    print("AUTO-SYNC: Running Full Synchronization (Push + Pull)...")
                    sync_job.do()
                else:
                    sync_job.push_local_changes()
                print("AUTO-SYNC: Synchronization completed successfully.")
            finally:
                self.__class__._is_syncing = False
                
        except Exception as e:
            print(f"AUTO-SYNC ERROR: {str(e)}")
