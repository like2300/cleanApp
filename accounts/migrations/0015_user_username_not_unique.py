from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_companysettings_constant_uuid"),
    ]

    operations = [
        # Le username reste techniquement unique (exigence Django USERNAME_FIELD),
        # mais il est genere a partir de l'uuid. Deux clients peuvent donc
        # partager le meme NOM affiche (stocke dans display_name). La vraie
        # distinction entre clients se fait via l'uuid (ID de synchronisation).
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=150, unique=True),
        ),
        # Nom reel affiche dans l'UI (peut etre partage par plusieurs clients).
        migrations.AddField(
            model_name="user",
            name="display_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
