from django.db import migrations
from django.db.models import Count
from django.utils.text import slugify


def _unique_slug(model, instance_pk, base_slug):
    """Append -2, -3, ... if slugify() collides with an existing row."""
    slug = base_slug
    counter = 2
    while model.objects.exclude(pk=instance_pk).filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def backfill(apps, schema_editor):
    Talent = apps.get_model("rulebook", "Talent")
    Attribute = apps.get_model("rulebook", "Attribute")
    Class = apps.get_model("rulebook", "Class")

    # --- Talent: fix orphaned class_for before it's made non-null in 0006 ---
    # Adjust this to however you actually want to assign these -- a "classless"
    # sentinel Class, or hand-pick each one in the admin/shell before running.
    fallback = Class.objects.filter(class_type="classless").first()
    if fallback:
        Talent.objects.filter(class_for__isnull=True).update(class_for=fallback)

    # --- Talent: backfill slugs (name is already unique, so no dedupe needed) ---
    for talent in Talent.objects.filter(slug__isnull=True):
        base = slugify(talent.name)
        talent.slug = _unique_slug(Talent, talent.pk, base)
        talent.save(update_fields=["slug"])

    # --- Attribute: rename duplicate names before uniqueness is enforced in 0006 ---
    dupes = (
        Attribute.objects.values("name")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .values_list("name", flat=True)
    )
    for name in dupes:
        matches = list(Attribute.objects.filter(name=name).select_related("kin_for"))
        # Leave the first occurrence alone, disambiguate the rest by kin name.
        for attr in matches[1:]:
            attr.name = f"{attr.name} ({attr.kin_for.name})"
            attr.save(update_fields=["name"])

    # --- Attribute: backfill slugs ---
    for attribute in Attribute.objects.filter(slug__isnull=True):
        base = slugify(attribute.name)
        attribute.slug = _unique_slug(Attribute, attribute.pk, base)
        attribute.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("rulebook", "0004_initial_glossary_index"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
