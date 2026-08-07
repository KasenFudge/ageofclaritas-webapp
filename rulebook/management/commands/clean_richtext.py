from django.core.management.base import BaseCommand

from accounts.models import Waiver
from events.models import Event
from rulebook.models import Attribute, Class, Kin, RulePage, Talent
from rulebook.sanitize import sanitize_richtext

RICHTEXT_FIELDS = {
    Class: ("description", "special_rules"),
    Talent: ("description",),
    Kin: ("short_description", "description"),
    Attribute: ("description",),
    RulePage: ("content",),
    Waiver: ("content",),
    Event: ("description",),
}


class Command(BaseCommand):
    help = (
        "One-time cleanup: runs every rich-text field through the same "
        "sanitize_richtext() used by the save-time signals and re-saves any "
        "record whose cleaned value differs. Safe to run repeatedly -- "
        "already-clean rows are left untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would change without writing anything."
        )
        parser.add_argument(
            "--model", action="append", dest="models", help="Restrict to one model (e.g. --model Talent). Repeatable."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        wanted = set(options["models"] or [])
        total_checked = total_changed = 0

        for model, fields in RICHTEXT_FIELDS.items():
            if wanted and model.__name__ not in wanted:
                continue
            checked = changed = 0
            for instance in model.objects.all():
                checked += 1
                diffs = []
                dirty = False
                for field_name in fields:
                    original = getattr(instance, field_name)
                    cleaned = sanitize_richtext(original)
                    if cleaned != original:
                        diffs.append((field_name, original, cleaned))
                        setattr(instance, field_name, cleaned)
                        dirty = True
                if dirty:
                    changed += 1
                    label = getattr(instance, "name", None) or getattr(instance, "title", None) or instance.pk
                    if dry_run:
                        for field_name, original, cleaned in diffs:
                            self.stdout.write(
                                f"  [{model.__name__} pk={instance.pk} {label!r}] {field_name}: "
                                f"{len(original)} chars -> {len(cleaned)} chars"
                            )
                    else:
                        instance.save()  # re-triggers pre_save (harmless no-op 2nd pass) and,
                        # for Class/Talent/Kin/Attribute, the post_save index mirror.
            total_checked += checked
            total_changed += changed
            verb = "would change" if dry_run else "changed"
            self.stdout.write(f"  {model.__name__}: {checked} checked, {changed} {verb}")

        summary = (
            f"{'Dry run: ' if dry_run else ''}{total_changed} of {total_checked} "
            f"record(s) {'would change' if dry_run else 'cleaned'}"
        )
        self.stdout.write((self.style.WARNING if dry_run else self.style.SUCCESS)(summary))
