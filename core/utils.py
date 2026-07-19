from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from accounts.models import User


def actionnaire_read_only(view_func):
    """
    Decorator that prevents read-only roles from making write requests.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        read_only_roles = [User.Role.SHAREHOLDER]
        if request.user.is_authenticated and request.user.role in read_only_roles:
            if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                messages.error(
                    request,
                    "Accès en lecture seule. Vous pouvez consulter les données, mais pas les modifier.",
                )
                return redirect(request.META.get("HTTP_REFERER", "dashboard"))
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def read_only_role_blocked(user):
    return user.is_authenticated and user.role in [
        User.Role.SHAREHOLDER,
    ]


def block_read_only_role(request):
    if read_only_role_blocked(request.user):
        messages.error(
            request,
            "Accès en lecture seule. Vous pouvez consulter les données, mais pas les modifier.",
        )
        return redirect(request.META.get("HTTP_REFERER", "dashboard"))
    return None


def check_zone_access(user, zone_id):
    """
    Checks if a user has access to a specific zone.
    Returns True if access is granted, False otherwise.
    """
    if user.is_anonymous:
        return False

    if user.role in [User.Role.SUPER_ADMIN, User.Role.SHAREHOLDER]:
        return True

    if user.role in [User.Role.ZONE_MANAGER, User.Role.ACCOUNTANT]:
        # Check if the user has assigned zones
        managed_zones = user.zones.all()
        if managed_zones.exists():
            if managed_zones.filter(id=int(zone_id)).exists():
                return True
            return False
        # If no zones assigned, Zone Manager gets False, Accountant gets True (Global)
        return True if user.role == User.Role.ACCOUNTANT else False

    return False


def get_zone_queryset(user, queryset, zone_field="zone"):
    """
    Filters a queryset based on the user's role and assigned zone.
    If the user is a SUPER_ADMIN or SHAREHOLDER, they see everything.
    If the user is a ZONE_MANAGER or ACCOUNTANT with zones, they are restricted.
    """
    if user.is_anonymous:
        return queryset.none()

    if user.role in [User.Role.SUPER_ADMIN, User.Role.SHAREHOLDER]:
        return queryset

    if user.role in [User.Role.ZONE_MANAGER, User.Role.ACCOUNTANT]:
        managed_zones = user.zones.all()
        if not managed_zones.exists():
            if user.role == User.Role.ZONE_MANAGER:
                return queryset.none()
            # Accountant without assigned zones can see everything for specific models
            from business.models import Zone
            from finance.models import Invoice, Payment

            if queryset.model in [Invoice, Payment, Zone]:
                return queryset
            return queryset

        # If the queryset is for Zone model itself
        from business.models import Zone

        if queryset.model == Zone:
            return queryset.filter(id__in=managed_zones)

        # Standard filtering by zone field
        filter_kwargs = {f"{zone_field}__in": managed_zones}
        return queryset.filter(**filter_kwargs)

    return queryset
