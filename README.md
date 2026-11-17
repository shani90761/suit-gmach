# גמ"ח חליפות לשמחות — מערכת ניהול

מערכת פנימית למנהלת הגמ"ח: מלאי ז'קטים, בדיקת זמינות, הזמנות טלפוניות, איסוף/החזרה, ומיילים ללקוחות.
אפיון: `docs/gemach-suits/spec.md` (גרסה 2). מצב הפרויקט: `docs/gemach-suits/STATE.md`.

## הרצה מקומית
```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py demo_data      # משתמש demo / demo-12345
python manage.py runserver
python manage.py test gemach
```

## העלאה לאוויר — ראו docs/gemach-suits/DEPLOY.md
