"""Contenu des documents imprimés (sans mise en page) : fonctions pures sur EtatAtelier et DonneesSage.

Deux regards sur le même atelier :
- général, qui suit le produit : fiche suiveuse d'OF (tout le parcours), fiche commande ;
- poste, qui suit la machine : fiche d'étape (un OF vu par un seul poste), liste de travail d'un poste.
S'y ajoutent les étiquettes des articles et la page d'essai de la douchette. Le rendu PDF est dans admiral/pdf.py.
"""
from dataclasses import dataclass
from datetime import date
from typing import List

from . import codes, progression, sage
from .synthese import format_date_complete as format_date   # sur papier, toujours avec l'année


@dataclass
class EnteteCommande:
    cde: str
    client: str
    reference: str = ""
    date_commande: str = ""     # « JJ/MM/AAAA »
    delai: str = ""             # « JJ/MM/AAAA »
    delai_depasse: bool = False
    observation: str = ""
    observation_bloquante: bool = False


@dataclass
class Article:
    """Ligne de commande d'un OF (ou l'OF lui-même s'il n'a pas de ligne : code vide)."""
    code: str                 # code-barres « CC261234-1000 » ("" : pas de code)
    numero: str               # « 1000 »
    reference: str            # article Sage
    designation: str
    quantite: str             # « 4 » ou « 7,6 ML »
    pieces: int               # quantité entière, pour les étiquettes à la pièce (0 si l'unité n'est pas la pièce)
    dimensions: str           # « 1200 × 800 »
    chants: str               # « 1H+2L »
    surface: float = 0.0      # m², toute la ligne
    ml_chant: float = 0.0     # mètres de chant, toute la ligne


@dataclass
class Etape:
    numero: int
    code_op: str
    libelle: str
    poste: str                # « FAC1 · Ligne façonnage 1 » ou « Tout poste »
    consigne: str
    faites: int
    qte: int
    validee: bool = False     # terminée par un chef d'atelier


@dataclass
class FicheOF:
    """Fiche suiveuse : tout l'OF, qui accompagne les pièces d'un poste à l'autre."""
    id: str
    commande: EnteteCommande
    produit: str              # « VT8 · Verre trempé 8 mm clair »
    designation: str
    qte: int
    dimensions: str
    observations: str
    urgent: bool
    besoin: str               # « JJ/MM/AAAA »
    retard: bool
    articles: List[Article]
    etapes: List[Etape]
    resume: str               # « 12 pièces · 3,4 m² · 18,2 ml de chant »
    gabarit = "portrait"


@dataclass
class FicheEtape:
    """Un OF vu par le poste d'une seule étape : ce qu'il y a à faire ici, d'où ça vient, où ça part."""
    fiche: FicheOF
    index: int                # étape dans fiche.etapes
    pretes: int               # pièces disponibles pour cette étape (faites à l'étape précédente)
    gabarit = "demi"

    @property
    def etape(self):
        return self.fiche.etapes[self.index]

    @property
    def precedente(self):
        return self.fiche.etapes[self.index - 1] if self.index > 0 else None

    @property
    def suivante(self):
        return self.fiche.etapes[self.index + 1] if self.index + 1 < len(self.fiche.etapes) else None


@dataclass
class OFCommande:
    id: str
    produit: str
    designation: str
    qte: int
    dimensions: str
    besoin: str
    urgent: bool
    etat: str                 # « À faire », « En cours », « Terminé »
    faites: dict              # {code opération: pièces faites} ; absent : l'OF ne passe pas par cette opération


@dataclass
class FicheCommande:
    commande: EnteteCommande
    operations: List[tuple]   # [(code, libellé)] des OF de la commande, dans l'ordre de leurs gammes
    ofs: List[OFCommande]
    lignes_libres: List[Article]   # lignes à fabriquer pas encore dans un OF
    resume: str

    @property
    def gabarit(self):
        """Paysage au-delà de 4 opérations : une colonne par opération, la désignation garde sa place."""
        return "paysage" if len(self.operations) > 4 else "portrait"


@dataclass
class TravailOF:
    id: str
    cde: str
    client: str
    designation: str
    dimensions: str
    chants: str
    reste: int                # pièces encore à faire à ce poste
    qte: int
    pretes: int               # disponibles maintenant (faites à l'étape précédente)
    attente: str              # « attend Découpe » quand rien n'est prêt
    besoin: str
    urgent: bool
    retard: bool
    consigne: str


@dataclass
class ListeTravail:
    """Tous les OF qu'un poste a encore à faire, regroupés par produit (le travail se fait par lots)."""
    codpost: str
    poste: str                # désignation du poste
    operation: str            # libellé de l'opération du poste
    groupes: List[tuple]      # [(produit, [TravailOF])]
    resume: str               # « 9 OF · 74 pièces · 31 prêtes »
    gabarit = "paysage"


@dataclass
class Etiquette:
    code: str
    cde: str
    id_of: str
    numero: str
    designation: str
    dimensions: str
    quantite: str
    chants: str
    client: str
    piece: str = ""           # « 2/4 » quand on imprime une étiquette par pièce


@dataclass
class Etiquettes:
    etiquettes: List[Etiquette]
    debut: int = 1            # première étiquette de la planche à utiliser (planche entamée)
    gabarit = "etiquettes"


@dataclass
class PageEssai:
    codes: List[tuple]        # [(libellé, code, ce qu'Admiral doit répondre)]
    gabarit = "portrait"


# --- Briques communes ---

def _pluriel(n, mot):
    return f"{n} {mot}{'s' if n > 1 and mot != 'OF' else ''}"


def entete_commande(donnees, cde, aujourd_hui=None):
    infos = donnees.infos_commande(cde)
    aujourd_hui = aujourd_hui or date.today()
    return EnteteCommande(cde=cde, client=donnees.client(cde, ""), reference=infos.reference,
                          date_commande=format_date(infos.date), delai=format_date(infos.delai),
                          delai_depasse=bool(infos.delai) and infos.delai < aujourd_hui.isoformat(),
                          observation=infos.observations, observation_bloquante=infos.niveau != "info")


def _dimensions(ligne):
    longueur, largeur = sage.dimension_mm(ligne.get("LONG")), sage.dimension_mm(ligne.get("LARG"))
    return f"{longueur} × {largeur}" if longueur and largeur else ""


def article(cde, cle, ligne):
    qte = sage.nombre(ligne.get("DL_Qte")) or 0
    piece = (ligne.get("EU_Enumere") or "U").strip().upper() in ("", "U")
    return Article(code=codes.code_article(cde, cle), numero=str(ligne.get("DL_Ligne", "")).strip(),
                   reference=ligne.get("AR_Ref", ""), designation=ligne.get("DL_Design", ""),
                   quantite=sage.quantite(ligne), pieces=sage.lire_qte(ligne.get("DL_Qte"), 0) if piece else 0,
                   dimensions=_dimensions(ligne), chants=sage.chants(ligne),
                   surface=(sage.nombre(ligne.get("SURF")) or 0) * qte, ml_chant=(sage.nombre(ligne.get("CHANT")) or 0) * qte)


def articles_of(donnees, of):
    """Lignes de commande de l'OF ; sans ligne (OF saisi à la main), l'OF lui-même, sans code article."""
    lignes = [article(of.cde, cle, ligne) for cle, _, ligne in sage.lignes_enfants(donnees, of.cde, of.lignes_sage)]
    if lignes:
        return lignes
    return [Article(code="", numero="—", reference=of.prod, designation=of.design, quantite=str(of.qte),
                    pieces=of.qte, dimensions=of.dimensions.replace(" mm", "") if of.dimensions != "—" else "",
                    chants="")]


def _resume(qte, articles):
    surface = sum(a.surface for a in articles)
    chant = sum(a.ml_chant for a in articles)
    parties = [_pluriel(qte, "pièce")]
    if surface > 0:
        parties.append(f"{sage.ecrire_nombre(surface)} m²")
    if chant > 0:
        parties.append(f"{sage.ecrire_nombre(chant, 1)} ml de chant")
    return " · ".join(parties)


def libelle_poste(code, postes):
    if not code:
        return "Tout poste"
    designation = postes.get(code, "")
    return f"{code} · {designation}" if designation else code


# --- Documents ---

def fiche_of(etat, donnees, of, libelles, postes, produits, aujourd_hui=None):
    """libelles : {opération: libellé} ; postes : {poste: désignation} ; produits : {réf.: désignation}."""
    aujourd_hui = aujourd_hui or date.today()
    articles = articles_of(donnees, of)
    etapes = [Etape(numero=i + 1, code_op=op, libelle=libelles.get(op) or op, poste=libelle_poste(assigne, postes),
                    consigne=etat.consigne(of.id, op), faites=min(etat.compter(of.id, op), of.qte), qte=of.qte,
                    validee=bool(etat.validation(of.id, op)))
              for i, (op, assigne) in enumerate(etat.gamme(of.id))]
    produit = f"{of.prod} · {produits[of.prod]}" if produits.get(of.prod) else of.prod
    return FicheOF(id=of.id, commande=entete_commande(donnees, of.cde, aujourd_hui), produit=produit,
                   designation=of.design, qte=of.qte, dimensions=of.dimensions if of.dimensions != "—" else "",
                   observations=of.observations, urgent=of.urgent, besoin=format_date(of.date_besoin),
                   retard=etat.en_retard(of, aujourd_hui), articles=articles, etapes=etapes,
                   resume=_resume(of.qte, articles))


def fiches_etape(etat, donnees, of, libelles, postes, produits, code_op=None, aujourd_hui=None):
    """Fiches d'étape de l'OF : toutes ses étapes, ou seulement celle de l'opération code_op."""
    fiche = fiche_of(etat, donnees, of, libelles, postes, produits, aujourd_hui)
    gamme = etat.gamme(of.id)
    return [FicheEtape(fiche, i, max(progression.disponibles(etat, of, gamme, i, op), 0))
            for i, (op, _) in enumerate(gamme) if code_op is None or op == code_op]


def etat_of(etat, of):
    if etat.termine(of):
        texte = "Terminé"
    elif any(etat.compter(of.id, op) for op, _ in etat.gamme(of.id)):
        texte = "En cours"
    else:
        texte = "À faire"
    return f"{texte} · urgent" if of.urgent and texte != "Terminé" else texte


def fiche_commande(etat, donnees, cde, libelles, aujourd_hui=None):
    ofs = etat.ofs_par_cde.get(cde, [])
    operations = []
    for of in ofs:
        for op, _ in etat.gamme(of.id):
            if op not in operations:
                operations.append(op)
    lignes_ofs = [OFCommande(id=of.id, produit=of.prod, designation=of.design, qte=of.qte,
                             dimensions=of.dimensions if of.dimensions != "—" else "",
                             besoin=format_date(of.date_besoin), urgent=of.urgent, etat=etat_of(etat, of),
                             faites={op: min(etat.compter(of.id, op), of.qte) for op, _ in etat.gamme(of.id)})
                  for of in ofs]
    affectees = {codes.code_article(of.cde, c) for of in ofs for c in (of.lignes_sage or "").split(",") if c.strip()}
    libres = [article(cde, cle, ligne) for cle, ligne in donnees.lignes_commande(cde)
              if sage.fabricable(ligne) and cle not in affectees]
    pieces = sum(of.qte for of in ofs)
    resume = [_pluriel(len(ofs), "OF"), _pluriel(pieces, "pièce")]
    surface = sum(a.surface for of in ofs for a in articles_of(donnees, of))
    if surface > 0:
        resume.append(f"{sage.ecrire_nombre(surface)} m²")
    if libres:
        resume.append(f"{_pluriel(len(libres), 'ligne')} pas encore en OF")
    return FicheCommande(commande=entete_commande(donnees, cde, aujourd_hui),
                         operations=[(op, libelles.get(op) or op) for op in operations], ofs=lignes_ofs,
                         lignes_libres=libres, resume=" · ".join(resume))


def liste_travail(etat, donnees, codpost, libelles, postes, produits, aujourd_hui=None):
    """Ce que le poste a encore à faire : urgents et retards en tête, puis par date de besoin."""
    aujourd_hui = aujourd_hui or date.today()
    ref_op = etat.operation_poste.get(codpost)
    groupes = {}
    for of, index in progression.ofs_du_poste(etat, codpost):
        gamme = etat.gamme(of.id)
        faites = etat.compter(of.id, ref_op)
        if faites >= of.qte or etat.validation(of.id, ref_op):
            continue
        pretes = max(progression.disponibles(etat, of, gamme, index, ref_op), 0)
        precedente = gamme[index - 1][0] if index > 0 else None
        articles = articles_of(donnees, of)
        chants = {a.chants for a in articles}
        travail = TravailOF(id=of.id, cde=of.cde, client=donnees.client(of.cde, ""), designation=of.design,
                            dimensions=of.dimensions if of.dimensions != "—" else "",
                            chants=chants.pop() if len(chants) == 1 else "variés",
                            reste=of.qte - faites, qte=of.qte, pretes=min(pretes, of.qte - faites),
                            attente=f"attend {libelles.get(precedente) or precedente}" if precedente and not pretes else "",
                            besoin=format_date(of.date_besoin), urgent=of.urgent,
                            retard=etat.en_retard(of, aujourd_hui), consigne=etat.consigne(of.id, ref_op))
        produit = f"{of.prod} · {produits[of.prod]}" if produits.get(of.prod) else (of.prod or "Sans produit")
        groupes.setdefault(produit, []).append((of, travail))
    def priorite(paire):
        of, travail = paire
        return (not travail.urgent, not travail.retard, of.date_besoin or "9999", of.id)

    triees = sorted(groupes.items(), key=lambda g: (min(priorite(p) for p in g[1]), g[0]))
    rangs = [(produit, [t for _, t in sorted(travaux, key=priorite)]) for produit, travaux in triees]
    tous = [t for _, travaux in rangs for t in travaux]
    resume = (f"{_pluriel(len(tous), 'OF')} · {_pluriel(sum(t.reste for t in tous), 'pièce')} à faire"
              f" · {sum(t.pretes for t in tous)} prête{'s' if sum(t.pretes for t in tous) > 1 else ''}")
    return ListeTravail(codpost=codpost, poste=postes.get(codpost, ""), operation=libelles.get(ref_op) or ref_op or "",
                        groupes=rangs, resume=resume)


def etiquettes(donnees, ofs, par_piece=False, debut=1):
    """Étiquettes des articles des OF : une par ligne de commande, ou une par pièce (même code-barres,
    numérotées « 2/4 »). Les lignes dont l'unité n'est pas la pièce (ML, M2) ont une seule étiquette."""
    resultat = []
    for of in ofs:
        client = donnees.nom_client(of.cde) or donnees.client(of.cde, "")
        for art in articles_of(donnees, of):
            if not art.code:
                continue
            modele = Etiquette(code=art.code, cde=of.cde, id_of=of.id, numero=art.numero, designation=art.designation,
                               dimensions=art.dimensions, quantite=art.quantite, chants=art.chants, client=client)
            if par_piece and art.pieces > 1:
                resultat += [Etiquette(**{**modele.__dict__, "piece": f"{n}/{art.pieces}"})
                             for n in range(1, art.pieces + 1)]
            else:
                resultat.append(modele)
    return Etiquettes(resultat, max(1, debut))


def page_essai(etat, donnees):
    """Codes à scanner pour vérifier la douchette, avec des éléments réels quand il y en a."""
    of = next(iter(etat.ofs_en_service()), None)
    cde = of.cde if of else next(iter(donnees.entetes), "CC000000")
    lignes = sage.lignes_enfants(donnees, of.cde, of.lignes_sage) if of else []
    codes_essai = [("Test du clavier de la douchette", codes.CODE_ESSAI,
                    "« Douchette bien réglée ». Sinon, Admiral indique comment la régler.")]
    codes_essai.append(("Commande", cde, f"La commande {cde} s'affiche."))
    if of:
        codes_essai.append(("OF", of.id, f"Une pièce de {of.id} est comptée (sur un poste de sa gamme)."))
    if lignes:
        code = codes.code_article(of.cde, lignes[0][0])
        codes_essai.append(("Article (ligne de commande)", code, f"Une pièce de la ligne {code} est comptée."))
    return PageEssai(codes_essai)


# --- Assemblage d'une impression ---

@dataclass
class Choix:
    """Ce que l'utilisateur a coché dans la fenêtre d'impression."""
    cde: str = None
    ids_of: tuple = ()
    fiche_commande: bool = False
    fiches_suiveuses: bool = False
    fiches_etape: bool = False
    etape: str = None            # code opération des fiches d'étape ; None : toutes les étapes
    etiquettes: bool = False
    par_piece: bool = False
    debut: int = 1               # première étiquette libre de la planche
    postes: tuple = ()           # listes de travail de ces postes

    @property
    def vide(self):
        return not (self.fiche_commande and self.cde) and not self.postes and not (
            self.ids_of and (self.fiches_suiveuses or self.fiches_etape or self.etiquettes))


def assembler(choix, etat, donnees, libelles, postes, produits, aujourd_hui=None):
    """Documents à imprimer, dans l'ordre : fiche commande, fiches suiveuses, fiches d'étape regroupées par
    opération (toutes les fiches d'un poste se suivent, prêtes à distribuer), listes de travail, étiquettes.
    Seuls les OF en service (ni annulés, ni d'une commande clôturée) sont imprimés."""
    docs = []
    if choix.fiche_commande and choix.cde:
        docs.append(fiche_commande(etat, donnees, choix.cde, libelles, aujourd_hui))
    ofs = [etat.ofs[i] for i in choix.ids_of if i in etat.ofs and etat.en_service(etat.ofs[i])]
    if choix.fiches_suiveuses:
        docs += [fiche_of(etat, donnees, of, libelles, postes, produits, aujourd_hui) for of in ofs]
    if choix.fiches_etape:
        ordre = list(dict.fromkeys(op for of in ofs for op, _ in etat.gamme(of.id)))
        fiches = [fe for of in ofs for fe in fiches_etape(etat, donnees, of, libelles, postes, produits, choix.etape, aujourd_hui)]
        docs += sorted(fiches, key=lambda fe: ordre.index(fe.etape.code_op))   # tri stable : OF dans l'ordre choisi
    docs += [liste_travail(etat, donnees, codpost, libelles, postes, produits, aujourd_hui) for codpost in choix.postes]
    if choix.etiquettes and ofs:
        docs.append(etiquettes(donnees, ofs, choix.par_piece, choix.debut))
    return docs
