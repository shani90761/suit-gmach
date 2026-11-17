"""מפעיל את המערכת על המחשב: שרת מקומי + פתיחת הדפדפן.
הנתונים נשמרים ב-%LOCALAPPDATA%\\GemachSuits (או ~/.gemach-suits בלינוקס/מק)."""
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"


def data_dir():
    base = os.environ.get("LOCALAPPDATA")
    d = Path(base) / "GemachSuits" if base else Path.home() / ".gemach-suits"
    d.mkdir(parents=True, exist_ok=True)
    return d


def already_running():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def setup_env(d):
    key_file = d / "secret.key"
    if not key_file.exists():
        key_file.write_text(secrets.token_urlsafe(50), encoding="utf-8")
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DEBUG": "0",
        "LOCAL_APP": "1",
        "SECRET_KEY": key_file.read_text(encoding="utf-8").strip(),
        "ALLOWED_HOSTS": "127.0.0.1,localhost",
        "DATABASE_URL": "sqlite:///" + (d / "gemach.sqlite3").as_posix(),
        "CRON_TOKEN": secrets.token_urlsafe(16),
    })
    # הגדרות מייל אופציונליות: קובץ email.env בתיקיית הנתונים (שורות KEY=VALUE)
    env_file = d / "email.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def backup(d):
    """גיבוי אוטומטי בכל הפעלה — שומר 10 אחרונים."""
    db = d / "gemach.sqlite3"
    if not db.exists():
        return
    bdir = d / "backups"
    bdir.mkdir(exist_ok=True)
    (bdir / time.strftime("gemach-%Y%m%d-%H%M%S.sqlite3")).write_bytes(db.read_bytes())
    for old in sorted(bdir.glob("gemach-*.sqlite3"))[:-10]:
        old.unlink()


def reminders_loop():
    from gemach.services import run_reminders
    while True:
        try:
            run_reminders()
        except Exception as e:  # noqa: BLE001
            print("reminders:", e)
        time.sleep(600)


def main():
    for stream in (sys.stdout, sys.stderr):  # חלון שחור בווינדוס — שהעברית לא תפיל את התוכנה
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    if already_running():
        webbrowser.open(URL)
        return
    d = data_dir()
    setup_env(d)
    backup(d)
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)
    from waitress import serve
    from config.wsgi import application
    threading.Thread(target=reminders_loop, daemon=True).start()
    threading.Timer(1.2, lambda: webbrowser.open(URL)).start()
    print("גמ\"ח חליפות לשמחות פועל בכתובת", URL)
    print("לסגירת המערכת — סוגרים את החלון הזה.")
    serve(application, host="127.0.0.1", port=PORT, threads=4)


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        sys.path.insert(0, getattr(sys, "_MEIPASS", ""))
    main()
