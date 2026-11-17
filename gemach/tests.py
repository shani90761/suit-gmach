"""טסטים לדרישות המרכזיות. כל טסט מציין את מזהה הדרישה מ-spec.md."""
import datetime as dt
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from . import services as S
from .models import Customer, EmailLog, Jacket, JacketModel, Order, OrderLine, Settings, today

D = dt.date(2027, 1, 10)


def mk_order(customer, event, lines, model):
    o = Order.objects.create(customer=customer, event_date=event)
    for size in lines:
        OrderLine.objects.create(order=o, model=model, size=size)
    return o


@mock.patch("gemach.services.today", lambda: dt.date(2027, 1, 1))
@mock.patch("gemach.models.today", lambda: dt.date(2027, 1, 1))
class AvailabilityTests(TestCase):
    def setUp(self):
        self.m = JacketModel.objects.get(name="קטיפה שחורה")
        self.j1 = Jacket.objects.create(tag=1, model=self.m, size="8")
        self.j2 = Jacket.objects.create(tag=2, model=self.m, size="8")
        self.c = Customer.objects.create(name="כהן", phone="052-700-0001", email="c@example.com")

    def test_av2_counts_overlapping_window(self):
        """REQ-AV-2 / BR-3: הזמנה בתאריך קרוב תופסת; רחוק — לא."""
        mk_order(self.c, D, ["8"], self.m)
        self.assertEqual(S.availability(D)[(self.m.id, "8")], 1)
        self.assertEqual(S.availability(D + dt.timedelta(days=2))[(self.m.id, "8")], 1)  # חפיפה ביום החזרה/איסוף
        self.assertEqual(S.availability(D + dt.timedelta(days=3))[(self.m.id, "8")], 2)

    def test_q2_same_day_turnover_setting(self):
        """Q-2: כשמותר לצאת באותו יום שחזר — פער של יומיים לא חוסם."""
        s = Settings.get(); s.same_day_turnover = True; s.save()
        mk_order(self.c, D, ["8"], self.m)
        self.assertEqual(S.availability(D + dt.timedelta(days=2))[(self.m.id, "8")], 2)

    def test_inv5_disabled_not_counted(self):
        """REQ-INV-5 / BR-5."""
        self.j2.active = False; self.j2.save()
        self.assertEqual(S.availability(D)[(self.m.id, "8")], 1)

    def test_ord5_block_when_full(self):
        """REQ-ORD-5: אי אפשר להזמין יותר ממה שפנוי."""
        mk_order(self.c, D, ["8", "8"], self.m)
        self.assertTrue(S.check_lines(D, [(self.m.id, "8")]))
        self.assertFalse(S.check_lines(D + dt.timedelta(days=5), [(self.m.id, "8")]))

    def test_cancelled_releases(self):
        """REQ-CXL-1: ביטול משחרר מלאי."""
        o = mk_order(self.c, D, ["8", "8"], self.m)
        o.status = Order.CANCELLED; o.save()
        self.assertEqual(S.availability(D)[(self.m.id, "8")], 2)

    def test_edit_excludes_own_order(self):
        """REQ-ORD-9: עריכת הזמנה לא מתנגשת בעצמה."""
        o = mk_order(self.c, D, ["8", "8"], self.m)
        self.assertFalse(S.check_lines(D, [(self.m.id, "8"), (self.m.id, "8")], exclude_order=o))

    def test_pu1_pickup_assigns_free_jackets(self):
        """REQ-PU-1/2."""
        o = mk_order(self.c, D, ["8", "8"], self.m)
        lines = o.live_lines
        self.assertEqual(S.do_pickup(o, {lines[0].id: self.j1.id, lines[1].id: self.j1.id}, True)[0][:4], "הז'ק")
        o.refresh_from_db(); self.assertEqual(o.status, Order.BOOKED)
        self.assertEqual(S.do_pickup(o, {lines[0].id: self.j1.id, lines[1].id: self.j2.id}, False), [])
        o.refresh_from_db()
        self.assertEqual(o.status, Order.PICKED)
        self.assertTrue(o.has_debt)  # REQ-PU-3

    def test_rt2_damaged_return_disables(self):
        """REQ-RT-1/2."""
        o = mk_order(self.c, D, ["8"], self.m)
        l = o.live_lines[0]
        S.do_pickup(o, {l.id: self.j1.id}, True)
        S.do_return(o, {l.id}, {l.id}, "קרע")
        self.j1.refresh_from_db(); o.refresh_from_db()
        self.assertFalse(self.j1.active)
        self.assertEqual(o.status, Order.RETURNED)


class LateAndReminderTests(TestCase):
    def setUp(self):
        self.m = JacketModel.objects.get(name="שמנת")
        self.j = Jacket.objects.create(tag=5, model=self.m, size="6")
        Jacket.objects.create(tag=6, model=self.m, size="6")
        self.c = Customer.objects.create(name="לוי", phone="0527000002", email="l@example.com")

    def _at(self, day):
        return (mock.patch("gemach.services.today", lambda: day), mock.patch("gemach.models.today", lambda: day))

    def test_rt3_late_and_occupies_future(self):
        """REQ-RT-3 + REQ-RT-4: ז'קט באיחור תופס גם תאריכים עתידיים ויוצר התרעת חוסר."""
        o = mk_order(self.c, D, ["6"], self.m)
        S.do_pickup(o, {o.live_lines[0].id: self.j.id}, True)
        future = mk_order(self.c, D + dt.timedelta(days=10), ["6", "6"], self.m)
        a, b = self._at(D + dt.timedelta(days=3))
        with a, b:
            o.refresh_from_db()
            self.assertTrue(o.is_late)
            self.assertEqual(S.availability(D + dt.timedelta(days=30))[(self.m.id, "6")], 1)
            self.assertEqual([s["order"].id for s in S.shortages()], [future.id])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reminders_once_per_day(self):
        """§8: תזכורת איסוף נשלחת פעם אחת ביום ורק למי שיש מייל."""
        mk_order(self.c, D, ["6"], self.m)
        no_mail = Customer.objects.create(name="בלי מייל", phone="0527000009")
        mk_order(no_mail, D, ["6"], self.m)
        a, b = self._at(D - dt.timedelta(days=1))
        with a, b:
            self.assertEqual(S.run_reminders(force=True), {"pickup": 1})
            self.assertEqual(S.run_reminders(force=True), {})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("לוי", mail.outbox[0].body)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_msg4_stop_late_reminders(self):
        o = mk_order(self.c, D, ["6"], self.m)
        S.do_pickup(o, {o.live_lines[0].id: self.j.id}, True)
        o.late_reminders_stopped = True; o.save()
        a, b = self._at(D + dt.timedelta(days=4))
        with a, b:
            self.assertEqual(S.run_reminders(force=True), {})


class ViewTests(TestCase):
    def setUp(self):
        self.m = JacketModel.objects.get(name="קטיפה שחורה")
        Jacket.objects.create(tag=1, model=self.m, size="8")
        self.u = get_user_model().objects.create_user("admin", "", "pass-12345")

    def test_role1_login_required(self):
        """REQ-ROLE-1/2: בלי כניסה — הפניה למסך כניסה."""
        for url in ("/", "/orders/", "/api/customers/?phone=0527000001", "/inventory/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertTrue(r["Location"].startswith("/login/"))

    def test_cron_requires_token(self):
        self.assertEqual(self.client.get("/cron/reminders/?token=wrong").status_code, 403)

    def test_ord7a_shared_phone_new_customer(self):
        """REQ-ORD-7a/7b: אותו טלפון — לקוח חדש לא דורס את הקיים."""
        self.client.force_login(self.u)
        old = Customer.objects.create(name="משה כהן", phone="0527000001")
        r = self.client.get("/api/customers/?phone=052-7000001")
        self.assertEqual([c["name"] for c in r.json()["customers"]], ["משה כהן"])
        event = (today() + dt.timedelta(days=20)).isoformat()
        r = self.client.post("/orders/new/", {"phone": "0527000001", "name": "רחל כהן", "email": "",
                                              "customer_id": "", "event_date": event, "line_id": [""],
                                              "line_model": [str(self.m.id)], "line_size": ["8"], "line_child": [""]})
        self.assertEqual(r.status_code, 302)
        old.refresh_from_db()
        self.assertEqual(old.name, "משה כהן")
        self.assertEqual(Customer.objects.filter(phone="0527000001").count(), 2)

    def test_ord_existing_customer_not_renamed(self):
        self.client.force_login(self.u)
        old = Customer.objects.create(name="משה כהן", phone="0527000001")
        event = (today() + dt.timedelta(days=20)).isoformat()
        self.client.post("/orders/new/", {"phone": "0527000001", "name": "שם אחר", "customer_id": str(old.id),
                                          "event_date": event, "line_id": [""], "line_model": [str(self.m.id)],
                                          "line_size": ["8"], "line_child": [""]})
        old.refresh_from_db()
        self.assertEqual(old.name, "משה כהן")
        self.assertEqual(old.orders.count(), 1)

    def test_ord5_view_blocks_overbooking(self):
        self.client.force_login(self.u)
        event = (today() + dt.timedelta(days=20)).isoformat()
        r = self.client.post("/orders/new/", {"phone": "0527000001", "name": "א", "customer_id": "",
                                              "event_date": event, "line_id": ["", ""],
                                              "line_model": [str(self.m.id)] * 2, "line_size": ["8", "8"],
                                              "line_child": ["", ""]})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "פנויים 1")
        self.assertEqual(Order.objects.count(), 0)

    def test_all_pages_render(self):
        self.client.force_login(self.u)
        for url in ("/", "/availability/?date=2030-01-01", "/board/", "/orders/", "/orders/new/",
                    "/inventory/", "/customers/", "/settings/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
