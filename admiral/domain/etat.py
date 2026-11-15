"""Photo de l'état de l'atelier : OF, gammes, postes et scans, chargés en une fois.

Les écrans calculent l'avancement à partir de cette photo au lieu d'interroger la base
pour chaque OF et chaque opération.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

# Marqueur "aucun filtre sur la ligne Sage" pour le comptage des scans
TOUS_SCANS = object()


@dataclass(frozen=True)
class OF:
    id: str
    cde: str
    prod: str
    design: str
    observ: str
    qte: int
    lignes_sage: str
    longueur: Optional[int] = None   # mm
    largeur: Optional[int] = None    # mm
    epaisseur: str = ""              # plus saisie ni affichée ; colonne gardée en base (anciens OF)
    statut: str = "actif"            # actif / annule
    date_besoin: Optional[str] = None  # AAAA-MM-JJ
    priorite: int = 0                # 0 normale, 1 urgente

    @property
    def annule(self):
        return self.statut == "annule"

    @property
    def urgent(self):
        return bool(self.priorite)

    @property
    def dimensions(self):
        """Dimensions à afficher. Les OF créés avant les champs dédiés les avaient dans OBSERV."""
        if self.longueur and self.largeur:
            return f"{self.longueur} × {self.largeur} mm"
        return self.observ or "—"

    @property
    def observations(self):
        """Observations à afficher à côté des dimensions (vide si OBSERV sert déjà de dimensions)."""
        return self.observ if self.longueur and self.largeur else ""


@dataclass(frozen=True)
class Validation:
    """Étape (code_op) ou OF entier (code_op None) déclaré terminé par un chef d'atelier."""
    id: int
    id_of: str
    code_op: Optional[str]
    chef: str
    motif: str
    commentaire: str
    date: str   # « AAAA-MM-JJ HH:MM:SS », heure locale


class EtatAtelier:
    def __init__(self, ofs, gammes, postes, scans, cloturees=(), validations=()):
        """
        ofs       : [OF] dans l'ordre de création (annulés compris)
        gammes    : [(ID_OF, CodeOp, Poste_Assigne)] triés par ID_OF puis Ordre
        postes    : [(CodPost, RefOp)]
        scans     : [(ID_OF, Poste, Child_Key, nombre)] — scans valides seulement
        cloturees : commandes clôturées (livrées)
        validations : [(ID, ID_OF, CodeOp ou None, Chef, Motif, Commentaire, date)] actives, de la plus ancienne
                      à la plus récente — étapes déclarées terminées par un chef d'atelier, sans scan
        """
        self.ofs = {of.id: of for of in ofs}
        self.cloturees = set(cloturees)
        self.tous_ofs_par_cde = defaultdict(list)   # annulés compris (Bureau d'Étude)
        self.ofs_par_cde = defaultdict(list)        # OF actifs seulement
        for of in ofs:
            self.tous_ofs_par_cde[of.cde].append(of)
            if not of.annule:
                self.ofs_par_cde[of.cde].append(of)

        self.gammes = defaultdict(list)
        for id_of, code_op, poste_assigne in gammes:
            self.gammes[id_of].append((code_op, poste_assigne))

        self.operation_poste = {codpost: ref_op for codpost, ref_op in postes}
        self.postes_par_operation = defaultdict(list)
        for codpost, ref_op in sorted(postes):
            self.postes_par_operation[ref_op].append(codpost)

        # Scans indexés par (OF, opération, ligne Sage) et par (OF, poste).
        # Un scan d'un poste inconnu n'a pas d'opération : il n'est compté que par poste.
        self._par_operation = defaultdict(int)
        self._total_operation = defaultdict(int)
        self._par_poste = defaultdict(int)
        self.validations = defaultdict(list)   # ID_OF -> validations actives
        for validation in validations:
            self.validations[validation[1]].append(Validation(*validation))

        for id_of, poste, child_key, nombre in scans:
            self._par_poste[(id_of, poste)] += nombre
            ref_op = self.operation_poste.get(poste)
            if ref_op is not None:
                self._par_operation[(id_of, ref_op, child_key)] += nombre
                self._total_operation[(id_of, ref_op)] += nombre

    def commandes(self):
        """Commandes en cours (au moins un OF actif, non clôturées), dans l'ordre du premier OF créé."""
        return [cde for cde, ofs in self.ofs_par_cde.items() if ofs and cde not in self.cloturees]

    def en_service(self, of):
        """OF à suivre en atelier : actif et commande non clôturée."""
        return not of.annule and of.cde not in self.cloturees

    def ofs_en_service(self):
        return [of for of in self.ofs.values() if self.en_service(of)]

    def termine(self, of):
        """OF fini : la dernière opération de sa gamme a toutes ses pièces."""
        gamme = self.gamme(of.id)
        return bool(gamme) and of.qte > 0 and self.compter(of.id, gamme[-1][0]) >= of.qte

    def en_retard(self, of, aujourd_hui):
        """Date de besoin dépassée et OF pas fini. aujourd_hui : date."""
        return bool(of.date_besoin) and of.date_besoin < aujourd_hui.isoformat() and not self.termine(of)

    def gamme(self, id_of):
        return self.gammes.get(id_of, [])

    def compter(self, id_of, ref_op, child_key=TOUS_SCANS):
        """Pièces d'un OF passées à une opération (tous postes confondus).
        child_key : TOUS_SCANS = tous, None = scans "généraux" de l'OF, sinon une ligne Sage.

        Une étape validée par un chef d'atelier compte comme faite en entier : c'est ici, et seulement ici,
        que la validation est prise en compte, donc tous les écrans la voient. Elle passe par les scans
        « généraux », que l'affichage répartit sur les lignes de commande."""
        if child_key is TOUS_SCANS:
            n = self._total_operation.get((id_of, ref_op), 0)
        else:
            n = self._par_operation.get((id_of, ref_op, child_key), 0)
        if child_key is not TOUS_SCANS and child_key is not None:
            return n
        of = self.ofs.get(id_of)
        if of is not None and self.validation(id_of, ref_op):
            return max(n, of.qte)
        return n

    def scans_reels(self, id_of, ref_op):
        """Pièces réellement scannées, sans les validations du chef."""
        return self._total_operation.get((id_of, ref_op), 0)

    def validation(self, id_of, ref_op=None):
        """Validation la plus récente qui couvre cette étape (ou, sans ref_op, tout l'OF), sinon None."""
        for v in reversed(self.validations.get(id_of, ())):
            if v.code_op is None or v.code_op == ref_op:
                if ref_op is not None or v.code_op is None:
                    return v
        return None

    def valide_par_chef(self, of):
        """OF dont toutes les étapes ont été validées par un chef (au moins une sans scan complet)."""
        gamme = self.gamme(of.id)
        return bool(gamme) and all(self.validation(of.id, op) for op, _ in gamme) \
            and any(self.scans_reels(of.id, op) < of.qte for op, _ in gamme)

    def compter_poste(self, id_of, codpost):
        return self._par_poste.get((id_of, codpost), 0)

    def premier_poste(self, ref_op):
        postes = self.postes_par_operation.get(ref_op)
        return postes[0] if postes else None
