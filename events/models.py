from django.db import models
from django.templatetags.static import static
from django.utils import timezone
from django.conf import settings
from datetime import datetime, time, timedelta
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.dispatch import receiver

# Create your models here.

# --- Events ---
class EventType(models.TextChoices):
    SENIOR = "senior", "Senior"
    JUNIOR = "junior", "Junior"
    FEAST = "feast", "Feast"
    OTHER = "other", "Other"

# --- Event Time Macros ---
def default_start_time():
    now = timezone.now()
    nine_am = datetime.combine(now.date(), time(hour=9))
    return timezone.make_aware(nine_am)

def default_end_time():
    now = timezone.now()
    four_pm_tomorrow = datetime.combine(now.date() + timedelta(days=1), time(hour=16))
    return timezone.make_aware(four_pm_tomorrow)

def default_downtime_due():
    now = timezone.now()
    two_weeks_later = datetime.combine(now.date() + timedelta(weeks=2, days=1), time(hour=23, minute=59, second=59))
    return timezone.make_aware(two_weeks_later)


# --- Image Upload Path Macros ---
def _upload_path(instance, filename, subdir=""):
    event = getattr(instance, "event", instance)
    slug = getattr(event, "slug", "untitled")

    base = "images/Events/{event_slug}"
    if subdir:
        base = f"{base}/{subdir}"
    return f"{base}/{filename}"

def upload_event_main(instance, filename):
    return _upload_path(instance, filename)

def upload_event_album(instance, filename):
    return _upload_path(instance, filename, "EventAlbum")

class Event(models.Model):
    title = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True, db_index=True)
    event_type = models.CharField(
        max_length = 10,
        choices = EventType.choices,
        default = EventType.OTHER
    )
    base_price_cents = models.IntegerField(
        help_text=(
            "Base price of a ticket for the event before discounts in cents.\n"
            "I.E. 5000 would be equivalent to $50.\n"
            "Serves as a fallback if price tiers are provided that is used if a user does not fall into any age bracket."
            )
    )

    registration_available = models.BooleanField(default=True, help_text="Disables registration buttons if unchecked while allowing information for events to be shared.")

    # No Parenthesis to call these defaults to pass the function, not call it.
    start_time = models.DateTimeField(default=default_start_time)
    end_time = models.DateTimeField(default=default_end_time)
    downtime_due = models.DateTimeField(default=default_downtime_due, help_text="This is the date by which attendees of the event must respond to the post event survey.")

    # Who is registered for the event.
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='EventAttendee',
        related_name="events"
    )

    #TODO: Add a Default Image
    event_image = models.ImageField(upload_to=upload_event_main, blank=True, help_text="The image that appears for this event in registration and event pages. A default image is Hardcoded if none is provided.")
    photographer = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # This forces the slug to be set only the first time the event is saved to ensure URLs don't change.
        if not self.slug:
            self.slug = slugify(self.title) 

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-start_time',]

# --- Overload for Event Pricing based on User's age that overrides base_price_cents ---
class EventPriceTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="price_tiers")
    label = models.CharField(max_length=30)
    min_age = models.PositiveSmallIntegerField(help_text="Lower Age Requirement for this tier.")
    max_age = models.PositiveSmallIntegerField(help_text="Upper Age Requirement for this tier.")
    price_cents = models.PositiveIntegerField(help_text="Base price of a ticket for the provided age range in cents. Overrides the Event's Base Price.")

class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETE = "complete", "Complete"
    REFUNDED = "refunded", "Refunded"

class EventAttendee(models.Model):
    # Event and User Details
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="registrations"
    )

    # Check for arrival at the event
    checked_in = models.BooleanField(default=False)

    # Time the user will arrive at the event.
    arrival_time = models.TimeField()

    base_price_cents = models.PositiveIntegerField(help_text="Base price before discounts, in cents")
    final_price_cents = models.PositiveIntegerField(help_text="Final price charged, in cents")
    discounts = models.JSONField(default=list, blank=True, help_text="Applied discounts snapshot")
    additional_items = models.JSONField(default=list, blank=True, help_text="Additional items charged snapshot")

    # Payment Information
    payment_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )

    def __str__(self):
        return self.user.get_full_name()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", settings.AUTH_USER_MODEL],
                name="unique_registration",
            )
        ]

# --- Pictures/Media for Events ---

class EventMedia(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='pictures')
    image = models.ImageField(upload_to=upload_event_album)
    alt_text = models.CharField(max_length=100)
    
    class Meta:
        verbose_name = "Picture"
        verbose_name_plural = "Pictures"

# --- Surveys ---

class SurveyType(models.TextChoices):
    POST_EVENT = "post_event", "Post Event"
    NEW_PLAYER = "new_player", "New Player"
    OTHER      = "other", "Other"


class Survey(models.Model):
    event = models.ForeignKey(
        "Event",
        on_delete=models.SET_NULL,
        related_name="surveys",
        null=True, blank=True,
    )
    survey_type = models.CharField(
        max_length=20,
        choices=SurveyType.choices,
        default=SurveyType.POST_EVENT,
    )
    title = models.CharField(
        max_length=80,
        help_text='If linked to an event, defaults to \"{Event Type} Post Event Survey: {Event Title}\".'
    )
    description = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # M2M via through for order/flags
    questions = models.ManyToManyField("Question", through="SurveyQuestion", related_name="surveys")

    def save(self, *args, **kwargs):
        if not self.title and self.event:
            self.title = f"{self.event.event_type} Survey: {self.event.title}"
        super().save(*args, **kwargs)

    def clean(self):
        # If no event, require explicit title
        if not self.event and not self.title:
            raise ValidationError("Title is required when no Event is linked.")

    def __str__(self):
        return self.title


# --- Questions ---

class QuestionType(models.TextChoices):
    MC_SINGLE = "mc_single", "Multiple Choice (single)"
    MC_MULTI  = "mc_multi",  "Multiple Choice (multiple)"
    TEXT      = "text",      "Short/Long Text"
    RATING    = "rating",    "Rating (e.g., 1-5)"


class Question(models.Model):
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.TEXT,
    )
    text = models.CharField(max_length=300)

    def __str__(self):
        return self.text


class SurveyQuestion(models.Model):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.SET_NULL,
        related_name="survey_questions",
        null=True
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="survey_links"
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first."
    )
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["survey", "question"], name="uq_survey_question_once")
        ]

    def __str__(self):
        return f"{self.survey}: {self.position} – {self.question}"


class Choice(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices"
    )
    label = models.CharField(max_length=100)
    position = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first."
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "label"], name="uq_choice_text_per_question")
        ]

    def __str__(self):
        return self.label


# --- Survey Responses & Answers ---

class Response(models.Model):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="submissions"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="survey_submissions"
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["survey", "submitted_at"])]

    def __str__(self):
        who = getattr(self.user, "user", None)
        return f"{self.survey} / {(who.get_full_name() if who else 'anon')} @ {self.submitted_at:%Y-%m-%d %H:%M}"


class Answer(models.Model):
    response = models.ForeignKey(
        Response,
        on_delete=models.CASCADE,
        related_name="answers"
    )
    survey_question = models.ForeignKey(
        SurveyQuestion,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    # Convenience denormalization: base question (kept in sync)
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        editable=False
    )

    # TEXT Answers
    text_response = models.TextField(null=True, blank=True)

    selected_choices = models.ManyToManyField(                     
        Choice,
        blank=True,
        related_name="answers"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["response", "survey_question"],
                name="uq_one_answer_per_survey_question_per_submission",
            )
        ]

    def clean(self):
        # Ensure Questions are in sync
        if self.survey_question and self.question and self.survey_question.question_id != self.question_id:
            raise ValidationError("Answer.question must match SurveyQuestion.question.")
        
        # Ensure Surveys are in sync
        if self.submission_id and self.survey_question_id:
            if self.response.survey_id != self.survey_question.survey_id:
                raise ValidationError("Submission.survey and SurveyQuestion.survey must match.")

        qtype = self.survey_question.question.question_type if self.survey_question_id else None

        if qtype == QuestionType.TEXT:
            # TEXT: must not have choices selected
            if self.selected_choices.exists():
                raise ValidationError("Choices are not allowed for a text question.")
            if self.survey_question.is_required and not (self.text_response or "").strip():
                raise ValidationError("This text answer is required.")

        elif qtype == QuestionType.MC_SINGLE | qtype == QuestionType.MC_MULTI | qtype == QuestionType.RATING:
            # MC/RATING: must not have a text response
            if (self.text_response or "").strip():
                raise ValidationError("Text is not allowed for a multiple-choice question.")
            # NOTE: Checks for if multiple options should be allowed are in the receiver below

    def save(self, *args, **kwargs):
        if self.survey_question_id and not self.question_id:
            self.question_id = self.survey_question.question_id
        self.full_clean()
        return super().save(*args, **kwargs)

@receiver(models.signals.m2m_changed, sender=Answer.selected_choices.through)
def validate_selected_choices(sender, instance: Answer, action, reverse, model, pk_set, **kwargs):
    # Only validate before add/clear
    if action not in {"pre_add", "pre_clear"}:
        return
    
    question_type = instance.survey_question.question.question_type

    # TEXT questions may never have choices
    if question_type == QuestionType.TEXT:
        if action in {"pre_add"} and pk_set:
            raise ValidationError("Choices are not allowed for a text question.")
        return

    # Enforce choices belong to the same base question
    if action == "pre_add" and pk_set:
        invalid = model.objects.filter(pk__in=pk_set).exclude(
            question=instance.question
        ).exists()
        if invalid:
            raise ValidationError("Selected choice does not belong to this question.")

        # Enforce single vs multi
        if not question_type == QuestionType.MC_MULTI:
            already = instance.selected_choices.count()
            incoming = len(pk_set)
            if already + incoming > 1:
                raise ValidationError("Only one option may be selected for this question.")