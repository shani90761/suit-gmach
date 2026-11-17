"""יוצר את משתמש המנהלת מתוך משתני סביבה (ADMIN_USERNAME / ADMIN_PASSWORD). רץ בכל עלייה; לא דורס סיסמה קיימת."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *a, **kw):
        u, p = os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_PASSWORD")
        if not u or not p:
            self.stdout.write("ADMIN_USERNAME/ADMIN_PASSWORD not set — skipping")
            return
        User = get_user_model()
        if User.objects.filter(username=u).exists():
            self.stdout.write(f"user {u} exists")
            return
        User.objects.create_superuser(u, "", p)
        self.stdout.write(f"created user {u}")
