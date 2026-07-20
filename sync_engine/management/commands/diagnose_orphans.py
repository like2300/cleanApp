"""
Diagnostic des enregistrements orphelins dans le cloud.

Un enregistrement est "orphelin" quand sa clé étrangère pointe vers un objet
qui n'existe plus (ou n'a jamais existé) dans la base cloud. Ces lignes ne
peuvent jamais être synchronisées et génèrent le spam d'erreurs
"Impossible d'accéder au champ 'client' / 'plan' / 'abonnement'".

Usage (sur le serveur AlwaysData) :
    python manage.py diagnose_orphans
    python manage.py diagnose_orphans --fix   # null les FK nullable orphelines

Le mode --fix ne touche QUE les FK déclarées null=True (ex: Subscription.plan,
Invoice.subscription, User.quartier/zone). Les FK non-nullables orphelines
(ex: Subscription.client) ne peuvent pas être nullées et sont listées pour
action manuelle (suppression côté cloud ou recréation du parent).
"""

from django.apps import apps
from django.core.management.base import BaseCommand

from sync_engine.models import SyncBaseModel


class Command(BaseCommand):
    help = "Liste (et optionnellement nettoie) les FK orphelines dans le cloud."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Null les FK nullable orphelines directement dans le cloud.",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        sync_models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]

        total_orphans = 0
        fixable = 0

        for model in sync_models:
            try:
                cloud_items = model.objects.using("cloud").all()
            except Exception as e:
                self.stderr.write(
                    f"[{model._meta.label}] impossible de lire le cloud : {e}"
                )
                continue

            for cloud_item in cloud_items:
                for field in model._meta.fields:
                    if not field.is_relation or not field.related_model:
                        continue
                    try:
                        value = getattr(cloud_item, field.name)
                    except Exception:
                        # FK orpheline : l'objet lié n'existe pas dans le cloud.
                        total_orphans += 1
                        if field.null:
                            fixable += 1
                            msg = (
                                f"ORPHELIN (fixable) {model._meta.label} "
                                f"UUID:{cloud_item.uuid} -> {field.name}"
                            )
                            if fix:
                                setattr(cloud_item, field.name, None)
                                cloud_item._syncing = True
                                cloud_item.save(using="cloud")
                                msg += " [NULLIFIÉ]"
                            self.stdout.write(msg)
                        else:
                            self.stdout.write(
                                f"ORPHELIN (NON-nullable) {model._meta.label} "
                                f"UUID:{cloud_item.uuid} -> {field.name} "
                                f"(action manuelle requise)"
                            )

        self.stdout.write(
            self.style.WARNING(
                f"\nTotal orphelins: {total_orphans} | fixables (nullable): {fixable}"
            )
        )
        if fixable and not fix:
            self.stdout.write(
                "Relance avec --fix pour nullifier les FK nullable orphelines."
            )
