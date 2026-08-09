from django.contrib import admin, messages
from django.db import transaction as db_transaction

from .models import Answer, Choice, Question, Response, Survey, SurveyAssignment, SurveyQuestion
from .services import sync_surveys_and_notify

# ==========================================
# INLINES
# ==========================================


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    fields = ["position", "label"]
    ordering = ["position"]


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0
    ordering = ["position"]
    fields = ["position", "question", "is_required"]
    autocomplete_fields = ["question"]
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "question":
            w = formfield.widget
            if hasattr(w, "can_add_related"):
                w.can_add_related = False
            if hasattr(w, "can_change_related"):
                w.can_change_related = True
            if hasattr(w, "can_delete_related"):
                w.can_delete_related = False
            if hasattr(w, "can_view_related"):
                w.can_view_related = True
        return formfield


class SurveyAssignmentInline(admin.TabularInline):
    model = SurveyAssignment
    extra = 0
    fields = ["user", "assigned_at"]
    readonly_fields = ["assigned_at"]
    autocomplete_fields = ["user"]


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    can_delete = False
    readonly_fields = ["question_display", "answer_display"]
    fields = ["question_display", "answer_display"]

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("survey_question", "survey_question__question", "response", "response__survey")
            .prefetch_related("selected_choices")
            .order_by("survey_question__position")
        )

    @admin.display(description="Question")
    def question_display(self, obj):
        return obj.survey_question.question.text

    @admin.display(description="Answer")
    def answer_display(self, obj):
        if obj.text_response:
            return obj.text_response
        choices = list(obj.selected_choices.all())
        return ", ".join(choice.label for choice in choices) if choices else "—"


# ==========================================
# ADMIN REGISTRATIONS
# ==========================================


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "question_type"]
    list_filter = ["question_type"]
    search_fields = ["text"]
    inlines = [ChoiceInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("choices")


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    # Added string reference safety checks for linked events
    list_display = ["title", "survey_type", "event", "due_date", "is_active"]
    list_filter = ["survey_type", "is_active", "event"]
    search_fields = ["title", "event__title"]
    readonly_fields = ["created_at"]
    inlines = [SurveyQuestionInline, SurveyAssignmentInline]
    actions = ["sync_assignments", "duplicate_survey"]

    @admin.action(description="Sync assignments from current check-ins")
    def sync_assignments(self, request, queryset):
        # Batched across the whole selection so a user newly eligible for more than one
        # of the selected surveys gets a single combined email, not one per survey.
        total = sync_surveys_and_notify(list(queryset))
        self.message_user(request, f"Created {total} new assignment(s).", level=messages.SUCCESS)

    def _duplicate_one(self, original):
        # Same question list, but detached from any event -- Feedback/Downtime surveys
        # get a fresh copy per event with identical questions, and reselecting them by
        # hand every time is exactly what this is meant to save someone from doing.
        base_title = original.title or original.get_survey_type_display()
        suffix = " (Copy)"
        title = f"{base_title[: 80 - len(suffix)]}{suffix}"

        copy = Survey.objects.create(
            event=None,
            survey_type=original.survey_type,
            title=title,
            description=original.description,
            is_active=original.is_active,
            # due_date is deliberately not copied -- it's stale relative to whatever
            # event this copy eventually gets assigned to. Survey.save() will fill in
            # a placeholder now and it's editable from the change form once assigned.
        )
        SurveyQuestion.objects.bulk_create(
            [
                SurveyQuestion(
                    survey=copy, question_id=link.question_id, position=link.position, is_required=link.is_required
                )
                for link in original.survey_questions.all()
            ]
        )
        # SurveyAssignment/Response/Answer are per-event/per-user and never copied.
        return copy

    @admin.action(description="Duplicate selected survey(s) (same questions, unassigned from any event)")
    def duplicate_survey(self, request, queryset):
        with db_transaction.atomic():
            copies = [self._duplicate_one(survey) for survey in queryset]

        titles = ", ".join(copy.title for copy in copies)
        self.message_user(
            request,
            f"Created {len(copies)} duplicate survey(s): {titles}. Assign each to an event from its edit page.",
            level=messages.SUCCESS,
        )


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["survey", "user", "submitted_at"]
    list_display_links = ["survey", "user"]
    list_filter = ["survey", "survey__survey_type", "submitted_at"]
    date_hierarchy = "submitted_at"

    search_fields = ["user__username", "user__first_name", "user__last_name", "survey__title", "answers__text_response"]

    ordering = ["-submitted_at"]
    list_per_page = 50
    list_select_related = ("survey", "user")
    readonly_fields = ["survey", "user", "submitted_at"]
    empty_value_display = "—"

    def get_inlines(self, request, obj):
        return [AnswerInline] if obj else []

    def has_add_permission(self, request):
        return False

    # Makes the panel completely read-only
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
