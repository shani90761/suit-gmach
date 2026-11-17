"""לוח עברי — המרה מתאריך לועזי לעברי, בלי ספריות חיצוניות.
האלגוריתם לפי Dershowitz & Reingold, "Calendrical Calculations". שמות החודשים זהים לאלה שהדפדפן מציג."""
import datetime as dt
from functools import lru_cache

EPOCH = -1373427  # R.D. של א׳ תשרי שנה 1
MONTHS = {1: "ניסן", 2: "אייר", 3: "סיוון", 4: "תמוז", 5: "אב", 6: "אלול", 7: "תשרי", 8: "חשוון",
          9: "כסלו", 10: "טבת", 11: "שבט", 12: "אדר", 13: "אדר ב׳"}
DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]  # date.weekday(): 0 = שני


def is_leap(y):
    return (7 * y + 1) % 19 < 7


def last_month(y):
    return 13 if is_leap(y) else 12


def _elapsed(y):
    months = (235 * y - 234) // 19
    parts = 12084 + 13753 * months
    day = months * 29 + parts // 25920
    return day + 1 if (3 * (day + 1)) % 7 < 3 else day


def _correction(y):
    ny0, ny1, ny2 = _elapsed(y - 1), _elapsed(y), _elapsed(y + 1)
    if ny2 - ny1 == 356:
        return 2
    if ny1 - ny0 == 382:
        return 1
    return 0


@lru_cache(maxsize=None)
def new_year(y):
    return EPOCH + _elapsed(y) + _correction(y)


def _days_in_year(y):
    return new_year(y + 1) - new_year(y)


def last_day(m, y):
    if m in (2, 4, 6, 10, 13):
        return 29
    if m == 12 and not is_leap(y):
        return 29
    if m == 8 and _days_in_year(y) % 10 != 5:
        return 29
    if m == 9 and _days_in_year(y) % 10 == 3:
        return 29
    return 30


def to_fixed(y, m, d):
    total = new_year(y) + d - 1
    if m < 7:
        total += sum(last_day(x, y) for x in range(7, last_month(y) + 1))
        total += sum(last_day(x, y) for x in range(1, m))
    else:
        total += sum(last_day(x, y) for x in range(7, m))
    return total


def from_date(date):
    """(שנה, חודש, יום) עבריים לתאריך לועזי."""
    fixed = date.toordinal()
    y = (fixed - EPOCH) * 98496 // 35975850
    while new_year(y + 1) <= fixed:
        y += 1
    m = 7 if fixed < to_fixed(y, 1, 1) else 1
    while fixed > to_fixed(y, m, last_day(m, y)):
        m += 1
    return y, m, fixed - to_fixed(y, m, 1) + 1


def month_name(m, y):
    if m == 12 and is_leap(y):
        return "אדר א׳"
    return MONTHS[m]


_ONES = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
_TENS = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
_HUND = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"]


def gematria(n):
    n %= 1000
    s = _HUND[n // 100]
    r = n % 100
    s += "טו" if r == 15 else "טז" if r == 16 else _TENS[r // 10] + _ONES[r % 10]
    return s[:-1] + "״" + s[-1] if len(s) > 1 else s + "׳"


def weekday(date):
    return "יום " + DAYS[date.weekday()]


def short(date):
    """כ״ו כסלו"""
    y, m, d = from_date(date)
    return f"{gematria(d)} {month_name(m, y)}"


def long(date):
    """כ״ו כסלו תשפ״ז"""
    y, m, d = from_date(date)
    return f"{gematria(d)} {month_name(m, y)} {gematria(y)}"


def full(date):
    """יום שישי, כ״ו כסלו"""
    return f"{weekday(date)}, {short(date)}"


def today_he():
    from django.utils import timezone
    return full(timezone.localdate())


if __name__ == "__main__":  # בדיקה מהירה
    print(long(dt.date(2026, 11, 17)), "|", full(dt.date(2026, 12, 12)))
