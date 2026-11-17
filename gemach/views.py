import datetime as dt
import re

from django.conf import settings as conf
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services as S
from .models import Customer, EmailLog, Jacket, JacketModel, Order, OrderLine, Settings, today


def parse_date(s):
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ---------- מסך ראשי (§9) ----------

def dashboard(request):
    d = today()
    tmr = d + dt.timedelta(days=1)
    base = Order.objects.select_related("customer").prefetch_related("lines__model", "lines__jacket")

    def day_items(day):
        items = []
        for o in base.filter(status=Order.BOOKED, event_date=day + dt.timedelta(days=1)):
            items.append({"kind": "out", "o": o, "options": [(l, S.free_jackets_for(l)) for l in o.live_lines]})
        for o in base.filter(status=Order.PICKED, event_date=day - dt.timedelta(days=1)):
            items.append({"kind": "in", "o": o})
        return items

    late = S.late_orders()
    debts = list(base.filter(status__in=[Order.PICKED, Order.RETURNED], paid=False))
    today_items, tomorrow_items = day_items(d), day_items(tmr)
    return render(request, "gemach/dashboard.html", {
        "late": late, "disabled": Jacket.objects.filter(active=False).select_related("model"),
        "shortages": S.shortages(), "today_items": today_items, "tomorrow_items": tomorrow_items,
        "debts": debts, "debt_total": sum(o.total for o in debts), "today": d,
        "k_out": sum(1 for i in today_items if i["kind"] == "out"),
        "k_in": sum(1 for i in today_items if i["kind"] == "in"),
        "k_late": sum(len([l for l in o.live_lines if not l.returned]) for o in late),
    })


def _back(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return fallback


def customer_search(request):
    """חיפוש הלקוח בסרגל העליון."""
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"customers": []})
    digits = Customer.normalize_phone(q)
    cond = Q(name__icontains=q)
    if len(digits) >= 3:
        cond |= Q(phone__contains=digits)
    out = []
    for c in Customer.objects.filter(cond).prefetch_related("orders")[:8]:
        orders = list(c.orders.all())
        nxt = min((o.event_date for o in orders if o.status == Order.BOOKED and o.event_date >= today()), default=None)
        from . import hebcal
        out.append({"id": c.id, "name": c.name, "phone": c.phone, "orders": len(orders),
                    "next": hebcal.short(nxt) if nxt else "", "late": any(o.is_late for o in orders)})
    return JsonResponse({"customers": out})


def calendar_view(request):
    return render(request, "gemach/calendar.html", {"start": request.GET.get("d", "")})


def calendar_api(request):
    """אירועי היומן בטווח תאריכים: איסוף, שמחה, החזרה."""
    a, b = parse_date(request.GET.get("from")), parse_date(request.GET.get("to"))
    if not a or not b or (b - a).days > 120:
        return JsonResponse({"error": "range"}, status=400)
    qs = (Order.objects.exclude(status=Order.CANCELLED)
          .filter(event_date__gte=a - dt.timedelta(days=1), event_date__lte=b + dt.timedelta(days=1))
          .select_related("customer").prefetch_related("lines__model", "lines__jacket"))
    out = []
    for o in qs:
        lines = o.live_lines
        jackets = ", ".join(f"{l.model.name} {l.size}" + (f" #{l.jacket.tag}" if l.jacket else "") for l in lines)
        base = {"order": o.id, "name": o.customer.name, "n": len(lines), "jackets": jackets}
        late = o.is_late
        for kind, day, done in (("out", o.pickup_date, o.status in (Order.PICKED, Order.RETURNED)),
                                ("event", o.event_date, False),
                                ("in", o.return_date, o.status == Order.RETURNED)):
            if a <= day <= b:
                out.append({**base, "kind": kind, "date": day.isoformat(), "done": done,
                            "late": late and kind == "in"})
    return JsonResponse({"events": out, "today": today().isoformat()})


def availability_api(request):
    """זמינות לתאריך — לחלון ההזמנה החדשה."""
    d = parse_date(request.GET.get("date"))
    if not d:
        return JsonResponse({"error": "date"}, status=400)
    models = []
    rows = S.availability_table(d)
    for m in JacketModel.objects.all():
        sizes = [{"size": r["size"], "free": r["free"]} for r in rows if r["model"].id == m.id]
        if sizes:
            models.append({"id": m.id, "name": m.name, "sizes": sizes})
    return JsonResponse({"date": d.isoformat(), "pickup": (d - dt.timedelta(days=1)).isoformat(),
                         "return": (d + dt.timedelta(days=1)).isoformat(), "models": models})


def availability(request):
    d = parse_date(request.GET.get("date"))
    rows = S.availability_table(d) if d else []
    return render(request, "gemach/availability.html", {
        "date": d, "rows": rows,
        "pickup": d - dt.timedelta(days=1) if d else None, "ret": d + dt.timedelta(days=1) if d else None})


def availability_board(request):
    """REQ-AV-4: לוח 14 ימים קדימה."""
    start = parse_date(request.GET.get("from")) or today()
    days = [start + dt.timedelta(days=i) for i in range(14)]
    per_day = [S.availability(day) for day in days]
    models = {m.id: m for m in JacketModel.objects.all()}
    keys = sorted({k for a in per_day for k in a},
                  key=lambda k: (models[k[0]].order, models[k[0]].name, S.size_key(k[1])))
    rows = [{"model": models[k[0]], "size": k[1], "cells": [max(a.get(k, 0), 0) for a in per_day]} for k in keys]
    return render(request, "gemach/board.html", {"days": days, "rows": rows, "start": start,
                                                 "prev": start - dt.timedelta(days=14),
                                                 "next": start + dt.timedelta(days=14)})


# ---------- הזמנות (§5) ----------

def order_list(request):
    q = request.GET.get("q", "").strip()
    show = request.GET.get("show", "open")
    qs = Order.objects.select_related("customer").prefetch_related("lines")
    if show == "open":
        qs = qs.filter(status__in=S.OPEN)
    if q:
        digits = Customer.normalize_phone(q)
        cond = Q(customer__name__icontains=q)
        if digits:
            cond |= Q(customer__phone__contains=digits)
        qs = qs.filter(cond)
    qs = qs.order_by("-event_date" if show == "all" else "event_date")[:300]
    return render(request, "gemach/orders.html", {"orders": qs, "q": q, "show": show})


def customer_lookup(request):
    """REQ-ORD-7/7a/7b: מחזיר את כל הלקוחות עם הטלפון — המסך רק מציע."""
    phone = Customer.normalize_phone(request.GET.get("phone"))
    if len(phone) < 9:
        return JsonResponse({"customers": []})
    out = []
    for c in Customer.objects.filter(phone=phone).prefetch_related("orders"):
        last = c.orders.order_by("-event_date").first()
        from . import hebcal
        out.append({"id": c.id, "name": c.name, "email": c.email, "notes": c.notes,
                    "orders": c.orders.count(),
                    "last": hebcal.short(last.event_date) if last else ""})
    return JsonResponse({"customers": out})


def _lines_from_post(post):
    ids, models_, sizes, kids = (post.getlist(k) for k in ("line_id", "line_model", "line_size", "line_child"))
    lines = []
    for i in range(len(models_)):
        if not models_[i] or not sizes[i]:
            continue
        lines.append({"id": int(ids[i]) if i < len(ids) and ids[i] else None, "model_id": int(models_[i]),
                      "size": sizes[i].strip(), "child": (kids[i] if i < len(kids) else "").strip()})
    return lines


def order_form(request, pk=None):
    order = get_object_or_404(Order, pk=pk) if pk else None
    if order and order.status not in (Order.BOOKED,):
        messages.error(request, "אפשר לערוך רק הזמנה שעוד לא נאספה.")
        return redirect("order_detail", pk=order.pk)
    errors = []
    data = {}
    if request.method == "POST":
        p = request.POST
        data = p
        event = parse_date(p.get("event_date"))
        lines = _lines_from_post(p)
        phone = Customer.normalize_phone(p.get("phone"))
        name = p.get("name", "").strip()
        if not event:
            errors.append("חסר תאריך שמחה.")
        elif event < today() and not order:
            errors.append("תאריך השמחה כבר עבר.")
        if not lines:
            errors.append("צריך לפחות ז'קט אחד.")
        if len(phone) < 9:
            errors.append("מספר טלפון לא תקין.")
        if not p.get("customer_id") and not name:
            errors.append("חסר שם לקוח.")
        if not errors:
            errors = S.check_lines(event, [(l["model_id"], l["size"]) for l in lines], exclude_order=order)
        if not errors:
            with transaction.atomic():
                cid = p.get("customer_id")
                email = p.get("email", "").strip()
                if cid:
                    cust = get_object_or_404(Customer, pk=cid, phone=phone)
                    if email and not cust.email:  # לא דורסים — רק משלימים מייל חסר
                        cust.email = email
                        cust.save(update_fields=["email"])
                else:
                    cust = Customer.objects.create(name=name, phone=phone, email=email)
                is_new = order is None
                if is_new:
                    order = Order(customer=cust)
                order.customer = cust
                order.event_date = event
                order.note = p.get("note", "")
                order.fitting_note = p.get("fitting_note", "")
                order.save()
                keep = set()
                existing = {l.id: l for l in order.lines.filter(removed=False)}
                for l in lines:
                    obj = existing.get(l["id"]) or OrderLine(order=order)
                    obj.model_id, obj.size, obj.child_name = l["model_id"], l["size"], l["child"]
                    obj.save()
                    keep.add(obj.id)
                for lid, obj in existing.items():
                    if lid not in keep:
                        obj.delete()
            if p.get("no_email") != "1":
                S.send_order_email(order, "confirm" if is_new else "update")
            messages.success(request, "ההזמנה נשמרה." if is_new else "ההזמנה עודכנה.")
            return redirect("order_detail", pk=order.pk)
    init_lines = ([{"id": l.id, "model_id": l.model_id, "size": l.size, "child": l.child_name}
                   for l in order.live_lines] if order else [])
    if request.method == "POST":
        init_lines = _lines_from_post(request.POST)
    src = request.POST if request.method == "POST" else {}
    cust = order.customer if order else None
    form = {
        "phone": src.get("phone", cust.phone if cust else ""),
        "name": src.get("name", cust.name if cust else ""),
        "email": src.get("email", cust.email if cust else ""),
        "customer_id": src.get("customer_id", cust.id if cust else ""),
        "event_date": src.get("event_date", order.event_date.isoformat() if order else request.GET.get("date", "")),
        "fitting_note": src.get("fitting_note", order.fitting_note if order else ""),
        "note": src.get("note", order.note if order else ""),
    }
    ctx = {
        "order": order, "errors": errors, "f": form,
        "models": JacketModel.objects.all(), "sizes": S.all_sizes(),
        "init_lines": init_lines or [{"id": None, "model_id": None, "size": "", "child": ""}],
        "prefill_date": request.GET.get("date", ""),
        "prefill_model": request.GET.get("model", ""), "prefill_size": request.GET.get("size", ""),
    }
    return render(request, "gemach/order_form.html", ctx)


def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer"), pk=pk)
    lines = order.live_lines
    pickup_options = []
    if order.status == Order.BOOKED:
        pickup_options = [(l, S.free_jackets_for(l)) for l in lines]
    return render(request, "gemach/order_detail.html", {
        "order": order, "lines": lines, "pickup_options": pickup_options,
        "emails": order.emails.all()[:30],
        "can_pickup_today": order.pickup_date <= today(),
    })


@require_POST
def order_pickup(request, pk):
    order = get_object_or_404(Order, pk=pk, status=Order.BOOKED)
    assign = {}
    for l in order.live_lines:
        v = request.POST.get(f"jacket_{l.id}")
        if v:
            assign[l.id] = int(v)
    errors = S.do_pickup(order, assign, paid=request.POST.get("paid") == "1")
    if errors:
        for e in errors:
            messages.error(request, e)
    else:
        messages.success(request, f"{order.customer.name}: סומן כנאסף." + ("" if order.paid else " ההזמנה מסומנת ״חוב״."))
    return _back(request, redirect("order_detail", pk=pk))


@require_POST
def order_return(request, pk):
    order = get_object_or_404(Order, pk=pk, status=Order.PICKED)
    ids = {int(x) for x in request.POST.getlist("returned")}
    damaged = {int(x) for x in request.POST.getlist("damaged")}
    if not ids:
        messages.error(request, "לא סומן אף ז'קט.")
    else:
        S.do_return(order, ids, damaged, request.POST.get("damage_note", "").strip())
        messages.success(request, f"{order.customer.name}: ההחזרה נרשמה." + (" ז'קט פגום הושבת." if damaged & ids else ""))
    return _back(request, redirect("order_detail", pk=pk))


@require_POST
def order_action(request, pk):
    order = get_object_or_404(Order, pk=pk)
    a = request.POST.get("action")
    if a == "cancel" and order.status == Order.BOOKED:  # REQ-CXL-1
        order.status = Order.CANCELLED
        order.save(update_fields=["status"])
        if request.POST.get("no_email") != "1":
            S.send_order_email(order, "cancel")
        messages.success(request, "ההזמנה בוטלה והז'קטים התפנו.")
    elif a == "remove_line" and order.status == Order.BOOKED:  # REQ-CXL-2
        line = get_object_or_404(OrderLine, pk=request.POST.get("line"), order=order)
        if len(order.live_lines) <= 1:
            messages.error(request, "זו השורה האחרונה — אפשר לבטל את כל ההזמנה.")
        else:
            line.removed = True
            line.save(update_fields=["removed"])
            if request.POST.get("no_email") != "1":
                S.send_order_email(order, "update")
            messages.success(request, "השורה הוסרה.")
    elif a == "paid":
        order.paid = True
        order.save(update_fields=["paid"])
        messages.success(request, "סומן ששולם.")
        return _back(request, redirect("order_detail", pk=pk))
    elif a == "stop_late":
        order.late_reminders_stopped = not order.late_reminders_stopped
        order.save(update_fields=["late_reminders_stopped"])
        messages.success(request, "תזכורות האיחור " + ("נעצרו." if order.late_reminders_stopped else "חודשו."))
    elif a == "resend":
        kind = request.POST.get("kind", "confirm")
        e = S.send_order_email(order, kind)
        messages.success(request, "המייל נשלח." if e and e.ok else "המייל לא נשלח — בדקי את הכתובת.")
    return redirect("order_detail", pk=pk)


# ---------- מלאי (§3) ----------

def inventory(request):
    if request.method == "POST":
        a = request.POST.get("action")
        if a == "add_jacket":
            from .models import next_tag
            mdl = JacketModel.objects.filter(pk=request.POST.get("model")).first()
            size = request.POST.get("size", "").strip()
            tag = request.POST.get("tag", "").strip().upper()
            try:
                count = max(1, min(30, int(request.POST.get("count") or 1)))
            except ValueError:
                count = 1
            if not mdl or not size:
                messages.error(request, "צריך לבחור דגם ומידה.")
            elif tag and not re.fullmatch(r"[A-Z]{1,10}", tag):
                messages.error(request, "תגית: אותיות באנגלית בלבד, למשל KDA.")
            elif tag and Jacket.objects.filter(tag=tag).exists():
                messages.error(request, f"התגית {tag} כבר קיימת.")  # REQ-INV-4
            else:
                made = []
                for i in range(count):
                    t = tag if (tag and i == 0) else next_tag(mdl, size)
                    Jacket.objects.create(tag=t, model=mdl, size=size)
                    made.append(t)
                messages.success(request, ("נוסף ז'קט " if len(made) == 1 else f"נוספו {len(made)} ז'קטים: ") + ", ".join(made))
        elif a == "retag":
            j = get_object_or_404(Jacket, pk=request.POST.get("jacket"))
            t = request.POST.get("tag", "").strip().upper()
            if not re.fullmatch(r"[A-Z]{1,10}", t):
                messages.error(request, "תגית: אותיות באנגלית בלבד.")
            elif Jacket.objects.filter(tag=t).exclude(pk=j.pk).exists():
                messages.error(request, f"התגית {t} כבר קיימת.")
            else:
                old, j.tag = j.tag, t
                j.save(update_fields=["tag"])
                messages.success(request, f"התגית שונתה: {old} ← {t}")
        elif a == "retag_old":
            from .models import next_tag
            changed = []
            for j in Jacket.objects.select_related("model"):
                if not re.fullmatch(r"[A-Z]{1,10}", j.tag):
                    old = j.tag
                    j.tag = next_tag(j.model, j.size)
                    j.save(update_fields=["tag"])
                    changed.append(f"{old}←{j.tag}")
            messages.success(request, "תגיות חדשות: " + ", ".join(changed) if changed else "אין ז'קטים עם תגית ישנה.")
        elif a in ("disable", "enable", "delete"):
            j = get_object_or_404(Jacket, pk=request.POST.get("jacket"))
            if a == "disable":
                j.active, j.disabled_note = False, request.POST.get("note", "").strip()
                j.save()
                messages.success(request, f"ז'קט {j.tag} הושבת.")
            elif a == "enable":
                j.active, j.disabled_note = True, ""
                j.save()
                messages.success(request, f"ז'קט {j.tag} חזר לפעיל.")
            else:
                if j.lines.exists():
                    messages.error(request, "אי אפשר למחוק ז'קט שהיה בהזמנות. אפשר להשבית אותו.")
                else:
                    j.delete()
                    messages.success(request, "הז'קט נמחק.")
            return _back(request, redirect("inventory"))
        elif a == "save_model":
            mid = request.POST.get("model_id")
            m = get_object_or_404(JacketModel, pk=mid) if mid else JacketModel()
            m.name = request.POST.get("name", "").strip() or m.name
            m.description = request.POST.get("description", m.description).strip()
            code = request.POST.get("code", "").strip().upper()[:1]
            if code:
                if not code.isalpha() or not code.isascii():
                    messages.error(request, "אות הדגם: אות אחת באנגלית.")
                    return redirect("inventory")
                if JacketModel.objects.filter(code=code).exclude(pk=m.pk).exists():
                    messages.error(request, f"האות {code} כבר שייכת לדגם אחר.")
                    return redirect("inventory")
                m.code = code
            f = request.FILES.get("image")
            if f:
                if f.size > conf.MAX_IMAGE_BYTES or not (f.content_type or "").startswith("image/"):
                    messages.error(request, "התמונה גדולה מדי (עד 1.5MB) או שאינה תמונה.")
                    return redirect("inventory")
                m.image, m.image_type = f.read(), f.content_type
            if m.name:
                m.save()
                messages.success(request, f"הדגם {m.name} נשמר.")
        return redirect("inventory")
    from .models import size_letter, tag_key
    jackets = sorted(Jacket.objects.select_related("model"), key=lambda j: tag_key(j.tag))
    sizes = S.all_sizes()
    table_sizes = sorted(set(sizes) | {str(n) for n in range(2, 15, 2)}, key=S.size_key)
    return render(request, "gemach/inventory.html", {
        "models": JacketModel.objects.all(), "jackets": jackets, "sizes": sizes,
        "size_table": [(sz, size_letter(sz)) for sz in table_sizes],
        "old_tags": sum(1 for j in jackets if not re.fullmatch(r"[A-Z]{1,10}", j.tag)),
        "tags_json": [j.tag for j in jackets],
        "codes_json": {m.id: (m.code or m.name[:1]).upper() for m in JacketModel.objects.all()},
    })


def model_image(request, pk):
    m = get_object_or_404(JacketModel, pk=pk)
    if not m.image:
        return HttpResponse(status=404)
    r = HttpResponse(bytes(m.image), content_type=m.image_type or "image/jpeg")
    r["Cache-Control"] = "private, max-age=3600"
    return r


# ---------- לקוחות ----------

def customers(request):
    q = request.GET.get("q", "").strip()
    qs = Customer.objects.all()
    if q:
        d = Customer.normalize_phone(q)
        qs = qs.filter(Q(name__icontains=q) | (Q(phone__contains=d) if d else Q(pk__in=[])))
    return render(request, "gemach/customers.html", {"customers": qs[:300], "q": q})


def customer_detail(request, pk):
    c = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        a = request.POST.get("action")
        if a == "save":
            c.name = request.POST.get("name", c.name).strip() or c.name
            c.phone = request.POST.get("phone", c.phone)
            c.email = request.POST.get("email", "").strip()
            c.notes = request.POST.get("notes", "")
            c.save()
            messages.success(request, "הפרטים נשמרו.")
        elif a == "delete":
            if c.orders.filter(status__in=S.OPEN).exists():
                messages.error(request, "ללקוח יש הזמנה פתוחה — אי אפשר למחוק.")
            else:
                c.orders.all().delete()
                c.delete()
                messages.success(request, "הלקוח וההיסטוריה שלו נמחקו.")
                return redirect("customers")
        return redirect("customer_detail", pk=pk)
    return render(request, "gemach/customer_detail.html", {"c": c, "orders": c.orders.order_by("-event_date")})


# ---------- הגדרות ----------

def settings_view(request):
    s = Settings.get()
    if request.method == "POST":
        s.gemach_phone = request.POST.get("gemach_phone", s.gemach_phone).strip()
        try:
            s.reminder_hour = max(0, min(23, int(request.POST.get("reminder_hour", s.reminder_hour))))
        except ValueError:
            pass
        s.same_day_turnover = request.POST.get("same_day_turnover") == "1"
        for k in ("confirm", "update", "cancel", "pickup", "return", "late"):
            v = request.POST.get(f"tpl_{k}")
            if v is not None and v.strip():
                setattr(s, f"tpl_{k}", v)
        s.save()
        messages.success(request, "ההגדרות נשמרו.")
        return redirect("settings")
    tpls = [("confirm", "אישור הזמנה"), ("update", "עדכון הזמנה"), ("cancel", "ביטול"),
            ("pickup", "תזכורת איסוף"), ("return", "תזכורת החזרה"), ("late", "תזכורת איחור")]
    return render(request, "gemach/settings.html", {
        "s": s, "tpls": [(k, label, getattr(s, f"tpl_{k}")) for k, label in tpls], "hours": range(6, 23)})


# ---------- תזכורות (נקרא מבחוץ) ----------

@csrf_exempt
def cron(request):
    token = request.GET.get("token") or request.headers.get("X-Cron-Token", "")
    if not conf.CRON_TOKEN or not constant_time_compare(token, conf.CRON_TOKEN):
        return HttpResponseForbidden("bad token")
    return JsonResponse({"ok": True, "sent": S.run_reminders()})


def first_setup(request):
    """בהתקנה חדשה (אין אף משתמש) — יצירת משתמש המנהלת. אחרי שיש משתמש, הדף סגור."""
    from django.contrib.auth import get_user_model, login
    User = get_user_model()
    if User.objects.exists():
        return redirect("login")
    error = ""
    if request.method == "POST":
        u = request.POST.get("username", "").strip()
        p1, p2 = request.POST.get("password", ""), request.POST.get("password2", "")
        if not u or len(p1) < 8:
            error = "צריך שם משתמש וסיסמה של 8 תווים לפחות."
        elif p1 != p2:
            error = "הסיסמאות לא זהות."
        else:
            user = User.objects.create_superuser(u, "", p1)
            login(request, user)
            return redirect("dashboard")
    return render(request, "gemach/setup.html", {"error": error})


def healthz(request):
    return HttpResponse("ok")
