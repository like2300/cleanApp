from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import models

from business.models import SubscriptionPlan
from finance.billing import next_period_end_date

from .forms import UserCreationForm, UserUpdateForm
from .models import CompanySettings

User = get_user_model()


@login_required
def company_settings_edit(request):
    if not request.user.is_superuser:
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    settings = CompanySettings.get_settings()

    if request.method == "POST":
        settings.name = request.POST.get("name")
        settings.primary_color = request.POST.get("primary_color")
        settings.secondary_color = request.POST.get("secondary_color")
        settings.address = request.POST.get("address")
        settings.phone = request.POST.get("phone")
        settings.email = request.POST.get("email")

        if "logo" in request.FILES:
            settings.logo = request.FILES["logo"]

        settings.save()
        messages.success(request, "Paramètres mis à jour avec succès.")
        return redirect("accounts:company_settings_edit")

    return render(request, "accounts/company_settings.html", {"settings": settings})


from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout


def logout_user(request):
    role = None
    if request.user.is_authenticated:
        role = getattr(request.user, "role", None)

    auth_logout(request)

    if role == "CLIENT":
        return redirect("accounts:client_login")
    return redirect("accounts:login")


def client_login(request):
    if request.method == "POST":
        matricule = request.POST.get("matricule")
        try:
            user = User.objects.get(
                registration_number=matricule, role=User.Role.CLIENT
            )
            # Since there is no password check for this simple access,
            # we just log the user in. In a real app, you might want a PIN or password.
            auth_login(request, user)
            messages.success(request, f"Bienvenue {user.first_name or user.username} !")
            return redirect("accounts:client_dashboard")
        except User.DoesNotExist:
            messages.error(request, "Matricule invalide ou compte non trouvé.")

    return render(request, "accounts/client_login.html")


@login_required
def custom_login_redirect(request):
    """
    Redirects users to their appropriate dashboard after login based on their role.
    """
    if request.user.role == User.Role.CLIENT:
        return redirect("accounts:client_dashboard")

    # For all other roles (SUPER_ADMIN, ACCOUNTANT, ZONE_MANAGER, SHAREHOLDER)
    return redirect("dashboard")


@login_required
def client_dashboard(request):
    if request.user.role != User.Role.CLIENT:
        return redirect("dashboard")

    user = request.user
    subscription = user.subscriptions.select_related("plan").first()
    today = timezone.now().date()
    subscription_alert = None
    renewal_invoice = None

    if subscription:
        from finance.models import Invoice

        def ensure_renewal_invoice():
            invoice = Invoice.objects.filter(
                client=user,
                subscription=subscription,
                status=Invoice.Status.PENDING,
                due_date=subscription.end_date,
            ).first()
            if invoice:
                return invoice
            return Invoice.objects.create(
                client=user,
                subscription=subscription,
                amount=subscription.plan.price,
                due_date=subscription.end_date,
                status=Invoice.Status.PENDING,
                invoice_type=Invoice.InvoiceType.PAIEMENT,
                synced=False,
            )

        if subscription.end_date < today:
            if subscription.is_active:
                subscription.is_active = False
                subscription.synced = False
                subscription.save(update_fields=["is_active", "synced", "updated_at"])
            renewal_invoice = ensure_renewal_invoice()
            subscription_alert = {
                "type": "expired",
                "title": "Abonnement terminé",
                "message": "Votre abonnement est arrivé à échéance. Une facture de renouvellement a été générée automatiquement.",
            }
        else:
            days_until_end = (subscription.end_date - today).days
            if days_until_end <= 3:
                renewal_invoice = ensure_renewal_invoice()
                subscription_alert = {
                    "type": "ending",
                    "title": "Fin d’abonnement proche",
                    "message": f"Votre abonnement se termine dans {days_until_end} jour(s). Une facture de renouvellement est disponible.",
                }
            elif (
                not subscription.is_active
                and not Invoice.objects.filter(
                    subscription=subscription, status=Invoice.Status.PENDING
                ).exists()
            ):
                renewal_invoice = ensure_renewal_invoice()

    invoices = user.invoices.all().order_by("-created_at")
    plans = SubscriptionPlan.objects.all()

    # Calculate progress if subscription exists AND is active
    progress = 0
    days_left = 0
    total_days = 0
    current_day = 0
    if subscription and subscription.is_active:
        # total_days is the duration (e.g., 30)
        total_days = max(1, (subscription.end_date - subscription.start_date).days)

        # days_diff is 0 on the first day, 1 on the second, etc.
        days_diff = max(0, (today - subscription.start_date).days)

        # current_day is 1 on the first day, 2 on the second, etc.
        current_day = min(total_days, max(1, days_diff + 1))

        # days_left should still reflect remaining full days
        days_left = max(0, (subscription.end_date - today).days)

        if total_days > 0:
            # Progress based on the current day out of total days
            progress = min(100, (current_day / total_days) * 100)

    return render(
        request,
        "accounts/client_dashboard.html",
        {
            "subscription": subscription,
            "invoices": invoices[:5],  # Only show last 5 in dashboard
            "plans": plans,
            "progress": progress,
            "days_left": days_left,
            "current_day": current_day,
            "total_days": total_days,
            "subscription_alert": subscription_alert,
            "renewal_invoice": renewal_invoice,
        },
    )


@login_required
def change_subscription_plan(request):
    if request.user.role != User.Role.CLIENT:
        return redirect("dashboard")

    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        subscription = request.user.subscriptions.first()
        from finance.models import Invoice

        # Delete ANY existing pending invoices to avoid confusion
        Invoice.objects.filter(
            client=request.user, status=Invoice.Status.PENDING
        ).delete()

        if subscription:
            # If sub is already active, DON'T touch it yet.
            # We only create a pending invoice.
            # If it's NOT active, we can update it now but keep it inactive.
            if not subscription.is_active:
                subscription.plan = plan
                subscription.start_date = timezone.now().date()
                subscription.end_date = (
                    request.user.fixed_due_date
                    or next_period_end_date(
                        request.user,
                        subscription,
                        subscription.start_date,
                    )
                )
                if not request.user.fixed_due_date:
                    request.user.fixed_due_date = subscription.end_date
                    request.user.save(
                        update_fields=["fixed_due_date", "synced", "updated_at"]
                    )
                subscription.save()

            Invoice.objects.create(
                client=request.user,
                subscription=subscription,
                amount=plan.price,
                due_date=subscription.end_date,  # Use the subscription's fixed due date
                status=Invoice.Status.PENDING,
                invoice_type=Invoice.InvoiceType.PAIEMENT,
                synced=False,
            )

            if subscription.is_active:
                messages.success(
                    request,
                    f"Demande de changement vers {plan.name} enregistrée. Votre abonnement actuel reste actif jusqu'au paiement.",
                )
            else:
                messages.success(
                    request,
                    f"Offre {plan.name} sélectionnée. Veuillez payer pour l'activer.",
                )
        else:
            # Create a new inactive subscription
            from business.models import Subscription

            temp_subscription = Subscription(client=request.user, plan=plan)
            end_date = request.user.fixed_due_date or next_period_end_date(
                request.user,
                temp_subscription,
                timezone.now().date(),
            )
            if not request.user.fixed_due_date:
                request.user.fixed_due_date = end_date
                request.user.save(
                    update_fields=["fixed_due_date", "synced", "updated_at"]
                )
            new_sub = Subscription.objects.create(
                client=request.user, plan=plan, end_date=end_date, is_active=False
            )

            Invoice.objects.create(
                client=request.user,
                subscription=new_sub,
                amount=plan.price,
                due_date=end_date,
                status=Invoice.Status.PENDING,
                invoice_type=Invoice.InvoiceType.PAIEMENT,
                synced=False,
            )
            messages.success(
                request, f"Offre {plan.name} choisie. Veuillez payer pour l'activer."
            )

    return redirect("accounts:client_dashboard")


@login_required
def client_invoice_list(request):
    if request.user.role != User.Role.CLIENT:
        return redirect("dashboard")

    invoices = request.user.invoices.all().order_by("-created_at")
    return render(request, "accounts/client_invoice_list.html", {"invoices": invoices})


@login_required
def user_list(request):
    if not request.user.role == User.Role.SUPER_ADMIN:
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    # Get filter parameters from request
    role_filter = request.GET.get('role')
    search_query = request.GET.get('search', '')
    
    users = User.objects.all().order_by("-date_joined")
    
    # Apply role filter if provided
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Apply search filter if provided
    if search_query:
        users = users.filter(
            models.Q(username__icontains=search_query) |
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(email__icontains=search_query) |
            models.Q(registration_number__icontains=search_query)
        )
    
    # Get distinct roles for filter dropdown
    roles = User.Role.choices
    
    return render(request, "accounts/user_list.html", {
        "users": users,
        "roles": roles,
        "selected_role": role_filter,
        "search_query": search_query
    })


@login_required
def user_create(request):
    if not request.user.role == User.Role.SUPER_ADMIN:
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request, f"L'utilisateur {user.username} a été créé avec succès."
            )
            return redirect("accounts:user_list")
    else:
        form = UserCreationForm()

    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Créer un utilisateur", "button_text": "Créer"},
    )


@login_required
def user_update(request, pk):
    # Allow superadmin to edit anyone, or user to edit themselves
    if not (request.user.role == User.Role.SUPER_ADMIN or request.user.pk == pk):
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=user, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"L'utilisateur {user.username} a été mis à jour."
            )
            if request.user.role == User.Role.SUPER_ADMIN:
                return redirect("accounts:user_list")
            return redirect("accounts:user_update", pk=user.pk)
    else:
        form = UserUpdateForm(instance=user, request_user=request.user)

    return render(
        request,
        "accounts/user_form.html",
        {
            "form": form,
            "user_obj": user,
            "title": f"Modifier {user.username}",
            "button_text": "Enregistrer",
        },
    )


@login_required
def user_delete(request, pk):
    if not request.user.role == User.Role.SUPER_ADMIN:
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect("accounts:user_list")

    if request.method == "POST":
        user.delete()
        messages.success(request, "L'utilisateur a été supprimé.")
        return redirect("accounts:user_list")

    return render(request, "accounts/user_confirm_delete.html", {"user_obj": user})


@login_required
def user_password_reset(request, pk):
    if not (request.user.role == User.Role.SUPER_ADMIN or request.user.pk == pk):
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        # If superadmin is changing another user's password, use SetPasswordForm
        # If user is changing their own, use PasswordChangeForm (requires old password)
        if request.user.role == User.Role.SUPER_ADMIN and request.user != user:
            form = SetPasswordForm(user, request.POST)
        else:
            form = PasswordChangeForm(user, request.POST)

        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, "Le mot de passe a été mis à jour.")
            if request.user.role == User.Role.SUPER_ADMIN:
                return redirect("accounts:user_list")
            return redirect("accounts:user_update", pk=user.pk)
    else:
        if request.user.role == User.Role.SUPER_ADMIN and request.user != user:
            form = SetPasswordForm(user)
        else:
            form = PasswordChangeForm(user)

    return render(
        request, "accounts/password_reset.html", {"form": form, "user_obj": user}
    )


@login_required
def user_toggle_active(request, pk):
    if not request.user.role == User.Role.SUPER_ADMIN:
        messages.error(request, "Accès refusé.")
        return redirect("dashboard")

    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect("accounts:user_list")

    user.is_active = not user.is_active
    user.synced = False
    user.save()

    status = "activé" if user.is_active else "désactivé"
    messages.success(request, f"L'utilisateur {user.username} a été {status}.")
    return redirect("accounts:user_list")
