from django import template

register = template.Library()


@register.filter
def swatch(model_name):
    """צבע הנקודה של הדגם."""
    n = str(model_name)
    if "שחור" in n:
        return "#1b1b1b"
    if "שמנת" in n:
        return "#EFE6D2"
    return "#c9c4b8"


@register.filter
def phone(p):
    p = str(p or "")
    return f"{p[:3]}-{p[3:6]}-{p[6:]}" if len(p) == 10 and p.isdigit() else p
