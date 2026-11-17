# PyInstaller — בונה את המערכת כתוכנה לווינדוס (תיקייה אחת). מריצים מתיקיית הפרויקט:
#   python manage.py collectstatic --no-input && pyinstaller desktop/gemach.spec --noconfirm
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
import sys, glob
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

def own_modules(pkg):
    """כל קבצי ה-py של החבילה, כולל migrations ו-templatetags."""
    out = []
    for f in glob.glob(os.path.join(ROOT, pkg, "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, ROOT)[:-3].replace(os.sep, ".")
        out.append(rel[:-9] if rel.endswith(".__init__") else rel)
    return out

skip = lambda m: not m.startswith(("django.contrib.gis", "django.contrib.postgres", "django.db.backends.oracle",
                                   "django.db.backends.mysql", "django.db.backends.postgresql", "django.contrib.admin"))

hidden = (collect_submodules("django", filter=skip) + own_modules("gemach") + own_modules("config")
          + collect_submodules("waitress") + ["dj_database_url", "whitenoise", "whitenoise.middleware",
          "whitenoise.storage"])
datas = (collect_data_files("django")
         + [(os.path.join(ROOT, "gemach/templates"), "gemach/templates"), (os.path.join(ROOT, "staticfiles"), "staticfiles")])

a = Analysis(["launcher.py"], pathex=[ROOT], hiddenimports=hidden, datas=datas,
             excludes=["tkinter", "psycopg", "psycopg_binary", "gunicorn", "django.contrib.gis", "django.contrib.admin"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GemachSuits", console=True,
          icon=os.path.join(SPECPATH, "icon.ico") if os.path.exists(os.path.join(SPECPATH, "icon.ico")) else None)
coll = COLLECT(exe, a.binaries, a.datas, name="GemachSuits")
