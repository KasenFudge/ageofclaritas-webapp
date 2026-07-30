from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Deletes accounts that registered but never verified their email within the "
        "given time window (default 24 hours). Verified/active accounts are never touched."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=float,
            default=24,
            help="Age threshold in hours since registration (default: 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["hours"])

        # is_active=False is the only signal this schema has for "unverified" -
        # it's set False at registration and flipped True on activation. Restrict
        # to accounts that never logged in and hold no elevated permissions, so
        # this can't sweep up a real account an admin manually deactivated.
        stale_accounts = User.objects.filter(
            is_active=False,
            is_staff=False,
            is_superuser=False,
            last_login__isnull=True,
            date_joined__lt=cutoff,
            parent_account__isnull=True,  # never sweep dependent/linked-teen profiles
        )

        count = stale_accounts.count()

        if options["dry_run"]:
            for user in stale_accounts:
                self.stdout.write(f"  Would delete: {user.username} <{user.email}> (joined {user.date_joined})")
            self.stdout.write(self.style.WARNING(f"Dry run: {count} unverified account(s) would be deleted"))
            return

        deleted_count, _ = stale_accounts.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} unverified account(s) older than {options['hours']}h"))
