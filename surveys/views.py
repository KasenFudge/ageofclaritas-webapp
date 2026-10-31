from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import SurveyResponseForm
from .models import Survey


@login_required
def respond_view(request, pk, user_id=None):
    survey = get_object_or_404(Survey, pk=pk)
    actor = request.user

    if user_id and user_id != actor.id:
        target_user = get_object_or_404(actor.child_accounts.all(), id=user_id)
    else:
        target_user = actor

    if not survey.assignments.filter(user=target_user).exists():
        # Survey emails about a child go to the parent with the child-less link. Rather than a
        # 403, send the parent to the child's copy, or to the dashboard to pick between children.
        if target_user == actor:
            assigned_children = actor.child_accounts.filter(survey_assignments__survey=survey).distinct()
            pending = list(assigned_children.exclude(survey_submissions__survey=survey))
            if len(pending) == 1:
                return redirect("surveys:respond_sub", pk=survey.pk, user_id=pending[0].pk)
            if pending:
                messages.info(request, f'Choose which of your children to fill out "{survey.title}" for.')
                return redirect(f"{reverse('accounts:dashboard')}?open=surveys")
            if assigned_children.exists():
                messages.info(request, f'"{survey.title}" has already been submitted for your household.')
                return redirect("accounts:dashboard")
        raise PermissionDenied("You have not been assigned this survey.")

    if not survey.is_open:
        messages.error(request, "This survey is no longer accepting responses.")
        return redirect("accounts:dashboard")

    if survey.submissions.filter(user=target_user).exists():
        messages.info(request, "You've already submitted this survey.")
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = SurveyResponseForm(request.POST, survey=survey)
        if form.is_valid():
            form.save(user=target_user)
            messages.success(request, f'Thanks for completing "{survey.title}"!')
            return redirect("accounts:dashboard")
    else:
        form = SurveyResponseForm(survey=survey)

    return render(request, "surveys/respond.html", {"form": form, "survey": survey, "target_user": target_user})
