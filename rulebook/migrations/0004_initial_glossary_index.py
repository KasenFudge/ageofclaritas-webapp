from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rulebook", "0003_alter_talent_options_remove_class_has_special_rules"),
    ]

    operations = [
        # Old single-purpose glossary model -- superseded by the unified index below.
        migrations.DeleteModel(
            name="Definition",
        ),
        migrations.CreateModel(
            name="RulePage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=100, unique=True)),
                ("content", models.TextField(blank=True, default="", help_text="CKEditor HTML content.")),
            ],
            options={
                "ordering": ["title"],
            },
        ),
        # Brand new table, so the final shape (including uniqueness) can be created
        # directly -- no existing rows to reconcile, unlike Talent/Attribute below.
        migrations.CreateModel(
            name="Definition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("term", models.CharField(max_length=100)),
                ("slug", models.SlugField(blank=True, max_length=115, unique=True)),
                ("short_description", models.CharField(blank=True, default="", max_length=300)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "index_type",
                    models.CharField(
                        choices=[
                            ("class", "Class"),
                            ("talent", "Talent"),
                            ("kin", "Kin"),
                            ("attribute", "Attribute"),
                            ("mechanic", "Game Mechanic"),
                            ("glossary", "Glossary Term"),
                        ],
                        default="glossary",
                        max_length=15,
                    ),
                ),
                ("target_url", models.CharField(blank=True, default="", max_length=255)),
                (
                    "source_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        help_text="PK of the source row when this Definition is synced from another model. Null for glossary terms.",
                    ),
                ),
            ],
            options={
                "ordering": ["term"],
                "unique_together": {("index_type", "source_id")},
            },
        ),
        # --- Existing tables: temporary nullable/non-unique slugs, finalized in 0006 ---
        migrations.AlterUniqueTogether(
            name="attribute",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="attribute",
            name="slug",
            field=models.SlugField(max_length=55, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="talent",
            name="slug",
            field=models.SlugField(max_length=55, null=True, blank=True),
        ),
    ]
