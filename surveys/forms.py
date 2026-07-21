from django import forms

from events.forms import CHECKBOX_CLASSES, RADIO_CLASSES, TEXT_INPUT_CLASSES

from .models import Answer, QuestionType, Response


class SurveyResponseForm(forms.Form):
    def __init__(self, *args, survey, **kwargs):
        self.survey = survey
        self.survey_questions = list(
            survey.survey_questions.select_related("question").prefetch_related("question__choices")
        )
        super().__init__(*args, **kwargs)

        for survey_question in self.survey_questions:
            question = survey_question.question
            field_name = f"question_{survey_question.id}"
            required = survey_question.is_required

            if question.question_type == QuestionType.TEXT:
                self.fields[field_name] = forms.CharField(
                    label=question.text,
                    required=required,
                    widget=forms.Textarea(attrs={"class": TEXT_INPUT_CLASSES, "rows": 4}),
                )
                continue

            choices = [(choice.id, choice.label) for choice in question.choices.all()]
            if question.question_type == QuestionType.MC_MULTI:
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=question.text,
                    required=required,
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple(attrs={"class": CHECKBOX_CLASSES}),
                )
            else:  # MC_SINGLE or RATING
                self.fields[field_name] = forms.ChoiceField(
                    label=question.text,
                    required=required,
                    choices=choices,
                    widget=forms.RadioSelect(attrs={"class": RADIO_CLASSES}),
                )

    def save(self, *, user):
        response = Response.objects.create(survey=self.survey, user=user)

        for survey_question in self.survey_questions:
            question = survey_question.question
            field_name = f"question_{survey_question.id}"
            value = self.cleaned_data.get(field_name)

            answer = Answer(response=response, survey_question=survey_question, question=question)

            if question.question_type == QuestionType.TEXT:
                answer.text_response = value or ""
                answer.save()
            else:
                answer.save()
                selected_ids = value if question.question_type == QuestionType.MC_MULTI else ([value] if value else [])
                answer.selected_choices.set(selected_ids)

        return response
