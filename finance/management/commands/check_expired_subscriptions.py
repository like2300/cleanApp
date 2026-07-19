from django.core.management.base import BaseCommand
from finance.views import check_and_create_invoices_for_expired_subscriptions

class Command(BaseCommand):
    help = 'Check for expired subscriptions and create pending invoices automatically'

    def handle(self, *args, **options):
        self.stdout.write("Checking for expired subscriptions...")
        
        count = check_and_create_invoices_for_expired_subscriptions()
        
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} expired subscriptions'))
        else:
            self.stdout.write(self.style.WARNING('No expired subscriptions found'))