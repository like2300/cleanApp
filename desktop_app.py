import os
import sys
import socket
import threading
import time
import shutil
import urllib.request
from pathlib import Path
import webview


def find_free_port(start_port=8000):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                port += 1


def start_django(port):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

    # If running inside a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)

    from django.core.management import execute_from_command_line
    sys.argv = ['manage.py', 'runserver', f'127.0.0.1:{port}', '--noreload']
    execute_from_command_line(sys.argv)


def setup_bundle_dirs():
    """Prépare les dossiers nécessaires quand on tourne depuis le bundle PyInstaller."""
    if not getattr(sys, 'frozen', False):
        return

    base_dir = Path(sys._MEIPASS)
    exec_dir = Path(sys.executable).parent

    # ── Base de données ──────────────────────────────────────────────────────
    local_db = exec_dir / "db.sqlite3"
    bundled_db = base_dir / "db.sqlite3"
    if not local_db.exists() and bundled_db.exists():
        try:
            shutil.copy2(bundled_db, local_db)
        except Exception as e:
            print(f"[WARN] Impossible de copier db.sqlite3 : {e}")

    # ── Media ────────────────────────────────────────────────────────────────
    local_media = exec_dir / "media"
    if not local_media.exists():
        local_media.mkdir(exist_ok=True)
        bundled_media = base_dir / "media"
        if bundled_media.exists():
            try:
                shutil.copytree(bundled_media, local_media, dirs_exist_ok=True)
            except Exception as e:
                print(f"[WARN] Impossible de copier media/ : {e}")

    # ── Static (collectstatic pré-compilé) ──────────────────────────────────
    # On s'assure que STATIC_ROOT pointe sur exec_dir/staticfiles
    local_static = exec_dir / "staticfiles"
    bundled_static = base_dir / "staticfiles"
    if not local_static.exists() and bundled_static.exists():
        try:
            shutil.copytree(bundled_static, local_static, dirs_exist_ok=True)
        except Exception as e:
            print(f"[WARN] Impossible de copier staticfiles/ : {e}")


def main():
    setup_bundle_dirs()

    port = find_free_port(8000)

    # Démarrer Django en thread daemon
    t = threading.Thread(target=start_django, args=(port,), daemon=True)
    t.start()

    # Attendre que Django soit prêt (max ~10 s)
    url = f"http://127.0.0.1:{port}/"
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{url}accounts/login/", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.1)

    # Fenêtre native webview
    window = webview.create_window(
        title="Clean Desktop",
        url=url,
        width=1366,
        height=860,
        resizable=True,
        min_size=(1024, 680),
    )

    webview.start()


if __name__ == '__main__':
    main()
