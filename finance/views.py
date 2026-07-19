from calendar import monthrange
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from business.models import Subscription, Zone
from core.excel import ExcelReportBuilder
from core.utils import block_read_only_role, check_zone_access, get_zone_queryset
from finance.billing import (
    invoice_due_date_for_subscription,
    payment_subscription_end_date,
)

from .models import Expense, ExpenseCategory, Invoice, Payment


def add_months_safe(date_value, months):
    month_index = date_value.month - 1 + months
    year = date_value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date_value.day, monthrange(year, month)[1])
    return date_value.replace(year=year, month=month, day=day)


def calculate_next_available_invoice_due_date(
    client, subscription, reference_date=None
):
    reference_date = reference_date or timezone.now().date()
    due_date = Invoice.calculate_due_date(client, reference_date)

    while Invoice.objects.filter(
        client=client,
        subscription=subscription,
        due_date__year=due_date.year,
        due_date__month=due_date.month,
    ).exists():
        due_date = add_months_safe(due_date, 1)

    return due_date


@login_required
def export_my_invoices_excel(request):
    if request.user.role != User.Role.CLIENT:
        messages.error(request, "Accès réservé aux clients.")
        return redirect("dashboard")

    user = request.user
    invoices = user.invoices.all().order_by("-created_at")

    report = ExcelReportBuilder(
        "Mes factures",
        request=request,
        filename_prefix=f"mes_factures_{user.registration_number or user.username}",
    )
    ws = report.active_sheet("Factures")
    report.add_title(ws, 6)
    start = report.add_kpis(
        ws,
        [
            ("Factures", invoices.count()),
            ("Client", user.registration_number or user.username),
        ],
        start_row=4,
    )
    rows = [
        [
            inv.created_at.strftime("%d/%m/%Y"),
            str(inv.uuid)[:8].upper(),
            inv.amount,
            inv.get_invoice_type_display(),
            inv.due_date.strftime("%d/%m/%Y"),
            inv.get_status_display(),
        ]
        for inv in invoices
    ]
    report.add_table(
        ws,
        ["Date", "Référence", "Montant (FCFA)", "Type", "Échéance", "Statut"],
        rows,
        start_row=start,
        table_name="MesFactures",
    )
    return report.response()


@login_required
def expense_list(request):
    if request.user.role not in [User.Role.ACCOUNTANT, User.Role.SHAREHOLDER]:
        messages.error(
            request,
            "Accès refusé. Seul le comptable ou l'actionnaire peut consulter les dépenses.",
        )
        return redirect("dashboard")

    expenses_qs = Expense.objects.all().order_by("-expense_date")

    # Ensure default categories exist for older databases/data without creating data
    # during read-only shareholder consultation.
    if request.user.role == User.Role.ACCOUNTANT:
        for code, name in Expense.DEFAULT_CATEGORIES.items():
            ExpenseCategory.objects.get_or_create(code=code, defaults={"name": name})

    categories = ExpenseCategory.objects.all()

    # Filter
    cat_filter = request.GET.get("category")
    if cat_filter:
        expenses_qs = expenses_qs.filter(category=cat_filter)

    total_amount = expenses_qs.aggregate(Sum("amount"))["amount__sum"] or 0

    paginator = Paginator(expenses_qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "finance/expense_list.html",
        {
            "expenses": page_obj,
            "categories": categories,
            "total_amount": total_amount,
            "filters": {"category": cat_filter},
        },
    )


@login_required
def expense_create(request):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request,
            "Accès refusé. Seul le comptable peut enregistrer des dépenses.",
        )
        return redirect("expense_list")

    if request.method == "POST":
        title = request.POST.get("title")
        category = request.POST.get("category")
        amount = request.POST.get("amount")
        date = request.POST.get("expense_date")
        desc = request.POST.get("description")

        Expense.objects.create(
            title=title,
            category=category,
            amount=amount,
            expense_date=date,
            description=desc,
            recorded_by=request.user,
            synced=False,
        )
        messages.success(request, "Dépense enregistrée.")
        return redirect("expense_list")
    return render(
        request,
        "finance/expense_form.html",
        {
            "categories": ExpenseCategory.objects.filter(is_active=True),
            "form_title": "Nouvelle Dépense",
            "form_subtitle": "Enregistrez une charge pour la comptabilité.",
            "submit_label": "Enregistrer la Dépense",
        },
    )


@login_required
def expense_edit(request, pk):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request,
            "Accès refusé. Seul le comptable peut modifier les dépenses.",
        )
        return redirect("expense_list")

    expense = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        expense.title = request.POST.get("title")
        expense.category = request.POST.get("category")
        expense.amount = request.POST.get("amount")
        expense.expense_date = request.POST.get("expense_date")
        expense.description = request.POST.get("description")
        expense.recorded_by = request.user
        expense.synced = False
        expense.save()
        messages.success(request, "Dépense mise à jour.")
        return redirect("expense_list")

    return render(
        request,
        "finance/expense_form.html",
        {
            "expense": expense,
            "categories": ExpenseCategory.objects.filter(is_active=True),
            "form_title": "Modifier la Dépense",
            "form_subtitle": "Mettez à jour les informations de la dépense.",
            "submit_label": "Mettre à jour la Dépense",
        },
    )


@login_required
def expense_delete(request, pk):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request,
            "Accès refusé. Seul le comptable peut supprimer les dépenses.",
        )
        return redirect("expense_list")

    expense = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Dépense supprimée.")
    return redirect("expense_list")


@login_required
def expense_category_create(request):
    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request, "Accès refusé. Seul le comptable peut gérer les types de dépenses."
        )
        return redirect("expense_list")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip().upper().replace(" ", "_")
        if not code and name:
            code = name.upper().replace(" ", "_")

        if not name or not code:
            messages.error(request, "Le nom du type de dépense est requis.")
        elif ExpenseCategory.objects.filter(code=code).exists():
            messages.error(request, "Ce type de dépense existe déjà.")
        else:
            ExpenseCategory.objects.create(code=code, name=name, synced=False)
            messages.success(request, f"Type de dépense '{name}' ajouté.")

    return redirect("expense_list")


@login_required
def expense_category_edit(request, pk):
    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request, "Accès refusé. Seul le comptable peut gérer les types de dépenses."
        )
        return redirect("expense_list")

    category = get_object_or_404(ExpenseCategory, pk=pk)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        is_active = request.POST.get("is_active") == "on"
        if not name:
            messages.error(request, "Le nom du type de dépense est requis.")
        else:
            category.name = name
            category.is_active = is_active
            category.synced = False
            category.save()
            messages.success(request, "Type de dépense mis à jour.")

    return redirect("expense_list")


@login_required
def expense_category_delete(request, pk):
    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request, "Accès refusé. Seul le comptable peut gérer les types de dépenses."
        )
        return redirect("expense_list")

    category = get_object_or_404(ExpenseCategory, pk=pk)
    if request.method == "POST":
        if Expense.objects.filter(category=category.code).exists():
            category.is_active = False
            category.synced = False
            category.save()
            messages.warning(
                request,
                "Ce type est utilisé par des dépenses existantes, il a été désactivé.",
            )
        else:
            category.delete()
            messages.success(request, "Type de dépense supprimé.")

    return redirect("expense_list")


@login_required
def invoice_list(request):
    user = request.user

    # Base Queryset
    invoices_qs = get_zone_queryset(
        user, Invoice.objects.all(), zone_field="client__zone"
    ).select_related("client", "client__zone", "subscription", "subscription__plan")

    # Check if user has access to any invoices.
    # Only ZONE_MANAGER is blocked when no zone is assigned. ACCOUNTANT and
    # SHAREHOLDER see all data globally even without an assigned zone.
    if not invoices_qs.exists() and user.role == User.Role.ZONE_MANAGER:
        if not user.zones.exists():
            messages.error(
                request,
                "Vous n'avez pas de zone assignée. Veuillez contacter l'administrateur.",
            )
            return redirect("dashboard")
        else:
            messages.info(request, "Aucune facture trouvée pour vos zones.")

    # Filtering logic
    status_filter = request.GET.get("status")
    zone_filter = request.GET.get("zone")
    quartier_filter = request.GET.get("quartier")
    search_query = request.GET.get("q")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status_filter:
        invoices_qs = invoices_qs.filter(status=status_filter)
    if zone_filter:
        invoices_qs = invoices_qs.filter(client__zone_id=zone_filter)
    if quartier_filter:
        invoices_qs = invoices_qs.filter(client__quartier_id=quartier_filter)
    if search_query:
        from django.db.models import Q

        invoices_qs = invoices_qs.filter(
            Q(client__username__icontains=search_query)
            | Q(client__first_name__icontains=search_query)
            | Q(client__last_name__icontains=search_query)
            | Q(client__registration_number__icontains=search_query)
        )
    if date_from:
        invoices_qs = invoices_qs.filter(created_at__date__gte=date_from)
    if date_to:
        invoices_qs = invoices_qs.filter(created_at__date__lte=date_to)

    invoices_qs = invoices_qs.order_by("-created_at")

    # Global Stats (filtered by current queryset before pagination)
    total_invoiced = invoices_qs.aggregate(Sum("amount"))["amount__sum"] or 0
    # Payment doesn't have a direct zone field, so we filter by invoice
    payments = Payment.objects.filter(invoice__in=invoices_qs)
    total_paid = payments.aggregate(Sum("amount"))["amount__sum"] or 0

    # Pagination
    paginator = Paginator(invoices_qs, 25)  # 25 invoices per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Zone-wise Stats
    zones = get_zone_queryset(user, Zone.objects.all())
    from business.models import Quartier

    quartiers = get_zone_queryset(user, Quartier.objects.all(), zone_field="zone")

    zone_stats = []
    for zone in zones:
        zone_invoices = Invoice.objects.filter(client__zone=zone)
        zone_invoiced = zone_invoices.aggregate(Sum("amount"))["amount__sum"] or 0
        zone_paid = (
            Payment.objects.filter(invoice__client__zone=zone).aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        zone_stats.append(
            {
                "zone": zone,
                "invoiced": zone_invoiced,
                "paid": zone_paid,
                "percent": (zone_paid / zone_invoiced * 100)
                if zone_invoiced > 0
                else 0,
            }
        )

    # For the Global Invoice Modal
    clients = get_zone_queryset(
        user, User.objects.filter(role=User.Role.CLIENT).select_related("zone")
    )
    client_data = []
    for client in clients:
        sub = client.subscriptions.filter(is_active=True).first()
        next_due_date = (
            calculate_next_available_invoice_due_date(
                client, sub, timezone.now().date()
            )
            if sub
            else None
        )
        client_data.append(
            {
                "client": client,
                "subscription": sub,
                "price": sub.plan.price if sub else 0,
                "next_due_date": next_due_date,
            }
        )

    return render(
        request,
        "finance/invoice_list.html",
        {
            "invoices": page_obj,  # Pass page_obj as invoices
            "page_obj": page_obj,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "pending_amount": total_invoiced - total_paid,
            "recovery_rate": (total_paid / total_invoiced * 100)
            if total_invoiced > 0
            else 0,
            "zone_stats": zone_stats,
            "zones_list": zones,
            "quartiers_list": quartiers,
            "status_choices": Invoice.Status.choices,
            "now": timezone.now(),
            "client_data": client_data,
            "invoice_types": Invoice.InvoiceType.choices,
            "pending_payments": get_zone_queryset(
                user,
                Payment.objects.filter(is_validated=False),
                zone_field="invoice__client__zone",
            ).select_related("invoice", "invoice__client", "invoice__subscription"),
            "filters": {
                "status": status_filter,
                "zone": zone_filter,
                "quartier": quartier_filter,
                "q": search_query,
                "date_from": date_from,
                "date_to": date_to,
            },
        },
    )


@login_required
def invoice_create(request):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.ACCOUNTANT]:
        messages.error(
            request,
            "Accès refusé. Seul le comptable ou l'administrateur peut créer des factures.",
        )
        return redirect("invoice_list")

    if request.method == "POST":
        from decimal import Decimal

        client_id = request.POST.get("client")
        amount = Decimal(request.POST.get("amount", "0"))
        invoice_type = request.POST.get("invoice_type", Invoice.InvoiceType.PAIEMENT)

        client = get_object_or_404(User, id=client_id, role=User.Role.CLIENT)

        if client.zone and not check_zone_access(request.user, client.zone.id):
            messages.error(request, "Accès refusé.")
            return redirect("invoice_list")

        subscription = client.subscriptions.filter(is_active=True).first()

        if not subscription:
            messages.error(request, "Ce client n'a pas d'abonnement actif.")
            return redirect("invoice_list")

        # Check if there's already an existing invoice (paid or unpaid)
        existing_invoices = Invoice.objects.filter(
            client=client,
            subscription=subscription,
            status__in=[Invoice.Status.PENDING, Invoice.Status.PAID],
        ).order_by("-created_at")

        if existing_invoices.exists():
            latest_invoice = existing_invoices.first()
            if latest_invoice.status == Invoice.Status.PENDING:
                messages.error(
                    request,
                    f"Une facture impayée existe déjà pour ce client (Facture #{latest_invoice.id}). "
                    f"Veuillez la régler avant d'en créer une nouvelle.",
                )
            else:  # PAID
                messages.error(
                    request,
                    f"Une facture payée existe déjà pour ce client (Facture #{latest_invoice.id}). "
                    f"Attendez la fin de la période actuelle avant d'en créer une nouvelle.",
                )
            return redirect("invoice_list")

        plan_price = subscription.plan.price
        amount = plan_price

        calculated_due_date = calculate_next_available_invoice_due_date(
            client,
            subscription,
            timezone.now().date(),
        )

        invoice = Invoice.objects.create(
            client=client,
            subscription=subscription,
            amount=amount,
            invoice_type=invoice_type,
            due_date=calculated_due_date,
            synced=False,
        )
        messages.success(
            request,
            f"Facture de {amount} FCFA générée pour {client.first_name or client.username}.",
        )
        return redirect("payment_create", invoice_id=invoice.id)


@login_required
def create_invoice_from_subscription(request, subscription_id):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.ACCOUNTANT]:
        messages.error(request, "Accès refusé.")
        return redirect("invoice_list")

    subscription = get_object_or_404(Subscription, id=subscription_id)

    if subscription.client.zone and not check_zone_access(
        request.user, subscription.client.zone.id
    ):
        messages.error(request, "Accès refusé.")
        return redirect("invoice_list")

    calculated_due_date = calculate_next_available_invoice_due_date(
        subscription.client,
        subscription,
        timezone.now().date(),
    )

    invoice = Invoice.objects.create(
        client=subscription.client,
        subscription=subscription,
        amount=subscription.plan.price,
        due_date=calculated_due_date,
        status=Invoice.Status.PENDING,
        synced=False,
    )

    messages.success(request, f"Facture générée pour {subscription.client.username}")
    return redirect("payment_create", invoice_id=invoice.id)


@login_required
def initiate_payment(request, invoice_id=None):
    if request.method == "POST":
        user = request.user

        # If invoice_id is provided, use that invoice. Otherwise find a pending one or create one.
        if invoice_id:
            invoice = get_object_or_404(Invoice, id=invoice_id, client=user)
            if invoice.status == Invoice.Status.PAID:
                messages.info(request, "Cette facture est déjà payée.")
                return redirect("accounts:client_invoice_list")
            subscription = invoice.subscription
        else:
            subscription = user.subscriptions.select_related("plan").first()
            if not subscription:
                messages.error(request, "Aucun abonnement actif trouvé.")
                return redirect("accounts:client_dashboard")

            # Check for ANY pending invoice first
            invoice = Invoice.objects.filter(
                client=user, subscription=subscription, status=Invoice.Status.PENDING
            ).first()

            if invoice:
                # If an invoice exists, we should probably just use it or warn
                # The user requested to show a warning if they try to create a NEW one
                messages.warning(
                    request,
                    "Vous avez déjà une facture en attente. Veuillez la régler dans votre liste de factures.",
                )
                return redirect("accounts:client_dashboard")

            # Create new invoice if none exists
            # Calculate due date based on client's fixed due date
            calculated_due_date = calculate_next_available_invoice_due_date(
                user,
                subscription,
                timezone.now().date(),
            )

            invoice = Invoice.objects.create(
                client=user,
                subscription=subscription,
                amount=subscription.plan.price,
                due_date=calculated_due_date,
                status=Invoice.Status.PENDING,
                synced=False,
            )

        amount = int(invoice.amount)

        url = settings.OPENPAY_URL
        headers = {
            "XO-API-KEY": settings.OPENPAY_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "amount": amount,
            "description": f"Facture {invoice.uuid} - {user.registration_number}",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()

            if response.status_code == 200 or response.status_code == 201:
                payment_data = data.get("data", {})
                payment_url = payment_data.get("payment_url")

                if payment_url:
                    return redirect(payment_url)
                else:
                    messages.error(request, "Lien de paiement non reçu d'OpenPay.")
            else:
                error_msg = data.get(
                    "message", "Erreur lors de la création du lien de paiement."
                )
                messages.error(request, f"Erreur OpenPay : {error_msg}")

        except Exception as e:
            messages.error(request, f"Erreur de connexion à OpenPay : {str(e)}")

    return redirect("accounts:client_dashboard")


@login_required
def payment_create(request, invoice_id):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request,
            "Accès refusé. Seul le comptable peut effectuer le paiement d'une facture.",
        )
        return redirect("invoice_list")

    invoice = get_object_or_404(Invoice, id=invoice_id)

    if invoice.client.zone and not check_zone_access(
        request.user, invoice.client.zone.id
    ):
        messages.error(request, "Accès refusé.")
        return redirect("invoice_list")

    # Check for existing payment this month for this client
    now = timezone.now()
    existing_payment = Payment.objects.filter(
        invoice__client=invoice.client,
        paid_at__year=now.year,
        paid_at__month=now.month,
        is_validated=True,
    ).exists()

    if existing_payment:
        messages.warning(
            request,
            f"Attention: Un paiement a déjà été validé ce mois-ci pour {invoice.client.first_name or invoice.client.username}.",
        )

    if request.method == "POST":
        import uuid
        from decimal import Decimal

        amount = Decimal(request.POST.get("amount", "0"))
        transaction_id = request.POST.get("transaction_id")
        payment_method = request.POST.get("payment_method", Payment.Method.MOBILE_MONEY)

        if payment_method not in Payment.Method.values:
            messages.error(request, "Mode de paiement invalide.")
            return redirect("payment_create", invoice_id=invoice.id)

        if not transaction_id:
            transaction_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"

        Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_method=payment_method,
            transaction_id=transaction_id,
            is_validated=True,
            validated_by=request.user,
            validated_at=timezone.now(),
            synced=False,
        )

        # Update Invoice
        invoice.status = Invoice.Status.PAID
        invoice.synced = False
        invoice.save()

        # Update Subscription
        if invoice.subscription:
            sub = invoice.subscription
            sub.end_date = payment_subscription_end_date(invoice)
            sub.is_active = True
            sub.synced = False
            sub.save()

            # Sync back to client status if needed
            client = invoice.client
            client.synced = False
            client.save()

        messages.success(
            request, f"Paiement de {amount} FCFA enregistré et validé avec succès."
        )
        # Redirect to the print view directly
        return redirect("invoice_print", pk=invoice.pk)

    suggested_date = payment_subscription_end_date(invoice)

    return render(
        request,
        "finance/payment_form.html",
        {"invoice": invoice, "suggested_date": suggested_date.isoformat()},
    )


@login_required
def analytics_dashboard(request):
    if request.user.role not in [
        User.Role.SUPER_ADMIN,
        User.Role.ACCOUNTANT,
        User.Role.SHAREHOLDER,
    ]:
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    user = request.user

    # Filters
    zone_filter = request.GET.get("zone")
    quartier_filter = request.GET.get("quartier")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    # Base Querysets
    invoices_qs = get_zone_queryset(
        user, Invoice.objects.all(), zone_field="client__zone"
    )
    payments_qs = get_zone_queryset(
        user,
        Payment.objects.filter(is_validated=True),
        zone_field="invoice__client__zone",
    )

    # Check if user has access to any data.
    # Only ZONE_MANAGER is blocked when no zone is assigned. ACCOUNTANT and
    # SHAREHOLDER see all data globally even without an assigned zone.
    if (
        not invoices_qs.exists()
        and not payments_qs.exists()
        and user.role == User.Role.ZONE_MANAGER
    ):
        if not user.zones.exists():
            messages.error(
                request,
                "Vous n'avez pas de zone assignée. Veuillez contacter l'administrateur.",
            )
            return redirect("dashboard")
        else:
            messages.info(request, "Aucune donnée trouvée pour vos zones.")

    if zone_filter:
        invoices_qs = invoices_qs.filter(client__zone_id=zone_filter)
        payments_qs = payments_qs.filter(invoice__client__zone_id=zone_filter)
    if quartier_filter:
        invoices_qs = invoices_qs.filter(client__quartier_id=quartier_filter)
        payments_qs = payments_qs.filter(invoice__client__quartier_id=quartier_filter)
    if date_from:
        invoices_qs = invoices_qs.filter(created_at__date__gte=date_from)
        payments_qs = payments_qs.filter(paid_at__date__gte=date_from)
    if date_to:
        invoices_qs = invoices_qs.filter(created_at__date__lte=date_to)
        payments_qs = payments_qs.filter(paid_at__date__lte=date_to)

    # Global Stats
    total_invoiced = invoices_qs.aggregate(Sum("amount"))["amount__sum"] or 0
    total_paid = payments_qs.aggregate(Sum("amount"))["amount__sum"] or 0
    recovery_rate = (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0

    # 1. Recovery by Zone
    zones = get_zone_queryset(user, Zone.objects.all())
    zone_data = []
    for zone in zones:
        z_inv = (
            invoices_qs.filter(client__zone=zone).aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        z_pay = (
            payments_qs.filter(invoice__client__zone=zone).aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        zone_data.append(
            {
                "name": zone.name,
                "invoiced": float(z_inv),
                "paid": float(z_pay),
                "rate": (float(z_pay) / float(z_inv) * 100) if z_inv > 0 else 0,
            }
        )

    # 2. Monthly Trend (Last 6 months)
    now = timezone.now()
    monthly_labels = []
    monthly_invoiced = []
    monthly_paid = []

    for i in range(5, -1, -1):
        d = now - timedelta(days=i * 30)
        month_label = d.strftime("%b %Y")
        monthly_labels.append(month_label)

        m_inv = (
            invoices_qs.filter(
                created_at__month=d.month, created_at__year=d.year
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )
        m_pay = (
            payments_qs.filter(paid_at__month=d.month, paid_at__year=d.year).aggregate(
                Sum("amount")
            )["amount__sum"]
            or 0
        )
        monthly_invoiced.append(float(m_inv))
        monthly_paid.append(float(m_pay))

    # 3. Category Distribution
    cat_data = []
    for cat_val, cat_label in Expense.DEFAULT_CATEGORIES.items():
        amt = (
            Expense.objects.filter(category=cat_val).aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )
        if amt > 0:
            cat_data.append({"label": cat_label, "value": float(amt)})

    from business.models import Quartier

    return render(
        request,
        "finance/analytics_dashboard.html",
        {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "recovery_rate": recovery_rate,
            "zone_data": zone_data,
            "monthly_labels": monthly_labels,
            "monthly_invoiced": monthly_invoiced,
            "monthly_paid": monthly_paid,
            "cat_data": cat_data,
            "zones_list": zones,
            "quartiers_list": get_zone_queryset(
                user, Quartier.objects.all(), zone_field="zone"
            ),
            "filters": {
                "zone": zone_filter,
                "quartier": quartier_filter,
                "date_from": date_from,
                "date_to": date_to,
            },
        },
    )


@login_required
def payment_validate(request, payment_id):
    read_only_response = block_read_only_role(request)
    if read_only_response:
        return read_only_response

    if request.user.role != User.Role.ACCOUNTANT:
        messages.error(
            request,
            "Accès refusé. Seul le comptable peut valider les paiements.",
        )
        return redirect("invoice_list")

    payment = get_object_or_404(Payment, id=payment_id)

    # Check zone access for accountant if they have assigned zones
    if request.user.role == User.Role.ACCOUNTANT:
        client_zone = payment.invoice.client.zone
        if client_zone and not check_zone_access(request.user, client_zone.id):
            messages.error(request, "Accès refusé à cette zone.")
            return redirect("invoice_list")

    if request.method == "POST":
        invoice = payment.invoice
        end_date = payment_subscription_end_date(invoice)

        # Update Payment
        payment.is_validated = True
        payment.validated_by = request.user
        payment.validated_at = timezone.now()
        payment.synced = False
        payment.save()

        # Update Invoice
        invoice.status = Invoice.Status.PAID
        invoice.synced = False
        invoice.save()

        # Update Subscription
        if invoice.subscription:
            sub = invoice.subscription
            sub.end_date = end_date
            sub.is_active = True
            sub.synced = False
            sub.save()

            # Ensure client is active
            client = sub.client
            if not client.is_active:
                client.is_active = True
                client.synced = False
                client.save()

        messages.success(
            request,
            f"Paiement validé. Abonnement de {invoice.client.username} mis à jour jusqu'au {end_date}.",
        )

    return redirect("invoice_list")


def check_and_create_invoices_for_expired_subscriptions():
    """
    Check for expired subscriptions and automatically create pending invoices.
    This function should be called periodically (e.g., via cron job or management command).
    """
    from business.models import Subscription
    from finance.models import Invoice

    today = timezone.now().date()

    # Find active subscriptions that are expired or about to expire
    expired_subscriptions = Subscription.objects.filter(
        is_active=True, end_date__lte=today
    )

    for subscription in expired_subscriptions:
        client = subscription.client

        # Check if there's already a pending invoice for this subscription
        existing_pending_invoice = Invoice.objects.filter(
            client=client, subscription=subscription, status=Invoice.Status.PENDING
        ).exists()

        if not existing_pending_invoice:
            calculated_due_date = invoice_due_date_for_subscription(subscription)

            # Create a new pending invoice
            Invoice.objects.create(
                client=client,
                subscription=subscription,
                amount=subscription.plan.price,
                invoice_type=Invoice.InvoiceType.PAIEMENT,
                due_date=calculated_due_date,
                status=Invoice.Status.PENDING,
                synced=False,
            )

            print(
                f"Created pending invoice for client {client.username} (subscription {subscription.id})"
            )

        subscription.is_active = False
        subscription.synced = False
        subscription.save(update_fields=["is_active", "synced", "updated_at"])

    return len(expired_subscriptions)
