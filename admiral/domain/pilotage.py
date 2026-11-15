"""Pilotage du chef d'atelier : avancement des commandes et des OF, et validations « forcées ».

Fonctions pures sur EtatAtelier. Une validation du chef compte comme des pièces faites (voir
EtatAtelier.compter) : les fonctions ci-dessous distinguent seulement ce qui a été réellement scanné.
"""
from dataclasses import dataclass
from datetime import date

from . import progression

MOTIFS = ("Fait sans scan", "Douchette en panne", "Reprise / retouche", "Autre")
SEUIL_PRESQUE_FINI = 0.75   # part des étapes faites à partir de laquelle un OF est « presque fini »


@dataclass
class ResumeCommande:
    cde: str
    faites: int        # pièces sorties de la dernière étape de leur gamme
    prevues: int
    tag: str           # retard / encours / pas_demarre / terminee
    besoin: str        # plus proche date de besoin des OF non finis (AAAA-MM-JJ) ou ""
    nb_of: int
    validee: bool      # au moins un OF validé par un chef

    @property
    def pourcentage(self):
        return round(100 * self.faites / self.prevues) if self.prevues else 0


def part_faite(etat, of):
    """Part des pièces-étapes faites (0 à 1), validations comprises."""
    gamme = etat.gamme(of.id)
    if not gamme or of.qte <= 0:
        return 0.0
    return sum(min(etat.compter(of.id, op), of.qte) for op, _ in gamme) / (of.qte * len(gamme))


def etat_of(etat, of, aujourd_hui=None):
    """(libellé, tag) d'un OF au pilotage."""
    aujourd_hui = aujourd_hui or date.today()
    if of.annule:
        return "Annulé", "annule"
    if etat.termine(of):
        return ("Validé", "valide") if etat.valide_par_chef(of) else ("Terminé", "terminee")
    if etat.en_retard(of, aujourd_hui):
        return "En retard", "retard"
    if any(etat.compter(of.id, op) for op, _ in etat.gamme(of.id)):
        return ("Urgent · en cours" if of.urgent else "En cours"), "encours"
    return ("Urgent · à faire" if of.urgent else "À faire"), "bloque" if of.urgent else "pas_demarre"


def resume_commande(etat, cde, aujourd_hui=None):
    aujourd_hui = aujourd_hui or date.today()
    ofs = etat.ofs_par_cde.get(cde, [])
    faites, prevues, tag = progression.avancement_global_commande(etat, cde)
    restants = [of for of in ofs if not etat.termine(of)]
    if any(etat.en_retard(of, aujourd_hui) for of in restants):
        tag = "retard"
    besoin = min((of.date_besoin for of in restants if of.date_besoin), default="")
    return ResumeCommande(cde, faites, prevues, tag, besoin, len(ofs), any(etat.validations.get(of.id) for of in ofs))


def texte_etapes(etat, of, libelles):
    """« ✓ Découpe 8/8 · ◐ Façonnage 5/8 · ○ Trempe 0/8 » ; une étape validée sans scan complet : « ✓ Découpe validée »."""
    morceaux = []
    for op, _ in etat.gamme(of.id):
        nom = libelles.get(op) or op
        n = min(etat.compter(of.id, op), of.qte)
        if etat.validation(of.id, op) and etat.scans_reels(of.id, op) < of.qte:
            morceaux.append(f"✓ {nom} validée")
        elif n >= of.qte:
            morceaux.append(f"✓ {nom} {n}/{of.qte}")
        else:
            morceaux.append(f"{'◐' if n else '○'} {nom} {n}/{of.qte}")
    return " · ".join(morceaux) or "Pas de gamme"


def changements(etat, of, code_op=None):
    """Ce qu'une validation changerait : [(opération, pièces avant, pièces après)], étapes déjà faites exclues.
    code_op None : toutes les étapes de la gamme."""
    return [(op, etat.compter(of.id, op), of.qte) for op, _ in etat.gamme(of.id)
            if (code_op is None or op == code_op) and etat.compter(of.id, op) < of.qte]


def indicateurs(etat, aujourd_hui=None):
    """{en_cours, retard, presque_finis, valides_jour} sur les OF en service."""
    aujourd_hui = aujourd_hui or date.today()
    resultat = {"en_cours": 0, "retard": 0, "presque_finis": 0, "valides_jour": 0}
    for of in etat.ofs_en_service():
        if etat.termine(of):
            continue
        part = part_faite(etat, of)
        if part > 0:
            resultat["en_cours"] += 1
        if etat.en_retard(of, aujourd_hui):
            resultat["retard"] += 1
        if part >= SEUIL_PRESQUE_FINI:
            resultat["presque_finis"] += 1
    jour = aujourd_hui.isoformat()
    resultat["valides_jour"] = len({v.id_of for vs in etat.validations.values() for v in vs if v.date.startswith(jour)})
    return resultat
