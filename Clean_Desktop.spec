# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('db.sqlite3', '.'),
    ('media', 'media'),
    ('static/favicon.png', 'static'),  # icône dans le bundle
]
binaries = []
hiddenimports = []

for pkg in [
    'django', 'unfold', 'django_cron', 'rest_framework',
    'django_extensions', 'pymysql',
    'core', 'accounts', 'business', 'finance', 'notifications', 'sync_engine',
]:
    tmp = collect_all(pkg)
    datas    += tmp[0]
    binaries += tmp[1]
    hiddenimports += tmp[2]

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        'django.template.defaulttags',
        'django.template.loader_tags',
        'django.contrib.staticfiles',
        'django.contrib.staticfiles.finders',
        'django.contrib.staticfiles.storage',
    ],
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
    [],
    exclude_binaries=True,
    name='Clean Desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['static/favicon.ico'],   # favicon.ico pour l'icône Windows
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Clean_Desktop',
)
