"""לוגיקה עסקית: זמינות, איסוף, החזרה, מיילים ותזכורות."""
import datetime as dt
import logging
from collections import Counter

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import EmailLog, Jacket, JacketModel, Order, OrderLine, Settings, today

log = logging.getLogger(__name__)
OPEN = (Order.BOOKED, Order.PICKED)


# ---------- זמינות (REQ-AV-1/2, BR-3, BR-5, Q-2) ----------

def _gap():
    """כמה ימים לפחות צריכים להיות בין שתי שמחות על אותו ז'קט.
    ז'קט תפוס בימים [שמחה-1, שמחה+1]. אם אסור לצאת באותו יום שחזר — הפער חייב להיות 3+."""
    return 2 if Settings.get().same_day_turnover else 3


def overlaps(event_a, event_b):
    return abs((event_a - event_b).days) < _gap()


def occupying_lines(event_date, exclude_order=None):
    """שורות שתופסות ז'קט בתאריך השמחה הנתון."""
    qs = (OrderLine.objects.filter(removed=False, returned=False, order__status__in=OPEN)
          .select_related("order", "model", "jacket"))
    if exclude_order is not None and exclude_order.pk:
        qs = qs.exclude(order=exclude_order)
    out = []
    for line in qs:
        o = line.order
        # ז'קט באיחור נחשב בחוץ לכל תאריך עד שיוחזר
        if o.status == Order.PICKED and today() > o.return_date:
            out.append(line)
        elif overlaps(o.event_date, event_date):
            out.append(line)
    return out


def availability(event_date, exclude_order=None):
    """{(model_id, size): פנויים} לכל דגם+מידה שיש במלאי."""
    stock = Counter((j.model_id, j.size) for j in Jacket.objects.filter(active=True))
    used = Counter((l.model_id, l.size) for l in occupying_lines(event_date, exclude_order))
    keys = set(stock) | set(used)
    return {k: stock[k] - used[k] for k in keys}


def availability_table(event_date):
    """שורות לתצוגה: דגם, מידה, פנוי, סה"כ."""
    avail = availability(event_date)
    total = Counter((j.model_id, j.size) for j in Jacket.objects.filter(active=True))
    models = {m.id: m for m in JacketModel.objects.all()}
    rows = []
    for (mid, size), free in avail.items():
        rows.append({"model": models[mid], "size": size, "free": max(free, 0), "short": min(free, 0),
                     "total": total[(mid, size)]})
    rows.sort(key=lambda r: (r["model"].order, r["model"].name, size_key(r["size"])))
    return rows


def size_key(s):
    return (0, int(s)) if str(s).isdigit() else (1, str(s))


def all_sizes():
    return sorted({j.size for j in Jacket.objects.all()}, key=size_key)


def check_lines(event_date, wanted, exclude_order=None):
    """wanted: רשימת (model_id, size). מחזיר רשימת שגיאות בעברית (REQ-ORD-5)."""
    avail = availability(event_date, exclude_order)
    need = Counter(wanted)
    names = {m.id: m.name for m in JacketModel.objects.all()}
    errors = []
    for (mid, size), n in need.items():
        free = avail.get((mid, size), 0)
        if n > free:
            errors.append(f"{names.get(mid, '?')} מידה {size}: מבוקשים {n}, פנויים {max(free, 0)}")
    return errors


def shortages(days_ahead=120):
    """הזמנות עתידיות שאין להן מספיק ז'קטים — בגלל השבתה או איחור (REQ-INV-6, REQ-RT-4)."""
    out = []
    end = today() + dt.timedelta(days=days_ahead)
    for o in (Order.objects.filter(status=Order.BOOKED, event_date__gte=today(), event_date__lte=end)
              .select_related("customer").prefetch_related("lines__model")):
        wanted = [(l.model_id, l.size) for l in o.live_lines]
        errs = check_lines(o.event_date, wanted, exclude_order=o)
        if errs:
            out.append({"order": o, "errors": errs})
    return out


def free_jackets_for(line):
    """ז'קטים שאפשר לשבץ לשורה באיסוף (REQ-PU-1)."""
    taken = {l.jacket_id for l in occupying_lines(line.order.event_date, exclude_order=line.order) if l.jacket_id}
    return list(Jacket.objects.filter(model=line.model, size=line.size, active=True)
                .exclude(id__in=taken).order_by("tag"))


# ---------- איסוף / החזרה / ביטול ----------

@transaction.atomic
def do_pickup(order, assignments, paid):
    """assignments: {line_id: jacket_id}."""
    errors = []
    used = set()
    lines = order.live_lines
    for line in lines:
        jid = assignments.get(line.id)
        if not jid:
            errors.append(f"לא נבחר ז'קט ל{line}")
            continue
        allowed = {j.id for j in free_jackets_for(line)}
        if jid not in allowed or jid in used:
            errors.append(f"הז'קט שנבחר ל{line} לא פנוי")
            continue
        used.add(jid)
        line.jacket_id = jid
    if errors:
        transaction.set_rollback(True)
        return errors
    for line in lines:
        line.save(update_fields=["jacket"])
    order.status = Order.PICKED
    order.paid = paid
    order.picked_at = timezone.now()
    order.save(update_fields=["status", "paid", "picked_at"])
    return []


@transaction.atomic
def do_return(order, line_ids, damaged_ids, damage_note=""):
    """REQ-RT-1/2. ז'קט פגום מושבת מיד."""
    now = timezone.now()
    lines = order.live_lines
    for line in lines:
        if line.id in line_ids and not line.returned:
            line.returned, line.returned_at = True, now
            line.damaged = line.id in damaged_ids
            line.save(update_fields=["returned", "returned_at", "damaged"])
            if line.damaged and line.jacket:
                line.jacket.active = False
                line.jacket.disabled_note = damage_note or f"חזר פגום מהזמנה {order.id}"
                line.jacket.save(update_fields=["active", "disabled_note"])
    if all(l.returned for l in lines):
        order.status = Order.RETURNED
        order.save(update_fields=["status"])


def late_orders():
    return [o for o in Order.objects.filter(status=Order.PICKED).select_related("customer")
            .prefetch_related("lines__jacket", "lines__model") if o.is_late]


# ---------- מיילים (§8) ----------

def _fmt(order, tpl):
    s = Settings.get()
    lines = "\n".join(f"• {l.model.name}, מידה {l.size}" + (f" — {l.child_name}" if l.child_name else "")
                      for l in order.live_lines)
    return tpl.format_map(_Safe(
        name=order.customer.name, lines=lines, total=order.total, phone=s.gemach_phone,
        event=f"{order.event_date:%d.%m.%Y}", pickup=f"{order.pickup_date:%d.%m.%Y}",
        **{"return": f"{order.return_date:%d.%m.%Y}"}))


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


SUBJECTS = {"confirm": "ההזמנה נרשמה", "update": "ההזמנה עודכנה", "cancel": "ההזמנה בוטלה",
            "pickup": "תזכורת: איסוף היום", "return": "תזכורת: החזרה היום", "late": "תזכורת: הז'קטים טרם הוחזרו"}


def send_order_email(order, kind, for_date=None):
    """שולח רק אם ללקוח יש מייל. נרשם ביומן גם אם נכשל (EX-5)."""
    if not order.customer.email:
        return None
    s = Settings.get()
    body = _fmt(order, getattr(s, f"tpl_{kind}"))
    entry = EmailLog(order=order, kind=kind, for_date=for_date or today())
    try:
        send_mail(f"גמ״ח חליפות לשמחות — {SUBJECTS[kind]}", body, None, [order.customer.email])
    except Exception as e:  # noqa: BLE001 — כל כשל נרשם ולא מפיל את הפעולה
        log.exception("email failed")
        entry.ok, entry.error = False, str(e)[:300]
    entry.save()
    return entry


def run_reminders(force=False):
    """נקרא מבחוץ (cron-job.org). שולח כל תזכורת פעם אחת ביום, אחרי השעה שנקבעה."""
    s = Settings.get()
    now = timezone.localtime()
    if not force and now.hour < s.reminder_hour:
        return {"skipped": "before_hour"}
    d = today()
    sent = Counter()

    def once(order, kind):
        if EmailLog.objects.filter(order=order, kind=kind, for_date=d, ok=True).exists():
            return
        if send_order_email(order, kind, d):
            sent[kind] += 1

    for o in Order.objects.filter(status=Order.BOOKED, event_date=d + dt.timedelta(days=1)).select_related("customer"):
        once(o, "pickup")
    for o in Order.objects.filter(status=Order.PICKED, event_date=d - dt.timedelta(days=1)).select_related("customer"):
        once(o, "return")
    for o in late_orders():
        if not o.late_reminders_stopped:
            once(o, "late")
    return dict(sent)
