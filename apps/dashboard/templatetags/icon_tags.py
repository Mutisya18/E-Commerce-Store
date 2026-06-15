import os
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def icon(name, size=20, color='currentColor', css_class='', aria_label=''):
    aria = f'role="img" aria-label="{aria_label}"' if aria_label else 'aria-hidden="true"'
    # If name contains non-ASCII characters, treat it as an emoji
    if not name.isascii():
        cls = f'icon-emoji {css_class}'.strip()
        return mark_safe(
            f'<span class="{cls}" style="font-size:{size}px;line-height:1;" {aria}>{name}</span>'
        )
    # Auto-wrap CSS variable tokens
    if color.startswith('--'):
        color = f'var({color})'
    cls = f'icon {css_class}'.strip()
    return mark_safe(
        f'<svg class="{cls}" width="{size}" height="{size}" fill="{color}" {aria}>'
        f'<use href="#ph-{name}"></use>'
        f'</svg>'
    )


@register.simple_tag
def sprite():
    path = os.path.join(settings.STATICFILES_DIRS[0], 'icons', 'sprite.svg')
    with open(path, 'r') as f:
        return mark_safe(f.read())
