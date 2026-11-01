"""Lecture des données Sage (en-têtes et lignes de commandes).

Deux sources possibles dans le dossier Sage :
- le classeur Excel relié à Sage (« BASE SAGE ADM.xlsx »), actualisé depuis Sage par le client ;
- à défaut, les exports CSV (F-DOCENTETE.csv, F-DOCLIGNE.csv).
Dans les deux cas, les lignes sont des dictionnaires de textes avec les noms de colonnes de Sage.
"""
import csv
import os
from dataclasses import dataclass, field
from datetime import date, datetime

# Seules les pièces dont le numéro commence par ce préfixe sont des commandes clients
PREFIXE_COMMANDE = "CC"

FICHIERS_ENTETES = ("F-DOCENTETE.csv", "docentete.csv")
FICHIERS_LIGNES = ("F-DOCLIGNE.csv", "docligne.csv")

# Feuilles du classeur, comparées sans tirets ni casse (« F-DOCLIGNE », « F_DOCLIGNE »)
FEUILLE_ENTETES = "FDOCENTETE"
FEUILLE_LIGNES = "FDOCLIGNE"

# Colonnes renommées par Excel -> nom de la colonne dans Sage (les autres gardent leur nom)
COLONNES_CLASSEUR = {
    "TYPE": "DO_Type",
    "CDE": "DO_Piece",
    "DATE": "DO_Date",
    "CODECLI": "DO_Tiers",
    "REFCLI": "DO_Coord01",
    "DELAI": "DO_DateLivr",
    "CLIDIV": "Client Divers",
    "NUM": "cbMarq",
    "NUMCLI": "CT_Num",
    "ART": "AR_Ref",
    "DESIGN": "DL_Design",
    "UNIT": "EU_Enumere",
    "QTE": "DL_Qte",
    "LIGNE": "DL_Ligne",
}


class SageIllisible(Exception):
    """Le classeur Sage existe mais ne peut pas être lu (en cours d'enregistrement, abîmé, openpyxl absent)."""


@dataclass
class DonneesSage:
    entetes: dict = field(default_factory=dict)           # DO_Piece -> ligne CSV
    lignes: dict = field(default_factory=dict)            # "DO_Piece-DL_Ligne" -> ligne CSV
    lignes_par_piece: dict = field(default_factory=dict)  # DO_Piece -> [(clé, ligne CSV)]
    source: str = ""                                      # fichier lu (classeur ou CSV des lignes)
    date_source: str = ""                                 # enregistrement du fichier, « AAAA-MM-JJTHH:MM:SS »

    def lignes_commande(self, do_piece):
        return self.lignes_par_piece.get(do_piece, [])

    def client(self, do_piece, defaut="Inconnu"):
        return self.entetes.get(do_piece, {}).get("DO_Tiers", defaut)


@dataclass
class BilanSynchro:
    """Ce qu'une lecture de Sage a changé dans la copie de la base."""
    ignoree: str = ""                                     # motif si la lecture n'a pas été recopiée
    commandes_nouvelles: list = field(default_factory=list)
    commandes_sorties: list = field(default_factory=list)  # livrées, facturées ou supprimées dans Sage
    lignes_nouvelles: list = field(default_factory=list)
    lignes_modifiees: list = field(default_factory=list)
    lignes_sorties: list = field(default_factory=list)

    @property
    def changements(self):
        return bool(self.commandes_nouvelles or self.commandes_sorties or self.lignes_nouvelles
                    or self.lignes_modifiees or self.lignes_sorties)

    def resume(self):
        """« 2 nouvelles commandes · 1 sortie de Sage · 3 lignes modifiées », ou « aucun changement »."""
        def compte(liste, singulier, pluriel):
            return f"{len(liste)} {singulier if len(liste) == 1 else pluriel}" if liste else ""
        parties = [compte(self.commandes_nouvelles, "nouvelle commande", "nouvelles commandes"),
                   compte(self.commandes_sorties, "commande sortie de Sage", "commandes sorties de Sage"),
                   compte(self.lignes_nouvelles, "ligne ajoutée", "lignes ajoutées"),
                   compte(self.lignes_modifiees, "ligne modifiée", "lignes modifiées"),
                   compte(self.lignes_sorties, "ligne retirée", "lignes retirées")]
        return " · ".join(filter(None, parties)) or "aucun changement"


def lire_qte(valeur, defaut=1):
    """Quantité Sage ("5", "5.000", "5,000") en entier."""
    try:
        return int(float(str(valeur).replace(',', '.')))
    except (TypeError, ValueError):
        return defaut


def numero_ligne(ligne):
    """Clé de tri d'une ligne Sage : 1000, 2000, … 10000 dans l'ordre numérique (pas alphabétique)."""
    texte = str(ligne.get("DL_Ligne", "")).strip()
    try:
        return (0, float(texte.replace(",", ".")), texte)
    except ValueError:
        return (1, 0, texte)


def fabricable(ligne):
    """Ligne à fabriquer : un article et une quantité. Les lignes de texte, de commentaire ou de sous-total
    de Sage (sans référence article, ou à quantité nulle) ne vont pas dans un OF."""
    return bool(str(ligne.get("AR_Ref", "")).strip()) and lire_qte(ligne.get("DL_Qte", "0"), 0) > 0


def dimension_mm(valeur):
    """Dimension Sage ("600", "600.000", "600,5") en millimètres entiers, ou None si absente ou invalide."""
    try:
        nombre = round(float(str(valeur).strip().replace(',', '.')))
    except (TypeError, ValueError):
        return None
    return nombre if nombre > 0 else None


def dimensions_communes(lignes):
    """(longueur, largeur) en mm si toutes les lignes ont les mêmes dimensions, sinon (None, None)."""
    dims = {(dimension_mm(l.get("LONG")), dimension_mm(l.get("LARG"))) for l in lignes}
    return dims.pop() if len(dims) == 1 else (None, None)


def detecter_encodage(chemin):
    for encodage in ('utf-8-sig', 'cp1252'):
        try:
            with open(chemin, 'r', encoding=encodage) as f:
                f.read()
            return encodage
        except UnicodeDecodeError:
            continue
    return 'latin-1'  # accepte tous les octets


def detecter_separateur(premiere_ligne):
    return ';' if premiere_ligne.count(';') > premiere_ligne.count(',') else ','


def _lire_csv(chemin):
    encodage = detecter_encodage(chemin)
    with open(chemin, 'r', encoding=encodage, newline='') as f:
        separateur = detecter_separateur(f.readline())
        f.seek(0)
        return list(csv.DictReader(f, delimiter=separateur))


def _premier_existant(dossier, noms):
    for nom in noms:
        chemin = os.path.join(dossier, nom)
        if os.path.exists(chemin):
            return chemin
    return None


def texte_cellule(valeur):
    """Valeur d'une cellule du classeur écrite comme dans un export CSV : 1000.0 -> « 1000 », date -> « AAAA-MM-JJ »."""
    if valeur is None:
        return ""
    if isinstance(valeur, date):
        return "" if valeur.year <= 1753 else valeur.strftime("%Y-%m-%d")  # 01/01/1753 : date vide de Sage
    if isinstance(valeur, float) and valeur.is_integer():
        return str(int(valeur))
    return str(valeur).strip()


def _nom_feuille(nom):
    return "".join(c for c in nom.upper() if c.isalnum())


def _lire_feuille(feuille):
    """Lignes de commande d'une feuille du classeur, en dictionnaires avec les noms de colonnes de Sage."""
    lignes = feuille.iter_rows(values_only=True)
    entete = next(lignes, None) or ()
    colonnes = [COLONNES_CLASSEUR.get(texte_cellule(nom), texte_cellule(nom)) for nom in entete]
    if "DO_Piece" not in colonnes:
        return []
    index_piece = colonnes.index("DO_Piece")
    resultat = []
    for valeurs in lignes:
        # Filtre avant conversion : le classeur contient toutes les pièces (devis, factures, achats…)
        if len(valeurs) > index_piece and str(valeurs[index_piece] or "").strip().startswith(PREFIXE_COMMANDE):
            resultat.append({nom: texte_cellule(v) for nom, v in zip(colonnes, valeurs) if nom})
    return resultat


def _classeurs(dossier):
    """Classeurs .xlsx du dossier, du plus récent au plus ancien (sans les fichiers « ~$ » qu'Excel crée à l'ouverture)."""
    chemins = [os.path.join(dossier, nom) for nom in os.listdir(dossier)
               if nom.lower().endswith(".xlsx") and not nom.startswith("~$")]
    return sorted(chemins, key=os.path.getmtime, reverse=True)


def _lire_classeur_sage(dossier):
    """(chemin, en-têtes, lignes) du classeur Sage le plus récent du dossier, ou None s'il n'y en a pas.
    Un classeur sans les feuilles F-DOCENTETE et F-DOCLIGNE (le référentiel, par exemple) est ignoré."""
    chemins = _classeurs(dossier)
    if not chemins:
        return None
    try:
        import openpyxl
    except ImportError as exc:
        raise SageIllisible("La lecture du classeur Sage nécessite le module openpyxl "
                            "(pip install -r requirements.txt).") from exc
    for chemin in chemins:
        try:
            classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        except Exception as exc:  # fichier en cours d'enregistrement, abîmé…
            raise SageIllisible(f"{os.path.basename(chemin)} : {exc}") from exc
        try:
            feuilles = {_nom_feuille(nom): nom for nom in classeur.sheetnames}
            if FEUILLE_LIGNES not in feuilles:
                continue
            entetes = _lire_feuille(classeur[feuilles[FEUILLE_ENTETES]]) if FEUILLE_ENTETES in feuilles else []
            return chemin, entetes, _lire_feuille(classeur[feuilles[FEUILLE_LIGNES]])
        except Exception as exc:
            raise SageIllisible(f"{os.path.basename(chemin)} : {exc}") from exc
        finally:
            classeur.close()
    return None


def charger(dossier):
    """Lit les données Sage du dossier : le classeur Sage s'il y en a un, sinon les exports CSV.
    Retourne None si le dossier n'existe pas ; lève SageIllisible si le classeur ne peut pas être lu."""
    if not os.path.isdir(dossier):
        return None

    classeur = _lire_classeur_sage(dossier)
    if classeur:
        source, entetes, lignes = classeur
        fichiers = [source]
    else:
        chemin_entetes = _premier_existant(dossier, FICHIERS_ENTETES)
        chemin_lignes = _premier_existant(dossier, FICHIERS_LIGNES)
        entetes = _lire_csv(chemin_entetes) if chemin_entetes else []
        lignes = _lire_csv(chemin_lignes) if chemin_lignes else []
        source = chemin_lignes or chemin_entetes or ""
        fichiers = [chemin for chemin in (chemin_entetes, chemin_lignes) if chemin]

    # Date des données : l'enregistrement du fichier le plus récent (le classeur est enregistré après l'actualisation)
    enregistrement = max((os.path.getmtime(chemin) for chemin in fichiers), default=None)
    donnees = DonneesSage(source=source, date_source=datetime.fromtimestamp(enregistrement).isoformat(timespec="seconds")
                          if enregistrement else "")

    for row in entetes:
        do_piece = (row.get('DO_Piece') or '').strip()
        if do_piece.startswith(PREFIXE_COMMANDE):
            donnees.entetes[do_piece] = row

    for row in lignes:
        do_piece = (row.get('DO_Piece') or '').strip()
        if row.get('DL_Ligne') is None or not do_piece.startswith(PREFIXE_COMMANDE):
            continue
        cle = f"{do_piece}-{row['DL_Ligne'].strip()}"
        donnees.lignes[cle] = row
        donnees.lignes_par_piece.setdefault(do_piece, []).append((cle, row))

    return donnees


def cle_complete(do_piece, cle):
    """« 1000 » ou « CC1-1000 » -> « CC1-1000 » (les anciens OF stockaient parfois la clé courte)."""
    cle = cle.strip()
    return cle if cle.startswith(f"{do_piece}-") else f"{do_piece}-{cle}"


def lignes_enfants(donnees, do_piece, lignes_sage):
    """Lignes Sage rattachées à un OF : [(clé stockée, quantité, ligne CSV)].
    Les lignes sorties de Sage restent dans donnees.lignes (copie de la base) ; les clés introuvables sont ignorées."""
    if not lignes_sage:
        return []
    resultat = []
    for cle in lignes_sage.split(","):
        cle = cle.strip()
        ligne = donnees.lignes.get(cle_complete(do_piece, cle)) if cle else None
        if ligne:
            resultat.append((cle, lire_qte(ligne.get("DL_Qte", "1")), ligne))
    return resultat


def dimensions(ligne):
    longueur, largeur = ligne.get("LONG", ""), ligne.get("LARG", "")
    return f"{longueur}x{largeur}" if longueur and largeur else ""
