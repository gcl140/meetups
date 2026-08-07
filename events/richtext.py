"""Server-side sanitization for the rich-text event description field.

The Quill editor (static/js/rich_text.js) only exposes bold/italic/strike/
link/code/list/blockquote formatting, so the allowlist here is scoped to
exactly what that toolbar can produce. The client-side editor is a UX
nicety, not a trust boundary -- anyone can POST arbitrary HTML directly to
the form, so this is the actual defense against stored XSS.
"""

import re

import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 's', 'a', 'code', 'ul', 'ol', 'li', 'blockquote']
ALLOWED_ATTRIBUTES = {'a': ['href']}
ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']

# bleach strips a disallowed tag's markup but keeps its inner text by
# design -- fine for e.g. a stray <div>, but <script>/<style> content is
# never meant to be visible text, so drop those blocks (tag + content)
# entirely before the real allowlist pass below.
_SCRIPT_OR_STYLE_BLOCK = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)


def sanitize_rich_text(html):
    if not html:
        return ''

    html = _SCRIPT_OR_STYLE_BLOCK.sub('', html)
    cleaned = bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=ALLOWED_PROTOCOLS, strip=True,
    )

    # Quill's "empty" state is still markup (e.g. "<p><br></p>"), not an
    # empty string -- treat visually-blank content as genuinely blank so
    # templates can fall back to a "No description yet." message.
    if not bleach.clean(cleaned, tags=[], strip=True).strip():
        return ''

    return cleaned
