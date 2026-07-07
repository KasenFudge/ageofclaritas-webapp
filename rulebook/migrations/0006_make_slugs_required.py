import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rulebook", "0005_backfill_slugs_and_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="talent",
            name="class_for",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="talents",
                to="rulebook.class",
            ),
        ),
        migrations.AlterField(
            model_name="talent",
            name="slug",
            field=models.SlugField(max_length=55, unique=True, blank=True),
        ),
        migrations.AlterField(
            model_name="attribute",
            name="name",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AlterField(
            model_name="attribute",
            name="slug",
            field=models.SlugField(max_length=55, unique=True, blank=True),
        ),
    ]
