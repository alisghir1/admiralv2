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
    epaisseur: str = ""              # texte libre : "6", "4/16/4"…
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
            texte = f"{self.longueur} × {self.largeur} mm"
            return f"{texte} · ép. {self.epaisseur}" if self.epaisseur else texte
        return self.observ or "—"

    @property
    def observations(self):
        """Observations à afficher à côté des dimensions (vide si OBSERV sert déjà de dimensions)."""
        return self.observ if self.longueur and self.largeur else ""


class EtatAtelier:
    def __init__(self, ofs, gammes, postes, scans, cloturees=()):
        """
        ofs       : [OF] dans l'ordre de création (annulés compris)
        gammes    : [(ID_OF, CodeOp, Poste_Assigne)] triés par ID_OF puis Ordre
        postes    : [(CodPost, RefOp)]
        scans     : [(ID_OF, Poste, Child_Key, nombre)] — scans valides seulement
        cloturees : commandes clôturées (livrées)
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
        """Scans d'un OF pour une opération (tous postes confondus).
        child_key : TOUS_SCANS = tous, None = scans "généraux" de l'OF, sinon une ligne Sage."""
        if child_key is TOUS_SCANS:
            return self._total_operation.get((id_of, ref_op), 0)
        return self._par_operation.get((id_of, ref_op, child_key), 0)

    def compter_poste(self, id_of, codpost):
        return self._par_poste.get((id_of, codpost), 0)

    def premier_poste(self, ref_op):
        postes = self.postes_par_operation.get(ref_op)
        return postes[0] if postes else None
