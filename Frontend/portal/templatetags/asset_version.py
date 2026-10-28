from pathlib import Path

from django import template
from django.contrib.staticfiles.finders import find
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path):
    """Static URL plus the file's modification time, so browsers cannot reuse a stale copy."""
    url = static(path)
    found = find(path)
    if not found:
        return url
    version = int(Path(found).stat().st_mtime)
    return f"{url}?v={version}"
