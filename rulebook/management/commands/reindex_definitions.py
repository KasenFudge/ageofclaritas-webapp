from django.core.management.base import BaseCommand

from rulebook.models import Attribute, Class, Definition, IndexType, Kin, Talent


class Command(BaseCommand):
    help = "Rebuilds the Definition search index from Class, Talent, Kin, and Attribute."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Also delete synced Definition rows whose source object no longer exists.",
        )

    def handle(self, *args, **options):
        synced_types = [
            (Class, IndexType.CLASS),
            (Talent, IndexType.TALENT),
            (Kin, IndexType.KIN),
            (Attribute, IndexType.ATTRIBUTE),
        ]

        total = 0
        for model, index_type in synced_types:
            count = 0
            for instance in model.objects.all():
                instance.save()  # re-triggers the post_save sync signal
                count += 1
            self.stdout.write(f"  {index_type.label}: {count} synced")
            total += count

        if options["prune"]:
            pruned = 0
            for model, index_type in synced_types:
                valid_ids = set(model.objects.values_list("pk", flat=True))
                stale = Definition.objects.filter(index_type=index_type).exclude(source_id__in=valid_ids)
                pruned += stale.count()
                stale.delete()
            self.stdout.write(f"Pruned {pruned} stale Definition row(s)")

        self.stdout.write(self.style.SUCCESS(f"Reindexed {total} objects into Definition"))
