from django.apps import AppConfig


class SyncEngineConfig(AppConfig):
    name = 'sync_engine'

    def ready(self):
        import sync_engine.signals
