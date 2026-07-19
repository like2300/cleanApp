from django.db import models

from sync_engine.models import SyncBaseModel


class Zone(SyncBaseModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Quartier(SyncBaseModel):
    name = models.CharField(max_length=100)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="quartiers")

    def __str__(self):
        try:
            zone_name = self.zone.name
        except Exception:
            zone_name = "Zone inconnue"
        return f"{self.name} ({zone_name})"


class Position(SyncBaseModel):
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title


class Employee(SyncBaseModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="employees/", blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    phone_number_2 = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="employees")
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    position = models.ForeignKey(
        Position, on_delete=models.SET_NULL, null=True, related_name="employees"
    )
    hired_at = models.DateField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class SubscriptionPlan(SyncBaseModel):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)
    description = models.TextField(blank=True)
    characteristics = models.TextField(
        blank=True, help_text="Liste des caractéristiques, une par ligne."
    )

    def __str__(self):
        return self.name


class Subscription(SyncBaseModel):
    client = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        try:
            client_name = self.client.username
        except Exception:
            client_name = "Client inconnu"
        try:
            plan_name = self.plan.name
        except Exception:
            plan_name = "Plan inconnu"
        return f"{client_name} - {plan_name}"
