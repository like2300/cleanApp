from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

User = get_user_model()


class UserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role", "phone_number", "zone", "zones")

    def clean_zone(self):
        zone = self.cleaned_data.get("zone")
        role = self.cleaned_data.get("role")
        if zone and role == User.Role.ZONE_MANAGER:
            others = User.objects.filter(
                role=User.Role.ZONE_MANAGER, zone=zone
            ).exclude(pk=self.instance.pk if hasattr(self, "instance") else None)
            if others.exists():
                raise forms.ValidationError(
                    f"La zone '{zone.name}' est déjà assignée comme zone principale à un autre chef."
                )
        return zone

    def clean_zones(self):
        zones = self.cleaned_data.get("zones")
        role = self.cleaned_data.get("role")
        if role == User.Role.ZONE_MANAGER and zones:
            for zone in zones:
                already_managed_by = User.objects.filter(
                    role=User.Role.ZONE_MANAGER, zones=zone
                )
                if already_managed_by.exists():
                    manager_names = ", ".join([u.username for u in already_managed_by])
                    raise forms.ValidationError(
                        f"La zone '{zone.name}' est déjà gérée par : {manager_names}."
                    )
        return zones

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter out zones already assigned to another ZONE_MANAGER
        from business.models import Zone

        already_managed_zone_ids = (
            User.objects.filter(role=User.Role.ZONE_MANAGER)
            .exclude(
                pk=self.instance.pk if self.instance and self.instance.pk else None
            )
            .values_list("zones__id", flat=True)
        )
        available_zones = Zone.objects.exclude(id__in=already_managed_zone_ids)
        if "zones" in self.fields:
            self.fields["zones"].queryset = available_zones
            self.fields[
                "zones"
            ].help_text = "Maintenez Ctrl (ou Cmd) pour sélectionner plusieurs zones (pour les chefs de zone)."
        if "zone" in self.fields:
            self.fields["zone"].queryset = available_zones
        # ACCOUNTANT and SHAREHOLDER see all data globally: zone assignment is
        # irrelevant for them, so disable these fields to avoid confusion.
        submitted_role = None
        if self.data and "role" in self.data:
            submitted_role = self.data.get("role")
        elif self.initial.get("role"):
            submitted_role = self.initial.get("role")
        if submitted_role in [User.Role.ACCOUNTANT, User.Role.SHAREHOLDER]:
            for zone_field in ("zone", "zones"):
                if zone_field in self.fields:
                    self.fields[zone_field].disabled = True
                    self.fields[zone_field].required = False
                    self.fields[
                        zone_field
                    ].help_text = "Non requis pour ce rôle (accès global)."
        for field in self.fields:
            self.fields[field].widget.attrs.update(
                {
                    "class": "w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-dark-border dark:bg-dark-bg focus:ring-2 focus:ring-brand-500 outline-none transition-all"
                }
            )


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "username",
            "registration_number",
            "first_name",
            "last_name",
            "email",
            "role",
            "phone_number",
            "phone_number_2",
            "address",
            "zone",
            "zones",
        )

    def clean_zone(self):
        zone = self.cleaned_data.get("zone")
        role = self.cleaned_data.get("role")
        if zone and role == User.Role.ZONE_MANAGER:
            others = User.objects.filter(
                role=User.Role.ZONE_MANAGER, zone=zone
            ).exclude(pk=self.instance.pk if hasattr(self, "instance") else None)
            if others.exists():
                raise forms.ValidationError(
                    f"La zone '{zone.name}' est déjà assignée comme zone principale à un autre chef."
                )
        return zone

    def clean_zones(self):
        zones = self.cleaned_data.get("zones")
        role = self.cleaned_data.get("role")
        if role == User.Role.ZONE_MANAGER and zones:
            for zone in zones:
                already_managed_by = User.objects.filter(
                    role=User.Role.ZONE_MANAGER, zones=zone
                ).exclude(pk=self.instance.pk)
                if already_managed_by.exists():
                    manager_names = ", ".join([u.username for u in already_managed_by])
                    raise forms.ValidationError(
                        f"La zone '{zone.name}' est déjà gérée par : {manager_names}."
                    )
        return zones

    def __init__(self, *args, **kwargs):
        request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)

        # Restriction: only SUPER_ADMIN can change role, zones, registration_number, and username
        if request_user and request_user.role != User.Role.SUPER_ADMIN:
            for field in ["role", "zone", "zones", "registration_number", "username"]:
                if field in self.fields:
                    self.fields[field].disabled = True

        # Filter out zones already assigned to another ZONE_MANAGER
        from business.models import Zone

        already_managed_zone_ids = (
            User.objects.filter(role=User.Role.ZONE_MANAGER)
            .exclude(
                pk=self.instance.pk if self.instance and self.instance.pk else None
            )
            .values_list("zones__id", flat=True)
        )
        available_zones = Zone.objects.exclude(id__in=already_managed_zone_ids)
        if "zones" in self.fields:
            self.fields["zones"].queryset = available_zones
            self.fields[
                "zones"
            ].help_text = (
                "Pour les chefs de zone, sélectionnez toutes les zones gérées."
            )
        if "zone" in self.fields:
            self.fields["zone"].queryset = available_zones

        # ACCOUNTANT and SHAREHOLDER see all data globally: zone assignment is
        # irrelevant for them, so disable these fields to avoid confusion.
        role_to_check = None
        if self.data and "role" in self.data:
            role_to_check = self.data.get("role")
        elif self.instance and self.instance.role:
            role_to_check = self.instance.role
        if role_to_check in [User.Role.ACCOUNTANT, User.Role.SHAREHOLDER]:
            for zone_field in ("zone", "zones"):
                if zone_field in self.fields:
                    self.fields[zone_field].disabled = True
                    self.fields[zone_field].required = False
                    self.fields[
                        zone_field
                    ].help_text = "Non requis pour ce rôle (accès global)."

        for field in self.fields:
            self.fields[field].widget.attrs.update(
                {
                    "class": "w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-dark-border dark:bg-dark-bg focus:ring-2 focus:ring-brand-500 outline-none transition-all"
                }
            )
