from django.contrib import admin

from .models import Event, EventPicture, Survey, Response, Question, Choice, Answer

# Register your models here.

class EventImagesInline(admin.StackedInline):
    model = EventPicture

    def get_extra(self, request, obj=None, **kwargs):
        return 0  # Require Pictures to be added fully manually since it may not always be applicable

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    readonly_fields = ['attendees']
    fieldsets = (
        ("Event Info", {
            "fields": ['title', 'event_type', 'registration_available', 'event_image'],
        }),
        ("Event Date/Time", {
            "fields": ['start_time', 'end_time', 'downtime_due',],
        }),
        ("Attendees", {
            "fields": ['attendees'],
            "classes": ['wide'],
        }),
        ("General Picture Information", {
            "fields": ['photographer'],
        })
    )
    inlines = [EventImagesInline]
    list_filter = ['event_type', 'start_time',]
    search_fields = ['title',]

class QuestionInline(admin.TabularInline):
    model = Question

    def get_extra(self, request, obj=None, **kwargs):
        return 1

class ResponseInline(admin.StackedInline):
    model = Response
    exclude = ['user']  # User is shown in the Header of each row
    readonly_fields = ['submitted_at']

    def get_extra(self, request, obj=None, **kwargs):
        return 0  # This inline is readonly, don't display empty data
    
    def has_add_permission(self, request, obj = ...):
        return False
    
    def has_change_permission(self, request, obj = ...):
        return False

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    inlines = [QuestionInline, ResponseInline]
