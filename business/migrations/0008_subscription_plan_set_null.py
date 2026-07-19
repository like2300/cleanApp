"""
Switch Subscription.plan from PROTECT to SET_NULL.

Previously, deleting a SubscriptionPlan on a site that had no local
Subscription rows referencing it would succeed locally and enqueue a
DeletedRecord via the sync engine. When the sync engine then tried to replay
that deletion on the cloud (or any peer site still hosting referencing
Subscription rows), Django raised ProtectedError because
`Subscription.plan -> SubscriptionPlan` was declared on_delete=PROTECT:

    Cannot delete some instances of model 'SubscriptionPlan' because they are
    referenced through protected foreign keys: 'Subscription.plan'.

The Subscription history itself should never be destroyed when a plan is
retired, so we now null out the FK and keep the row, matching the pattern
already used by Employee.position (on_delete=SET_NULL, null=True). This also
makes Subscription.__str__ already-tolerant of an absent plan ("Plan inconnu").
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("business", "0007_alter_subscription_is_active"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subscription",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="business.subscriptionplan",
            ),
        ),
    ]
