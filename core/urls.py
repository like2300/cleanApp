import datetime

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import include, path
from django.utils import timezone
from django.views.generic import TemplateView

from business.models import Employee, Subscription
from finance.models import Invoice
from notifications.models import Reclamation

from .utils import get_zone_queryset

User = get_user_model()


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get(self, request, *args, **kwargs):
        if request.user.role == User.Role.CLIENT:
            return redirect("accounts:client_dashboard")
        # Check zone assignment for zone-restricted roles.
        # ZONE_MANAGER needs an assigned zone to see data; ACCOUNTANT and
        # SHAREHOLDER see everything globally and must NOT be blocked when
        # no zone is assigned.
        if (
            request.user.role == User.Role.ZONE_MANAGER
            and not request.user.zones.exists()
        ):
            messages.error(
                request,
                "Vous n'avez pas de zone assignée. Veuillez contacter l'administrateur.",
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Filtered counts and data
        employees = get_zone_queryset(user, Employee.objects.all())
        subscriptions = get_zone_queryset(
            user, Subscription.objects.all(), zone_field="client__zone"
        )
        invoices = get_zone_queryset(
            user, Invoice.objects.all(), zone_field="client__zone"
        )
        reclamations = get_zone_queryset(
            user, Reclamation.objects.all(), zone_field="user__zone"
        )  # Adjust if user.zone is the right field

        # Check if user has access to any data
        if (
            not employees.exists()
            and not subscriptions.exists()
            and not invoices.exists()
            and user.role in [User.Role.ZONE_MANAGER, User.Role.ACCOUNTANT]
        ):
            if user.zones.exists():
                messages.info(self.request, "Aucune donnée trouvée pour vos zones.")

        from django.db.models import Sum

        active_subs = subscriptions.filter(is_active=True)
        total_revenue = (
            active_subs.aggregate(Sum("plan__price"))["plan__price__sum"] or 0
        )
        context["total_revenue"] = float(total_revenue)

        # Counts for dashboard cards
        context["employee_count"] = employees.count()
        context["subscription_count"] = active_subs.count()

        # Recent Activities (Reclamations)
        context["recent_activities"] = reclamations.order_by("-created_at")[:5]

        # Monthly Revenue Data for Chart
        now = timezone.now()
        months = []
        revenue_data = []
        for i in range(5, -1, -1):
            date = now - datetime.timedelta(days=i * 30)
            month_name = date.strftime("%b")
            months.append(month_name)

            # Show historical estimation based on active subscriptions created before/during that month
            # (or simply display the monthly subscription revenue)
            revenue_data.append(float(total_revenue))

        context["chart_labels"] = months
        context["chart_data"] = revenue_data

        # Zone Profitability
        from django.db.models import Sum

        from business.models import Zone
        from finance.models import Payment

        zones = get_zone_queryset(user, Zone.objects.all())
        zone_stats = []
        total_zone_revenue = 0
        for zone in zones:
            zone_revenue = (
                active_subs.filter(client__zone=zone).aggregate(Sum("plan__price"))[
                    "plan__price__sum"
                ]
                or 0
            )

            total_zone_revenue += zone_revenue
            zone_stats.append({"name": zone.name, "revenue": float(zone_revenue)})

        # Calculate percentages and sort
        for stat in zone_stats:
            stat["percent"] = (
                (stat["revenue"] / float(total_zone_revenue) * 100)
                if total_zone_revenue > 0
                else 0
            )

        zone_stats.sort(key=lambda x: x["revenue"], reverse=True)
        context["zone_profitability"] = zone_stats
        context["zone_labels"] = [s["name"] for s in zone_stats]
        context["zone_data"] = [s["revenue"] for s in zone_stats]
        context["zone_percents"] = [round(s["percent"], 1) for s in zone_stats]

        # Count unsynced items
        from django.apps import apps

        from sync_engine.models import SyncBaseModel

        unsynced_count = 0
        for model in [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]:
            unsynced_count += model.objects.filter(synced=False).count()
        context["unsynced_count"] = unsynced_count
        return context


from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve

from . import export_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("business/", include("business.urls")),
    path("finance/", include("finance.urls")),
    path("sync/", include("sync_engine.urls")),
    path("notifications/", include("notifications.urls")),
    path(
        "export-global/",
        export_views.export_global_report_excel,
        name="export_global_report",
    ),
    path(
        "export-expenses/", export_views.export_expenses_excel, name="export_expenses"
    ),
    path(
        "export-clients-full/",
        export_views.export_clients_comprehensive_excel,
        name="export_clients_full",
    ),
    path(
        "export-invoicing-journal/",
        export_views.export_invoicing_journal_excel,
        name="export_invoicing_journal",
    ),
    path("", DashboardView.as_view(), name="dashboard"),
    # Toujours servir static et media (dev + bundle EXE)
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ── Gestionnaires d'erreurs personnalisés ─────────────────────────────────
handler400 = "django.views.defaults.bad_request"
handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
