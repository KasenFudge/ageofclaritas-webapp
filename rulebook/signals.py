from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import NoReverseMatch, reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from .models import Attribute, Class, Definition, IndexType, Kin, Talent

# Definition.short_description is a CharField(max_length=300) -- keep every
# value we write to it safely under that, no matter where it came from.
SHORT_DESCRIPTION_MAX_LENGTH = 300


# ------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------
def get_safe_url(view_name, **kwargs):
    """Safely attempts to resolve a URL, returning empty string if it fails."""
    try:
        return reverse(view_name, kwargs=kwargs)
    except NoReverseMatch:
        return ""


def sync_index(index_type, source_id, *, term, description, target_url, short_description=None):
    if not short_description:
        # Strip markup before truncating. Truncator.chars(..., html=True) only
        # counts *visible* text toward its limit and leaves surrounding tags
        # untouched -- so rich-text markup (a long <a href="...">, nested
        # <strong>/<em>/<p> tags, etc.) can push the rendered string well past
        # 295 characters even though only 295 chars of visible text were kept.
        # Plain text has no such overhead, so a straightforward char-count
        # truncation is safe here.
        short_description = Truncator(strip_tags(description)).chars(295)

    # Defensive hard cap: applies to the computed value above as well as any
    # short_description passed in directly (e.g. Kin.short_description, which
    # is a free-form TextField with no length limit of its own), so a value
    # from either path can never overflow the DB column.
    short_description = short_description[:SHORT_DESCRIPTION_MAX_LENGTH]

    Definition.objects.update_or_create(
        index_type=index_type,
        source_id=source_id,
        defaults={
            "term": term,
            "short_description": short_description,
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
        short_description=instance.short_description or None,
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
