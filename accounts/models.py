import random
import uuid as uuid_lib

from django.contrib.auth.models import AbstractUser
from django.db import models

from sync_engine.models import SyncBaseModel

# UUID constant pour CompanySettings : comme c'est un singleton (une seule
# instance d'entreprise), tous les sites (local + cloud) doivent partager le
# MEME uuid pour que le moteur de synchronisation (qui identifie les objets
# par uuid) le reconnaisse comme le meme enregistrement et propage les
# modifications (ex: couleurs) dans les deux sens.
COMPANY_SETTINGS_UUID = uuid_lib.UUID("00000000-0000-0000-0000-000000000001")


class User(AbstractUser, SyncBaseModel):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ZONE_MANAGER = "ZONE_MANAGER", "Chef de Zone"
        ACCOUNTANT = "ACCOUNTANT", "Comptable"
        AGENT = "AGENT", "Agent"
        CLIENT = "CLIENT", "Client"
        SHAREHOLDER = "SHAREHOLDER", "Actionnaire"

    # Le username reste techniquement unique (exigence Django USERNAME_FIELD),
    # mais il est genere a partir de l'uuid donc deux clients peuvent avoir
    # le meme NOM affiche. La distinction reelle se fait via l'uuid (ID de
    # synchronisation), pas le username. Le login client utilise
    # registration_number, pas username.
    username = models.CharField(max_length=150, unique=True, blank=False)

    # Nom reel affiche dans l'UI (peut etre partage par plusieurs clients).
    display_name = models.CharField(max_length=255, blank=True, null=True)

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

        # Garantir un username unique base sur l'uuid, sans empecher deux
        # clients d'avoir le meme NOM affiche. Le username est technique
        # (derive de l'uuid) ; le nom reel est stocke dans display_name.
        if not self.uuid:
            self.uuid = uuid_lib.uuid4()
        if not self.username:
            self.username = f"u{str(self.uuid).replace('-', '')[:12]}"
        # Copier le nom affiche si non renseigne
        if not self.display_name:
            self.display_name = self.first_name or self.last_name or self.username

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
        # CompanySettings est un singleton identifie par un UUID constant
        # (COMPANY_SETTINGS_UUID) afin que le moteur de synchronisation, qui
        # compare les objets par uuid, le reconnaisse comme le meme enregistrement
        # sur tous les sites (local + cloud) et propage les modifications.
        try:
            settings, created = cls.objects.get_or_create(
                uuid=COMPANY_SETTINGS_UUID,
                defaults={"name": "INFINITY"},
            )
            return settings
        except Exception:
            # Fallback to local SQLite if cloud fails
            try:
                settings, created = cls.objects.using("default").get_or_create(
                    uuid=COMPANY_SETTINGS_UUID,
                    defaults={"name": "INFINITY"},
                )
                return settings
            except Exception:
                # Last resort: empty object
                return cls(name="INFINITY")
