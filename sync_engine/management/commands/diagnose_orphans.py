"""
Diagnostic et nettoyage des enregistrements orphelins dans le cloud.

Un enregistrement est "orphelin" quand sa clé étrangère pointe vers un objet
qui n'existe plus (ou n'a jamais existé) ni dans le cloud ni en local. Ces
lignes ne peuvent jamais être synchronisées et génèrent le message récurrent
"SYNC PULL: N enregistrement(s) ignore(s) (dependance manquante dans le cloud)".

Usage (sur le serveur AlwaysData ou en local) :
    python manage.py diagnose_orphans                 # liste les orphelins
    python manage.py diagnose_orphans --fix            # null les FK nullable orphelines
    python manage.py diagnose_orphans --delete         # supprime les enregistrements orphelins

--fix  ne touche QUE les FK déclarées null=True (ex: Subscription.plan,
        Invoice.subscription, User.quartier/zone) : on les met à NULL pour
        rendre l'enregistrement synchronisable.
--delete supprime carrément les enregistrements dont une FK (nullable ou non)
        est orpheline. À utiliser quand la donnée parente a disparu des deux
        bases et que l'enregistrement n'a plus de sens (ex: un abonnement
        dont le client n'existe plus nulle part).
"""

from django.apps import apps
from django.core.management.base import BaseCommand

from sync_engine.models import SyncBaseModel


def _dependency_ordered_models():
    """Models ordered parent-first (parents before children)."""
    models = [m for m in apps.get_models() if issubclass(m, SyncBaseModel)]
    deps = {}
    for m in models:
        needed = set()
        for field in m._meta.fields:
            if field.is_relation and field.related_model:
                rel = field.related_model
                if rel is not m and issubclass(rel, SyncBaseModel):
                    needed.add(rel)
        deps[m] = needed

    ordered = []
    visited = set()

    def visit(m):
        if m in visited:
            return
        visited.add(m)
        for dep in deps.get(m, ()):
            visit(dep)
        ordered.append(m)

    for m in models:
        visit(m)
    return ordered


def _orphan_fields(cloud_item):
    """Return the list of FK field names that are orphaned on this cloud item."""
    orphans = []
    for field in cloud_item._meta.fields:
        if not field.is_relation or not field.related_model:
            continue
        try:
            value = getattr(cloud_item, field.name)
        except Exception:
            # FK target does not exist in the cloud DB at all.
            orphans.append(field)
            continue
        if value is None:
            continue
        related_uuid = getattr(value, "uuid", None)
        if not related_uuid:
            continue
        local_related = (
            field.related_model.objects.using("default")
            .filter(uuid=related_uuid)
            .first()
        )
        if local_related:
            continue
        cloud_related = (
            field.related_model.objects.using("cloud").filter(uuid=related_uuid).first()
        )
        if not cloud_related:
            orphans.append(field)
    return orphans


class Command(BaseCommand):
    help = "Liste (et optionnellement nettoie) les FK orphelines dans le cloud."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Null les FK nullable orphelines directement dans le cloud.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Supprime les enregistrements orphelins dans le cloud.",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        delete = options["delete"]

        if fix and delete:
            self.stderr.write("Choisissez --fix OU --delete, pas les deux.")
            return

        sync_models = _dependency_ordered_models()

        total_orphans = 0
        fixable = 0
        deleted = 0

        for model in sync_models:
            try:
                cloud_items = list(model.objects.using("cloud").all())
            except Exception as e:
                self.stderr.write(
                    f"[{model._meta.label}] impossible de lire le cloud : {e}"
                )
                continue

            for cloud_item in cloud_items:
                orphans = _orphan_fields(cloud_item)
                if not orphans:
                    continue

                total_orphans += len(orphans)

                if delete:
                    # Delete the whole orphaned record from the cloud.
                    cloud_item._syncing = True
                    cloud_item.delete(using="cloud")
                    deleted += 1
                    self.stdout.write(
                        f"SUPPRIME (orphelin) {model._meta.label} "
                        f"UUID:{cloud_item.uuid} -> FK: "
                        f"{', '.join(f.name for f in orphans)}"
                    )
                    continue

                for field in orphans:
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
                            f"(utilisez --delete pour le supprimer)"
                        )

        self.stdout.write(
            self.style.WARNING(
                f"\nTotal champs orphelins: {total_orphans} | "
                f"fixables (nullable): {fixable} | supprimes: {deleted}"
            )
        )
        if fixable and not fix and not delete:
            self.stdout.write(
                "Relance avec --fix pour nullifier les FK nullable orphelines."
            )
        if not delete and not fix:
            self.stdout.write(
                "Relance avec --delete pour supprimer les enregistrements orphelins."
            )
