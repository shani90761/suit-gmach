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


@register.filter
def hd(d, fmt="short"):
    """תאריך עברי. fmt: short (כ״ו כסלו) / long (+ שנה) / weekday (יום שישי, כ״ו כסלו) / day (כ״ו)."""
    from .. import hebcal
    if not d:
        return ""
    if hasattr(d, "date") and callable(d.date):  # datetime
        from django.utils import timezone
        d = timezone.localtime(d).date() if timezone.is_aware(d) else d.date()
    if fmt == "day":
        return hebcal.gematria(hebcal.from_date(d)[2])
    return {"long": hebcal.long, "weekday": hebcal.full}.get(fmt, hebcal.short)(d)


@register.filter
def weekday_letter(d):
    return "אבגדהוש"[(d.weekday() + 1) % 7] + "׳"
