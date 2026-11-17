# העלאה לאוויר — צעד אחר צעד

## 1. מסד נתונים — Neon (חינם, קבוע)
1. נרשמים ב-neon.tech ← New Project ← שם: gemach-suits ← אזור: Frankfurt.
2. מעתיקים את ה-Connection string (מתחיל ב-`postgresql://`).

## 2. Render
1. ב-Render: New ← Blueprint ← בוחרים את הריפו. Render קורא את `render.yaml`.
2. ממלאים את המשתנים שהוא מבקש:
   - `DATABASE_URL` — המחרוזת מ-Neon
   - `ADMIN_USERNAME` — שם המשתמש של המנהלת
   - `ADMIN_PASSWORD` — סיסמה חזקה (12+ תווים)
   - מייל (אפשר גם אחר כך): `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
3. Apply. אחרי כמה דקות האתר באוויר בכתובת `https://gemach-suits.onrender.com` (או דומה).

## 3. מיילים — Gmail
1. חשבון Gmail ייעודי לגמ"ח ← אבטחה ← אימות דו-שלבי ← "סיסמאות לאפליקציות" ← יוצרים סיסמה.
2. ב-Render: `EMAIL_HOST=smtp.gmail.com`, `EMAIL_HOST_USER=<המייל>`, `EMAIL_HOST_PASSWORD=<סיסמת האפליקציה>`,
   `DEFAULT_FROM_EMAIL=גמ״ח חליפות לשמחות <המייל>`.

## 4. תזכורות + שמירה על האתר ער — cron-job.org
1. ב-Render ← Environment ← מעתיקים את הערך של `CRON_TOKEN`.
2. ב-cron-job.org: Create cronjob
   - URL: `https://<הכתובת>/cron/reminders/?token=<CRON_TOKEN>`
   - כל 10 דקות (גם מעיר את האתר, וגם שולח תזכורות פעם ביום אחרי השעה שבהגדרות).

## 5. נטפרי / סינון
לבקש מהסינון לאשר את הכתובת של האתר (`*.onrender.com` או הכתובת המדויקת).

## 6. שני המחשבים
בכל מחשב: פותחים את הכתובת בכרום ← תפריט ⋮ ← "העברה, שיתוף ושמירה" ← "התקנת הדף כאפליקציה" (או "יצירת קיצור דרך").
נוצר אייקון על שולחן העבודה שנפתח בחלון משלו.
