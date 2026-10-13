"""Indicateurs de pilotage (onglet Synthèse). Fonctions pures sur EtatAtelier."""
from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass
class LignePoste:
    code: str
    designation: str
    operation: str
    pieces_jour: int
    a_faire: int
    en_cours: int
    termines: int
    reste_operation: int   # pièces restant à faire à l'opération du poste (tous postes confondus)


@dataclass
class Synthese:
    pieces_jour: int = 0
    of_a_faire: int = 0
    of_en_cours: int = 0
    of_termines: int = 0
    of_retard: int = 0
    avancement: float = 0.0   # part des pièces sorties de la dernière opération (0 à 1)
    postes: List[LignePoste] = field(default_factory=list)


def format_date(iso):
    """'2026-10-15' -> '15/10' (année affichée seulement si ce n'est pas l'année en cours)."""
    if not iso:
        return ""
    annee, mois, jour = iso.split("-")
    return f"{jour}/{mois}" if int(annee) == date.today().year else f"{jour}/{mois}/{annee}"


def calculer(etat, postes, libelles, scans_jour, aujourd_hui):
    """postes : [(CodPost, DesPost, RefOp)] ; libelles : {RefOp: libellé} ; scans_jour : {poste: n} ; aujourd_hui : date."""
    ofs = etat.ofs_en_service()
    s = Synthese(pieces_jour=sum(scans_jour.values()))

    faites = prevues = 0
    for of in ofs:
        gamme = etat.gamme(of.id)
        if etat.termine(of):
            s.of_termines += 1
        elif any(etat.compter(of.id, op) for op, _ in gamme):
            s.of_en_cours += 1
        else:
            s.of_a_faire += 1
        if gamme:
            faites += min(etat.compter(of.id, gamme[-1][0]), of.qte)
            prevues += of.qte

        s.of_retard += etat.en_retard(of, aujourd_hui)
    s.avancement = faites / prevues if prevues else 0.0

    for code, designation, ref_op in postes:
        ligne = LignePoste(code, designation, libelles.get(ref_op, ref_op or "—"), scans_jour.get(code, 0), 0, 0, 0, 0)
        for of in ofs:
            if not any(op == ref_op and (not assigne or assigne == code) for op, assigne in etat.gamme(of.id)):
                continue
            n = etat.compter_poste(of.id, code)
            if n == 0:
                ligne.a_faire += 1
            elif n >= of.qte:
                ligne.termines += 1
            else:
                ligne.en_cours += 1
            ligne.reste_operation += max(0, of.qte - etat.compter(of.id, ref_op))
        s.postes.append(ligne)
    return s
