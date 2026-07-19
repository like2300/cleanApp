import random

from django.contrib.auth.models import AbstractUser
from django.db import models

from sync_engine.models import SyncBaseModel


class User(AbstractUser, SyncBaseModel):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ZONE_MANAGER = "ZONE_MANAGER", "Chef de Zone"
        ACCOUNTANT = "ACCOUNTANT", "Comptable"
        AGENT = "AGENT", "Agent"
        CLIENT = "CLIENT", "Client"
        SHAREHOLDER = "SHAREHOLDER", "Actionnaire"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)

    # Redundant fields removed as they are now in SyncBaseModel:
    # uuid, synced, updated_at, site_id

    # Additional fields
    registration_number = models.CharField(
        max_length=6, unique=True, blank=True, null=True
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    phone_number_2 = models.CharField(max_length=20, blank=True, null=True)
    quartier = models.ForeignKey(
        "business.Quartier", on_delete=models.SET_NULL, null=True, blank=True
    )
    address = models.TextField(blank=True, null=True)
    zone = models.ForeignKey(
        "business.Zone", on_delete=models.SET_NULL, null=True, blank=True
    )  # Legacy/Client single zone
    zones = models.ManyToManyField(
        "business.Zone", blank=True, related_name="managers"
    )  # For multi-zone support

    # MoMo payment specific fields
    uses_momo_payment = models.BooleanField(
        default=False, help_text="Si le client paie via Mobile Money"
    )
    fixed_due_date = models.DateField(
        null=True, blank=True, help_text="Date d'échéance fixe pour les paiements MoMo"
    )

    def save(self, *args, **kwargs):
        # Generate registration number if needed
        if not self.registration_number and self.role == self.Role.CLIENT:
            while True:
                number = f"{random.randint(100000, 999999)}"
                if not User.objects.filter(registration_number=number).exists():
                    self.registration_number = number
                    break

        # Store the original fixed_due_date to detect changes
        original_due_date = None
        if self.pk:
            # Use the same database as the save operation
            using = kwargs.get("using", "default")
            original_user = User.objects.using(using).filter(pk=self.pk).first()
            if original_user:
                original_due_date = original_user.fixed_due_date

        super().save(*args, **kwargs)

        # Update all invoices if fixed_due_date changed
        if (
            original_due_date
            and self.fixed_due_date
            and original_due_date != self.fixed_due_date
        ):
            self._update_invoice_due_dates()

    def _update_invoice_due_dates(self):
        """Update all invoices to use the new fixed_due_date"""
        from django.db.models import Q

        from finance.models import Invoice

        # Update all pending invoices for this client
        invoices = Invoice.objects.filter(
            Q(client=self)
            & Q(status=Invoice.Status.PENDING)
            & ~Q(due_date=self.fixed_due_date)
        )

        for invoice in invoices:
            invoice.due_date = Invoice.calculate_due_date(self, invoice.due_date)
            invoice.save()
            print(f"Updated invoice {invoice.uuid} due date to {invoice.due_date}")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class CompanySettings(SyncBaseModel):
    name = models.CharField(max_length=255, default="INFINITY")
    logo = models.ImageField(upload_to="company/", blank=True, null=True)
    primary_color = models.CharField(
        max_length=7,
        default="#010694",
        help_text="Hex code for primary color (e.g. #010694)",
    )
    secondary_color = models.CharField(max_length=7, default="#2435c9")
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        verbose_name = "Paramètres de la société"
        verbose_name_plural = "Paramètres de la société"

    def __str__(self):
        return self.name

    @classmethod
    def get_settings(cls):
        try:
            # Try the routed database (could be cloud in AUTO mode)
            settings, created = cls.objects.get_or_create(id=1)
            return settings
        except Exception:
            # Fallback to local SQLite if cloud fails
            try:
                settings, created = cls.objects.using("default").get_or_create(id=1)
                return settings
            except:
                # Last resort: empty object
                return cls(id=1, name="INFINITY")
