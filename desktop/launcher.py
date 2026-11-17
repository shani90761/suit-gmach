"""מפעיל את המערכת על המחשב: שרת מקומי + פתיחת הדפדפן.
הנתונים נשמרים ב-%LOCALAPPDATA%\\GemachSuits (או ~/.gemach-suits בלינוקס/מק)."""
import os
import secrets
import shutil
import socket
import subprocess
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


def find_app_browser():
    """Edge (קיים בכל ווינדוס) או Chrome — לפתיחה בחלון אפליקציה משלה."""
    override = os.environ.get("GEMACH_BROWSER")
    if override:
        return override
    cands = []
    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA")):
        if base:
            cands += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                      Path(base) / "Google/Chrome/Application/chrome.exe"]
    for c in cands:
        if c.exists():
            return str(c)
    for name in ("msedge", "google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def open_app_window(d):
    """פותח חלון אפליקציה ומחזיר את התהליך (או None אם אין דפדפן מתאים)."""
    exe = find_app_browser()
    if not exe:
        webbrowser.open(URL)
        return None
    profile = d / "window"
    return subprocess.Popen([exe, f"--app={URL}", f"--user-data-dir={profile}", "--window-size=1400,900",
                             "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"])


def reminders_loop():
    from gemach.services import run_reminders
    while True:
        try:
            run_reminders()
        except Exception as e:  # noqa: BLE001
            print("reminders:", e)
        time.sleep(600)


def main():
    if sys.stdout is None or sys.stderr is None:  # בלי חלון שחור — רושמים ללוג בתיקיית הנתונים
        log = open(data_dir() / "app.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    if already_running():
        open_app_window(data_dir())
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
    threading.Thread(target=lambda: serve(application, host="127.0.0.1", port=PORT, threads=4), daemon=True).start()
    for _ in range(50):  # מחכים שהשרת יעלה
        if already_running():
            break
        time.sleep(0.1)
    win = open_app_window(d)
    if win is None:  # אין Edge/Chrome — נפתח בדפדפן הרגיל, והשרת רץ עד כיבוי המחשב
        while True:
            time.sleep(3600)
    win.wait()  # סגירת החלון = סגירת המערכת
    os._exit(0)


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        sys.path.insert(0, getattr(sys, "_MEIPASS", ""))
    main()
