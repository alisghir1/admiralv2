# Admiral v2

Application de suivi d'atelier (MES) : commandes Sage → ordres de fabrication (OF) → scans par poste.

## Fonctionnement

1. Les commandes Sage sont lues dans `data/` : le classeur Excel relié à Sage (`BASE SAGE Admiral.xlsx`, feuilles DOCENTETE et DOCLIGNE, commandes en cours seulement ; l'ancien `BASE SAGE ADM.xlsx`, feuilles F-DOCENTETE et F-DOCLIGNE, est encore lu) s'il y en a un, sinon les exports `F-DOCENTETE.csv` et `F-DOCLIGNE.csv`. « Actualiser Sage » relit le dossier.
   Chaque lecture est recopiée dans la base (tables `SageCommandes`, `SageLignes`, `SageLecture`) et les écrans lisent cette copie : tous les postes qui partagent la base voient les mêmes commandes, même sans dossier Sage. Rien n'y est effacé : une commande livrée ou une ligne supprimée dans Sage est marquée sortie et n'est plus listée, mais ses OF gardent le détail de leurs lignes. Un fichier plus ancien que la copie (resté sur un autre poste) n'est pas recopié, ni une lecture vide.
   Le dossier est relu automatiquement toutes les 3 minutes (`actualisation_sage_minutes`), dans un fil d'arrière-plan et seulement si un fichier a été enregistré entre-temps : il suffit que le client actualise puis **enregistre** le classeur. Les écrans se mettent à jour quand la copie change (par ce poste ou un autre) ; c'est reporté tant qu'une fenêtre est ouverte ou que le Bureau d'étude a des lignes sélectionnées.
2. Le Bureau d'Étude crée les OF à partir des lignes de commande et choisit leur gamme (opérations et postes).
3. À chaque poste, l'opérateur scanne le code-barres de l'OF ; l'avancement se calcule par opération.
   Numéro d'OF : « OF » + numéro de la commande sans « CC » + rang de l'OF dans la commande sur deux chiffres (`OF261234-01`, `OF261234-02`, puis `OF261235-01`…), attribué sous verrou d'écriture (deux PC ne prennent jamais le même). Un OF annulé garde son rang ; un OF supprimé (jamais scanné) libère le sien. Un OF qui change de commande (possible seulement avant tout scan) prend un numéro dans sa nouvelle commande, reporté dans ses gammes, lignes, scans annulés et validations. Les OF créés avant cette numérotation (`OF-1000`…) gardent leur numéro.
4. Le Chef d'atelier (profil « Chef d'atelier », code personnel) pilote l'atelier et peut valider un OF, une étape ou une commande entière sans scan. Aucun faux scan n'est créé : la validation est enregistrée à part (`ValidationsChef` : chef, date, motif) et comptée comme faite par `EtatAtelier.compter`, donc par tous les écrans. Elle s'annule en restant tracée (onglet Validations). Les chefs et leurs codes se gèrent dans Administration (table `Chefs`) ; tant qu'il n'y en a aucun, le code `code_chef_atelier` (défaut 1111) ouvre l'accès.

5. **Remise à zéro** (Administration › Mise en service, `Depot.remettre_a_zero`) : vide les OF, scans, validations, clôtures et la copie des commandes Sage, garde le référentiel et les chefs d'atelier ; confirmation « VIDER » et copie de la base dans `sauvegardes/` avant. Le classeur est relu puis un point de départ est posé (table `Parametres`, commun à tous les PC) : plus rien n'est affiché, et seules les commandes qui arrivent ensuite dans le classeur, datées du jour ou après, s'affichent (`sage.commande_nouvelle`, filtrée dans `Depot.charger_sage` ; une commande qui a des OF reste toujours affichée). « Réafficher les commandes d'avant » retire le point de départ. Les autres PC suivent à leur relecture de la base. `clear_atelier.py` fait la même chose en ligne de commande.
6. **Impression** (`domain/documents.py` pour le contenu, `pdf.py` pour le rendu reportlab, `ui/impression.py` pour la fenêtre) : fiche suiveuse d'OF (vue générale), fiche d'étape (un OF vu par un poste, demi-page), fiche commande, liste de travail d'un poste (A4 paysage, par produit), étiquettes d'articles (planche 3 × 7) et page d'essai de la douchette. Noir et blanc, cases à cocher au stylo, codes-barres Code 128 uniques : commande `CC261234`, OF `OF261234-01`, article (ligne de commande) `CC261234-1000` (`domain/codes.py`). Scanner un article compte une pièce sur sa ligne ; une douchette en clavier américain est corrigée et signalée.
7. **Douchette** (`douchette.py`) : en mode clavier, un scan est reconnu à sa vitesse de frappe (`DetecteurScan`) et traité où que soit le curseur dans Admiral (recherche, fenêtre ouverte), le code tapé dans un champ en est retiré ; en port COM (`douchette_port`), il est lu dans un fil d'arrière-plan et arrive même si Admiral n'est pas au premier plan (la fenêtre revient devant). Le même code relu dans la seconde est ignoré. Un code qui ne passe pas par le poste est refusé avec le parcours prévu par le bureau d'étude, et un son d'erreur. Une commande scannée s'affiche avec ses OF du poste ; « Terminer la commande » les termine tous à ce poste après confirmation. Chaque étape d'un OF peut porter une consigne du Bureau d'étude (`OF_Gammes.Consigne`), affichée sur la carte de l'OF au poste concerné et imprimée.

Profils d'un PC : poste machine (écran Atelier, douchette), Bureau d'étude (code `code_bureau_etude`, tous les onglets de pilotage) ou Chef d'atelier (Synthèse, Pilotage, Charge des postes, Validations). Chaque PC relit la base toutes les 5 s (`PRAGMA data_version`) : ce qu'un autre poste écrit (OF corrigé, scan, validation) apparaît sans action.

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
  "dossier_sage": "data",
  "actualisation_sage_minutes": 3
}
```

Douchette réglée en port COM (facultatif) : `"douchette_port": "COM3"` (ou `"auto"` : le seul port USB branché), `"douchette_vitesse": 9600`. Sans cette clé, la douchette tape comme un clavier.

Seul `poste` est obligatoire (il est écrit par l'application). `base_de_donnees` et `dossier_sage` sont facultatifs : un chemin relatif part du dossier de l'application. Ils permettent de pointer plusieurs postes vers la même base et le même dossier Sage. `actualisation_sage_minutes` aussi (défaut 3 ; 0 : pas de relecture automatique).

Dans le dossier Sage, le classeur `.xlsx` le plus récent qui a une feuille DOCLIGNE (ou F-DOCLIGNE) est prioritaire sur les CSV (les autres classeurs, comme le référentiel, sont ignorés). Les colonnes du classeur (Commande, CodeCli, Quantité… ou CDE, CODECLI, QTE… dans l'ancien) sont ramenées aux noms Sage (`COLONNES_ENTETES` et `COLONNES_LIGNES` dans `domain/sage.py`) ; l'unité, donnée par son numéro dans Sage, est remise en libellé (U, ML, M2). Les autres données de Sage sont affichées là où elles servent, sans nouvelle colonne dans les listes : sous le titre de la commande (Atelier, Création d'OF, Pilotage ; composant `BandeauCommande`), l'observation en pastille (rouge si annulée ou bloquée, orange si en attente ou en rupture), la réf. client, la date de commande (Création d'OF seulement) et le délai (en rouge s'il est dépassé) ; dans les lignes, les chants notés comme dans les désignations (« 1H+2L », rien si Sage ne les précise pas) et la quantité avec son unité si ce ne sont pas des pièces ; au Bureau d'étude, le total des lignes sélectionnées (pièces, m², mètres de chant) et le délai rappelé à côté de la date de besoin. La recherche des commandes porte aussi sur la réf. client et l'observation. Le client est affiché partout avec son nom et son code (« AGENCEMENTS DU LITTORAL (C0901) » ; pour un client divers, le nom saisi dans « Client Divers ») ; le tri « Client (A → Z) » suit le nom. Un classeur illisible (en cours d'enregistrement) laisse les données déjà lues en place.

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
  db/depot.py            toutes les requêtes SQL (dont la copie des commandes Sage)
  domain/etat.py         photo de l'atelier (OF, gammes, scans) chargée en 4 requêtes
  domain/progression.py  règles de scan et d'avancement (sans base ni interface)
  domain/sage.py         lecture du classeur Sage ou des CSV (séparateur , ou ; détecté)
  domain/lecture_sage.py relecture du dossier Sage en arrière-plan, seulement si un fichier a changé
  domain/referentiel.py  lecture du référentiel Excel (PRODUIT, OPERATION, POSTE, GAMPROD)
  domain/synthese.py     indicateurs de l'onglet Synthèse
  domain/pilotage.py     avancement et validations du chef d'atelier (onglet Pilotage)
  domain/tri.py          tri des listes (numéro dans l'ordre naturel, client, état, besoin)
  domain/codes.py        contenu des codes-barres, lecture d'un scan (correction du clavier américain)
  domain/documents.py    contenu des documents imprimés (fiches, listes, étiquettes, page d'essai)
  pdf.py                 rendu PDF des documents (reportlab, Code 128)
  douchette.py           douchette : scan reconnu à la vitesse de frappe, port COM, double lecture
  ui/app.py              fenêtre principale : en-tête, onglets, état partagé
  ui/atelier.py          onglet Atelier : commandes du poste, cartes d'OF, bandeau de scan
  ui/carte_of.py         carte d'un OF (mise à jour sur place)
  ui/be_generation.py    onglet Création d'OF
  ui/be_matrice.py       avancement des commandes (matrice commandes × opérations), dans la Synthèse
  ui/be_charge.py        onglet Charge des postes (colonnes de cartes)
  ui/synthese.py         onglet Synthèse (indicateurs, avancement des commandes, postes)
  ui/administration.py   onglet Administration (référentiel, chefs d'atelier, import Excel)
  ui/pilotage.py         onglets Pilotage et Validations (chef d'atelier), fenêtre de validation
  ui/dialogs.py          choix du poste, nouvel OF, modification d'OF, historique des scans
  ui/impression.py       fenêtre d'impression (aperçu dans le lecteur PDF, enregistrement)
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
| `clear_atelier.py` | Remet l'atelier à zéro (OF, scans, validations, copie Sage), garde le référentiel et les chefs ; copie de la base avant |
| `build_exe.bat` | Construit l'exécutable Windows (PyInstaller) |
| `preparer_livraison.py` | Prépare `livraison_client/Admiral` avec les vraies données (base neuve avec le référentiel, classeur Sage, LISEZMOI) ; il reste à y glisser `Admiral.exe` (GitHub Actions). Ce dossier n'est jamais versionné |
| `AUDIT_ET_PLAN.md` | Audit et plan de modifications |
| `docs/Admiral_architecture_base_de_donnees.pdf` | Architecture de la base expliquée au client |
