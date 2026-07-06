from django.contrib import admin

from .models import Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("name", "quote")
