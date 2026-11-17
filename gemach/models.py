"""מודל הנתונים. מזהי הדרישות מתייחסים ל-docs/gemach-suits/spec.md (גרסה 2)."""
import datetime as dt

from django.db import models
from django.utils import timezone

PRICE_PER_JACKET = 30  # BR-1


def today():
    return timezone.localdate()


class Settings(models.Model):
    """הגדרות כלליות — רשומה אחת בלבד."""
    gemach_phone = models.CharField("טלפון הגמ\"ח", max_length=30, default="052-7614312")
    reminder_hour = models.PositiveSmallIntegerField("שעת שליחת תזכורות", default=9)  # REQ-MSG-1
    same_day_turnover = models.BooleanField(
        "ז'קט שמוחזר ביום מסוים יכול לצאת באותו יום", default=False)  # Q-2 (המלצה: לא)
    tpl_confirm = models.TextField("נוסח: אישור הזמנה", default=(
        "שלום {name},\nההזמנה שלכם בגמ\"ח חליפות לשמחות נרשמה.\n\n{lines}\n\n"
        "איסוף: {pickup}\nהחזרה: {return}\nלתשלום: {total} ₪ במזומן באיסוף.\n\n"
        "לשינויים: {phone}\nבשמחות!"))
    tpl_update = models.TextField("נוסח: עדכון הזמנה", default=(
        "שלום {name},\nההזמנה שלכם עודכנה.\n\n{lines}\n\nאיסוף: {pickup}\nהחזרה: {return}\n"
        "לתשלום: {total} ₪.\n\nלשאלות: {phone}"))
    tpl_cancel = models.TextField("נוסח: ביטול", default=(
        "שלום {name},\nההזמנה שלכם לתאריך {event} בוטלה.\nלשאלות: {phone}"))
    tpl_pickup = models.TextField("נוסח: תזכורת איסוף", default=(
        "שלום {name},\nתזכורת: היום ({pickup}) אוספים את הז'קטים לשמחה.\n{lines}\n"
        "לתשלום: {total} ₪ במזומן.\nבשמחות!"))
    tpl_return = models.TextField("נוסח: תזכורת החזרה", default=(
        "שלום {name},\nמזל טוב! תזכורת: היום ({return}) מחזירים את הז'קטים.\nתודה רבה!"))
    tpl_late = models.TextField("נוסח: תזכורת איחור", default=(
        "שלום {name},\nהז'קטים היו אמורים לחזור ב-{return} ועדיין לא הוחזרו.\n"
        "נשמח שתחזירו בהקדם — ילדים אחרים מחכים להם.\nלתיאום: {phone}"))

    class Meta:
        verbose_name = "הגדרות"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class JacketModel(models.Model):
    """דגם — קטיפה שחורה / שמנת. REQ-INV-1, REQ-INV-2."""
    name = models.CharField("שם הדגם", max_length=60, unique=True)
    description = models.CharField("תיאור", max_length=200, blank=True)
    image = models.BinaryField("תמונה", blank=True, null=True, editable=True)
    image_type = models.CharField(max_length=40, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


def tag_key(tag):
    """מיון טבעי של תגיות: A2 לפני A10."""
    import re
    return [(0, int(p)) if p.isdigit() else (1, p) for p in re.findall(r"\d+|\D+", str(tag))]


class Jacket(models.Model):
    """ז'קט פיזי עם מספר תגית. REQ-INV-3..5."""
    tag = models.CharField("מספר תגית", max_length=10, unique=True)  # REQ-INV-4 — אותיות באנגלית ומספרים, למשל A12
    model = models.ForeignKey(JacketModel, on_delete=models.PROTECT, related_name="jackets", verbose_name="דגם")
    size = models.CharField("מידה", max_length=10)
    active = models.BooleanField("פעיל", default=True)
    disabled_note = models.CharField("סיבת השבתה", max_length=200, blank=True)

    class Meta:
        ordering = ["tag"]

    def __str__(self):
        return f"{self.tag} · {self.model} · {self.size}"

    def save(self, *a, **kw):
        self.tag = str(self.tag).strip().upper()
        super().save(*a, **kw)


class Customer(models.Model):
    """לקוח. טלפון אינו ייחודי — בני משפחה יכולים לחלוק טלפון (BR-7, REQ-ORD-7a)."""
    name = models.CharField("שם", max_length=80)
    phone = models.CharField("טלפון", max_length=20, db_index=True)
    email = models.EmailField("מייל", blank=True)
    notes = models.TextField("הערות (רק את רואה)", blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @staticmethod
    def normalize_phone(p):
        return "".join(ch for ch in (p or "") if ch.isdigit())

    def save(self, *a, **kw):
        self.phone = self.normalize_phone(self.phone)
        super().save(*a, **kw)


class Order(models.Model):
    BOOKED, PICKED, RETURNED, CANCELLED = "booked", "picked", "returned", "cancelled"
    STATUS = [(BOOKED, "הוזמנה"), (PICKED, "נאספה"), (RETURNED, "הוחזרה"), (CANCELLED, "בוטלה")]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders", verbose_name="לקוח")
    event_date = models.DateField("תאריך השמחה")
    status = models.CharField(max_length=10, choices=STATUS, default=BOOKED)
    note = models.TextField("הערה", blank=True)
    fitting_note = models.CharField("מדידה (מה סוכם)", max_length=120, blank=True)  # REQ-ORD-8
    paid = models.BooleanField("שולם", default=False)
    late_reminders_stopped = models.BooleanField("עצירת תזכורות איחור", default=False)  # REQ-MSG-4
    created = models.DateTimeField(auto_now_add=True)
    picked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["event_date", "id"]

    def __str__(self):
        return f"הזמנה {self.id} · {self.customer.name} · {self.event_date:%d.%m.%Y}"

    @property
    def pickup_date(self):  # BR-2
        return self.event_date - dt.timedelta(days=1)

    @property
    def return_date(self):
        return self.event_date + dt.timedelta(days=1)

    @property
    def live_lines(self):
        return [l for l in self.lines.all() if not l.removed]

    @property
    def total(self):
        return PRICE_PER_JACKET * len(self.live_lines)

    @property
    def is_late(self):  # REQ-RT-3
        return self.status == self.PICKED and today() > self.return_date and any(
            not l.returned for l in self.live_lines)

    @property
    def has_debt(self):  # REQ-PU-3
        return self.status in (self.PICKED, self.RETURNED) and not self.paid


class OrderLine(models.Model):
    """ז'קט אחד בהזמנה: דגם + מידה; מספר ז'קט משובץ באיסוף (REQ-ORD-3, REQ-PU-1)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    model = models.ForeignKey(JacketModel, on_delete=models.PROTECT, verbose_name="דגם")
    size = models.CharField("מידה", max_length=10)
    child_name = models.CharField("שם הילד", max_length=40, blank=True)
    jacket = models.ForeignKey(Jacket, on_delete=models.PROTECT, null=True, blank=True, related_name="lines")
    returned = models.BooleanField(default=False)
    returned_at = models.DateTimeField(null=True, blank=True)
    damaged = models.BooleanField(default=False)
    removed = models.BooleanField(default=False)  # REQ-CXL-2 — ביטול חלקי

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.model} {self.size}" + (f" ({self.child_name})" if self.child_name else "")


class EmailLog(models.Model):
    """יומן מיילים — REQ-MSG-3. גם מונע שליחה כפולה של תזכורות."""
    KINDS = [("confirm", "אישור"), ("update", "עדכון"), ("cancel", "ביטול"),
             ("pickup", "תזכורת איסוף"), ("return", "תזכורת החזרה"), ("late", "תזכורת איחור")]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="emails")
    kind = models.CharField(max_length=10, choices=KINDS)
    for_date = models.DateField()
    sent_at = models.DateTimeField(auto_now_add=True)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-sent_at"]
