"""D3: green < 1 week, yellow < 1 month, red > 1 month (or never verified)."""
from django.utils import timezone
from datetime import timedelta


def staleness(last_verified_at):
    if last_verified_at is None:
        return "red"
    age = timezone.now() - last_verified_at
    if age < timedelta(days=7):
        return "green"
    if age < timedelta(days=30):
        return "yellow"
    return "red"
