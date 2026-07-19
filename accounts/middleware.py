from django.contrib import messages
from django.shortcuts import redirect

from accounts.models import User


class ReadOnlyMiddleware:
    """
    Prevent read-only roles from performing write requests.

    SHAREHOLDER accounts can consult data, but cannot create, update,
    validate, pay, delete, or sync through POST/PUT/PATCH/DELETE.
    ACCOUNTANT accounts can manage finance expenses and expense categories.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.method in [
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        ]:
            if request.path.endswith("/logout/") or "logout" in request.path:
                return self.get_response(request)

            if request.user.role == User.Role.ACCOUNTANT and request.path.startswith(
                "/finance/expenses/"
            ):
                return self.get_response(request)

            if request.user.role == User.Role.SHAREHOLDER:
                messages.error(
                    request,
                    "Accès en lecture seule. Vous pouvez consulter les données, mais pas les modifier.",
                )
                return redirect(request.META.get("HTTP_REFERER", "dashboard"))

        return self.get_response(request)
