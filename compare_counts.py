from finance.models import Invoice
from finance.models import Payment
from accounts.models import User
from business.models import Subscription, Zone

models = [Invoice, Payment, User, Subscription, Zone]

for model in models:
    local_count = model.objects.using('default').count()
    try:
        cloud_count = model.objects.using('cloud').count()
        print(f"{model._meta.label}: Local={local_count}, Cloud={cloud_count}")
    except Exception as e:
        print(f"Error checking {model._meta.label} on cloud: {e}")
