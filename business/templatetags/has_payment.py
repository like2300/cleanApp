from django import template
from finance.models import Payment

register = template.Library()

@register.filter
def has_payment_for_month(client, month):
    """Check if client has payment for specific month"""
    if not client or not month:
        return False
    
    # Parse month if it's a string
    if isinstance(month, str):
        from datetime import datetime
        month = datetime.strptime(month, '%Y-%m-%d').date()
    
    # Check if any payment exists for this month
    first_day = month.replace(day=1)
    if month.month == 12:
        last_day = first_day.replace(year=first_day.year + 1, month=1, day=1)
    else:
        last_day = first_day.replace(month=first_day.month + 1, day=1)
    
    return Payment.objects.filter(
        invoice__client=client,
        paid_at__gte=first_day,
        paid_at__lte=last_day
    ).exists()
