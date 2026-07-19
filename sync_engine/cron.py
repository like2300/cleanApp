import json
import logging

import requests
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django_cron import CronJobBase, Schedule

from sync_engine.models import SyncBaseModel

logger = logging.getLogger(__name__)


class SyncDataCronJob(CronJobBase):
    RUN_EVERY_MINS = 5

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = "sync_engine.sync_data_cron_job"

    def _is_online(self):
        from .router import SyncRouter

        return SyncRouter()._check_cloud_connectivity()

    def do(self):
        logger.info("Starting Sync Process...")
        if not self._is_online():
            logger.warning("Sync skipped: Cloud is unreachable.")
            return

        # 1. PUSH: Local -> Cloud
        self.push_local_changes()
        # 2. PULL: Cloud -> Local
        self.pull_cloud_changes()

    def push_local_changes(self):
        if not self._is_online():
            raise ConnectionError(
                "Impossible d'envoyer les données : le cloud est injoignable."
            )

        # 1. Handle actual record updates/creates
        sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]

        for model in sync_models:
            local_items = model.objects.using("default").filter(synced=False)

            for local_item in local_items:
                try:
                    cloud_item = (
                        model.objects.using("cloud")
                        .filter(uuid=local_item.uuid)
                        .first()
                    )

                    data = {}
                    skip_item = False
                    for field in model._meta.fields:
                        if field.primary_key:
                            continue

                        try:
                            value = getattr(local_item, field.name)
                        except Exception as fk_err:
                            # Related object doesn't exist locally yet — skip this item
                            skip_item = True
                            logger.warning(
                                f"SYNC SKIP [PUSH]: {model._meta.label} UUID:{local_item.uuid} - Could not access field '{field.name}': {fk_err}"
                            )
                            break

                        if field.is_relation and value:
                            related_uuid = getattr(value, "uuid", None)
                            if related_uuid:
                                related_model = field.related_model
                                cloud_related = (
                                    related_model.objects.using("cloud")
                                    .filter(uuid=related_uuid)
                                    .first()
                                )
                                if not cloud_related:
                                    # Dependency not met yet on cloud
                                    skip_item = True
                                    logger.warning(
                                        f"SYNC SKIP [PUSH]: {model._meta.label} UUID:{local_item.uuid} - Related {related_model._meta.label} {related_uuid} not on Cloud yet."
                                    )
                                    break
                                value = cloud_related

                        data[field.name] = value

                    if skip_item:
                        continue

                    if cloud_item:
                        if local_item.updated_at > cloud_item.updated_at:
                            # Update existing cloud item
                            for key, val in data.items():
                                setattr(cloud_item, key, val)

                            cloud_item._syncing = True
                            cloud_item.save(using="cloud")

                            # Handle ManyToMany
                            for m2m_field in model._meta.many_to_many:
                                local_m2m = getattr(local_item, m2m_field.name).all()
                                cloud_m2m_objs = []
                                for item in local_m2m:
                                    c_obj = (
                                        m2m_field.related_model.objects.using("cloud")
                                        .filter(uuid=item.uuid)
                                        .first()
                                    )
                                    if c_obj:
                                        cloud_m2m_objs.append(c_obj)
                                getattr(cloud_item, m2m_field.name).set(cloud_m2m_objs)

                            print(
                                f"SYNC [PUSH/UPDATE]: {model._meta.label} UUID:{local_item.uuid} updated on Cloud"
                            )
                    else:
                        # Check for unique field conflicts on User model
                        if model.__name__ == "User":
                            # Check username conflict (case-insensitive for MySQL)
                            if "username" in data and data["username"]:
                                cloud_user_with_username = (
                                    model.objects.using("cloud")
                                    .filter(username__iexact=data["username"])
                                    .first()
                                )
                                if cloud_user_with_username:
                                    logger.warning(
                                        f"SYNC SKIP [PUSH]: {model._meta.label} UUID:{local_item.uuid} - Username '{data['username']}' already exists on Cloud with UUID {cloud_user_with_username.uuid}"
                                    )
                                    skip_item = True
                                    continue
                            # Check registration_number conflict
                            if (
                                "registration_number" in data
                                and data["registration_number"]
                            ):
                                cloud_user_with_reg = (
                                    model.objects.using("cloud")
                                    .filter(
                                        registration_number=data["registration_number"]
                                    )
                                    .first()
                                )
                                if cloud_user_with_reg:
                                    logger.warning(
                                        f"SYNC SKIP [PUSH]: {model._meta.label} UUID:{local_item.uuid} - Registration number '{data['registration_number']}' already exists on Cloud with UUID {cloud_user_with_reg.uuid}"
                                    )
                                    skip_item = True
                                    continue

                        # Create new on cloud
                        cloud_item = model.objects.using("cloud").create(**data)

                        # Handle ManyToMany for new item
                        for m2m_field in model._meta.many_to_many:
                            local_m2m = getattr(local_item, m2m_field.name).all()
                            cloud_m2m_objs = []
                            for item in local_m2m:
                                c_obj = (
                                    m2m_field.related_model.objects.using("cloud")
                                    .filter(uuid=item.uuid)
                                    .first()
                                )
                                if c_obj:
                                    cloud_m2m_objs.append(c_obj)
                            getattr(cloud_item, m2m_field.name).set(cloud_m2m_objs)

                        print(
                            f"SYNC [PUSH/NEW]: {model._meta.label} UUID:{local_item.uuid} created on Cloud"
                        )

                    local_item.synced = True
                    local_item._syncing = True
                    local_item.save(using="default")
                except Exception as e:
                    logger.error(
                        f"Push failed for {model._meta.label} UUID:{local_item.uuid}: {str(e)}"
                    )

        # 2. Handle deletions
        from django.db import IntegrityError
        from django.db.models.deletion import ProtectedError

        from .models import DeletedRecord

        deleted_records = list(DeletedRecord.objects.all())
        for dr in deleted_records:
            try:
                model = apps.get_model(dr.model_label)
                # Delete from cloud if exists. If the cloud schema still
                # enforces a PROTECT relationship (older migration) on a parent
                # that has referencing children, this raises ProtectedError.
                # Once every site has applied migration
                # 0008_subscription_plan_set_null, this is no longer possible
                # for SubscriptionPlan because Subscription.plan becomes
                # SET_NULL and Django simply nulls the FKs on delete.
                #
                # IntegrityError (MySQL 1048 "Column 'plan_id' cannot be null")
                # means the cloud column is still NOT NULL while Django thinks
                # SET_NULL is allowed — defer until migrate --database=cloud
                # has been applied.
                model.objects.using("cloud").filter(uuid=dr.uuid).delete()
                print(
                    f"SYNC [PUSH/DELETE]: {dr.model_label} UUID:{dr.uuid} deleted from Cloud"
                )
                dr.delete()
            except ProtectedError as e:
                # Stale cloud schema (PROTECT FK still in place) or genuine
                # protected children. Keep DeletedRecord and retry next cycle.
                logger.debug(
                    f"Deferring deletion for {dr.model_label} UUID:{dr.uuid} "
                    f"(protected children on cloud): {e.args[0] if e.args else e}"
                )
            except IntegrityError as e:
                # Typically NOT NULL on a SET_NULL FK that local code expects
                # to null (e.g. business_subscription.plan_id). Defer until
                # the cloud schema is migrated; avoid ERROR spam each cycle.
                logger.warning(
                    f"Deferring deletion for {dr.model_label} UUID:{dr.uuid} "
                    f"(cloud schema mismatch / IntegrityError): {e}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to push deletion for {dr.model_label} UUID:{dr.uuid}: {str(e)}"
                )

    def pull_cloud_changes(self, force=False):
        if not self._is_online():
            raise ConnectionError(
                "Impossible de récupérer les données : le cloud est injoignable."
            )

        sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]

        for model in sync_models:
            try:
                cloud_items = model.objects.using("cloud").all()
                cloud_uuids = set(cloud_items.values_list("uuid", flat=True))

                # 1. Sync updates and new items
                for cloud_item in cloud_items:
                    local_item = (
                        model.objects.using("default")
                        .filter(uuid=cloud_item.uuid)
                        .first()
                    )

                    if (
                        not local_item
                        or force
                        or cloud_item.updated_at > local_item.updated_at
                    ):
                        data = {}
                        skip_item = False
                        for field in model._meta.fields:
                            if field.primary_key:
                                continue

                            try:
                                value = getattr(cloud_item, field.name)
                            except Exception as fk_err:
                                # Related object doesn't exist on cloud yet — skip this item
                                skip_item = True
                                logger.warning(
                                    f"SYNC SKIP [PULL]: {model._meta.label} UUID:{cloud_item.uuid} - Could not access field '{field.name}': {fk_err}"
                                )
                                break

                            if field.is_relation and value:
                                related_uuid = getattr(value, "uuid", None)
                                if related_uuid:
                                    related_model = field.related_model
                                    local_related = (
                                        related_model.objects.using("default")
                                        .filter(uuid=related_uuid)
                                        .first()
                                    )
                                    if not local_related:
                                        # Dependency missing locally
                                        skip_item = True
                                        logger.warning(
                                            f"SYNC SKIP [PULL]: {model._meta.label} UUID:{cloud_item.uuid} - Related {related_model._meta.label} {related_uuid} not found locally."
                                        )
                                        break
                                    value = local_related

                            data[field.name] = value

                        if skip_item:
                            continue

                        if not local_item:
                            # Create new locally
                            data["synced"] = True
                            local_item = model(**data)
                            local_item._syncing = True
                            local_item.save(using="default")

                            # Handle ManyToMany
                            for m2m_field in model._meta.many_to_many:
                                cloud_m2m = getattr(cloud_item, m2m_field.name).all()
                                local_m2m_objs = []
                                for item in cloud_m2m:
                                    l_obj = (
                                        m2m_field.related_model.objects.using("default")
                                        .filter(uuid=item.uuid)
                                        .first()
                                    )
                                    if l_obj:
                                        local_m2m_objs.append(l_obj)
                                getattr(local_item, m2m_field.name).set(local_m2m_objs)

                            print(
                                f"SYNC [PULL/NEW]: {model._meta.label} UUID:{cloud_item.uuid} imported locally"
                            )
                        else:
                            # Update local from cloud
                            for key, val in data.items():
                                setattr(local_item, key, val)

                            local_item.synced = True
                            local_item._syncing = True
                            local_item.save(using="default")

                            # Handle ManyToMany
                            for m2m_field in model._meta.many_to_many:
                                cloud_m2m = getattr(cloud_item, m2m_field.name).all()
                                local_m2m_objs = []
                                for item in cloud_m2m:
                                    l_obj = (
                                        m2m_field.related_model.objects.using("default")
                                        .filter(uuid=item.uuid)
                                        .first()
                                    )
                                    if l_obj:
                                        local_m2m_objs.append(l_obj)
                                getattr(local_item, m2m_field.name).set(local_m2m_objs)

                            print(
                                f"SYNC [PULL/UPDATE]: {model._meta.label} UUID:{cloud_item.uuid} updated locally (Force={force})"
                            )

                # 2. Sync deletions from Cloud
                local_synced_items = model.objects.using("default").filter(synced=True)
                for local_item in local_synced_items:
                    if local_item.uuid not in cloud_uuids:
                        local_item._syncing = True
                        local_item.delete()
                        print(
                            f"SYNC [PULL/DELETE]: {model._meta.label} UUID:{local_item.uuid} deleted locally (Gone from Cloud)"
                        )

            except Exception as e:
                logger.error(f"Pull failed for {model._meta.label}: {str(e)}")


from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from finance.models import Invoice
from notifications.models import Notification


class DeactivateDelinquentClientsCronJob(CronJobBase):
    RUN_EVERY_MINS = 1440  # Daily

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = "sync_engine.deactivate_delinquent_clients"

    def do(self):
        logger.info("Starting Deactivation Process for delinquent clients...")
        two_months_ago = timezone.now().date() - timedelta(days=60)

        # Get active clients
        active_clients = User.objects.filter(role=User.Role.CLIENT, is_active=True)

        deactivated_count = 0
        for client in active_clients:
            # Check if they have 2 or more PENDING invoices
            pending_invoices_count = Invoice.objects.filter(
                client=client, status=Invoice.Status.PENDING
            ).count()

            if pending_invoices_count >= 2:
                client.is_active = False
                client.synced = False
                client.save()

                # Also deactivate their subscription
                client.subscriptions.filter(is_active=True).update(
                    is_active=False, synced=False
                )

                deactivated_count += 1
                logger.info(
                    f"Client {client.username} deactivated due to {pending_invoices_count} unpaid invoices."
                )

        logger.info(
            f"Deactivation process completed. {deactivated_count} clients deactivated."
        )


class LatePaymentNotificationCronJob(CronJobBase):
    RUN_EVERY_MINS = 1440  # Daily

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = "sync_engine.late_payment_notification"

    def do(self):
        logger.info("Starting Late Payment Notification Process...")
        today = timezone.now().date()

        # 1. Overdue Invoices: due_date < today
        overdue_invoices = Invoice.objects.filter(
            status=Invoice.Status.PENDING, due_date__lt=today
        )

        notification_count = 0
        for invoice in overdue_invoices:
            # Only notify if not notified in the last 3 days
            if not invoice.last_alert_sent or (
                today - invoice.last_alert_sent
            ) >= timedelta(days=3):
                Notification.objects.create(
                    user=invoice.client,
                    title="Retard de Paiement",
                    message=f"Votre facture de {invoice.amount} FCFA (échéance le {invoice.due_date}) est en retard. Veuillez régulariser votre situation.",
                    synced=False,
                )
                invoice.last_alert_sent = today
                invoice.synced = False
                invoice.save()
                notification_count += 1

        # 2. Due Today Invoices: due_date == today
        due_today_invoices = Invoice.objects.filter(
            status=Invoice.Status.PENDING, due_date=today
        )

        reminder_count = 0
        for invoice in due_today_invoices:
            if not invoice.last_alert_sent:
                Notification.objects.create(
                    user=invoice.client,
                    title="Rappel de Paiement",
                    message=f"Votre facture de {invoice.amount} FCFA arrive à échéance aujourd'hui. N'oubliez pas de la régler.",
                    synced=False,
                )
                invoice.last_alert_sent = today
                invoice.synced = False
                invoice.save()
                reminder_count += 1

        logger.info(
            f"Notification process completed. {notification_count} late alerts and {reminder_count} reminders sent."
        )


class SubscriptionExpiryNotificationCronJob(CronJobBase):
    RUN_EVERY_MINS = 1440  # Daily

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = "sync_engine.subscription_expiry_notification"

    def do(self):
        logger.info(
            "Starting Subscription Expiry & Pending Payment Notification Process..."
        )
        today = timezone.now().date()
        from business.models import Subscription
        from finance.models import Payment

        # 1. Subscriptions expiring in 3 days
        expiry_3_days = today + timedelta(days=3)
        subs_to_notify = Subscription.objects.filter(
            is_active=True, end_date=expiry_3_days
        )

        sub_notif_count = 0
        for sub in subs_to_notify:
            plan_name = sub.plan.name if sub.plan else "(plan supprimé)"
            Notification.objects.create(
                user=sub.client,
                title="Échéance d'Abonnement",
                message=f"Votre abonnement {plan_name} arrive à expiration dans 3 jours (le {sub.end_date}). Pensez à le renouveler.",
                synced=False,
            )
            sub_notif_count += 1

        # 2. Subscriptions expired today
        expired_today = Subscription.objects.filter(is_active=True, end_date=today)
        for sub in expired_today:
            plan_name = sub.plan.name if sub.plan else "(plan supprimé)"
            Notification.objects.create(
                user=sub.client,
                title="Abonnement Expiré",
                message=f"Votre abonnement {plan_name} a expiré aujourd'hui. Votre accès sera limité jusqu'au prochain paiement.",
                synced=False,
            )
            sub_notif_count += 1

        # 3. Pending Mobile Money payments (not validated)
        # These are payments created via OpenPay/Momo but not yet confirmed by accountant
        pending_momo = Payment.objects.filter(
            is_validated=False, payment_method="Mobile Money", paid_at__date=today
        )

        momo_notif_count = 0
        for pay in pending_momo:
            # Notify the client that their payment is being processed
            Notification.objects.create(
                user=pay.invoice.client,
                title="Paiement en cours de validation",
                message=f"Votre paiement de {pay.amount} FCFA par Mobile Money est en cours de validation par nos services. Votre accès sera activé sous peu.",
                synced=False,
            )
            momo_notif_count += 1

        logger.info(
            f"Subscription process completed. {sub_notif_count} expiry alerts and {momo_notif_count} momo status alerts sent."
        )
