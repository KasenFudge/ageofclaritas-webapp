from django.db.models.signals import pre_save
from django.dispatch import receiver

from rulebook.sanitize import sanitize_richtext

from .models import Waiver


@receiver(pre_save, sender=Waiver)
def sanitize_waiver_content(sender, instance, raw=False, **kwargs):
    if raw:
        return
    instance.content = sanitize_richtext(instance.content)
