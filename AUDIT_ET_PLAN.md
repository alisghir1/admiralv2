# Admiral v2 — Audit complet et plan de modifications

Date : 12 octobre 2026. Périmètre : `suivi_atelier.py` (2 401 lignes), scripts annexes, base SQLite, données Sage.

## 1. Verdict global

L'application est fonctionnelle dans ses grandes lignes et le concept métier est bon : commandes Sage → OF créés par le BE → gammes par opération → scans par poste → avancement. Le thème visuel « Slate » est cohérent.

Mais en l'état elle n'est **pas exploitable en atelier réel** pour quatre raisons :

1. **La création d'OF est cassée** : choisir un produit ne remplit ni la désignation ni la gamme, donc on ne peut cocher aucune opération et le bouton « Créer l'OF » refuse toujours.
2. **La base est locale à chaque PC** : les scans faits au poste DEC1 sont invisibles au poste FAC1. Un MES multi-postes a besoin d'une base partagée.
3. **Les étiquettes ne s'impriment pas** : sans code-barres physique, la douchette ne sert à rien ; seul le simulateur fonctionne.
4. **Le scan n'applique pas les règles métier** qu'affiche pourtant l'écran : on peut scanner un OF « Bloqué », scanner à un poste non prévu dans la gamme, et les scans manuels gonflent les compteurs des étapes précédentes.

Le code est un fichier unique de 2 400 lignes, sans test, avec 300 couleurs en dur et des requêtes SQL dans toutes les boucles. Il faut le restructurer avant d'ajouter des fonctionnalités.

## 2. Bugs confirmés

> **Phase 1 terminée (12/10/2026).** Tous les bugs ci-dessous sont corrigés et testés (20 tests sur une copie de la base). Bug supplémentaire trouvé pendant les tests :
> **B0 — Plantage des listes déroulantes** : `CTkComboBox(textvariable=…)` n'existe pas dans CustomTkinter 6 (le paramètre est `variable`). La fenêtre « Créer l'OF » et la fenêtre « Changer de poste » plantaient dès leur ouverture, tout comme le premier lancement d'un poste sans `config_poste.json`.

### Bloquants
| # | Bug | Où | Détail |
|---|-----|----|--------|
| B1 | Création d'OF impossible | `suivi_atelier.py:164` | `cb_prod.bind("<<ComboboxSelected>>", …)` : cet événement est propre à `ttk.Combobox`, `CTkComboBox` ne l'émet jamais (vérifié dans la lib). `on_prod_select` n'est jamais appelé → pas de gamme → « Veuillez cocher au moins une opération ». Correctif : `command=self.on_prod_select`. |
| B2 | Barre de recherche inutilisable à la souris | `:386` | Tout clic dans la fenêtre redonne le focus au champ scan après 100 ms, y compris un clic dans la recherche. Le texte tapé part dans le champ scan. |
| B3 | Scans manuels faussent les étapes précédentes | `:2180-2219` | `_add_scans_with_catchup` ajoute `amount_to_add` scans à **chaque** étape précédente, sans regarder si elle est déjà complète (`target_total_scans` calculé puis ignoré). Un « +1 » au poste TRE sur un OF déjà 5/5 en DEC donne 6/5 en DEC. |
| B4 | Scan douchette sans contrôle métier | `:2112-2142` | `process_scan` vérifie seulement `scans < qte`. Il ne vérifie ni que l'opération du poste est dans la gamme de l'OF, ni le `Poste_Assigne`, ni la disponibilité (étape précédente faite). L'écran affiche « Bloqué » mais le scan passe. |

### Importants
| # | Bug | Où | Détail |
|---|-----|----|--------|
| B5 | « \n » affiché en clair | `:1919`, `:2157` | `\\n` dans le source = backslash-n littéral. Le panneau flash et la frise affichent `...\nDimensions`. |
| B6 | Un OF ne peut couvrir qu'une seule ligne Sage | `:1044` | `tree_be_sage` est en `selectmode="browse"` ; le code additionne pourtant « toutes les lignes sélectionnées ». Un OF multi-lignes (comme OF-1001 du jeu de test) est impossible depuis l'UI. |
| B7 | Tri des commandes faux | `:1178-1181` | `sort_key` teste `tag == ''` qui n'arrive jamais ; « pas démarré » et « terminée » ont le même rang. |
| B8 | Deux vues, deux comptages | `:1778-1820` vs `:1505-1514` | Atelier répartit les scans « généraux » (sans `Child_Key`) sur les lignes enfants ; la Matrice ne compte que les scans à `Child_Key` précis. Les scans douchette n'ont jamais de `Child_Key` → la Matrice affiche 0/5 sur une ligne que l'Atelier montre 5/5. |
| B9 | Format `ART-` mort | `:2094-2102` | Il construit une clé `CCxxxx-1000` puis la cherche dans `CdeDetail.ID_OF` qui ne contient que des `OF-xxxx`. Ne peut jamais matcher. |
| B10 | Charge machines vide à l'ouverture | `:1612` | `refresh_be_charge` ne remplit que la liste des postes ; les colonnes Kanban restent vides tant qu'on ne clique pas un poste. |
| B11 | Double rafraîchissement | `:974-985` | `on_be_tab_changed` rafraîchit Matrice/Charge deux fois ; `on_main_tab_changed` une troisième. |

### Mineurs
- `change_poste` écrit « TABLEAU DE BORD \| POSTE : … » alors que l'en-tête initial est « POSTE : … » (`:1120` vs `:675`).
- Dialogues centrés avant d'être dessinés : `winfo_width()` vaut 1 → fenêtre décalée (`:73-78`, `:133-138`).
- Génération d'ID OF par tri alphabétique (`ORDER BY ID_OF DESC`) : casse à `OF-10000` (`:298`).
- `grab_set()` avant que la fenêtre soit visible : peut lever `grab failed: window not viewable` au tout premier lancement (ConfigDialog créé avant `build_ui`).
- `scan_counts`, `scans_globaux`, `load_scans_cache` : calculés, jamais lus.
- 9 `except:` nus qui masquent les erreurs.
- Le bouton « Imprimer Étiquettes » n'a pas de `command` (`:1073`).
- `crash.log` périmé (bug Tk 9 déjà corrigé, chemin `Desktop`).
- `patch_postes.py` et `refactor_kanban.py` : scripts de patch textuel qui ciblent du code `tk.Label` disparu → inutilisables.
- `setup_db.py` : chemin Windows en dur, `DROP TABLE` sans confirmation, schéma différent de `init_db` (clés étrangères, pas de `LignesSage` ni `Child_Key`).
- Police « Segoe UI » : absente sur macOS, remplacée silencieusement.

## 3. Problèmes techniques et d'architecture

### A1. Base de données locale par poste (critique)
`DB_FILE = APP_DIR/suivi_atelier.db`. Chaque PC d'atelier a sa propre base ; les scans ne se voient pas d'un poste à l'autre, la Matrice du BE ne reflète que son propre PC. Options :
- **Recommandé** : un petit serveur central (PostgreSQL, ou SQLite derrière une API FastAPI sur un PC/NAS) ; l'app devient un client.
- Minimum : `DB_FILE` sur un partage réseau avec SQLite en mode WAL + verrou applicatif. Fragile sur SMB, à éviter si plus de 2-3 postes.
À trancher avant tout : cela conditionne la structure du code.

### A2. Performance des requêtes
- `refresh_dashboard` appelle `get_order_progress` pour **chaque** commande, **deux fois** (liste Atelier + liste BE), avec 1 + N requêtes chacune, et `get_mon_op` refait une requête à chaque appel. Relancé **à chaque frappe** dans la recherche. Avec un export Sage réel (centaines de commandes), l'interface gèlera.
- `refresh_be_matrice` : 3 requêtes par OF × opérations × lignes enfants.
- Correctif : une seule requête agrégée (`GROUP BY ID_OF, RefOp`) chargée en mémoire, filtrage Python ; index sur `Scans(ID_OF, Poste)` ; debounce de 250 ms sur la recherche.

### A3. Structure du code
- Un fichier de 2 400 lignes, UI + SQL + règles métier mélangés dans les mêmes méthodes. Impossible à tester.
- 300 littéraux de couleur, 12 teintes répétées 7 à 44 fois.
- Pas de `requirements.txt` (dépendances : customtkinter 6, pillow, openpyxl). Pas de test. Pas de log applicatif.
- Deux définitions de schéma divergentes (`init_db` et `setup_db.py`).
- `Sotraglace_Suivi_Atelier.exe` (11 Mo) et `.venv` dans le dossier projet.

### A4. Import Sage
- Délimiteur `,` en dur et filtre `DO_Piece.startswith('CC')` : les exports Sage 100 sont souvent en `;` / cp1252 et le préfixe de pièce est paramétrable. À confirmer avec un vrai export.
- Aucun filtre d'ancienneté : toutes les commandes du CSV s'affichent pour toujours. Il faut un statut « clos » ou un filtre date/livré.
- Pas d'horodatage ni d'indicateur « dernière actualisation CSV ».

### A5. Modèle de données
- Les dimensions d'un OF sont stockées dans `OBSERV` (« 1200 x 800 mm ») et affichées sous « DIMENSIONS ». Il manque `Longueur`/`Largeur`/`Epaisseur` sur l'OF, alors que Sage les fournit (`LONG`, `LARG`).
- `Scans` a un `Timestamp` jamais affiché ; pas d'opérateur, pas de motif d'annulation → aucune traçabilité.
- Pas de statut d'OF (ouvert / terminé / annulé), pas de priorité ni de date de besoin.
- Suppression d'un scan = `DELETE` physique : pas d'historique.

## 4. Manques fonctionnels

| Priorité | Manque | Impact |
|----------|--------|--------|
| Haute | **Impression d'étiquettes** avec code-barres (Code 128 ou QR) par OF, et par ligne Sage si besoin | Sans ça, pas de douchette possible |
| Haute | **Modifier / supprimer un OF** (quantité, gamme, poste, observations) | Toute erreur de saisie est définitive |
| Haute | **Administration** des Produits, Opérations, Postes, Gammes depuis l'UI (ou import Excel guidé) | Aujourd'hui uniquement via `setup_db.py` qui efface tout |
| Haute | **Contrôle du scan** : refus si poste non concerné, si étape précédente incomplète, avec message clair | Fiabilité des données |
| Moyenne | **Historique des scans** par OF (date, heure, poste) et annulation tracée | Traçabilité, litiges |
| Moyenne | **Clôture / archivage** des commandes livrées | Listes qui grossissent sans fin |
| Moyenne | **Vue « Charge » utile** : compteurs par poste, pièces en attente, retard, cliquable vers l'OF | Pilotage BE |
| Moyenne | **Indicateurs** : pièces du jour par poste, OF en retard, taux d'avancement global | Direction / chef d'atelier |
| Basse | Export CSV/Excel de l'avancement | Reporting |
| Basse | Scan d'une commande entière (`CMD-`) : auto-sélection déjà gérée, mais pas d'action groupée | Confort |

## 5. Visuel et UX/UI

### Ce qui est bien
- Palette slate sombre cohérente, adaptée à un atelier (faible luminance, bon contraste).
- Zone de scan bien visible, retour coloré plein écran (bandeau vert/rouge) : parfait pour une lecture à distance.
- Panneau « flash » après scan avec gros chiffres de progression.

### Ce qui pose problème
1. **Deux widgets, deux styles** : `ttk.Treeview` (thème clam) et `tk.Listbox` cohabitent avec CustomTkinter. Les Listbox du Kanban « Charge » n'ont ni couleurs d'état, ni compteur, ni clic.
2. **Frise incohérente** : à l'ouverture elle montre les **postes** ; dès qu'on sélectionne un OF elle montre les **opérations**. L'opérateur voit la structure changer sous ses yeux.
3. **Tailles atelier** : boutons de 32-36 px, police 11-12 px dans les tableaux. Pour un opérateur debout, à un mètre, parfois ganté, il faut ≥ 44 px de hauteur, texte ≥ 14 px, lignes de tableau ≥ 44 px.
4. **Statuts textuels trop longs** dans un tableau étroit (« Bloqué (Étape précédente non finie) », « Prêt à produire : 3 dispo ») : préférer une pastille colorée + un mot, le détail en infobulle ou dans le panneau latéral.
5. **Le bandeau d'état ne se réinitialise jamais** : une erreur reste rouge jusqu'au prochain scan. Prévoir un retour au neutre après 5-6 s.
6. **Tout en MAJUSCULES** (titres, onglets, boutons) : lisibilité réduite, surtout pour les libellés longs (« BUREAU D'ÉTUDE (Nomenclatures) »).
7. **Bordures partout** : chaque carte a une bordure 1 px + coins arrondis + carte imbriquée. Ça « grille » l'écran. Garder les bordures pour les zones interactives, utiliser le contraste de fond pour les conteneurs.
8. **Onglet BE** : trois sous-onglets dans un onglet, avec en-tête dupliqué (« BUREAU D'ÉTUDE — Matrice »). Une barre latérale ou des onglets de premier niveau seraient plus directs.
9. **Dialogue « Créer l'OF »** : 740×720 fixe, combobox de produits sans recherche (illisible à 200 produits), cases à cocher + combobox par opération serrées.
10. **Pas de mode clair** ni de choix : certains ateliers très éclairés préfèrent un fond clair. Pas prioritaire, mais à prévoir via des jetons de couleur.
11. **Police** : « Segoe UI » n'existe pas sur macOS. Utiliser une police système selon la plateforme, ou embarquer Inter/Fira Sans.

### Propositions visuelles
- **Jetons de design** centralisés (module `theme.py`) : fond, carte, surface, bordure, texte, texte atténué, accent, succès, avertissement, erreur, info ; tailles de police S/M/L/XL ; espacements 4/8/12/16/24. La base UI/UX installée recommande pour ce type d'écran : fond `#020617`, cartes `#0E1223`, bordure `#334155`, accent vert `#16A34A` (« running »), rouge `#DC2626` (« failed »), ambre (« queued »), typographie Fira Sans / Fira Code pour les chiffres. C'est très proche de la palette actuelle : on garde l'esprit, on nettoie.
- **Écran Atelier** réorganisé en trois bandes claires : (1) en-tête compact poste + actions, (2) zone centrale : liste des commandes à gauche (40 %), détail de la commande à droite avec les OF en **cartes** (pastille d'état, désignation, dimensions en gros, `3 / 5`, bouton +1 large) plutôt qu'un Treeview à 7 colonnes, (3) bandeau scan en bas, inchangé.
- **Frise toujours par opérations**, avec le poste courant surligné, et un état par étape : fait / en cours / à faire / bloqué.
- **Kanban « Charge »** en vraies cartes colorées par état, compteur par colonne, clic → sélectionne l'OF.
- **Matrice** : une couleur de cellule par état (`-` gris, `0/5` neutre, `2/5` ambre, `5/5` vert) au lieu du texte seul.
- **Dialogue OF** : champ produit avec filtre texte, dimensions L × l dédiées pré-remplies depuis Sage, gamme en liste ordonnée avec poste par ligne, bouton principal unique.
- **Micro-interactions sobres** : surbrillance 150 ms sur la ligne scannée, pas d'animation ailleurs.

## 6. Plan de modifications détaillé

Chaque phase est livrable seule. Les durées sont indicatives (travail avec Claude).

### Décisions en attente (reportées par le client le 12/10/2026, à reprendre plus tard)
- **D1 — Base partagée** entre les postes : serveur central ou fichier sur partage réseau ? (le chemin est déjà configurable)
- **D2 — Export Sage réel** : un vrai `F-DOCENTETE.csv` / `F-DOCLIGNE.csv` pour valider colonnes, séparateur et encodage.
- **D3 — Étiquettes** : imprimante (PDF / Zebra ZPL / planche A4), format (100×50, 50×30, 100×150…), une étiquette par pièce ou par OF. À voir avec le client. **L'impression d'étiquettes attend cette réponse.**
- **D4 — Postes cibles** : Windows seul ou aussi macOS ? écrans tactiles ?
- **D5 — Opérateur** : le poste suffit-il, ou faut-il un code opérateur (prise de poste ou badge) ? **L'historique des scans est prêt à recevoir cette information.**

### Phase 0 — Décisions préalables (toi)
- D1. Base partagée : serveur central (recommandé) ou fichier SQLite sur partage réseau ?
- D2. Format réel des exports Sage (un vrai `F-DOCENTETE.csv` / `F-DOCLIGNE.csv`) : délimiteur, encodage, colonnes, préfixe des pièces, présence de `LONG`/`LARG`/épaisseur.
- D3. Étiquettes : imprimante (Zebra/Brother ? format 50×30 ? 100×50 ?), code-barres ou QR, une étiquette par OF ou par pièce ?
- D4. Cibles : Windows uniquement en atelier, ou aussi macOS ? Écrans tactiles ?
- D5. Faut-il identifier l'opérateur (badge / code) ou le poste suffit-il ?

### Phase 1 — Corrections de bugs et nettoyage (½ journée)
1. B1 : `command=self.on_prod_select` sur la combobox produit.
2. B2 : ne forcer le focus scan que si le clic n'est pas dans un champ de saisie.
3. B3 : réécrire le rattrapage : pour chaque étape précédente, n'ajouter que `max(0, nouveau_total_mon_étape − total_étape_précédente)`.
4. B4 : fonction unique `verifier_scan(id_of, codpost)` qui retourne OK ou un motif (opération absente de la gamme, poste non assigné, étape précédente incomplète, quantité atteinte), utilisée par la douchette **et** les boutons manuels.
5. B5 : `\n` réels. B6 : `selectmode="extended"`. B7 : tri sur `encours < pas_demarre < terminee`. B9 : supprimer `ART-`. B10/B11 : un seul rafraîchissement, Kanban rempli à l'ouverture sur le premier poste.
6. Mineurs : centrage des dialogues après `update_idletasks()` + `wait_visibility()` avant `grab_set`, ID OF via `MAX(CAST(SUBSTR(ID_OF,4) AS INTEGER))`, en-tête poste cohérent, suppression du code mort (`scan_counts`, `scans_globaux`, scripts de patch, `crash.log`), `except Exception as e` + log.
7. Ajouter `requirements.txt`, `.gitignore` pour `.venv`, `README` mis à jour.
8. Mettre `setup_db.py` au même schéma que l'app ou le supprimer au profit d'un import depuis l'UI (phase 4).

### Phase 2 — Restructuration technique (1 à 1,5 jour)

> **Terminée (12/10/2026).** Paquet `admiral/` en place, 37 tests automatisés (28 unitaires + 9 scénarios d'interface). Sur 500 commandes / 1 500 OF / 11 500 scans : liste des commandes 856 ms → 10 ms, Matrice 2,6 s → 23 ms. Écart avec le plan : **pas de mode WAL**, car il ne fonctionne pas sur un partage réseau ; à la place, délai d'attente de 10 s sur les verrous. Le chemin de la base et du dossier Sage est configurable dans `config_poste.json` (décision D1 toujours ouverte).

Découper `suivi_atelier.py` en paquet, sans changer le comportement :
```
admiral/
  main.py              # point d'entrée
  config.py            # chemins, poste courant
  theme.py             # jetons de couleurs/polices/espacements
  db/
    schema.py          # création + migrations versionnées
    repository.py      # toutes les requêtes SQL (une fonction = une requête)
  domain/
    sage.py            # lecture CSV Sage, détection délimiteur/encodage
    progression.py     # calculs d'avancement, règles de scan (pur Python, testable)
  ui/
    app.py             # fenêtre principale, onglets
    atelier.py         # écran atelier
    be_generation.py   # création d'OF
    be_matrice.py
    be_charge.py
    dialogs.py         # ConfigDialog, AddOfDialog
    widgets.py         # Treeview stylé, carte OF, pastille d'état
tests/
  test_progression.py  # règles métier (sans UI)
  test_sage.py
```
- Index SQL sur `Scans(ID_OF, Poste)`, `OF_Gammes(ID_OF, Ordre)`, `CdeDetail(CDE)`.
- Un seul calcul d'avancement agrégé par rafraîchissement, résultats en mémoire, debounce 250 ms sur la recherche.
- Migrations de schéma versionnées (table `meta(version)`), au lieu de `ALTER … except`.
- Si D1 = serveur : couche `repository.py` prête à être remplacée par un client HTTP ; sinon, chemin de base configurable + WAL.
- Journalisation dans `logs/admiral.log` (rotation) au lieu de `crash.log`.

### Phase 3 — Refonte visuelle et UX (1 à 1,5 jour)

> **Terminée (12/10/2026).** 46 tests automatisés, audit géométrique sans défaut à 1440×860 et à la taille minimale 1180×720. Écarts avec le plan :
> - **Matrice** : un tableau ttk ne sait pas colorer une cellule isolée ; chaque cellule porte un symbole d'état (✓ ◐ ○ —) et la ligne est teintée.
> - **Polices** : les polices Fira recommandées ne se chargent pas dans Tkinter ; police système (Segoe UI sous Windows, Helvetica Neue sous macOS) et police à chasse fixe pour les chiffres et codes.
> - **Contrastes corrigés** : boutons verts (3,8:1 → 5,5:1) et ambre (texte blanc 3,2:1 → texte sombre 5,9:1).
> - **Bouton « Imprimer étiquettes » retiré** jusqu'à la phase 4 (il ne faisait rien).
> - **Dimensions d'OF en champs dédiés** (migration 3 : Longueur, Largeur, Epaisseur) ; les anciens OF gardent leurs dimensions dans Observations.
> - **Gamme standard pré-cochée** à la création d'un OF ; « Tout annuler » demande confirmation.
1. `theme.py` + composants réutilisables (`Carte`, `Pastille`, `BoutonPrincipal`, `TableauStyle`) ; police selon plateforme.
2. Écran Atelier : cartes OF, frise par opérations unique, tailles atelier (boutons 48 px, texte 14-16 px, lignes 44 px), bandeau d'état qui revient au neutre après 6 s, statuts en pastille + mot.
3. Onglet BE : navigation simplifiée (onglets de premier niveau : Atelier · Génération OF · Matrice · Charge · Administration), suppression des en-têtes en double, casse normale.
4. Kanban Charge en cartes colorées + compteurs ; Matrice avec cellules colorées.
5. Dialogue OF : produit filtrable, dimensions dédiées (L × l × ép.) pré-remplies depuis la ligne Sage, gamme ordonnée.

### Phase 4 — Fonctionnalités manquantes (2 à 3 jours selon D3)

> **Terminée le 12/10/2026, sauf l'impression d'étiquettes (en attente de D3).** 67 tests automatisés, audit de mise en page sans défaut (écrans et fenêtres, y compris sur un portable 1366×768). Livré :
> - **OF** : modification (désignation, quantité ≥ pièces déjà scannées, dimensions, observations, date de besoin, urgence, postes assignés), annulation / réactivation, suppression seulement s'il n'a jamais été scanné.
> - **Scans** : annulation tracée (le scan reste dans l'historique, marqué « annulé le … ») ; fenêtre « Historique des scans » depuis l'atelier (menu « Plus ») et le Bureau d'Étude.
> - **Commandes** : clôture / réouverture ; une commande clôturée disparaît de l'atelier et ses OF ne se scannent plus.
> - **Priorité et date de besoin** : pastille « Urgent », date en rouge si dépassée, OF urgents en tête des cartes.
> - **Onglet Synthèse** : pièces du jour, OF à faire / en cours / terminés / en retard, avancement global, tableau par poste, OF à surveiller (actualisation automatique chaque minute).
> - **Onglet Administration** : produits et gammes (opérations réordonnables), opérations, postes, avec refus explicite de supprimer un élément utilisé ; import du référentiel Excel avec aperçu, sans toucher aux OF ni aux scans (même lecture que `setup_db.py`).
> - Schéma de base en version 4 (migration automatique).
> - Écart : le code opérateur (D5) n'est pas ajouté ; l'historique indique le poste, la date et l'heure.
1. **Étiquettes** : génération PDF (reportlab + python-barcode/qrcode) ou impression directe ZPL si Zebra ; aperçu avant impression ; une étiquette par OF (+ option par pièce avec `OF-1001/3`).
2. **Édition / suppression d'OF** avec garde-fou si des scans existent.
3. **Administration** : écrans Produits / Opérations / Postes / Gammes avec import Excel guidé (remplace `setup_db.py`).
4. **Historique des scans** par OF et annulation tracée (colonne `Annule`, `Motif`, au lieu du `DELETE`).
5. **Clôture de commande** et filtre « masquer les clôturées ».
6. **Tableau de bord** : pièces du jour par poste, OF bloqués, avancement global.
7. Champs OF : `Longueur`, `Largeur`, `Epaisseur`, `Statut`, `DateBesoin`, `Priorite`.

### Phase 5 — Déploiement (½ journée)
- Script de build Windows (PyInstaller) propre avec icône et version ; `Lancer_Admiral.command` pour macOS.
- Procédure d'installation d'un poste : copier l'exe, créer `config_poste.json`, pointer vers la base partagée / le serveur.
- Jeu de données de test réaliste (`seed_mock_data.py` étendu) + tests automatisés sur les règles métier.

## 7. Ordre que je recommande

1. Tu réponds aux décisions D1 à D5.
2. Phase 1 immédiatement (petite, rend l'app utilisable pour les tests).
3. Phase 2 avant toute refonte visuelle : refaire l'UI sur un code monolithique reviendrait à tout refaire deux fois.
4. Phases 3 et 4 en parallèle par écran (chaque écran refait reçoit en même temps ses nouvelles fonctions).
5. Phase 5 quand un premier poste pilote est prêt.
