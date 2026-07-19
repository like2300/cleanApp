from django.db import models
from django.conf import settings
from sync_engine.models import SyncBaseModel

class Notification(SyncBaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        try:
            username = self.user.username
        except Exception:
            username = "Utilisateur inconnu"
        return f"Notif for {username}: {self.title}"

class Reclamation(SyncBaseModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours'
        RESOLVED = 'RESOLVED', 'Résolue'
        CLOSED = 'CLOSED', 'Fermée'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reclamations', null=True, blank=True)
    guest_name = models.CharField(max_length=100, null=True, blank=True)
    guest_contact = models.CharField(max_length=100, null=True, blank=True)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reclamation {self.id} - {self.subject}"
