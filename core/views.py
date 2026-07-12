from django.views.generic import ListView, TemplateView

from .models import TeamMember, Testimonial


# Create your views here.
class IndexView(TemplateView):
    template_name = "core/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["testimonials"] = Testimonial.objects.filter(is_active=True)
        return context


class TeamMemberView(ListView):
    model = TeamMember
    template_name = "core/our_team.html"
    context_object_name = "team_members"


class WhatIsLarpView(TemplateView):
    template_name = "core/what_is_larp.html"
