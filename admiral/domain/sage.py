"""Lecture des exports CSV de Sage (en-têtes et lignes de commandes)."""
import csv
import os
from dataclasses import dataclass, field

# Seules les pièces dont le numéro commence par ce préfixe sont des commandes clients
PREFIXE_COMMANDE = "CC"

FICHIERS_ENTETES = ("F-DOCENTETE.csv", "docentete.csv")
FICHIERS_LIGNES = ("F-DOCLIGNE.csv", "docligne.csv")


@dataclass
class DonneesSage:
    entetes: dict = field(default_factory=dict)           # DO_Piece -> ligne CSV
    lignes: dict = field(default_factory=dict)            # "DO_Piece-DL_Ligne" -> ligne CSV
    lignes_par_piece: dict = field(default_factory=dict)  # DO_Piece -> [(clé, ligne CSV)]

    def lignes_commande(self, do_piece):
        return self.lignes_par_piece.get(do_piece, [])

    def client(self, do_piece, defaut="Inconnu"):
        return self.entetes.get(do_piece, {}).get("DO_Tiers", defaut)


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


def charger(dossier):
    """Lit les CSV Sage du dossier. Retourne None si le dossier n'existe pas."""
    if not os.path.isdir(dossier):
        return None

    donnees = DonneesSage()

    chemin = _premier_existant(dossier, FICHIERS_ENTETES)
    if chemin:
        for row in _lire_csv(chemin):
            do_piece = (row.get('DO_Piece') or '').strip()
            if do_piece.startswith(PREFIXE_COMMANDE):
                donnees.entetes[do_piece] = row

    chemin = _premier_existant(dossier, FICHIERS_LIGNES)
    if chemin:
        for row in _lire_csv(chemin):
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
    Les clés introuvables dans l'export courant sont ignorées."""
    if not lignes_sage:
        return []
    lignes_dict = dict(donnees.lignes_commande(do_piece))
    resultat = []
    for cle in lignes_sage.split(","):
        cle = cle.strip()
        ligne = lignes_dict.get(cle) or lignes_dict.get(f"{do_piece}-{cle}")
        if cle and ligne:
            resultat.append((cle, lire_qte(ligne.get("DL_Qte", "1")), ligne))
    return resultat


def dimensions(ligne):
    longueur, largeur = ligne.get("LONG", ""), ligne.get("LARG", "")
    return f"{longueur}x{largeur}" if longueur and largeur else ""
