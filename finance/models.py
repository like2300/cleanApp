from calendar import monthrange
from datetime import timedelta

from django.db import models
from django.utils import timezone

from finance.billing import add_months_safe
from sync_engine.models import SyncBaseModel


class Invoice(SyncBaseModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        PAID = "PAID", "Payée"
        CANCELLED = "CANCELLED", "Annulée"

    class InvoiceType(models.TextChoices):
        PAIEMENT = "PAIEMENT", "Paiement"

    client = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="invoices"
    )
    subscription = models.ForeignKey(
        "business.Subscription", on_delete=models.SET_NULL, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_type = models.CharField(
        max_length=20, choices=InvoiceType.choices, default=InvoiceType.PAIEMENT
    )
    due_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    last_alert_sent = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        try:
            client_name = self.client.username
        except Exception:
            client_name = "Client inconnu"
        return f"Facture {self.uuid} - {client_name}"

    @property
    def has_pending_validation(self):
        return self.payments.filter(is_validated=False).exists()

    @staticmethod
    def calculate_due_date(client, reference_date=None):
        """
        Calculate the next invoice due date using the client's saved billing day.
        The day stays fixed and only the month advances.
        """
        if not reference_date:
            reference_date = timezone.now().date()

        if not client.fixed_due_date:
            return reference_date + timedelta(days=7)

        due_date = reference_date.replace(
            day=min(
                client.fixed_due_date.day,
                monthrange(reference_date.year, reference_date.month)[1],
            )
        )
        if due_date < reference_date:
            due_date = add_months_safe(
                due_date, 1, anchor_day=client.fixed_due_date.day
            )

        return due_date


class Payment(SyncBaseModel):
    class Method(models.TextChoices):
        MOBILE_MONEY = "Mobile Money", "Mobile Money"
        PHYSIQUE = "Physique", "Physique"
        AUTRE = "Autre", "Autre"

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=50, choices=Method.choices, default=Method.MOBILE_MONEY
    )
    transaction_id = models.CharField(max_length=100, unique=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure paid_at is timezone-aware if USE_TZ is True
        from django.conf import settings
        from django.utils import timezone

        if settings.USE_TZ and self.paid_at and timezone.is_naive(self.paid_at):
            # Make the datetime timezone-aware using the default timezone
            self.paid_at = timezone.make_aware(self.paid_at)

        super().save(*args, **kwargs)

    # Validation fields
    is_validated = models.BooleanField(default=False)
    validated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_payments",
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        try:
            invoice_uuid = self.invoice.uuid
        except Exception:
            invoice_uuid = "Facture inconnue"
        return f"Paiement {self.transaction_id} pour {invoice_uuid}"


class ExpenseCategory(SyncBaseModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Type de dépense"
        verbose_name_plural = "Types de dépenses"

    def __str__(self):
        return self.name


class Expense(SyncBaseModel):
    DEFAULT_CATEGORIES = {
        "SALARY": "Salaires",
        "RENT": "Loyer",
        "EQUIPMENT": "Matériel",
        "FUEL": "Carburant",
        "MAINTENANCE": "Entretien",
        "TAXES": "Impôts & Taxes",
        "OTHER": "Autre",
    }

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, default="OTHER")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def category_display(self):
        category = ExpenseCategory.objects.filter(code=self.category).first()
        if category:
            return category.name
        return self.DEFAULT_CATEGORIES.get(self.category, self.category)

    def __str__(self):
        return f"{self.title} - {self.amount} FCFA"
