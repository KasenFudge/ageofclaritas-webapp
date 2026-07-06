from django.views.generic import TemplateView

from .models import Testimonial


# Create your views here.
class IndexView(TemplateView):
    template_name = "core/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Home"
        context["testimonials"] = Testimonial.objects.filter(is_active=True)
        return context
