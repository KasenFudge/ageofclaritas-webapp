"""
Server-side HTML sanitizer for CKEditor 5 rich-text fields -- single source
of truth called from both the pre_save signal handlers (rulebook/signals.py,
accounts/signals.py, events/signals.py) and the one-time `clean_richtext`
management command, so prevention and cleanup can never drift apart.

Allowlist is scoped to what CKEDITOR_5_CONFIGS["default"]["toolbar"]
(ageofclaritas/settings.py) can actually produce: heading (h1-h4), bold,
italic, underline, bulletedList, numberedList, link, insertTable (+
tableColumn/tableRow/mergeTableCells/tableProperties/tableCellProperties),
undo, redo -- plus:

  - style="..." on table/thead/tbody/tr/td/th only: legitimately settable
    via the tableProperties/tableCellProperties toolbar buttons (border/
    background color, padding, alignment) -- narrowed to a specific CSS
    property allowlist rather than blanket-stripped like other style
    attributes.
  - <blockquote>/<figure>/<figcaption>: compiled-in plugins with no
    toolbar button (BlockQuote) or always emitted by an active one (Table
    wraps every <table> in <figure class="table">; TableCaption emits
    <figcaption>) -- harmless, so allowed through.

Everything else with no toolbar button and no plugin-schema justification
(bare <span style>, font-color/font-family anywhere, arbitrary classes,
script/iframe/etc.) is dropped.
"""

import re

import bleach
from bleach.css_sanitizer import CSSSanitizer
from django.utils.html import strip_tags

ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "ul",
        "ol",
        "li",
        "a",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "table",
        "figure",
        "figcaption",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
    }
)

# Tags where CKEditor's tableProperties/tableCellProperties toolbar buttons
# can legitimately produce a style="..." attribute.
_TABLE_STYLE_TAGS = frozenset({"table", "thead", "tbody", "tr", "td", "th"})

# CSS properties tableProperties/tableCellProperties can actually set --
# nothing else exists on that toolbar (no font controls).
_ALLOWED_TABLE_CSS_PROPERTIES = frozenset(
    {
        "background-color",
        "border-color",
        "border-style",
        "border-width",
        "padding",
        "text-align",
        "vertical-align",
        "width",
        "height",
    }
)


def _allowed_attributes(tag, name, value):
    if tag == "a":
        return name in ("href", "title")
    if tag == "figure":
        return name == "class" and value == "table"
    if tag in _TABLE_STYLE_TAGS:
        return name == "style"
    return False


_cleaner = bleach.sanitizer.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=_allowed_attributes,
    protocols=frozenset({"http", "https", "mailto"}),
    strip=True,
    strip_comments=True,
    css_sanitizer=CSSSanitizer(allowed_css_properties=_ALLOWED_TABLE_CSS_PROPERTIES),
)

# Matches one non-nested <p ...>...</p> pair (HTML doesn't allow nesting a
# <p> inside a <p>, and neither CKEditor nor the cleaner above ever produces
# that, so a non-greedy regex is safe here -- this only ever runs on output
# that already passed through _cleaner, i.e. only the ALLOWED_TAGS/attribute
# set above can appear in it).
_P_TAG_RE = re.compile(r"<p(?:\s[^>]*)?>(.*?)</p>", re.DOTALL)


def _strip_empty_paragraphs(html):
    """Removes <p> tags that are visually blank once tags/entities are
    stripped -- most commonly '<p>&nbsp;</p>' or '<p><br></p>', which Word/
    Google Docs paste routinely inserts as a manual "blank line" between
    sections (e.g. between an ability's intro text and its Rank I/II/III
    breakdown) instead of relying on paragraph spacing. Once main.css gives
    every real <p> consistent margin-block spacing on its own, keeping
    these doubles up the gap -- a manual blank line stacked on top of
    automatic spacing reads as a much bigger, more jarring gap than either
    alone, which is exactly the "artificial large whitespace between
    lines" users see in talent descriptions with several such spacers."""
    return _P_TAG_RE.sub(lambda m: "" if is_html_blank(m.group(1)) else m.group(0), html)


def sanitize_richtext(html):
    """Cleans one CKEditor-authored HTML string. Safe to call on '', None, or
    plain text with no markup (e.g. a bare [[slug]] shortcode -- see
    rulebook/templatetags/rulebook_filters.py; shortcodes are substituted at
    render time, long after this ever runs, so there's nothing here for this
    function to see or mangle)."""
    if not html:
        return html
    return _strip_empty_paragraphs(_cleaner.clean(html))


def is_html_blank(value):
    """True if `value` has no visible content once tags/entities are
    stripped -- e.g. '<p>&nbsp;</p>' or '<p><br></p>', which a rich-text
    widget commonly leaves behind after a user "clears" a field. Mirrors the
    logic Class.has_special_rules already used ad hoc (see rulebook/models.py);
    centralized here so other code (e.g. the droplet reference-data import)
    can reuse the identical rule."""
    if not value:
        return True
    text = strip_tags(value).replace("&nbsp;", " ").replace("\xa0", " ")
    return not text.strip()
