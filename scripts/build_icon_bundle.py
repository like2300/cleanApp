#!/usr/bin/env python3
"""
Génère un bundle Iconify local (static/js/iconify-bundle.js) contenant toutes les
icônes référencées dans les templates, pour un fonctionnement 100% hors-ligne.

Fonctionnement :
  1. Scanne tous les fichiers .html de templates/ pour extraire les noms d'icônes
     uniques utilisés dans <iconify-icon icon="...">.
  2. Récupère les données de chaque icône via l'API Iconify (https://api.iconify.design)
     -> nécessite une connexion internet UNE SEULE FOIS, au moment de la génération.
  3. Écrit un fichier JS qui enregistre chaque collection localement via
     Iconify.addCollection(), éliminant toute dépendance réseau au runtime.

Usage :
  python scripts/build_icon_bundle.py
"""

import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request


# Contexte SSL : sur macOS, les certificats racines ne sont pas toujours disponibles
# pour Python. On utilise le bundle de certifi si présent, sinon le contexte par défaut.
def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open_url(url):
    ctx = _ssl_context()
    try:
        return urllib.request.urlopen(url, timeout=30, context=ctx)
    except urllib.error.URLError as e:
        # Repli : si la vérification échoue et que l'utilisateur accepte le mode
        # non sécurisé, on retente sans vérification (uniquement pour les icônes
        # publiques d'Iconify).
        if isinstance(e.reason, ssl.SSLError) and os.environ.get("ICONIFY_INSECURE"):
            insecure = ssl.create_default_context()
            insecure.check_hostname = False
            insecure.verify_mode = ssl.CERT_NONE
            return urllib.request.urlopen(url, timeout=30, context=insecure)
        raise


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_FILE = os.path.join(BASE_DIR, "static", "js", "iconify-bundle.js")

ICON_RE = re.compile(r'icon="([^"]+)"')

# Icônes définies dynamiquement via des templatetags Django ({% if %}...{% else %}...)
# et donc non détectées par le scan automatique. À maintenir à la main.
EXTRA_ICONS = [
    "solar:danger-triangle-bold",
    "solar:bell-bing-bold",
    "solar:danger-circle-linear",
    "solar:check-circle-linear",
    "solar:lock-keyhole-minimalistic-linear",
    "solar:key-linear",
]


def collect_icons():
    """Retourne un dict {prefix: set(nom_icone)} pour toutes les icônes trouvées."""
    icons = {}
    # Icônes dynamiques explicites
    for icon in EXTRA_ICONS:
        if ":" in icon:
            prefix, name = icon.split(":", 1)
            icons.setdefault(prefix, set()).add(name)
    for root, _dirs, files in os.walk(TEMPLATES_DIR):
        for fname in files:
            if not fname.endswith(".html"):
                continue
            path = os.path.join(root, fname)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for match in ICON_RE.findall(content):
                # Gère les icônes dynamiques type {% if ... %}solar:foo{% else %}solar:bar{% endif %}
                # On ne garde que les noms statiques (contiennent ':' et pas de templatetag).
                if ":" not in match or "{" in match or "%" in match:
                    continue
                prefix, name = match.split(":", 1)
                icons.setdefault(prefix, set()).add(name)
    return icons


def fetch_collection(prefix, names):
    """Récupère une collection Iconify complète pour un prefix donné."""
    url = f"https://api.iconify.design/{prefix}.json"
    with _open_url(url) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def main():
    icons = collect_icons()
    if not icons:
        print("Aucune icône trouvée dans les templates.")
        sys.exit(1)

    print(f"Préfixes d'icônes trouvés : {', '.join(sorted(icons))}")
    for prefix, names in icons.items():
        print(f"  - {prefix}: {len(names)} icône(s)")

    collections = {}
    for prefix, names in icons.items():
        try:
            data = fetch_collection(prefix, names)
            # On ne garde que les icônes effectivement utilisées pour alléger le fichier
            used = {n: data["icons"][n] for n in names if n in data.get("icons", {})}
            if not used:
                print(f"  /!\\ Aucune icône résolue pour le préfixe '{prefix}'")
                continue
            collection = {
                "prefix": data.get("prefix", prefix),
                "icons": used,
            }
            # Copie des métadonnées éventuelles (width, height, etc.)
            for key in ("width", "height", "verticalAlign", "aliases"):
                if key in data:
                    collection[key] = data[key]
            collections[prefix] = collection
            print(f"  + '{prefix}' : {len(used)} icône(s) embarquées")
        except Exception as e:
            print(f"  /!\\ Erreur lors du chargement de '{prefix}': {e}")

    if not collections:
        print(
            "Impossible de récupérer aucune collection. Vérifiez la connexion internet."
        )
        sys.exit(1)

    # Génération du fichier JS
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    parts = []
    parts.append("/*")
    parts.append(
        " * Iconify offline bundle - généré automatiquement par scripts/build_icon_bundle.py"
    )
    parts.append(
        " * Enregistre les collections d'icônes localement pour un usage hors-ligne."
    )
    parts.append(" * Ne pas éditer manuellement.")
    parts.append(" */")
    parts.append("(function() {")
    parts.append("  function addCollection(data) {")
    parts.append("    if (window.Iconify) {")
    parts.append("      window.Iconify.addCollection(data);")
    parts.append("    } else if (window.iconify) {")
    parts.append("      window.iconify.addCollection(data);")
    parts.append("    }")
    parts.append("  }")
    for prefix, collection in collections.items():
        parts.append(
            "  addCollection(" + json.dumps(collection, separators=(",", ":")) + ");"
        )
    parts.append("})();")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(parts) + "\n")

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\nBundle généré : {OUTPUT_FILE} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
