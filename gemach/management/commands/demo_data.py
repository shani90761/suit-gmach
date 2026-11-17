"""נתוני דמו לבדיקה מקומית בלבד. לא להריץ באוויר."""
import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from gemach import services as S
from gemach.models import Customer, Jacket, JacketModel, Order, OrderLine, today


class Command(BaseCommand):
    def handle(self, *a, **kw):
        U = get_user_model()
        if not U.objects.filter(username="demo").exists():
            U.objects.create_superuser("demo", "", "demo-12345")
        black, cream = JacketModel.objects.get(name="קטיפה שחורה"), JacketModel.objects.get(name="שמנת")
        import string
        letters = iter(list(string.ascii_uppercase) + [a + b for a in "AB" for b in string.ascii_uppercase])
        for m, sizes in ((black, {"2": 2, "4": 2, "6": 3, "8": 3, "10": 2, "12": 2}),
                         (cream, {"2": 1, "4": 2, "6": 2, "8": 2, "10": 1})):
            for size, n in sizes.items():
                for _ in range(n):
                    Jacket.objects.get_or_create(tag=next(letters), defaults={"model": m, "size": size})
        d = today()
        def order(name, phone, email, event, lines, status="booked"):
            c = Customer.objects.create(name=name, phone=phone, email=email)
            o = Order.objects.create(customer=c, event_date=event)
            for m, s, kid in lines:
                OrderLine.objects.create(order=o, model=m, size=s, child_name=kid)
            if status in ("picked", "returned"):
                S.do_pickup(o, {l.id: S.free_jackets_for(l)[0].id for l in o.live_lines}, paid=status == "returned")
            return o
        order("משפחת כהן", "0527000001", "cohen@example.com", d + dt.timedelta(days=1), [(black, "8", "יוסי"), (black, "6", "משה")])
        order("משפחת לוי", "0527000002", "", d + dt.timedelta(days=2), [(cream, "4", "")])
        late = order("משפחת פרידמן", "0527000003", "fr@example.com", d - dt.timedelta(days=4), [(black, "10", "שמואל")], status="picked")
        order("משפחת גולדברג", "0527000004", "", d - dt.timedelta(days=1), [(cream, "6", ""), (cream, "8", "")], status="picked")
        order("משפחת כהן", "0527000001", "", d + dt.timedelta(days=9), [(black, "8", "")])  # אותו טלפון, לקוח אחר (סבתא)
        j = Jacket.objects.filter(model=cream, size="10").first()
        j.active, j.disabled_note = False, "קרע בשרוול"
        j.save()
        self.stdout.write("demo data ready — user demo / demo-12345")
