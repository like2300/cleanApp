from calendar import monthrange
from datetime import timedelta

from django.utils import timezone


def add_months_safe(date_value, months, anchor_day=None):
    """Shift a date by N months while preserving the billing day when possible."""
    month_index = date_value.month - 1 + months
    year = date_value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor_day or date_value.day, monthrange(year, month)[1])
    return date_value.replace(year=year, month=month, day=day)


def plan_period_months(plan):
    """Convert a plan duration to billing months for monthly subscriptions."""
    duration_days = getattr(plan, "duration_days", 30) or 30
    if duration_days < 28:
        return None
    return max(1, round(duration_days / 30))


def next_period_end_date(client, subscription, reference_date=None):
    """
    Return the next subscription end date.

    For monthly plans, keep the same billing day saved on the client
    (`fixed_due_date.day`). Only the month changes. If no fixed date exists,
    use the current subscription end day as the anchor.
    """
    reference_date = reference_date or timezone.now().date()
    months = (
        plan_period_months(subscription.plan)
        if subscription and subscription.plan
        else 1
    )

    if months is None:
        if subscription and subscription.plan:
            return reference_date + timedelta(days=subscription.plan.duration_days)
        return add_months_safe(reference_date, 1)

    anchor_day = None
    if getattr(client, "fixed_due_date", None):
        anchor_day = client.fixed_due_date.day
    elif subscription and subscription.end_date:
        anchor_day = subscription.end_date.day

    return add_months_safe(reference_date, months, anchor_day=anchor_day)


def payment_subscription_end_date(invoice):
    """Calculate the subscription end date after paying an invoice."""
    today = timezone.now().date()

    if not invoice.subscription:
        return add_months_safe(today, 1)

    subscription = invoice.subscription
    client = invoice.client

    previous_paid_invoice_exists = (
        subscription.invoice_set.filter(status="PAID").exclude(pk=invoice.pk).exists()
    )

    # First activation: the initial invoice carries the first period end date.
    # If it is paid late, move to the next same-day monthly period.
    if not subscription.is_active and not previous_paid_invoice_exists:
        first_end = invoice.due_date
        while first_end <= today:
            first_end = next_period_end_date(client, subscription, first_end)
        return first_end

    base_date = subscription.end_date or invoice.due_date or today

    # If the subscription is already overdue, advance complete monthly periods
    # until the new end date covers the current date.
    next_end = next_period_end_date(client, subscription, base_date)
    while next_end <= today:
        next_end = next_period_end_date(client, subscription, next_end)

    return next_end


def invoice_due_date_for_subscription(subscription):
    """Due date for a renewal invoice generated at the end of a subscription."""
    return subscription.end_date
