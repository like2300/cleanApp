from django.db import migrations

COMPANY_SETTINGS_UUID = "00000000-0000-0000-0000-000000000001"


def migrate_company_settings_uuid(apps, schema_editor):
    """Ramene l'unique instance CompanySettings vers un UUID constant afin
    que le moteur de synchronisation (qui identifie les objets par uuid)
    la reconnaisse comme le meme enregistrement sur tous les sites."""
    CompanySettings = apps.get_model("accounts", "CompanySettings")
    db_alias = schema_editor.connection.alias

    # Supprimer d'eventuels doublons (crees par des pulls precedents)
    existing = list(CompanySettings.objects.using(db_alias).order_by("id"))
    if not existing:
        # Rien a faire, l'instance sera cree avec le bon uuid via get_settings()
        return

    # Conserver la premiere instance comme reference (elle porte les vraies donnees)
    primary = existing[0]
    for dup in existing[1:]:
        dup.delete(using=db_alias)

    # Forcer l'UUID constant sur l'instance conservee
    if str(primary.uuid) != COMPANY_SETTINGS_UUID:
        # Eviter un conflit d'unicite : retirer temporairement l'uuid des autres
        primary.uuid = COMPANY_SETTINGS_UUID
        primary.save(using=db_alias)


def reverse_company_settings_uuid(apps, schema_editor):
    # Non reversible de facon meaningful : on laisse tel quel.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(
            migrate_company_settings_uuid, reverse_company_settings_uuid
        ),
    ]
