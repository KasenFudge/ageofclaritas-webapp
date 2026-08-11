from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SurveyResponseForm
from .models import Survey


@login_required
def respond_view(request, pk, user_id=None):
    survey = get_object_or_404(Survey, pk=pk, is_active=True)
    actor = request.user

    if user_id and user_id != actor.id:
        target_user = get_object_or_404(actor.child_accounts.all(), id=user_id)
    else:
        target_user = actor

    if not survey.assignments.filter(user=target_user).exists():
        raise PermissionDenied("You have not been assigned this survey.")

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
