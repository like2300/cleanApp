from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from accounts.models import User
from business.models import Employee, Quartier, Subscription, SubscriptionPlan, Zone
from core.excel import ExcelReportBuilder
from core.utils import get_zone_queryset
from finance.models import Expense, Invoice, Payment
from notifications.models import Reclamation


def _forbidden():
    return HttpResponse("Non autorisé", status=403)


def _money(value):
    return value or 0


def _date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def _datetime(value):
    return value.strftime("%d/%m/%Y %H:%M") if value else "-"


def _full_name(user):
    if not user:
        return "-"
    return user.get_full_name() or user.first_name or user.username


def _filter_label(model, pk, attr="name"):
    if not pk:
        return ""
    try:
        return getattr(model.objects.get(pk=pk), attr)
    except model.DoesNotExist:
        return str(pk)


def _apply_date_filters(queryset, request, field_name):
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        queryset = queryset.filter(**{f"{field_name}__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field_name}__lte": date_to})
    return queryset


@login_required
def export_expenses_excel(request):
    if request.user.role not in [User.Role.ACCOUNTANT, User.Role.SHAREHOLDER]:
        return _forbidden()

    category = request.GET.get("category")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    expenses = Expense.objects.select_related("recorded_by").order_by("-expense_date")
    if category:
        expenses = expenses.filter(category=category)
    expenses = _apply_date_filters(expenses, request, "expense_date")

    total_amount = _money(expenses.aggregate(Sum("amount"))["amount__sum"])

    report = ExcelReportBuilder(
        "Rapport des dépenses", request=request, filename_prefix="rapport_depenses"
    )
    ws = report.active_sheet("Dépenses")
    report.add_title(ws, 6)
    start = report.add_filters_summary(
        ws,
        [
            ("Catégorie", category),
            ("Date début", date_from),
            ("Date fin", date_to),
        ],
    )
    start = report.add_kpis(
        ws, [("Total dépenses", total_amount), ("Nombre", expenses.count())], start
    )
    rows = [
        [
            _date(exp.expense_date),
            exp.title,
            exp.category_display,
            exp.amount,
            exp.description or "-",
            exp.recorded_by.username if exp.recorded_by else "-",
        ]
        for exp in expenses
    ]
    end = report.add_table(
        ws,
        [
            "Date",
            "Titre",
            "Catégorie",
            "Montant (FCFA)",
            "Description",
            "Enregistré par",
        ],
        rows,
        start_row=start,
        table_name="Depenses",
    )
    report.add_total_row(ws, end, 3, "TOTAL", {4: total_amount})

    ws_cat = report.create_sheet("Résumé catégories")
    report.add_title(ws_cat, 3, "Répartition des dépenses par catégorie")
    cat_rows = []
    for code, name in Expense.DEFAULT_CATEGORIES.items():
        cat_qs = expenses.filter(category=code)
        amount = _money(cat_qs.aggregate(Sum("amount"))["amount__sum"])
        if amount:
            cat_rows.append([name, cat_qs.count(), amount])
    report.add_table(
        ws_cat,
        ["Catégorie", "Nombre", "Montant (FCFA)"],
        cat_rows,
        start_row=4,
        table_name="ResumeCategories",
    )
    return report.response()


@login_required
def export_clients_comprehensive_excel(request):
    if request.user.role not in [
        User.Role.SUPER_ADMIN,
        User.Role.ACCOUNTANT,
        User.Role.SHAREHOLDER,
    ]:
        return _forbidden()

    zone_id = request.GET.get("zone")
    quartier_id = request.GET.get("quartier")
    status = request.GET.get("status")
    search = request.GET.get("q") or request.GET.get("search")

    clients = get_zone_queryset(
        request.user,
        User.objects.filter(role=User.Role.CLIENT).select_related("zone", "quartier"),
        zone_field="zone",
    ).prefetch_related("subscriptions", "invoices")

    if zone_id:
        clients = clients.filter(zone_id=zone_id)
    if quartier_id:
        clients = clients.filter(quartier_id=quartier_id)
    if search:
        clients = clients.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(registration_number__icontains=search)
            | Q(phone_number__icontains=search)
        )

    today = timezone.now().date()
    if status == "active":
        clients = clients.filter(
            subscriptions__is_active=True, subscriptions__end_date__gte=today
        ).distinct()
    elif status == "expired":
        clients = clients.filter(subscriptions__end_date__lt=today).distinct()
    elif status == "none":
        clients = clients.filter(subscriptions__isnull=True)

    report = ExcelReportBuilder(
        "Base clients complète", request=request, filename_prefix="base_clients"
    )
    ws = report.active_sheet("Clients")
    report.add_title(ws, 13)
    start = report.add_filters_summary(
        ws,
        [
            ("Zone", _filter_label(Zone, zone_id)),
            ("Quartier", _filter_label(Quartier, quartier_id)),
            ("Statut", status),
            ("Recherche", search),
        ],
    )
    start = report.add_kpis(
        ws,
        [
            ("Total clients", clients.count()),
            ("Date", timezone.now().strftime("%d/%m/%Y")),
        ],
        start,
    )

    rows = []
    for client in clients:
        sub = (
            client.subscriptions.filter(is_active=True).first()
            or client.subscriptions.order_by("-end_date").first()
        )
        sub_status = (
            "ACTIF"
            if sub and sub.is_active and sub.end_date >= today
            else "EXPIRÉ"
            if sub
            else "AUCUN"
        )
        rows.append(
            [
                client.registration_number or "-",
                client.username,
                _full_name(client),
                client.phone_number or "-",
                client.phone_number_2 or "-",
                client.zone.name if client.zone else "-",
                client.quartier.name if client.quartier else "-",
                client.address or "-",
                _date(client.date_joined),
                sub.plan.name if sub else "-",
                sub.plan.price if sub else 0,
                _date(sub.end_date) if sub else "-",
                sub_status,
            ]
        )
    report.add_table(
        ws,
        [
            "Matricule",
            "Username",
            "Nom",
            "Téléphone 1",
            "Téléphone 2",
            "Zone",
            "Quartier",
            "Adresse",
            "Inscription",
            "Plan",
            "Prix",
            "Échéance",
            "Statut",
        ],
        rows,
        start_row=start,
        table_name="Clients",
    )

    ws_zone = report.create_sheet("Résumé zones")
    report.add_title(ws_zone, 4, "Analyse des clients par zone")
    zone_rows = []
    zones = get_zone_queryset(request.user, Zone.objects.all())
    for zone in zones:
        z_clients = clients.filter(zone=zone)
        active_subs = Subscription.objects.filter(
            client__in=z_clients, is_active=True, end_date__gte=today
        )
        zone_rows.append(
            [
                zone.name,
                z_clients.count(),
                active_subs.count(),
                _money(active_subs.aggregate(Sum("plan__price"))["plan__price__sum"]),
            ]
        )
    report.add_table(
        ws_zone,
        ["Zone", "Clients", "Abonnements actifs", "Recette potentielle"],
        zone_rows,
        start_row=4,
        table_name="ResumeZones",
    )

    ws_plan = report.create_sheet("Plans")
    report.add_title(ws_plan, 3, "Distribution des plans")
    plan_rows = []
    for plan in SubscriptionPlan.objects.all():
        count = Subscription.objects.filter(
            plan=plan, is_active=True, end_date__gte=today, client__in=clients
        ).count()
        plan_rows.append([plan.name, count, count * plan.price])
    report.add_table(
        ws_plan,
        ["Plan", "Clients actifs", "Recette"],
        plan_rows,
        start_row=4,
        table_name="DistributionPlans",
    )
    return report.response()


@login_required
def export_global_report_excel(request):
    if not request.user.is_staff and request.user.role != User.Role.SHAREHOLDER:
        return _forbidden()

    user = request.user
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    zone_id = request.GET.get("zone")

    clients = get_zone_queryset(
        user,
        User.objects.filter(role=User.Role.CLIENT).select_related("zone", "quartier"),
        zone_field="zone",
    )
    employees = get_zone_queryset(
        user, Employee.objects.all().select_related("zone", "position")
    )
    invoices = get_zone_queryset(
        user,
        Invoice.objects.all().select_related(
            "client", "client__zone", "subscription__plan"
        ),
        zone_field="client__zone",
    )
    payments = get_zone_queryset(
        user,
        Payment.objects.filter(is_validated=True).select_related(
            "invoice__client", "invoice__client__zone", "validated_by"
        ),
        zone_field="invoice__client__zone",
    )
    expenses = Expense.objects.all().select_related("recorded_by")
    reclamations = get_zone_queryset(
        user,
        Reclamation.objects.all().select_related("user", "user__zone"),
        zone_field="user__zone",
    )

    if zone_id:
        clients = clients.filter(zone_id=zone_id)
        employees = employees.filter(zone_id=zone_id)
        invoices = invoices.filter(client__zone_id=zone_id)
        payments = payments.filter(invoice__client__zone_id=zone_id)
        reclamations = reclamations.filter(user__zone_id=zone_id)

    invoices = _apply_date_filters(invoices, request, "created_at__date")
    payments = _apply_date_filters(payments, request, "paid_at__date")
    expenses = _apply_date_filters(expenses, request, "expense_date")

    total_invoiced = _money(invoices.aggregate(Sum("amount"))["amount__sum"])
    total_paid = _money(payments.aggregate(Sum("amount"))["amount__sum"])
    total_expenses = _money(expenses.aggregate(Sum("amount"))["amount__sum"])
    recovery_rate = (total_paid / total_invoiced * 100) if total_invoiced else 0

    report = ExcelReportBuilder(
        "Rapport global de gestion", request=request, filename_prefix="rapport_global"
    )
    ws = report.active_sheet("Résumé")
    report.add_title(ws, 4)
    start = report.add_filters_summary(
        ws,
        [
            ("Zone", _filter_label(Zone, zone_id)),
            ("Date début", date_from),
            ("Date fin", date_to),
        ],
    )
    start = report.add_kpis(
        ws,
        [
            ("Clients", clients.count()),
            ("Facturé", total_invoiced),
            ("Encaissé", total_paid),
            ("Dépenses", total_expenses),
            ("Net estimé", total_paid - total_expenses),
        ],
        start,
    )
    report.add_table(
        ws,
        ["Section", "Indicateur", "Valeur", "Remarque"],
        [
            [
                "Général",
                "Total clients",
                clients.count(),
                "Clients visibles selon vos droits",
            ],
            ["Général", "Total employés", employees.count(), "Personnel"],
            ["Finances", "Total facturé", total_invoiced, "Factures filtrées"],
            ["Finances", "Total encaissé", total_paid, "Paiements validés"],
            [
                "Finances",
                "Taux de recouvrement",
                f"{recovery_rate:.1f}%",
                "Encaissé / facturé",
            ],
            ["Finances", "Dépenses", total_expenses, "Charges"],
            [
                "Service",
                "Réclamations ouvertes",
                reclamations.exclude(status="CLOSED").count(),
                "À traiter",
            ],
        ],
        start_row=start,
        table_name="ResumeGlobal",
    )

    ws_zone = report.create_sheet("Zones")
    report.add_title(ws_zone, 6, "Performance par zone")
    zone_rows = []
    for zone in get_zone_queryset(user, Zone.objects.all()):
        z_inv = invoices.filter(client__zone=zone)
        z_pay = payments.filter(invoice__client__zone=zone)
        z_inv_amt = _money(z_inv.aggregate(Sum("amount"))["amount__sum"])
        z_pay_amt = _money(z_pay.aggregate(Sum("amount"))["amount__sum"])
        zone_rows.append(
            [
                zone.name,
                clients.filter(zone=zone).count(),
                z_inv.count(),
                z_inv_amt,
                z_pay_amt,
                (z_pay_amt / z_inv_amt * 100) if z_inv_amt else 0,
            ]
        )
    report.add_table(
        ws_zone,
        ["Zone", "Clients", "Factures", "Facturé", "Encaissé", "Taux %"],
        zone_rows,
        start_row=4,
        table_name="Zones",
    )

    detail_specs = [
        (
            "Clients",
            ["Matricule", "Nom", "Téléphone", "Zone", "Quartier", "Statut"],
            [
                [
                    c.registration_number or "-",
                    _full_name(c),
                    c.phone_number or "-",
                    c.zone.name if c.zone else "-",
                    c.quartier.name if c.quartier else "-",
                    "Actif" if c.is_active else "Inactif",
                ]
                for c in clients
            ],
        ),
        (
            "Factures",
            ["Référence", "Date", "Client", "Zone", "Montant", "Échéance", "Statut"],
            [
                [
                    str(i.uuid)[:8].upper(),
                    _datetime(i.created_at),
                    _full_name(i.client),
                    i.client.zone.name if i.client.zone else "-",
                    i.amount,
                    _date(i.due_date),
                    i.get_status_display(),
                ]
                for i in invoices.order_by("-created_at")
            ],
        ),
        (
            "Paiements",
            ["Transaction", "Date", "Client", "Montant", "Mode", "Validé par"],
            [
                [
                    p.transaction_id,
                    _datetime(p.paid_at),
                    _full_name(p.invoice.client),
                    p.amount,
                    p.payment_method,
                    p.validated_by.username if p.validated_by else "-",
                ]
                for p in payments.order_by("-paid_at")
            ],
        ),
        (
            "Dépenses",
            ["Date", "Titre", "Catégorie", "Montant", "Description"],
            [
                [
                    _date(e.expense_date),
                    e.title,
                    e.category_display,
                    e.amount,
                    e.description or "-",
                ]
                for e in expenses.order_by("-expense_date")
            ],
        ),
        (
            "Réclamations",
            ["Date", "Client", "Zone", "Sujet", "Statut"],
            [
                [
                    _datetime(r.created_at),
                    _full_name(r.user) if r.user else r.guest_name,
                    r.user.zone.name if r.user and r.user.zone else "-",
                    r.subject,
                    r.get_status_display(),
                ]
                for r in reclamations.order_by("-created_at")
            ],
        ),
    ]
    for title, columns, rows in detail_specs:
        sheet = report.create_sheet(title)
        report.add_title(sheet, len(columns), title)
        report.add_table(
            sheet, columns, rows, start_row=4, table_name=title.replace("é", "e")
        )

    return report.response()


@login_required
def export_invoicing_journal_excel(request):
    if request.user.role not in [
        User.Role.SUPER_ADMIN,
        User.Role.ACCOUNTANT,
        User.Role.SHAREHOLDER,
    ]:
        return _forbidden()

    invoices = get_zone_queryset(
        request.user,
        Invoice.objects.all().select_related(
            "client",
            "client__zone",
            "client__quartier",
            "subscription",
            "subscription__plan",
        ),
        zone_field="client__zone",
    )

    status_filter = request.GET.get("status")
    zone_filter = request.GET.get("zone")
    quartier_filter = request.GET.get("quartier")
    search_query = request.GET.get("q")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status_filter:
        invoices = invoices.filter(status=status_filter)
    if zone_filter:
        invoices = invoices.filter(client__zone_id=zone_filter)
    if quartier_filter:
        invoices = invoices.filter(client__quartier_id=quartier_filter)
    if search_query:
        invoices = invoices.filter(
            Q(client__username__icontains=search_query)
            | Q(client__first_name__icontains=search_query)
            | Q(client__registration_number__icontains=search_query)
        )
    invoices = _apply_date_filters(invoices, request, "created_at__date").order_by(
        "-created_at"
    )

    payments = Payment.objects.filter(
        invoice__in=invoices, is_validated=True
    ).select_related("invoice__client", "invoice__client__zone")
    total_invoiced = _money(invoices.aggregate(Sum("amount"))["amount__sum"])
    total_paid = _money(payments.aggregate(Sum("amount"))["amount__sum"])

    report = ExcelReportBuilder(
        "Journal de facturation", request=request, filename_prefix="journal_facturation"
    )
    ws = report.active_sheet("Factures")
    report.add_title(ws, 11)
    start = report.add_filters_summary(
        ws,
        [
            ("Statut", status_filter),
            ("Zone", _filter_label(Zone, zone_filter)),
            ("Quartier", _filter_label(Quartier, quartier_filter)),
            ("Recherche", search_query),
            ("Date début", date_from),
            ("Date fin", date_to),
        ],
    )
    start = report.add_kpis(
        ws,
        [
            ("Factures", invoices.count()),
            ("Facturé", total_invoiced),
            ("Encaissé", total_paid),
            ("Reste", total_invoiced - total_paid),
        ],
        start,
    )
    rows = [
        [
            _datetime(inv.created_at),
            _full_name(inv.client),
            inv.client.registration_number or "-",
            inv.client.zone.name if inv.client.zone else "-",
            inv.client.quartier.name if inv.client.quartier else "-",
            inv.get_invoice_type_display(),
            inv.subscription.plan.name if inv.subscription else "Ponctuel",
            inv.subscription.plan.duration_days if inv.subscription else "-",
            _date(inv.subscription.end_date) if inv.subscription else "-",
            inv.amount,
            inv.get_status_display(),
        ]
        for inv in invoices
    ]
    end = report.add_table(
        ws,
        [
            "Date",
            "Client",
            "Matricule",
            "Zone",
            "Quartier",
            "Type",
            "Plan",
            "Durée",
            "Fin abonnement",
            "Montant",
            "Statut",
        ],
        rows,
        start_row=start,
        table_name="Factures",
    )
    report.add_total_row(ws, end, 9, "TOTAL", {10: total_invoiced})

    ws_pay = report.create_sheet("Paiements")
    report.add_title(ws_pay, 7, "Paiements validés liés aux factures filtrées")
    pay_rows = [
        [
            _datetime(p.paid_at),
            _full_name(p.invoice.client),
            p.invoice.client.registration_number or "-",
            p.invoice.client.zone.name if p.invoice.client.zone else "-",
            p.amount,
            p.payment_method,
            p.transaction_id,
        ]
        for p in payments.order_by("-paid_at")
    ]
    pay_end = report.add_table(
        ws_pay,
        [
            "Date paiement",
            "Client",
            "Matricule",
            "Zone",
            "Montant",
            "Mode",
            "Transaction",
        ],
        pay_rows,
        start_row=4,
        table_name="Paiements",
    )
    report.add_total_row(ws_pay, pay_end, 4, "TOTAL ENCAISSÉ", {5: total_paid})

    ws_analysis = report.create_sheet("Analyse")
    report.add_title(ws_analysis, 2, "Résumé analytique")
    report.add_table(
        ws_analysis,
        ["Indicateur", "Valeur"],
        [
            ["Nombre de factures", invoices.count()],
            ["Nombre de paiements", payments.count()],
            ["Total facturé", total_invoiced],
            ["Total encaissé", total_paid],
            [
                "Taux de recouvrement",
                f"{(total_paid / total_invoiced * 100) if total_invoiced else 0:.1f}%",
            ],
            ["Reste à recouvrer", total_invoiced - total_paid],
        ],
        start_row=4,
        table_name="AnalyseFacturation",
    )
    return report.response()
