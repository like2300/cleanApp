from django import template
from finance.models import Payment
from django.utils import timezone
from datetime import timedelta

register = template.Library()

@register.filter(name='has_payment')
def has_payment(client, month):
    """
    Check if a client has a payment for a specific month
    """
    if not client or not month:
        return False
    
    # Get the first and last day of the month
    if isinstance(month, str):
        # Parse the month string if needed
        from datetime import datetime
        month = datetime.strptime(month, '%Y-%m-%d').date()
    
    first_day = month.replace(day=1)
    if month.month == 12:
        last_day = first_day.replace(year=first_day.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = first_day.replace(month=first_day.month + 1, day=1) - timedelta(days=1)
    
    # Check if client has any payment in this month
    return Payment.objects.filter(
        client=client,
        created_at__gte=first_day,
        created_at__lte=last_day
    ).exists()