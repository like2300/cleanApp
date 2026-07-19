#!/usr/bin/env python3
"""
Patch de compatibilité django-cron pour Django 5.1+.

django-cron (dernière version PyPI) déclare encore ``index_together`` dans la
Meta de son modèle ``CronJobLog``, attribut **supprimé en Django 5.1** (erreur
``TypeError: la classe Meta possède un ou plusieurs attributs invalides :
index_together`` au chargement de Django).

Ce script convertit ``index_together = ((a, b), ...)`` en
``indexes = [models.Index(fields=[a, b]), ...]`` directement dans le package
installé (site-packages), ce qui rend django-cron compatible sans modifier
le code du projet.

Usage (dans le CI, après pip install) :
  python scripts/patch_django_cron.py
"""

import importlib.util
import pathlib
import re
import sys


def main():
    spec = importlib.util.find_spec("django_cron")
    if not spec or not spec.origin:
        print("django_cron non trouvé, rien à patcher.")
        return

    p = pathlib.Path(spec.origin).parent / "models.py"
    if not p.exists():
        print(f"{p} introuvable, rien à patcher.")
        return

    text = p.read_text(encoding="utf-8")
    if "index_together" not in text:
        print("django_cron déjà compatible (pas de index_together), OK.")
        return

    lines = text.split("\n")
    patched = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("index_together"):
            # Récupère l'indentation de la ligne d'origine
            indent = line[: len(line) - len(line.lstrip())]
            # Extrait tous les champs entre guillemets sur la ligne
            fields = re.findall(r"[\"']([^\"']+)[\"']", line)
            if fields:
                indexes = (
                    f"{indent}indexes = [\n"
                    f"{indent}    models.Index(fields=["
                    + ", ".join(repr(f) for f in fields)
                    + "]),\n"
                    f"{indent}]"
                )
            else:
                # Aucun champ trouvé : on supprime simplement la ligne
                indexes = ""
            lines[i] = indexes
            patched = True
            break

    if not patched:
        print("index_together détecté mais non patché (format inconnu).")
        return

    p.write_text("\n".join(lines), encoding="utf-8")
    print("django_cron patché avec succès.")


if __name__ == "__main__":
    main()
