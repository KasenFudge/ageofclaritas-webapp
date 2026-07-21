from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SurveyResponseForm
from .models import Survey


@login_required
def respond_view(request, pk):
    survey = get_object_or_404(Survey, pk=pk, is_active=True)
    user = request.user

    if not survey.assignments.filter(user=user).exists():
        raise PermissionDenied("You have not been assigned this survey.")

    if survey.submissions.filter(user=user).exists():
        messages.info(request, "You've already submitted this survey.")
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = SurveyResponseForm(request.POST, survey=survey)
        if form.is_valid():
            form.save(user=user)
            messages.success(request, f'Thanks for completing "{survey.title}"!')
            return redirect("accounts:dashboard")
    else:
        form = SurveyResponseForm(survey=survey)

    return render(request, "surveys/respond.html", {"form": form, "survey": survey})
