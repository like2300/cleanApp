#!/usr/bin/env python3
"""
Prépare l'environnement pour un build PyInstaller (desktop) ou un déploiement web.

- Applique les migrations pour créer une base SQLite locale valide.
- Lance collectstatic pour générer staticfiles/.
- Génère un fichier .env à partir des variables d'environnement (ou d'un
  .env.example si absent), afin que l'exécutable embarque une configuration.

Usage (dans le CI ou en local) :
  python scripts/prepare_build.py
"""

import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


def run(cmd):
    print(f"\n>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=BASE_DIR)


def main():
    # 1. Migrations -> crée db.sqlite3 local
    run([sys.executable, "manage.py", "migrate", "--noinput"])

    # 2. Collectstatic -> staticfiles/
    staticfiles = os.path.join(BASE_DIR, "staticfiles")
    if os.path.isdir(staticfiles):
        shutil.rmtree(staticfiles)
    run(
        [
            sys.executable,
            "manage.py",
            "collectstatic",
            "--noinput",
            "--clear",
        ]
    )

    # 3. Générer .env si inexistant (le CI fournit les variables d'env)
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        example = os.path.join(BASE_DIR, ".env.example")
        if os.path.exists(example):
            shutil.copy(example, env_path)
            print("\n>> .env créé à partir de .env.example")
        else:
            print(
                "\n>> Aucun .env ni .env.example trouvé, on laisse Django "
                "utiliser ses valeurs par défaut."
            )

    print("\n✅ Préparation du build terminée.")


if __name__ == "__main__":
    main()
