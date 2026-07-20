# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all


def safe_collect(pkg):
    """collect_all tolérant : ignore les packages non installés."""
    try:
        return collect_all(pkg)
    except Exception as e:
        print(f"[WARN] collect_all('{pkg}') ignoré : {e}")
        return [], [], []


datas = [("templates", "templates"), ("static", "static"), ("db.sqlite3", ".")]
binaries = []
hiddenimports = []
for pkg in [
    "django",
    "unfold",
    "django_cron",
    "rest_framework",
    "django_extensions",
    "pymysql",
    "pywebview",
    "core",
    "accounts",
    "business",
    "finance",
    "notifications",
    "sync_engine",
]:
    tmp = safe_collect(pkg)
    datas += tmp[0]
    binaries += tmp[1]
    hiddenimports += tmp[2]


a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="desktop_app",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["logo.ico"],
)

# Regroupe l'exécutable (et ses données embarquées) dans un dossier
# dist/desktop_app/ afin que les étapes de signature et de packaging
# (Compress-Archive dist\desktop_app\*) du workflow CI fonctionnent.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="desktop_app",
)
