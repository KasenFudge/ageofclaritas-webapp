from django.db import migrations


def backfill_refunds(apps, schema_editor):
    """
    Before refunds were tracked per registration, a REFUNDED payment showed every registration on it as
    refunded. Record those as full refunds so they keep showing the same way. The refund date wasn't
    stored, so refunded_at stays empty.
    """
    Transaction = apps.get_model("payments", "Transaction")

    for transaction in Transaction.objects.filter(payment_status="refunded"):
        transaction.refunded_amount_cents = transaction.total_amount_cents
        transaction.save(update_fields=["refunded_amount_cents"])
        for registration in transaction.registrations.all():
            registration.refunded_cents = registration.final_price_cents
            registration.save(update_fields=["refunded_cents"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0010_registration_refund_tracking"),
        ("payments", "0007_transaction_refund_tracking"),
    ]

    operations = [
        migrations.RunPython(backfill_refunds, migrations.RunPython.noop),
    ]
