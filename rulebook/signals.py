from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import NoReverseMatch, reverse

from .models import Attribute, Class, Definition, IndexType, Kin, RulePage, Talent
from .sanitize import sanitize_richtext


# ------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------
def get_safe_url(view_name, **kwargs):
    """Safely attempts to resolve a URL, returning empty string if it fails."""
    try:
        return reverse(view_name, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def sync_index(index_type, source_id, *, term, description, target_url):
    # update_or_create() only persists the columns named in `defaults` (it
    # calls save(update_fields=...) under the hood on an update) -- slug must
    # be listed explicitly here or a rename would recompute it in memory
    # inside Definition.save() and then silently fail to write it, since
    # Definition.save() itself doesn't control what update_fields it was
    # called with.
    Definition.objects.update_or_create(
        index_type=index_type,
        source_id=source_id,
        defaults={
            "term": term,
            "slug": Definition.build_slug(index_type, term),
            "description": description,
            "target_url": target_url,
        },
    )


def remove_from_index(index_type, source_id):
    Definition.objects.filter(index_type=index_type, source_id=source_id).delete()


# ------------------------------------------------------------------------
# CLASS SIGNALS
# ------------------------------------------------------------------------
@receiver(post_save, sender=Class)
def sync_class_to_index(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    sync_index(
        IndexType.CLASS,
        instance.pk,
        term=instance.name,
        description=instance.description,
        target_url=get_safe_url("rulebook:class_detail", slug=instance.slug),
    )


@receiver(post_delete, sender=Class)
def remove_class_from_index(sender, instance, **kwargs):
    remove_from_index(IndexType.CLASS, instance.pk)


# ------------------------------------------------------------------------
# TALENT SIGNALS
# ------------------------------------------------------------------------
@receiver(post_save, sender=Talent)
def sync_talent_to_index(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    target_url = ""
    if instance.class_for_id:
        base_url = get_safe_url("rulebook:class_detail", slug=instance.class_for.slug)
        if base_url:
            target_url = f"{base_url}#{instance.slug}"

    sync_index(
        IndexType.TALENT,
        instance.pk,
        term=instance.name,
        description=instance.description,
        target_url=target_url,
    )


@receiver(post_delete, sender=Talent)
def remove_talent_from_index(sender, instance, **kwargs):
    remove_from_index(IndexType.TALENT, instance.pk)


# ------------------------------------------------------------------------
# KIN SIGNALS
# ------------------------------------------------------------------------
@receiver(post_save, sender=Kin)
def sync_kin_to_index(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    sync_index(
        IndexType.KIN,
        instance.pk,
        term=instance.name,
        description=instance.description,
        target_url=get_safe_url("rulebook:kin_detail", slug=instance.slug),
    )


@receiver(post_delete, sender=Kin)
def remove_kin_from_index(sender, instance, **kwargs):
    remove_from_index(IndexType.KIN, instance.pk)


# ------------------------------------------------------------------------
# ATTRIBUTE SIGNALS
# ------------------------------------------------------------------------
@receiver(post_save, sender=Attribute)
def sync_attribute_to_index(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    target_url = ""
    if instance.kin_for_id:
        base_url = get_safe_url("rulebook:kin_detail", slug=instance.kin_for.slug)
        if base_url:
            target_url = f"{base_url}#{instance.slug}"

    sync_index(
        IndexType.ATTRIBUTE,
        instance.pk,
        term=instance.name,
        description=instance.description,
        target_url=target_url,
    )


@receiver(post_delete, sender=Attribute)
def remove_attribute_from_index(sender, instance, **kwargs):
    remove_from_index(IndexType.ATTRIBUTE, instance.pk)


# ------------------------------------------------------------------------
# RICH-TEXT SANITIZATION (pre_save, runs before the index-mirror post_save
# handlers above so Definition always receives the already-cleaned value)
# ------------------------------------------------------------------------
RICHTEXT_FIELDS = {
    Class: ("description", "special_rules"),
    Talent: ("description",),
    Kin: ("short_description", "description"),
    Attribute: ("description",),
    RulePage: ("content",),
}


@receiver(pre_save)
def sanitize_richtext_fields(sender, instance, raw=False, **kwargs):
    if raw:
        return
    fields = RICHTEXT_FIELDS.get(sender)
    if not fields:
        return
    for field_name in fields:
        setattr(instance, field_name, sanitize_richtext(getattr(instance, field_name)))
