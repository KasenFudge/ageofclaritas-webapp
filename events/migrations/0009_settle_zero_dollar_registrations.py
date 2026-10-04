from django.db import migrations
from django.db.models import Q


def settle_zero_dollar_registrations(apps, schema_editor):
    """
    Registrations whose price was lowered to $0 before EventRegistration.save() settled them automatically
    were left looking unpaid. Give each one the same $0 succeeded transaction a new $0 registration gets.
    """
    EventRegistration = apps.get_model("events", "EventRegistration")
    Transaction = apps.get_model("payments", "Transaction")

    unsettled = EventRegistration.objects.filter(final_price_cents=0).filter(
        Q(transaction__isnull=True) | Q(transaction__payment_status__in=["incomplete", "failed"])
    )
    for registration in unsettled:
        registration.transaction = Transaction.objects.create(
            total_amount_cents=0, payment_status="succeeded", payment_method="online"
        )
        registration.save(update_fields=["transaction"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0008_remove_event_downtime_due"),
        ("payments", "0005_promotion_voucher"),
    ]

    operations = [
        migrations.RunPython(settle_zero_dollar_registrations, migrations.RunPython.noop),
    ]
