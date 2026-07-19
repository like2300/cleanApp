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

    def repl(match):
        indent = match.group(1)
        body = match.group(2)
        tuples = re.findall(r"\(([^)]*)\)", body)
        indexes = []
        for tup in tuples:
            fields = [
                f.strip().strip("'").strip('"') for f in tup.split(",") if f.strip()
            ]
            if fields:
                indexes.append(
                    "models.Index(fields=[" + ", ".join(repr(f) for f in fields) + "])"
                )
        return (
            f"{indent}indexes = [\n{indent}    "
            + ",\n{indent}    ".join(indexes)
            + f"\n{indent}]\n"
        )

    new_text = re.sub(
        r"( *)index_together\s*=\s*\((.*?)\)\s*\n", repl, text, flags=re.S
    )

    if new_text == text:
        # Fallback : suppression simple de la ligne index_together
        new_text = re.sub(r"\n.*index_together.*\n", "\n", text)
        print("Fallback : ligne index_together supprimée.")
    else:
        print("index_together converti en indexes.")

    p.write_text(new_text, encoding="utf-8")
    print("django_cron patché avec succès.")


if __name__ == "__main__":
    main()
