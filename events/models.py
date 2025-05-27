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
    title = models.CharField()
    event_type = models.CharField(
        max_length = 10,
        choices = EventType.choices,
        default = EventType.GENERAL
    )

    start_time = models.DateTimeField(default=default_start_time())
    end_time = models.DateTimeField(default=default_end_time())
    downtime_due = models.DateTimeField(default=default_downtime_due)
    registration_link = models.CharField() #Temporary while I don't have event registration in site.
    background_image = models.ImageField(upload_to="images/Events/", blank=True, null=True)
    photographer = models.CharField()
    attendees = models.ManyToManyField(Profile, related_name="events")
    
    # def image_src(self):
    #     if self.background_image:
    #         return self.background_image.url
    #     return static('images/4guysHouseOctavious.jpg')

# Images and Media for Events
def image_upload_path(instance, filename):
    event_name = instance.event.title.replace(" ", "_")
    return os.path.join(f'images/EventAlbums/{event_name}/', filename)

class Media(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=image_upload_path)
    alt_text = models.CharField()

# Surveys for Events
class SurveyType(models.TextChoices):
    DOWNTIME = "downtime", "Downtime"
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
        default=SurveyType.DOWNTIME
    )

    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.title:
            self.title = f"{self.event.get_event_type_display()} Post Event Survey: {self.event.title}"
        super().save(*args, **kwargs)

class Response(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='responses')
    user = models.ForeignKey(Profile, related_name="downtimes")
    submitted_at = models.DateTimeField(auto_now_add=True)

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
    text = models.CharField()
    required = models.BooleanField(default=True)

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField()

class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text_response = models.TextField(blank=True, null=True)  # For text/rating
    choice_response = models.ForeignKey(Choice, on_delete=models.SET_NULL, blank=True, null=True)  # For MCQs