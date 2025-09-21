from django.db import models
from django.templatetags.static import static
from accounts.models import Profile
from django.utils import timezone
from datetime import datetime, time, timedelta
import os

# Create your models here.

# General Event Models:
class EventType(models.TextChoices):
    GENERAL = "general", "General"
    SENIOR = "senior", "Senior"
    JUNIOR = "junior", "Junior"

# Macros for defaulting the start_time, end_time, and downtime_due fields
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

class Event(models.Model):
    title = models.CharField(max_length=50)
    event_type = models.CharField(
        max_length = 10,
        choices = EventType.choices,
        default = EventType.GENERAL
    )

    registration_available = models.BooleanField(default=True, help_text="Disables registration buttons if unchecked while allowing information for events to be shared.")

    # No Parenthesis to call these defaults to pass the function, not call it.
    start_time = models.DateTimeField(default=default_start_time)
    end_time = models.DateTimeField(default=default_end_time)
    downtime_due = models.DateTimeField(default=default_downtime_due, help_text="This is the date by which attendees of the event must send a post event survey.")
    
    #TODO: Add a Default Image
    event_image = models.ImageField(upload_to="images/Events/", blank=True, help_text="The image that appears for this event in registration and event pages. A default image is Hardcoded if none is provided.")
    photographer = models.CharField(max_length=50, null=True, blank=True)
    attendees = models.ManyToManyField(Profile, related_name="events")

    class Meta:
        ordering = ['-start_time',]

# Images and Media for Events
def image_upload_path(instance, filename):
    event_name = instance.event.title.replace(" ", "_")
    return os.path.join(f'images/EventAlbums/{event_name}/', filename)

class EventPicture(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=image_upload_path)
    alt_text = models.CharField(max_length=100)
    
    # class Meta:
    #     verbose_name = "Picture"
    #     verbose_name_plural = "Pictures"

# Surveys for Events
class SurveyType(models.TextChoices):
    POST_EVENT = "post_event", "Post Event"
    NEW_PLAYER = "new_player", "New Player"

class Survey(models.Model):
    event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name='surveys', 
        null=True, blank=True
    )

    survey_type = models.CharField(
        max_length=20,
        choices=SurveyType.choices,
        default=SurveyType.POST_EVENT
    )

    title = models.CharField(max_length=80, help_text="If left blank, will save as \"<Event Type> Post Event Survey: <Event Title>\" by default.")
    description = models.CharField(max_length=500, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.title and self.event:
            self.title = f"{self.event.event_type} Post Event Survey: {self.event.title}"
        super().save(*args, **kwargs)

class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="downtimes")
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.user.get_full_name()}"

class QuestionType(models.TextChoices):
    TEXT = "text", "Text"
    MC = "mc", "Multiple Choice"

class Question(models.Model):
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.TEXT
    )
    
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=100)
    required = models.BooleanField(default=True)

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=30)

class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text_response = models.TextField(null=True, blank=True)  # For text/rating
    choice_response = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)  # For MCQs