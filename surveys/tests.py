import re
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Question, QuestionType, Response, Survey, SurveyAssignment, SurveyQuestion

User = get_user_model()


def born_years_ago(years):
    today = timezone.localdate()
    return date(today.year - years, today.month, 1) - timedelta(days=200)


def make_user(username, age=36, **extra):
    extra.setdefault("email", f"{username}@example.test")
    return User.objects.create_user(username=username, password="test-pass", date_of_birth=born_years_ago(age), **extra)


class ParentSurveyLinkTests(TestCase):
    """Survey emails about a child reach the parent with the plain /surveys/<pk>/ link, which
    doesn't name the child. Following it should lead to the child's survey, not a 403."""

    def setUp(self):
        self.survey = Survey.objects.create(title="Feedback", due_date=timezone.now() + timedelta(days=7))
        question = Question.objects.create(text="How was it?", question_type=QuestionType.TEXT)
        self.survey_question = SurveyQuestion.objects.create(survey=self.survey, question=question)
        self.parent = make_user("parent")
        self.client.force_login(self.parent)

    def child(self, username, assigned=True):
        child = make_user(username, age=10, parent_account=self.parent, email=f"{username}@dependent.invalid")
        if assigned:
            SurveyAssignment.objects.create(survey=self.survey, user=child)
        return child

    def respond_url(self, user_id=None):
        if user_id:
            return reverse("surveys:respond_sub", args=[self.survey.pk, user_id])
        return reverse("surveys:respond", args=[self.survey.pk])

    def test_emailed_link_takes_parent_to_their_childs_survey(self):
        kid = self.child("kid")

        # The assignment email went to the parent, with the link that used to 403
        (email,) = mail.outbox
        self.assertEqual(email.to, [self.parent.email])
        link = re.search(r"https?://[^/\s]+(/surveys/\d+/)", email.body).group(1)
        self.assertEqual(link, self.respond_url())

        response = self.client.get(link)
        self.assertRedirects(response, self.respond_url(kid.pk))

        self.client.post(self.respond_url(kid.pk), {f"question_{self.survey_question.pk}": "Great!"})
        self.assertTrue(Response.objects.filter(survey=self.survey, user=kid).exists())

    def test_several_open_children_go_to_dashboard_surveys(self):
        self.child("kid1")
        self.child("kid2")
        response = self.client.get(self.respond_url())
        self.assertRedirects(response, f"{reverse('accounts:dashboard')}?open=surveys", fetch_redirect_response=False)
        self.assertIn("Choose which of your children", str(list(get_messages(response.wsgi_request))[0]))

    def test_skips_children_who_already_submitted(self):
        done = self.child("done")
        Response.objects.create(survey=self.survey, user=done)
        pending = self.child("pending")
        self.assertRedirects(self.client.get(self.respond_url()), self.respond_url(pending.pk))

    def test_everyone_submitted_says_so_instead_of_403(self):
        done = self.child("done")
        Response.objects.create(survey=self.survey, user=done)
        response = self.client.get(self.respond_url())
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        self.assertIn("already been submitted", str(list(get_messages(response.wsgi_request))[0]))

    def test_unrelated_user_still_gets_403(self):
        self.child("kid", assigned=False)
        self.assertEqual(self.client.get(self.respond_url()).status_code, 403)

    def test_assigned_child_logged_in_themselves_is_unaffected(self):
        kid = self.child("kid")
        self.client.force_login(kid)
        self.assertEqual(self.client.get(self.respond_url()).status_code, 200)
