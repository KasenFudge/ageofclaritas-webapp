from django.db.models.signals import pre_save
from django.dispatch import receiver

from rulebook.sanitize import sanitize_richtext

from .models import Event


@receiver(pre_save, sender=Event)
def sanitize_event_description(sender, instance, raw=False, **kwargs):
    if raw:
        return
    instance.description = sanitize_richtext(instance.description)
