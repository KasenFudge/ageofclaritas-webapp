import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from rulebook.models import Definition

register = template.Library()

# Double brackets rather than single -- "[[fireball]]" is unambiguous, while a
# single-bracket [fireball] pattern risks colliding with ordinary bracketed
# prose an author might type, like "[see the table below]".
SHORTCODE_RE = re.compile(r"\[\[([a-z0-9\-]+)\]\]")


def _popup(term, description):
    return (
        '<span class="relative inline-block group">'
        f'<span class="border-b border-dotted border-indigo-400 cursor-help">{escape(term)}</span>'
        '<span class="pointer-events-none absolute z-20 bottom-full left-1/2 -translate-x-1/2 mb-2 '
        'hidden group-hover:block w-64 p-3 text-sm bg-slate-900 text-white rounded-lg shadow-lg">'
        f"{description}</span></span>"
    )


def _link(term, url):
    return f'<a href="{url}" class="text-indigo-700 underline hover:text-indigo-900">{escape(term)}</a>'


@register.filter(is_safe=True)
def parse_rules(text):
    """
    Replaces [[slug]] shortcodes with either a hover-popup (Glossary
    entries, or anything missing a target_url) or a hyperlink (Class,
    Talent, Kin, Attribute -- using the target_url signals.py already
    precomputed on save).
    """
    if not text:
        return text

    def replace(match):
        slug = match.group(1)
        try:
            definition = Definition.objects.get(slug=slug)
        except Definition.DoesNotExist:
            return match.group(0)  # leave the shortcode visible -- an easy typo to spot

        if definition.uses_hover_display or not definition.target_url:
            # short_description is curated/truncated specifically to be popup-sized;
            # description (esp. for a Mechanic's full RulePage content) is not.
            popup_content = definition.short_description or definition.description
            return _popup(definition.term, popup_content)

        return _link(definition.term, definition.target_url)

    return mark_safe(SHORTCODE_RE.sub(replace, text))
