"""
Server-site HTML sanitizer for CKEditor5 and its rich-text fields. Used
throughout the site in different signals.py files for consistent styling.

Allowlist includes what the CKEditor5 config to add toolbar buttons
is setup to support already, and also the following special cases:

  - style="..." is settable only on table tags, as this is allowed through
    the CKEditor5 Toolbar.
  - <blockquote>, <figure>, and <figcaption> are used for compiled-in plugins
    that aren't directly tied to a specific toolbar button.
  - class="spacing-loose" on <p> only: Used by the toolbars styles dropdown
    in lieu of allowing blank lines for consistent style.

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
    if tag == "p":
        return name == "class" and value == "spacing-loose"
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

# Matches one non-nested <p ...>...</p> pair.
_P_TAG_RE = re.compile(r"<p(?:\s[^>]*)?>(.*?)</p>", re.DOTALL)


def _strip_empty_paragraphs(html):
    """
    Removes <p> tags that are visually blank once tags/entities are
    stripped, primarily '<p>&nbsp;</p>' or '<p><br></p>'
    """
    return _P_TAG_RE.sub(lambda m: "" if is_html_blank(m.group(1)) else m.group(0), html)


def sanitize_richtext(html):
    """
    Cleans a CKEditor-authored HTML string.
    """
    if not html:
        return html
    return _strip_empty_paragraphs(_cleaner.clean(html))


def is_html_blank(value):
    """
    True if `value` has no visible content once tags/entities are
    stripped -- e.g. '<p>&nbsp;</p>' or '<p><br></p>'
    """
    if not value:
        return True
    text = strip_tags(value).replace("&nbsp;", " ").replace("\xa0", " ")
    return not text.strip()
