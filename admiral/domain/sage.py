"""Lecture des données Sage (en-têtes et lignes de commandes).

Deux sources possibles dans le dossier Sage :
- le classeur Excel relié à Sage (« BASE SAGE Admiral.xlsx », feuilles DOCENTETE et DOCLIGNE, ou l'ancien
  « BASE SAGE ADM.xlsx », feuilles F-DOCENTETE et F-DOCLIGNE), actualisé depuis Sage par le client ;
- à défaut, les exports CSV (F-DOCENTETE.csv, F-DOCLIGNE.csv).
Dans les deux cas, les lignes sont des dictionnaires de textes avec les noms de colonnes de Sage.
"""
import csv
import os
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from .synthese import format_date

# Seules les pièces dont le numéro commence par ce préfixe sont des commandes clients
PREFIXE_COMMANDE = "CC"

FICHIERS_ENTETES = ("F-DOCENTETE.csv", "docentete.csv")
FICHIERS_LIGNES = ("F-DOCLIGNE.csv", "docligne.csv")

# Feuilles du classeur, comparées sans tirets ni casse et sans le « F » de Sage (« DOCLIGNE », « F-DOCLIGNE »)
FEUILLE_ENTETES = "DOCENTETE"
FEUILLE_LIGNES = "DOCLIGNE"

# Colonnes du classeur -> nom de la colonne dans Sage (les autres gardent leur nom : LONG, LARG, Chant-L…).
# Les noms sont comparés sans accents, espaces, tirets ni casse (« Désignation » = « DESIGNATION »).
# Deux versions du classeur : celle des commandes en cours (Commande, CodeCli, Client, Quantité…)
# et l'ancienne, sur les tables entières de Sage (CDE, CODECLI, QTE…).
# « Client » n'a pas le même sens dans les deux feuilles : le nom du client dans les en-têtes, son code dans les lignes.
COLONNES_ENTETES = {
    "TYPE": "DO_Type",
    "COMMANDE": "DO_Piece", "CDE": "DO_Piece",
    "DATE": "DO_Date",
    "CODECLI": "DO_Tiers",
    "CLIENT": "CT_Intitule",
    "CLIENTDIVERS": "Client Divers", "CLIDIV": "Client Divers",
    "REFCLIENT": "DO_Coord01", "REFCLI": "DO_Coord01",
    "DELAI": "DO_DateLivr",
    "OBSERVATIONS": "OBSERV", "OBSERV": "OBSERV",
    "NUM": "cbMarq",
}
COLONNES_LIGNES = {
    "TYPE": "DO_Type",
    "CLIENT": "CT_Num", "NUMCLI": "CT_Num",
    "COMMANDE": "DO_Piece", "CDE": "DO_Piece",
    "ARTICLE": "AR_Ref", "ART": "AR_Ref",
    "DESIGNATION": "DL_Design", "DESIGN": "DL_Design",
    "QUANTITE": "DL_Qte", "QTE": "DL_Qte",
    "UNIT": "EU_Enumere",
    "DLLIGNE": "DL_Ligne", "LIGNE": "DL_Ligne",
    "NUM": "cbMarq",
}

# Unité de vente : les vues donnent son numéro dans Sage, l'ancien classeur son libellé (vérifié sur les mêmes lignes)
UNITES = {"1": "ML", "2": "M2", "3": "U"}


# Observation de Sage -> niveau d'alerte (mots cherchés sans accents ni casse, fautes de frappe comprises)
MOTS_BLOQUANTS = ("ANNUL", "BLOQU")                                      # ne pas produire
MOTS_ALERTE = ("ATTENTE", "RUPTUR", "REPTU", "STOCK", "MANQU")           # production gênée


@dataclass
class InfosCommande:
    """Informations Sage d'une commande, en plus du client ; vides quand le classeur ne les donne pas."""
    reference: str = ""      # référence du client pour sa commande, souvent le chantier (« Villa des Pins »)
    date: str = ""           # date de la commande, « AAAA-MM-JJ »
    delai: str = ""          # livraison prévue, « AAAA-MM-JJ »
    observations: str = ""   # remarque saisie dans Sage (« EN ATTENTE MESURE », « ANNULEE »…)

    @property
    def niveau(self):
        """« bloque » (annulée, bloquée), « alerte » (en attente, rupture de stock) ou « info »."""
        cle = _cle_nom(self.observations)
        if any(mot in cle for mot in MOTS_BLOQUANTS):
            return "bloque"
        if any(mot in cle for mot in MOTS_ALERTE):
            return "alerte"
        return "info"

    def textes(self, avec_date=True, aujourd_hui=None):
        """(contexte, délai, délai dépassé) à afficher sous le titre de la commande :
        (« Réf. client : Villa des Pins · Commandée le 11/09/2025 · », « Délai : 10/11 », False)."""
        parties = [f"Réf. client : {self.reference}" if self.reference else "",
                   f"Commandée le {format_date(self.date)}" if avec_date and self.date else ""]
        contexte = " · ".join(filter(None, parties))
        if not self.delai:
            return contexte, "", False
        depasse = self.delai < (aujourd_hui or date.today()).isoformat()
        delai = f"{'Délai dépassé' if depasse else 'Délai'} : {format_date(self.delai)}"
        return (contexte + " · " if contexte else ""), delai, depasse


class SageIllisible(Exception):
    """Le classeur Sage existe mais ne peut pas être lu (en cours d'enregistrement, abîmé, openpyxl absent)."""


@dataclass
class DonneesSage:
    entetes: dict = field(default_factory=dict)           # DO_Piece -> ligne CSV
    lignes: dict = field(default_factory=dict)            # "DO_Piece-DL_Ligne" -> ligne CSV
    lignes_par_piece: dict = field(default_factory=dict)  # DO_Piece -> [(clé, ligne CSV)]
    entetes_sorties: dict = field(default_factory=dict)   # DO_Piece -> en-tête des commandes sorties de Sage (copie)
    source: str = ""                                      # fichier lu (classeur ou CSV des lignes)
    date_source: str = ""                                 # enregistrement du fichier, « AAAA-MM-JJTHH:MM:SS »
    # Point de départ de la remise à zéro (Depot.depart) : les commandes d'avant ne sont plus listées
    depart: tuple = None                                  # (jour « AAAA-MM-JJ », moment « AAAA-MM-JJTHH:MM:SS ») ou None
    anterieures: set = field(default_factory=set)         # commandes d'avant le point de départ, masquées

    def lignes_commande(self, do_piece):
        return self.lignes_par_piece.get(do_piece, [])

    def _entete(self, do_piece):
        """En-tête de la commande, même sortie de Sage (livrée) : ses OF restent affichés avec leur client."""
        return self.entetes.get(do_piece) or self.entetes_sorties.get(do_piece) or {}

    def nom_client(self, do_piece):
        """Nom exact du client : celui du client de passage (« Client Divers ») s'il est saisi, sinon le nom du compte."""
        entete = self._entete(do_piece)
        return (entete.get("Client Divers") or "").strip() or (entete.get("CT_Intitule") or "").strip()

    def client(self, do_piece, defaut="Inconnu"):
        """Client à afficher : « AGENCEMENTS DU LITTORAL (C0901) », le nom exact du client et le code de son compte Sage.
        Le nom d'abord : dans une colonne étroite, c'est le code qui est coupé. Sans nom (anciens classeurs), le code seul."""
        code = (self._entete(do_piece).get("DO_Tiers") or "").strip()
        nom = self.nom_client(do_piece)
        if not nom or nom.upper() == code.upper():
            return code or defaut
        return f"{nom} ({code})" if code else nom

    def infos_commande(self, do_piece):
        entete = self._entete(do_piece)
        return InfosCommande(reference=(entete.get("DO_Coord01") or "").strip(),
                             date=lire_date_sage(entete.get("DO_Date")),
                             delai=lire_date_sage(entete.get("DO_DateLivr")),
                             observations=(entete.get("OBSERV") or "").strip())

    def texte_recherche(self, do_piece):
        """Texte où cherchent les listes de commandes : numéro, client, réf. client et observation de Sage."""
        infos = self.infos_commande(do_piece)
        return " ".join((do_piece, self.client(do_piece, ""), infos.reference, infos.observations)).lower()

    def client_pour_tri(self, do_piece):
        """Tri « Client (A → Z) » : par nom du client (le code seul quand le nom manque)."""
        return self.nom_client(do_piece) or self.client(do_piece, "")


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


def _cle_nom(nom):
    """« Désignation » -> « DESIGNATION », « F-DOCLIGNE » -> « FDOCLIGNE » : sans accents, espaces, tirets ni casse."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in sans_accents.upper() if c.isalnum())


def _trouver_feuille(feuilles, nom):
    """Nom réel de la feuille « DOCLIGNE » (ou « F-DOCLIGNE », « F_DOCLIGNE »…) du classeur, ou None."""
    return next((feuille for feuille in feuilles if _cle_nom(feuille) in (nom, "F" + nom)), None)


def _lire_feuille(feuille, correspondance):
    """Lignes de commande d'une feuille du classeur, en dictionnaires avec les noms de colonnes de Sage."""
    lignes = feuille.iter_rows(values_only=True)
    entete = next(lignes, None) or ()
    colonnes = [correspondance.get(_cle_nom(texte_cellule(nom)), texte_cellule(nom)) for nom in entete]
    if "DO_Piece" not in colonnes:
        return []
    index_piece = colonnes.index("DO_Piece")
    resultat = []
    for valeurs in lignes:
        # Filtre avant conversion : l'ancien classeur contient toutes les pièces (devis, factures, achats…)
        if len(valeurs) > index_piece and str(valeurs[index_piece] or "").strip().startswith(PREFIXE_COMMANDE):
            ligne = {nom: texte_cellule(v) for nom, v in zip(colonnes, valeurs) if nom}
            if ligne.get("EU_Enumere") in UNITES:
                ligne["EU_Enumere"] = UNITES[ligne["EU_Enumere"]]
            resultat.append(ligne)
    return resultat


def _classeurs(dossier):
    """Classeurs .xlsx du dossier, du plus récent au plus ancien (sans les fichiers « ~$ » qu'Excel crée à l'ouverture)."""
    chemins = [os.path.join(dossier, nom) for nom in os.listdir(dossier)
               if nom.lower().endswith(".xlsx") and not nom.startswith("~$")]
    return sorted(chemins, key=os.path.getmtime, reverse=True)


def _lire_classeur_sage(dossier):
    """(chemin, en-têtes, lignes) du classeur Sage le plus récent du dossier, ou None s'il n'y en a pas.
    Un classeur sans feuille DOCLIGNE (ou F-DOCLIGNE) est ignoré : le référentiel, par exemple."""
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
            feuille_lignes = _trouver_feuille(classeur.sheetnames, FEUILLE_LIGNES)
            if feuille_lignes is None:
                continue
            feuille_entetes = _trouver_feuille(classeur.sheetnames, FEUILLE_ENTETES)
            entetes = _lire_feuille(classeur[feuille_entetes], COLONNES_ENTETES) if feuille_entetes else []
            return chemin, entetes, _lire_feuille(classeur[feuille_lignes], COLONNES_LIGNES)
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


# --- Données de commande et de ligne à afficher ---

def lire_date_sage(texte):
    """Date Sage en « AAAA-MM-JJ », ou "" si absente ou vide (01/01/1753 dans Sage).
    Classeur : « 2026-11-10 » ; anciens exports CSV : « 7/29/24 0:00 » (mois/jour) ; démonstration : « 29/07/2026 »."""
    texte = str(texte or "").strip().split(" ")[0]
    try:
        if "-" in texte:
            jour = datetime.strptime(texte[:10], "%Y-%m-%d").date()
        elif len(texte.rsplit("/", 1)[-1]) == 2:
            jour = datetime.strptime(texte, "%m/%d/%y").date()
            if (jour.month, jour.day, jour.year % 100) == (1, 1, 53):   # 01/01/1753 sur deux chiffres
                return ""
        else:
            jour = datetime.strptime(texte, "%d/%m/%Y").date()
    except ValueError:
        return ""
    return "" if jour.year <= 1753 else jour.isoformat()


def commande_nouvelle(entete, date_entree, depart):
    """La commande est-elle arrivée après la remise à zéro de l'atelier ?

    depart : (jour « AAAA-MM-JJ », moment « AAAA-MM-JJTHH:MM:SS ») de la remise à zéro, ou None (tout est affiché).
    Nouvelle = arrivée dans la copie de la base (date_entree, première lecture) après la remise à zéro, ET datée
    dans Sage du jour de la remise à zéro ou après. Les commandes déjà dans le classeur à la remise à zéro restent
    donc masquées, comme une ancienne commande qui n'arriverait qu'ensuite (classeur pas actualisé depuis longtemps)."""
    if not depart:
        return True
    jour, moment = depart
    if not (date_entree and date_entree > moment):
        return False
    date_commande = lire_date_sage(entete.get("DO_Date"))
    return not date_commande or date_commande >= jour


def nombre(valeur):
    """Nombre Sage (« 7.6 », « 7,6 ») en flottant, ou None."""
    try:
        return float(str(valeur).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def ecrire_nombre(valeur, decimales=2):
    """2.0 -> « 2 », 7.6 -> « 7,6 », 0.4234 -> « 0,42 » : virgule française, sans zéro inutile."""
    return f"{valeur:.{decimales}f}".rstrip("0").rstrip(".").replace(".", ",")


def quantite(ligne):
    """Quantité affichée : « 2 » pour des pièces (unité U), avec l'unité sinon (« 7,6 ML », « 9 M2 »)."""
    qte = nombre(ligne.get("DL_Qte"))
    if qte is None:
        return ""
    unite = (ligne.get("EU_Enumere") or "").strip()
    texte = ecrire_nombre(qte, 3)
    return texte if unite.upper() in ("", "U") else f"{texte} {unite}"


def chants(ligne):
    """Chants à poser, notés comme dans les désignations de Sage (« 1H+2L ») ; vide s'ils ne sont pas précisés."""
    hauteur, largeur = (lire_qte(ligne.get(colonne), 0) for colonne in ("Chant-H", "Chant-L"))
    return "+".join(filter(None, (f"{hauteur}H" if hauteur else "", f"{largeur}L" if largeur else "")))


def chants_communs(lignes):
    """Chants de lignes qui ont toutes les mêmes, sinon ""."""
    valeurs = {chants(ligne) for ligne in lignes}
    return valeurs.pop() if len(valeurs) == 1 else ""


def resume_lignes(lignes):
    """« 3 lignes · 12 pièces · 2,4 m² · 18,2 ml de chant » : ce que représentent des lignes choisies.
    Surface (SURF) et métrage de chant (CHANT) sont donnés par pièce dans Sage."""
    pieces = sum(lire_qte(ligne.get("DL_Qte"), 0) for ligne in lignes)
    surface = sum((nombre(l.get("SURF")) or 0) * (nombre(l.get("DL_Qte")) or 0) for l in lignes)
    chant = sum((nombre(l.get("CHANT")) or 0) * (nombre(l.get("DL_Qte")) or 0) for l in lignes)
    parties = [f"{len(lignes)} ligne{'s' if len(lignes) > 1 else ''}", f"{pieces} pièce{'s' if pieces > 1 else ''}"]
    if surface > 0:
        parties.append(f"{ecrire_nombre(surface)} m²")
    if chant > 0:
        parties.append(f"{ecrire_nombre(chant, 1)} ml de chant")
    return " · ".join(parties)
