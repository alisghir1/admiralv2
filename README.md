# Admiral v2

Application de suivi d'atelier (MES) pour Sotraglace : commandes Sage → ordres de fabrication (OF) → scans par poste.

## Fonctionnement

1. Sage exporte les commandes dans `data/F-DOCENTETE.csv` et `data/F-DOCLIGNE.csv`.
2. Le Bureau d'Étude crée les OF à partir des lignes de commande et choisit leur gamme (opérations et postes).
3. À chaque poste, l'opérateur scanne le code-barres de l'OF (`OF-1001`) ; l'avancement se calcule par opération.

Un scan est refusé si le poste ne fait pas partie de la gamme de l'OF, si la quantité est atteinte, ou si l'étape précédente n'a pas fourni de pièce. Les boutons manuels (« +1 », « TOUT ») permettent de forcer l'avancement : les étapes précédentes sont alors complétées automatiquement.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Lancement : `Lancer_Admiral.command` (macOS), `python suivi_atelier.py` ou `python -m admiral`. Au premier lancement, l'application demande le poste de ce PC.

## Configuration (`config_poste.json`)

```json
{
  "poste": "DEC1 - Découpe Numérique SEKTOR",
  "base_de_donnees": "suivi_atelier.db",
  "dossier_sage": "data"
}
```

Seul `poste` est obligatoire (il est écrit par l'application). `base_de_donnees` et `dossier_sage` sont facultatifs : un chemin relatif part du dossier de l'application. Ils permettent de pointer plusieurs postes vers la même base et le même dossier d'exports Sage.

La base est créée et mise à niveau automatiquement au démarrage (version du schéma dans `PRAGMA user_version`). Les erreurs et les scans sont journalisés dans `logs/admiral.log`.

## Structure du code

```
suivi_atelier.py         lanceur (compatible avec l'exécutable Windows)
admiral/
  __main__.py            démarrage, gestion des erreurs
  config.py              chemins et config_poste.json
  journal.py             logs/admiral.log
  theme.py               jetons de design : couleurs, polices, espacements, états
  db/schema.py           création et migrations de la base
  db/depot.py            toutes les requêtes SQL
  domain/etat.py         photo de l'atelier (OF, gammes, scans) chargée en 4 requêtes
  domain/progression.py  règles de scan et d'avancement (sans base ni interface)
  domain/sage.py         lecture des CSV Sage (séparateur , ou ; détecté)
  domain/referentiel.py  lecture du référentiel Excel (PRODUIT, OPERATION, POSTE, GAMPROD)
  domain/synthese.py     indicateurs de l'onglet Synthèse
  ui/app.py              fenêtre principale : en-tête, onglets, état partagé
  ui/atelier.py          onglet Atelier : commandes du poste, cartes d'OF, bandeau de scan
  ui/carte_of.py         carte d'un OF (mise à jour sur place)
  ui/be_generation.py    onglet Création d'OF
  ui/be_matrice.py       avancement des commandes (matrice commandes × opérations), dans la Synthèse
  ui/be_charge.py        onglet Charge des postes (colonnes de cartes)
  ui/synthese.py         onglet Synthèse (indicateurs, avancement des commandes, postes)
  ui/administration.py   onglet Administration (référentiel, import Excel)
  ui/dialogs.py          choix du poste, nouvel OF, modification d'OF, historique des scans
  ui/composants.py       cartes, pastilles d'état, boutons, tableaux
  ui/widgets.py          icônes, centrage, focus, sélection dans les tableaux
tests/                   tests automatisés
```

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```

`tests/test_interface.py` ouvre brièvement une fenêtre masquée ; il est ignoré sans affichage.

## Scripts annexes

| Fichier | Rôle |
|---|---|
| `setup_db.py` | Réinitialise la base et importe le référentiel depuis l'Excel Sage (efface tout, demande confirmation) |
| `seed_mock_data.py` / `clean_mock_data.py` | Crée / supprime un jeu de données de test |
| `clear_atelier.py` | Supprime les OF et les scans, garde le référentiel |
| `build_exe.bat` | Construit l'exécutable Windows (PyInstaller) |
| `AUDIT_ET_PLAN.md` | Audit et plan de modifications |
