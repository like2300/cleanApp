from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User
from business.models import Zone

class Command(BaseCommand):
    help = 'Assign all clients without a zone to a specified zone'

    def add_arguments(self, parser):
        parser.add_argument(
            '--zone-name',
            type=str,
            required=True,
            help='Name of the zone to assign clients to (e.g., "Diata B")'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes'
        )

    def handle(self, *args, **options):
        zone_name = options['zone_name']
        dry_run = options['dry_run']

        # Find the zone
        try:
            zone = Zone.objects.get(name__iexact=zone_name)
            self.stdout.write(self.style.SUCCESS(f'Zone found: {zone.name} (ID: {zone.pk})'))
        except Zone.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Zone "{zone_name}" not found!'))
            self.stdout.write('Available zones:')
            for z in Zone.objects.all():
                self.stdout.write(f'  - {z.name}')
            return

        # Find clients without a zone
        clients_without_zone = User.objects.filter(
            role=User.Role.CLIENT,
            zone__isnull=True
        )

        self.stdout.write(self.style.WARNING(f'\nFound {clients_without_zone.count()} clients without a zone:'))
        for client in clients_without_zone[:10]:  # Show first 10
            self.stdout.write(f'  - {client.username} ({client.first_name} {client.last_name}) - {client.email}')
        if clients_without_zone.count() > 10:
            self.stdout.write(f'  ... and {clients_without_zone.count() - 10} more')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run: No changes made.'))
            return

        # Confirm with user
        self.stdout.write(self.style.WARNING('\nYou are about to assign these clients to zone "' + zone.name + '"'))
        self.stdout.write('Type "yes" to confirm, or anything else to cancel: ')
        response = input()
        
        if response.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Cancelled.'))
            return

        # Assign clients to zone
        try:
            with transaction.atomic():
                updated_count = clients_without_zone.update(zone=zone)
                self.stdout.write(self.style.SUCCESS(f'\nSuccessfully assigned {updated_count} clients to zone "{zone.name}"'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            transaction.rollback()
