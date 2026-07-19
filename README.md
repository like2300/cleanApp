# CLEAN — Plateforme de gestion d'abonnements & de facturation

**CLEAN** (aussi nommée *INFINITY Management* dans l'interface d'administration) est une application web Django destinée à la gestion centralisée des **abonnements clients**, de la **facturation**, des **employés**, des **zones géographiques** et de la **synchro­nisation des données** entre une instance locale (bureau) et un serveur cloud.

Elle est conçue pour fonctionner aussi bien en mode web classique (serveur Django) qu'en **application de bureau** packagée (bundle PyInstaller / EXE), avec une base de données locale SQLite et une base cloud MySQL distante.

---

## 🎯 À quoi sert ce projet

CLEAN permet de :

- Gérer les **clients** et leurs **abonnements** (plans, dates de début/fin, statut actif/inactif).
- Émettre et suivre des **factures** et des **paiements** (Mobile Money, Physique, Autre).
- Superviser les **employés** et les **zones / quartiers**.
- Consulter des **tableaux de bord analytiques** (recouvrement, performance par zone, évolution facturation vs encaissement, répartition des dépenses).
- **Synchroniser** les données entre le poste local et le cloud (mode `LOCAL`, `CLOUD` ou `AUTO`).
- Gérer les **rôles et permissions** avec un accès adapté à chaque profil.

---

## 👥 Rôles et permissions

| Rôle | Libellé | Accès aux données |
|------|---------|-------------------|
| `SUPER_ADMIN` | Super Admin | Accès total à tout le système. |
| `ZONE_MANAGER` | Chef de Zone | Restreint aux zones qui lui sont assignées. **Doit** avoir au moins une zone assignée. |
| `ACCOUNTANT` | Comptable | Accès **global** à toutes les données (factures, paiements, zones) — **ne nécessite pas** d'assignation de zone. |
| `AGENT` | Agent | Rôle opérationnel (accès limité selon configuration). |
| `CLIENT` | Client | Accès à son propre espace (abonnements, factures, paiement). |
| `SHAREHOLDER` | Actionnaire | Accès **global** en lecture à toutes les informations — **ne nécessite pas** d'assignation de zone. |

> 💡 Les comptables et actionnaires voient l'ensemble des données sans avoir besoin d'être rattachés à une zone. L'interface de création de compte désactive d'ailleurs les champs de zone pour ces rôles.

---

## 🧱 Architecture

- **Framework** : Django (avec interface d'administration [Unfold](https://github.com/unfoldadmin/django-unfold)).
- **Base locale** : SQLite (`db.sqlite3`).
- **Base cloud** : MySQL (AlwaysData) synchronisée via un routeur et un moteur de sync.
- **Front-end** : Tailwind CSS (build local), [Iconify](https://iconify.design/) (icônes, bundle local hors-ligne), Chart.js (graphiques), QRCode.js.
- **Paiements** : API OpenPay (lien de paiement).
- **Desktop** : packagé en exécutable via PyInstaller (`desktop_app.spec`, `Clean_Desktop.spec`).

### Applications du projet

| App | Rôle |
|-----|------|
| `accounts` | Utilisateurs, rôles, authentification, paramètres entreprise. |
| `business` | Employés, zones, quartiers, abonnements, plans, clients. |
| `finance` | Factures, paiements, dépenses, tableaux de bord analytiques. |
| `notifications` | Réclamations / notifications clients. |
| `sync_engine` | Synchronisation locale ↔ cloud, routeur de base de données, middleware auto-sync. |
| `core` | Configuration Django, URLs racine, vues de tableau de bord global. |

---

## ⚙️ Configuration

Toutes les données sensibles (clés secrètes, identifiants de base de données cloud, clés API) sont externalisées dans un fichier **`.env`** (chargé automatiquement par `core/settings.py`).

### 1. Préparer l'environnement

```sh
cd CLEAN
python -m venv env        # ou utiliser l'env existant
source env/bin/activate   # Linux/macOS
pip install -r requirements.txt   # voir note ci-dessous
```

> ⚠️ **Note** : ce dépôt ne contient pas encore de `requirements.txt`. Installez au minimum : `django`, `unfold`, `djangorestframework`, `django-cron`, `django-extensions`, `pymysql`, `python-dotenv` (optionnel), `PyInstaller` (pour le build desktop). Un fichier `requirements.txt` devra être ajouté pour figer les versions.

### 2. Fichier `.env`

Copiez le modèle et renseignez vos valeurs :

```sh
cp .env.example .env
```

Variables principales :

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Clé secrète Django (à générer, surtout en production). |
| `DEBUG` | `True` en dev, `False` en production. |
| `ALLOWED_HOSTS` | Hôtes autorisés (séparés par des virgules). |
| `CLOUD_DB_NAME` / `CLOUD_DB_USER` / `CLOUD_DB_PASSWORD` / `CLOUD_DB_HOST` / `CLOUD_DB_PORT` | Identifiants de la base MySQL cloud. |
| `OPENPAY_API_KEY` / `OPENPAY_URL` | Configuration de l'API de paiement OpenPay. |
| `CLOUD_SYNC_URL` / `CLOUD_API_KEY` | Paramètres de synchronisation cloud. |
| `SITE_ID` | Identifiant du site/local. |
| `LIVE_MODE` | `LOCAL`, `CLOUD` ou `AUTO` (auto-bascule vers le local si le cloud est injoignable). |
| `CSRF_TRUSTED_ORIGINS` | Origines de confiance pour les requêtes cross-site. |

### 3. Lancer le serveur de développement

```sh
python manage.py migrate
python manage.py runserver
```

L'application est alors accessible sur `http://127.0.0.1:8000/`.

---

## 🔒 Sécurité

- Le fichier **`.env` est ignoré par Git** (voir `.gitignore`). **Ne le commitez jamais**.
- Un `.env.example` est fourni comme modèle (sans valeurs réelles).
- En production : régénérez `SECRET_KEY`, mettez `DEBUG=False`, et restreignez `ALLOWED_HOSTS`.

---

## 🖥️ Build de l'application de bureau

Le projet peut être packagé en exécutable autonome avec PyInstaller :

```sh
pyinstaller desktop_app.spec
# ou
pyinstaller Clean_Desktop.spec
```

Les fichiers modifiables (base SQLite, `media/`, statics collectés) sont alors placés à côté de l'exécutable (`RUNTIME_DIR`), ce qui permet à l'app desktop de fonctionner hors-ligne.

---

## 📁 Structure du dépôt

```
CLEAN/
├── core/            # Settings, URLs racine, dashboard global
├── accounts/        # Auth, rôles, utilisateurs, paramètres
├── business/        # Employés, zones, abonnements, clients
├── finance/         # Factures, paiements, dépenses, analytics
├── notifications/   # Réclamations / notifications
├── sync_engine/     # Sync locale↔cloud, routeur DB
├── templates/       # Templates HTML (base, dashboard, etc.)
├── static/          # Assets locaux (Tailwind, Iconify, Chart.js…)
├── scripts/         # Scripts utilitaires (bundle d'icônes, vérifications…)
├── media/           # Fichiers uploadés (ignoré par Git)
├── .env.example     # Modèle de configuration
├── .gitignore       # Exclusions (secrets, DB, builds…)
└── manage.py
```

---

## 📝 Licence

Projet interne — tous droits réservés © 2026 CLEAN.
# cleanApp
