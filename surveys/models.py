from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.dispatch import receiver

class SurveyType(models.TextChoices):
    POST_EVENT = "post_event", "Post Event"
    NEW_PLAYER = "new_player", "New Player"
    OTHER      = "other", "Other"


class Survey(models.Model):
    # Cross-app relation pointed safely using String boundaries
    event = models.ForeignKey(
        "events.Event",
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
        help_text='If linked to an event, defaults to "{Event Type} Post Event Survey: {Event Title}".'
    )
    description = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    questions = models.ManyToManyField("Question", through="SurveyQuestion", related_name="surveys")

    def save(self, *args, **kwargs):
        if not self.title and self.event:
            self.title = f"{self.event.get_event_type_display()} Survey: {self.event.title}"
        super().save(*args, **kwargs)

    def clean(self):
        if not self.event and not self.title:
            raise ValidationError("Title is required when no Event is linked.")

    def __str__(self):
        return self.title


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
    survey = models.ForeignKey(Survey, on_delete=models.SET_NULL, related_name="survey_questions", null=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="survey_links")
    position = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["survey", "question"], name="uq_survey_question_once")
        ]

    def __str__(self):
        return f"{self.survey}: {self.position} - {self.question}"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    label = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "label"], name="uq_choice_text_per_question")
        ]

    def __str__(self):
        return self.label


class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="survey_submissions"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["survey", "submitted_at"])]

    def __str__(self):
        return f"{self.survey} / {self.user} @ {self.submitted_at:%Y-%m-%d %H:%M}"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    survey_question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, editable=False)
    text_response = models.TextField(null=True, blank=True)
    selected_choices = models.ManyToManyField(Choice, blank=True, related_name="answers")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["response", "survey_question"],
                name="uq_one_answer_per_survey_question_per_submission",
            )
        ]

    def clean(self):
        if self.survey_question and self.question and self.survey_question.question_id != self.question_id:
            raise ValidationError("Answer.question must match SurveyQuestion.question.")
        
        if self.response_id and self.survey_question_id:
            if self.response.survey_id != self.survey_question.survey_id:
                raise ValidationError("Submission.survey and SurveyQuestion.survey must match.")

        qtype = self.survey_question.question.question_type if self.survey_question_id else None

        if qtype == QuestionType.TEXT:
            if self.selected_choices.exists():
                raise ValidationError("Choices are not allowed for a text question.")
            if self.survey_question.is_required and not (self.text_response or "").strip():
                raise ValidationError("This text answer is required.")
        elif qtype in {QuestionType.MC_SINGLE, QuestionType.MC_MULTI, QuestionType.RATING}:
            if (self.text_response or "").strip():
                raise ValidationError("Text is not allowed for a multiple-choice question.")

    def save(self, *args, **kwargs):
        if self.survey_question_id and not self.question_id:
            self.question_id = self.survey_question.question_id
        self.full_clean()
        return super().save(*args, **kwargs)


@receiver(models.signals.m2m_changed, sender=Answer.selected_choices.through)
def validate_selected_choices(sender, instance: Answer, action, reverse, model, pk_set, **kwargs):
    if action not in {"pre_add", "pre_clear"}:
        return
    
    question_type = instance.survey_question.question.question_type

    if question_type == QuestionType.TEXT:
        if action == "pre_add" and pk_set:
            raise ValidationError("Choices are not allowed for a text question.")
        return

    if action == "pre_add" and pk_set:
        invalid = model.objects.filter(pk__in=pk_set).exclude(question=instance.question).exists()
        if invalid:
            raise ValidationError("Selected choice does not belong to this question.")

        if question_type != QuestionType.MC_MULTI:
            already = instance.selected_choices.count()
            incoming = len(pk_set)
            if already + incoming > 1:
                raise ValidationError("Only one option may be selected for this question.")