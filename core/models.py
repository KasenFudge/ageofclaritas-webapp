from django.db import models


class Testimonial(models.Model):
    name = models.CharField(max_length=50)
    quote = models.TextField()
    role = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Optional context shown under the name, e.g. a character name or 'Attended 3 events'.",
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from the carousel without deleting it.")
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first in the carousel.")

    class Meta:
        ordering = ["order", "-id"]

    def __str__(self):
        return f"{self.name} \u2014 {self.quote[:40]}"
