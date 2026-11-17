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
        "שלום {name},\nההזמנה שלכם לשמחה ב{event} בוטלה.\nלשאלות: {phone}"))
    tpl_pickup = models.TextField("נוסח: תזכורת איסוף", default=(
        "שלום {name},\nתזכורת: היום, {pickup}, אוספים את הז'קטים לשמחה.\n{lines}\n"
        "לתשלום: {total} ₪ במזומן.\nבשמחות!"))
    tpl_return = models.TextField("נוסח: תזכורת החזרה", default=(
        "שלום {name},\nמזל טוב! תזכורת: היום, {return}, מחזירים את הז'קטים.\nתודה רבה!"))
    tpl_late = models.TextField("נוסח: תזכורת איחור", default=(
        "שלום {name},\nהז'קטים היו אמורים לחזור ב{return} ועדיין לא הוחזרו.\n"
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
    code = models.CharField("אות הדגם בתגית", max_length=1, blank=True)  # K = קטיפה שחורה, S = שמנת
    description = models.CharField("תיאור", max_length=200, blank=True)
    image = models.BinaryField("תמונה", blank=True, null=True, editable=True)
    image_type = models.CharField(max_length=40, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


def tag_key(tag):
    """מיון תגיות כמו בגיליון: A..Z, אחר כך AA, AB... (תגיות ישנות עם מספרים — בסוף)."""
    t = str(tag)
    return (0 if t.isalpha() else 1, len(t), t)


# ---------- תגית אוטומטית: דגם + מידה + סידורי (KDA) ----------
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ODD_SIZE_LETTERS = "TUVWXYZ"  # מידות אי-זוגיות 1,3,5..13


def size_letter(size):
    """A=2 B=4 C=6 D=8 E=10 F=12 G=14 … ; אי-זוגיות: T=1 U=3 V=5 W=7 X=9 Y=11 Z=13."""
    s = str(size).strip()
    if s.isdigit():
        n = int(s)
        if n % 2 == 0 and 2 <= n <= 36:
            return LETTERS[n // 2 - 1]
        if n % 2 == 1 and n <= 13:
            return ODD_SIZE_LETTERS[n // 2]
    letters = "".join(ch for ch in s.upper() if ch in LETTERS)
    return letters[:1] or "X"


def serial_letters(i):
    """0→A, 25→Z, 26→AA …"""
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = LETTERS[r] + out
    return out


def next_tag(model, size):
    prefix = (model.code or model.name[:1]).upper() + size_letter(size)
    used = set(Jacket.objects.filter(tag__startswith=prefix).values_list("tag", flat=True))
    i = 0
    while prefix + serial_letters(i) in used:
        i += 1
    return prefix + serial_letters(i)


class Jacket(models.Model):
    """ז'קט פיזי עם מספר תגית. REQ-INV-3..5."""
    tag = models.CharField("תגית", max_length=10, unique=True)  # REQ-INV-4 — אותיות באנגלית בלבד, למשל AB
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
