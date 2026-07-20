from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0014_companysettings_constant_uuid"),
    ]

    operations = [
        # Le username n'est plus unique : plusieurs clients peuvent partager
        # le meme nom. La distinction reelle se fait via l'uuid (ID de sync).
        # Le login client utilise registration_number, pas username.
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=150, unique=False),
        ),
    ]
