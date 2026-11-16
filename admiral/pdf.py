"""Rendu PDF des documents d'atelier (admiral/domain/documents.py) avec reportlab.

Mise en page d'atelier : noir et blanc (lisible photocopié, aucune information portée par la couleur seule),
gros chiffres pour les numéros, quantités et dimensions, cases à cocher au stylo, codes-barres Code 128.
Un seul PDF peut mêler les gabarits : A4 portrait, A4 paysage, demi-pages A4 (fiches d'étape, deux par
feuille avec trait de coupe) et planche d'étiquettes.
"""
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, FrameBreak, KeepInFrame, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

from . import __version__
from .domain import documents as D

MARGE = 12 * mm
NOIR = colors.black
GRIS = colors.Color(0.45, 0.45, 0.45)
TRAIT = colors.Color(0.6, 0.6, 0.6)
FOND_ENTETE = colors.Color(0.9, 0.9, 0.9)

# Planche d'étiquettes : 3 × 7 de 63,5 × 38,1 mm (format courant, type Avery L7160), marges imprimables
ETIQUETTE_L, ETIQUETTE_H = 63.5 * mm, 38.1 * mm
ETIQUETTES_COLONNES, ETIQUETTES_RANGEES = 3, 7
ETIQUETTE_PAS_X = 66.0 * mm
ETIQUETTES_MARGE_X = (A4[0] - (ETIQUETTES_COLONNES - 1) * ETIQUETTE_PAS_X - ETIQUETTE_L) / 2
ETIQUETTES_MARGE_Y = (A4[1] - ETIQUETTES_RANGEES * ETIQUETTE_H) / 2
ETIQUETTES_PAR_PLANCHE = ETIQUETTES_COLONNES * ETIQUETTES_RANGEES


def _style(nom, taille=9, gras=False, couleur=NOIR, alignement=0, interligne=None):
    return ParagraphStyle(nom, fontName="Helvetica-Bold" if gras else "Helvetica", fontSize=taille,
                          leading=interligne or taille * 1.2, textColor=couleur, alignment=alignement)


S_PETIT = _style("petit", 7.5, couleur=GRIS)
S_PETIT_NOIR = _style("petit_noir", 7.5)
S_CORPS = _style("corps", 9)
S_CORPS_GRAS = _style("corps_gras", 9, gras=True)
S_ENTETE = _style("entete", 7.5, gras=True)
S_MOYEN = _style("moyen", 11, gras=True)
S_GRAND = _style("grand", 14, gras=True)
S_TITRE = _style("titre", 22, gras=True, interligne=25)
S_TITRE_DEMI = _style("titre_demi", 17, gras=True, interligne=20)
S_CENTRE = _style("centre", 9, alignement=TA_CENTER)
S_DROITE = _style("droite", 9, alignement=TA_RIGHT)
S_CHIFFRE = _style("chiffre", 11, gras=True, alignement=TA_CENTER)


def _txt(valeur):
    """Texte sûr pour Paragraph : caractères spéciaux échappés, hors police standard remplacés."""
    texte = str(valeur if valeur is not None else "")
    texte = texte.encode("cp1252", errors="replace").decode("cp1252")
    return escape(texte)


def P(texte, style=S_CORPS):
    return Paragraph(_txt(texte), style)


def PM(markup, style=S_CORPS):
    """Paragraph à partir d'un texte déjà balisé (les valeurs y sont passées par _txt)."""
    return Paragraph(markup, style)


def _date_fr(moment):
    return f"{moment:%d/%m/%Y} à {moment:%H:%M}"


class Case(Flowable):
    """Case à cocher au stylo."""

    def __init__(self, cote=4.2 * mm):
        super().__init__()
        self.cote = cote
        self.width = self.height = cote

    def wrap(self, *args):
        return self.cote, self.cote

    def draw(self):
        self.canv.setLineWidth(1.1)
        self.canv.setStrokeColor(NOIR)
        self.canv.rect(0, 0, self.cote, self.cote)


class Champ(Flowable):
    """Zone à remplir à la main (quantité, date, visa)."""

    def __init__(self, largeur, hauteur=6 * mm):
        super().__init__()
        self.width, self.height = largeur, hauteur

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        self.canv.setLineWidth(0.8)
        self.canv.setStrokeColor(NOIR)
        self.canv.rect(0, 0, self.width, self.height)


class CodeBarres(Flowable):
    """Code 128 avec son texte en clair dessous ; largeur des barres réduite si la place manque."""

    def __init__(self, valeur, hauteur=9 * mm, module=0.3 * mm, largeur_max=None, taille_texte=8):
        super().__init__()
        self.valeur = valeur
        self.taille_texte = taille_texte
        code = Code128(valeur, barWidth=module, barHeight=hauteur, quiet=1, lquiet=4 * module, rquiet=4 * module)
        if largeur_max and code.width > largeur_max:
            module = module * largeur_max / code.width
            code = Code128(valeur, barWidth=module, barHeight=hauteur, quiet=1, lquiet=4 * module, rquiet=4 * module)
        self.code = code
        self.width = code.width
        self.height = hauteur + taille_texte * 1.25

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        self.code.drawOn(self.canv, 0, self.taille_texte * 1.25)
        self.canv.setFont("Helvetica", self.taille_texte)
        self.canv.setFillColor(NOIR)
        self.canv.drawCentredString(self.width / 2, 0.5, self.valeur)


def _grille(donnees, largeurs, entete=True, rangee_haute=None, styles=()):
    """Tableau d'atelier : traits fins, ligne d'en-tête grisée et soulignée, contenu centré verticalement."""
    table = Table(donnees, colWidths=largeurs, repeatRows=1 if entete else 0,
                  rowHeights=None if rangee_haute is None else [None] + [rangee_haute] * (len(donnees) - 1))
    commandes = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                 ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                 ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                 ("LINEBELOW", (0, 1), (-1, -1), 0.4, TRAIT)]
    if entete:
        commandes += [("BACKGROUND", (0, 0), (-1, 0), FOND_ENTETE), ("LINEBELOW", (0, 0), (-1, 0), 1, NOIR)]
    table.setStyle(TableStyle(commandes + list(styles)))
    return table


def _cadre(contenu, largeur, epaisseur=0.8, fond=None):
    """Encadré (bloc commande, produit, consigne…)."""
    table = Table([[contenu]], colWidths=[largeur])
    styles = [("BOX", (0, 0), (-1, -1), epaisseur, NOIR), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if fond:
        styles.append(("BACKGROUND", (0, 0), (-1, -1), fond))
    table.setStyle(TableStyle(styles))
    return table


def _badge(texte):
    """Mot blanc sur fond noir (« URGENT ») : visible même photocopié."""
    table = Table([[P(texte, _style("badge", 9, gras=True, couleur=colors.white))]])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NOIR), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 1),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return table


BADGE_EN_LIGNE = '<font backColor="black" color="white"><b> URGENT </b></font>'


def _en_ligne(elements, espace=3 * mm):
    """Éléments côte à côte, alignés au milieu (badge + texte)."""
    elements = [e for e in elements if e is not None]
    table = Table([elements], hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), espace), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return table


def _bandeau(gauche, droite, largeur, largeur_droite):
    """En-tête : titre à gauche, code-barres à droite, trait épais dessous."""
    table = Table([[gauche, droite]], colWidths=[largeur - largeur_droite, largeur_droite])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return [table, HRFlowable(width="100%", thickness=2, color=NOIR, spaceBefore=0, spaceAfter=4)]


def _intertitre(texte, apres=None):
    elements = [Spacer(1, 3 * mm), P(texte, S_ENTETE)]
    if apres:
        elements.append(P(apres, S_PETIT))
    elements.append(Spacer(1, 1 * mm))
    return elements


def _ligne_commande(commande):
    """« Réf. client : … · Commandée le … · Délai : … » ; délai dépassé en gras."""
    parties = []
    if commande.reference:
        parties.append(f"Réf. client : {_txt(commande.reference)}")
    if commande.date_commande:
        parties.append(f"Commandée le {_txt(commande.date_commande)}")
    if commande.delai:
        libelle = "Délai dépassé" if commande.delai_depasse else "Délai"
        valeur = f"<b>{_txt(commande.delai)}</b>" if commande.delai_depasse else _txt(commande.delai)
        parties.append(f"{libelle} : {valeur}")
    return " · ".join(parties)


def _bloc_observation(commande):
    if not commande.observation:
        return None
    style = _style("obs", 9, gras=commande.observation_bloquante)
    return PM(f"Observation Sage : {_txt(commande.observation)}", style)


# --- Fiche suiveuse d'OF ---

def _fiche_of(fiche, largeur):
    gauche = [P("Admiral · Ordre de fabrication · fiche suiveuse", S_PETIT), P(fiche.id, S_TITRE)]
    besoin = None
    if fiche.besoin:
        besoin = PM(f"<b>{'En retard · besoin' if fiche.retard else 'Besoin'} : {_txt(fiche.besoin)}</b>", S_MOYEN)
    if fiche.urgent or besoin:
        gauche += [Spacer(1, 1.5 * mm), _en_ligne([_badge("URGENT") if fiche.urgent else None, besoin])]
    elements = _bandeau(gauche, CodeBarres(fiche.id, hauteur=14 * mm, module=0.38 * mm, largeur_max=75 * mm, taille_texte=10),
                        largeur, 78 * mm)

    commande = fiche.commande
    bloc_cde = [P("Commande", S_PETIT), P(f"{commande.cde} · {commande.client}", S_MOYEN)]
    if _ligne_commande(commande):
        bloc_cde.append(PM(_ligne_commande(commande)))
    if _bloc_observation(commande):
        bloc_cde.append(_bloc_observation(commande))
    bloc_prod = [P("Produit", S_PETIT), P(fiche.produit, S_CORPS_GRAS)]
    if fiche.designation and fiche.designation not in fiche.produit:
        bloc_prod.append(P(fiche.designation))
    autres = "".join(f" · {_txt(partie)}" for partie in fiche.resume.split(" · ")[1:])
    bloc_prod.append(PM(f"<font size=16><b>{fiche.qte}</b></font> pièce{'s' if fiche.qte > 1 else ''}{autres}",
                        _style("q", 9, interligne=18)))
    if fiche.dimensions:
        bloc_prod.append(PM(f"Dimensions : <b>{_txt(fiche.dimensions)}</b>"))
    if fiche.observations:
        bloc_prod.append(P(f"Observations : {fiche.observations}"))
    gauche_l = largeur * 0.56
    blocs = Table([[_cadre(bloc_cde, gauche_l - 3 * mm), _cadre(bloc_prod, largeur - gauche_l)]],
                  colWidths=[gauche_l, largeur - gauche_l])
    blocs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    elements.append(blocs)

    # Articles : une case par étape devant chaque ligne (cochée au stylo à chaque poste)
    etapes = fiche.etapes
    elements += _intertitre("Articles — cochez la case de l'étape quand la ligne y est faite")
    entete = [P(e.code_op, _style("op", 7, gras=True, alignement=TA_CENTER)) for e in etapes] + \
        [P("Ligne", S_ENTETE), P("Désignation", S_ENTETE), P("Qté", S_ENTETE), P("Dimensions", S_ENTETE),
         P("Chants", S_ENTETE), P("Code article", S_ENTETE)]
    largeur_case = max([8 * mm] + [stringWidth(e.code_op, "Helvetica-Bold", 7) + 3 * mm for e in etapes])
    fixes = [largeur_case] * len(etapes) + [12 * mm, None, 13 * mm, 24 * mm, 14 * mm, 46 * mm]
    fixes[len(etapes) + 1] = largeur - sum(x for x in fixes if x)
    lignes = [entete]
    for art in fiche.articles:
        designation = [P(art.designation, S_CORPS_GRAS)]
        if art.reference and art.code:
            designation.append(P(f"Article {art.reference}", S_PETIT))
        lignes.append([Case() for _ in etapes] + [
            P(art.numero), designation, P(art.quantite, S_CHIFFRE), P(art.dimensions, S_CORPS_GRAS), P(art.chants),
            CodeBarres(art.code, hauteur=7 * mm, module=0.25 * mm, largeur_max=44 * mm, taille_texte=7) if art.code
            else P("pas de ligne de commande", S_PETIT)])
    lignes.append([Case() for _ in etapes] + [PM("<b>OF complet à l'étape</b> (visa)", S_PETIT_NOIR), "", "", "", "", ""])
    elements.append(_grille(lignes, fixes, styles=[
        ("ALIGN", (0, 0), (len(etapes) - 1, -1), "CENTER"),
        ("SPAN", (len(etapes), len(lignes) - 1), (-1, len(lignes) - 1)),
        ("LINEABOVE", (0, len(lignes) - 1), (-1, len(lignes) - 1), 0.8, NOIR),
        ("LINEAFTER", (len(etapes) - 1, 0), (len(etapes) - 1, -1), 0.8, NOIR)]))

    # Parcours : une ligne par étape, case « étape terminée » en tête, cases à remplir à la main
    elements += _intertitre("Parcours (gamme)", "« Fait » : pièces enregistrées dans Admiral au moment de l'impression.")
    lignes = [[P("", S_ENTETE), P("N°", S_ENTETE), P("Opération", S_ENTETE), P("Poste", S_ENTETE),
               P("Consigne du bureau d'étude", S_ENTETE), P("Fait", S_ENTETE), P("Qté", S_ENTETE),
               P("Date", S_ENTETE), P("Visa", S_ENTETE)]]
    for etape in etapes:
        fait = f"{etape.faites} / {etape.qte}" + (" (chef)" if etape.validee else "")
        lignes.append([Case(), P(str(etape.numero), S_CENTRE), P(etape.libelle, S_CORPS_GRAS), P(etape.poste),
                       P(etape.consigne, S_CORPS_GRAS) if etape.consigne else "", P(fait, S_CENTRE),
                       Champ(14 * mm), Champ(16 * mm), Champ(16 * mm)])
    fixes = [8 * mm, 8 * mm, 28 * mm, 34 * mm, None, 18 * mm, 17 * mm, 19 * mm, 19 * mm]
    fixes[4] = largeur - sum(x for x in fixes if x)
    elements.append(_grille(lignes, fixes, styles=[("ALIGN", (0, 0), (0, -1), "CENTER")]))

    elements += _intertitre("Remarques / non-conformités (casse, reprise, manque)")
    elements.append(_cadre(Spacer(1, 18 * mm), largeur))
    return elements


# --- Fiche d'étape (demi-page) ---

def _fiche_etape(fe, largeur):
    fiche, etape = fe.fiche, fe.etape
    gauche = [P(f"Fiche d'étape · étape {etape.numero} / {len(fiche.etapes)}", S_PETIT),
              P(f"{etape.libelle} · {etape.poste}", S_TITRE_DEMI)]
    contexte = [f"<font size=12><b>{_txt(fiche.id)}</b></font>", _txt(f"{fiche.commande.cde} · {fiche.commande.client}")]
    if fiche.urgent:
        contexte.append(BADGE_EN_LIGNE)
    if fiche.besoin:
        contexte.append(f"<b>{'en retard · besoin' if fiche.retard else 'besoin'} {_txt(fiche.besoin)}</b>")
    gauche.append(PM("  ·  ".join(contexte), _style("contexte", 9, interligne=14)))
    elements = _bandeau(gauche, CodeBarres(fiche.id, hauteur=11 * mm, module=0.33 * mm, largeur_max=62 * mm, taille_texte=9),
                        largeur, 64 * mm)

    precedente, suivante = fe.precedente, fe.suivante
    vient = f"{precedente.libelle} · {precedente.faites} / {precedente.qte} faites" if precedente else "Début du parcours"
    ensuite = f"{suivante.libelle} · {suivante.poste}" if suivante else "Fin du parcours"
    ici = PM(f"<font size=15><b>{etape.qte - etape.faites}</b></font> pièces à faire · {etape.faites} faites · "
             f"{fe.pretes} prête{'s' if fe.pretes > 1 else ''}", _style("ici", 9, interligne=17))
    flux = Table([[[P("Vient de", S_PETIT), P(vient)], [P("À faire ici", S_PETIT), ici], [P("Ensuite", S_PETIT), P(ensuite)]]],
                 colWidths=[largeur * 0.28, largeur * 0.44, largeur * 0.28])
    flux.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, NOIR), ("LINEBEFORE", (1, 0), (1, 0), 2, NOIR),
                              ("LINEAFTER", (1, 0), (1, 0), 2, NOIR), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    elements.append(flux)
    if etape.consigne:
        elements.append(Spacer(1, 2 * mm))
        elements.append(_cadre([P(f"Consigne pour {etape.libelle.lower()}", S_PETIT), P(etape.consigne, S_GRAND)],
                               largeur, epaisseur=2))
    elif fiche.observations:
        elements.append(Spacer(1, 2 * mm))
        elements.append(P(f"Observations de l'OF : {fiche.observations}"))

    elements.append(Spacer(1, 2 * mm))
    lignes = [[P("", S_ENTETE), P("Ligne", S_ENTETE), P("Désignation", S_ENTETE), P("Qté", S_ENTETE),
               P("Dimensions", S_ENTETE), P("Chants", S_ENTETE), P("Code article", S_ENTETE)]]
    for art in fiche.articles:
        lignes.append([Case(), P(art.numero), P(art.designation, S_CORPS_GRAS), P(art.quantite, S_CHIFFRE),
                       P(art.dimensions, S_CORPS_GRAS), P(art.chants, S_CORPS_GRAS),
                       CodeBarres(art.code, hauteur=6 * mm, module=0.25 * mm, largeur_max=44 * mm, taille_texte=7)
                       if art.code else ""])
    fixes = [8 * mm, 12 * mm, None, 13 * mm, 26 * mm, 16 * mm, 46 * mm]
    fixes[2] = largeur - sum(x for x in fixes if x)
    elements.append(_grille(lignes, fixes, styles=[("ALIGN", (0, 0), (0, -1), "CENTER")]))

    elements.append(Spacer(1, 2.5 * mm))
    pied = Table([[Case(), P(f"OF terminé à l'étape {etape.libelle.lower()}", S_CORPS_GRAS), P("Qté faite", S_PETIT),
                   Champ(16 * mm), P("Date", S_PETIT), Champ(20 * mm), P("Visa", S_PETIT), Champ(20 * mm)]],
                 colWidths=[7 * mm, None, 14 * mm, 19 * mm, 8 * mm, 23 * mm, 8 * mm, 21 * mm])
    pied.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 1),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 1)]))
    elements.append(pied)
    return elements


# --- Fiche commande ---

def _fiche_commande(fc, largeur):
    commande = fc.commande
    gauche = [P("Admiral · Commande", S_PETIT), P(commande.cde, S_TITRE), P(commande.client, S_MOYEN)]
    elements = _bandeau(gauche, CodeBarres(commande.cde, hauteur=13 * mm, module=0.38 * mm, largeur_max=60 * mm, taille_texte=10),
                        largeur, 64 * mm)
    infos = [PM(_ligne_commande(commande))] if _ligne_commande(commande) else []
    if _bloc_observation(commande):
        infos.append(_bloc_observation(commande))
    infos.append(P(fc.resume, S_CORPS_GRAS))
    elements += infos

    elements += _intertitre("OF de la commande — pièces faites par opération au moment de l'impression")
    if fc.ofs:
        entete = [P("", S_ENTETE), P("OF", S_ENTETE), P("Produit · désignation", S_ENTETE), P("Qté", S_ENTETE)] + \
            [P(code, _style("opc", 7, gras=True, alignement=TA_CENTER)) for code, _ in fc.operations] + \
            [P("Besoin", S_ENTETE), P("État", S_ENTETE)]
        lignes = [entete]
        for of in fc.ofs:
            designation = [P(of.produit, S_CORPS_GRAS), P(of.designation)]
            if of.dimensions:
                designation.append(P(of.dimensions, S_PETIT_NOIR))
            lignes.append([Case(), CodeBarres(of.id, hauteur=7 * mm, module=0.25 * mm, largeur_max=40 * mm, taille_texte=7),
                           designation, P(str(of.qte), S_CHIFFRE)] +
                          [P(str(of.faites[code]) if code in of.faites else "—", S_CENTRE) for code, _ in fc.operations] +
                          [P(of.besoin, S_CORPS_GRAS if of.urgent else S_CORPS), P(of.etat)])
        fixes = [8 * mm, 42 * mm, None, 11 * mm] + [11 * mm] * len(fc.operations) + [19 * mm, 20 * mm]
        fixes[2] = largeur - sum(x for x in fixes if x)
        elements.append(_grille(lignes, fixes, styles=[("ALIGN", (0, 0), (0, -1), "CENTER")]))
        if fc.operations:
            elements.append(P("Opérations : " + " · ".join(f"{code} = {libelle}" for code, libelle in fc.operations), S_PETIT))
    else:
        elements.append(P("Aucun OF pour cette commande."))

    if fc.lignes_libres:
        elements += _intertitre("Lignes à fabriquer pas encore dans un OF")
        lignes = [[P("", S_ENTETE), P("Ligne", S_ENTETE), P("Article", S_ENTETE), P("Désignation", S_ENTETE),
                   P("Qté", S_ENTETE), P("Dimensions", S_ENTETE), P("Chants", S_ENTETE)]]
        for art in fc.lignes_libres:
            lignes.append([Case(), P(art.numero), P(art.reference), P(art.designation), P(art.quantite, S_CHIFFRE),
                           P(art.dimensions), P(art.chants)])
        fixes = [8 * mm, 13 * mm, 24 * mm, None, 14 * mm, 28 * mm, 16 * mm]
        fixes[3] = largeur - sum(x for x in fixes if x)
        elements.append(_grille(lignes, fixes, styles=[("ALIGN", (0, 0), (0, -1), "CENTER")]))
    return elements


# --- Liste de travail d'un poste (A4 paysage) ---

def _liste_travail(lt, largeur):
    gauche = [P(f"Admiral · Liste de travail · opération {lt.operation}", S_PETIT),
              P(f"{lt.codpost} · {lt.poste}" if lt.poste else lt.codpost, S_TITRE)]
    droite = [P(lt.resume, _style("resume", 12, gras=True, alignement=TA_RIGHT)),
              P("Urgents et retards en tête · regroupés par produit", _style("aide", 7.5, couleur=GRIS, alignement=TA_RIGHT))]
    elements = _bandeau(gauche, droite, largeur, 110 * mm)
    if not lt.groupes:
        elements.append(Spacer(1, 6 * mm))
        elements.append(P("Aucun OF à faire à ce poste.", S_GRAND))
        return elements
    fixes = [8 * mm, 42 * mm, 44 * mm, None, 24 * mm, 15 * mm, 16 * mm, 22 * mm, 22 * mm, 48 * mm]
    fixes[3] = largeur - sum(x for x in fixes if x)
    for produit, travaux in lt.groupes:
        pieces = sum(t.reste for t in travaux)
        elements.append(Spacer(1, 3 * mm))
        elements.append(PM(f"<b>{_txt(produit)}</b> — {len(travaux)} OF · {pieces} pièce{'s' if pieces > 1 else ''} à faire",
                           _style("groupe", 10)))
        elements.append(HRFlowable(width="100%", thickness=1, color=NOIR, spaceBefore=1, spaceAfter=1))
        lignes = [[P("", S_ENTETE), P("OF", S_ENTETE), P("Commande · client", S_ENTETE), P("Désignation", S_ENTETE),
                   P("Dimensions", S_ENTETE), P("Chants", S_ENTETE), P("À faire", S_ENTETE), P("Prêtes", S_ENTETE),
                   P("Besoin", S_ENTETE), P("Consigne", S_ENTETE)]]
        for t in travaux:
            besoin = [P(t.besoin, S_CORPS_GRAS if t.retard or t.urgent else S_CORPS)]
            if t.urgent:
                besoin.append(_badge("URGENT"))
            elif t.retard:
                besoin.append(P("en retard", S_CORPS_GRAS))
            pretes = [P(str(t.pretes), S_CHIFFRE)] + ([P(t.attente, S_PETIT)] if t.attente else [])
            lignes.append([Case(), CodeBarres(t.id, hauteur=7 * mm, module=0.25 * mm, largeur_max=42 * mm, taille_texte=7),
                           [P(t.cde, S_CORPS_GRAS), P(t.client, S_PETIT_NOIR)], P(t.designation),
                           P(t.dimensions, S_CORPS_GRAS), P(t.chants), P(f"{t.reste} / {t.qte}", S_CHIFFRE), pretes,
                           besoin, P(t.consigne, S_CORPS_GRAS) if t.consigne else ""])
        elements.append(_grille(lignes, fixes, styles=[("ALIGN", (0, 0), (0, -1), "CENTER")]))
    return elements


# --- Étiquettes ---

def _etiquette(e):
    largeur = ETIQUETTE_L - 7 * mm
    haut = f"{e.cde} · {e.id_of} · L.{e.numero}" + (f" · pièce {e.piece}" if e.piece else "")
    dims = Table([[P(e.dimensions or "—", _style("dim", 14, gras=True, interligne=16)),
                   P(" · ".join(filter(None, [f"Qté {e.quantite}" if e.quantite else "", e.chants])),
                     _style("qte", 8, gras=True, alignement=TA_RIGHT))]],
                 colWidths=[largeur * 0.55, largeur * 0.45])
    dims.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    contenu = [P(haut, _style("eh", 6.5, couleur=GRIS)), P(e.designation, _style("ed", 8, gras=True, interligne=9)), dims,
               CodeBarres(e.code, hauteur=8.5 * mm, module=0.25 * mm, largeur_max=largeur, taille_texte=7),
               P(e.client, _style("ec", 6.5, couleur=GRIS))]
    return KeepInFrame(largeur, ETIQUETTE_H - 6 * mm, contenu, mode="shrink")


def _etiquettes(lot, largeur):
    elements = []
    for _ in range((lot.debut - 1) % ETIQUETTES_PAR_PLANCHE):   # planche entamée : on saute les étiquettes déjà utilisées
        elements += [Spacer(1, 1), FrameBreak()]
    for i, etiquette in enumerate(lot.etiquettes):
        if i:
            elements.append(FrameBreak())   # étiquette suivante (pas de saut après la dernière : pas de page blanche)
        elements.append(_etiquette(etiquette))
    if not lot.etiquettes:
        elements.append(P("Aucun article à étiqueter : ces OF n'ont pas de lignes de commande.", S_PETIT_NOIR))
    return elements


# --- Page d'essai de la douchette ---

def _page_essai(pe, largeur):
    elements = _bandeau([P("Admiral · douchette", S_PETIT), P("Page d'essai de la douchette", S_TITRE)], "", largeur, 1 * mm)
    for consigne in ("1. Ouvrez Admiral sur un poste machine (écran Atelier), le champ de scan actif.",
                     "2. Scannez les codes ci-dessous, un par un, en commençant par le test du clavier.",
                     "3. Comparez la réponse d'Admiral avec celle attendue. Si Admiral signale un clavier américain, "
                     "réglez la douchette en clavier français (AZERTY) avec le code de configuration de sa notice."):
        elements.append(P(consigne, S_CORPS))
    for libelle, code, attendu in pe.codes:
        elements.append(Spacer(1, 7 * mm))
        elements.append(P(libelle, S_GRAND))
        elements.append(Spacer(1, 2 * mm))
        elements.append(CodeBarres(code, hauteur=16 * mm, module=0.4 * mm, largeur_max=largeur * 0.7, taille_texte=11))
        elements.append(Spacer(1, 1.5 * mm))
        elements.append(P(f"Réponse attendue : {attendu}", S_PETIT_NOIR))
    return elements


RENDUS = {D.FicheOF: _fiche_of, D.FicheEtape: _fiche_etape, D.FicheCommande: _fiche_commande,
          D.ListeTravail: _liste_travail, D.Etiquettes: _etiquettes, D.PageEssai: _page_essai}


# --- Assemblage ---

class _Document(BaseDocTemplate):
    def __init__(self, chemin, titre, moment, **kwargs):
        super().__init__(chemin, pagesize=A4, title=titre, author="Admiral", creator=f"Admiral {__version__}",
                         leftMargin=MARGE, rightMargin=MARGE, topMargin=MARGE, bottomMargin=MARGE + 4 * mm, **kwargs)
        self.pied = f"Imprimé le {_date_fr(moment)} · Admiral {__version__}"
        largeur, hauteur = A4
        paysage_l, paysage_h = landscape(A4)
        demi_h = hauteur / 2
        demi_marge = 9 * mm
        self.gabarits = {
            "portrait": PageTemplate("portrait", [Frame(MARGE, MARGE + 4 * mm, largeur - 2 * MARGE, hauteur - 2 * MARGE - 4 * mm,
                                                        id="p", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                                     onPage=self._pied, pagesize=A4),
            "paysage": PageTemplate("paysage", [Frame(MARGE, MARGE + 4 * mm, paysage_l - 2 * MARGE, paysage_h - 2 * MARGE - 4 * mm,
                                                      id="l", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                                    onPage=self._pied, pagesize=landscape(A4)),
            "demi": PageTemplate("demi", [Frame(demi_marge, demi_h + demi_marge, largeur - 2 * demi_marge, demi_h - 2 * demi_marge,
                                                id="haut", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
                                          Frame(demi_marge, demi_marge + 3 * mm, largeur - 2 * demi_marge, demi_h - 2 * demi_marge - 3 * mm,
                                                id="bas", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                                 onPage=self._pied_demi, pagesize=A4),
            "etiquettes": PageTemplate("etiquettes", [
                Frame(ETIQUETTES_MARGE_X + c * ETIQUETTE_PAS_X, A4[1] - ETIQUETTES_MARGE_Y - (r + 1) * ETIQUETTE_H,
                      ETIQUETTE_L, ETIQUETTE_H, id=f"e{r}{c}", leftPadding=3.5 * mm, rightPadding=3.5 * mm,
                      topPadding=3 * mm, bottomPadding=2 * mm)
                for r in range(ETIQUETTES_RANGEES) for c in range(ETIQUETTES_COLONNES)], pagesize=A4),
        }

    def _pied(self, canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 7)
        canv.setFillColor(GRIS)
        largeur = canv._pagesize[0]
        canv.drawString(MARGE, MARGE - 1 * mm, self.pied)
        canv.drawRightString(largeur - MARGE, MARGE - 1 * mm, f"page {doc.page}")
        canv.restoreState()

    def _pied_demi(self, canv, doc):
        canv.saveState()
        largeur, hauteur = A4
        canv.setDash(4, 3)
        canv.setStrokeColor(GRIS)
        canv.setLineWidth(0.5)
        canv.line(5 * mm, hauteur / 2, largeur - 5 * mm, hauteur / 2)
        canv.setDash()
        canv.setFont("Helvetica", 6.5)
        canv.setFillColor(GRIS)
        canv.drawCentredString(largeur / 2, hauteur / 2 + 1.2 * mm, "couper ici")
        canv.drawString(9 * mm, 6 * mm, self.pied)
        canv.drawRightString(largeur - 9 * mm, 6 * mm, f"page {doc.page}")
        canv.restoreState()


def largeur_utile(gabarit):
    if gabarit == "paysage":
        return landscape(A4)[0] - 2 * MARGE
    if gabarit == "demi":
        return A4[0] - 18 * mm
    return A4[0] - 2 * MARGE


def generer(chemin, docs, titre="Admiral", moment=None, compresser=True):
    """Écrit un PDF avec les documents (objets de domain/documents.py), chacun sur ses pages, dans l'ordre."""
    if not docs:
        raise ValueError("Rien à imprimer.")
    moment = moment or datetime.now()
    document = _Document(chemin, titre, moment, pageCompression=1 if compresser else 0)
    ordre = list(dict.fromkeys(doc.gabarit for doc in docs))
    document.addPageTemplates([document.gabarits[nom] for nom in ordre]
                              + [g for nom, g in document.gabarits.items() if nom not in ordre])
    histoire = []
    precedent = None
    for doc in docs:
        gabarit = doc.gabarit
        if precedent is not None:
            if gabarit == precedent == "demi":
                histoire.append(FrameBreak())   # fiche d'étape suivante : demi-page suivante
            elif gabarit == precedent == "etiquettes":
                histoire.append(FrameBreak())   # les étiquettes se suivent sur la même planche
            else:
                histoire += [NextPageTemplate(gabarit), PageBreak()]
        histoire += RENDUS[type(doc)](doc, largeur_utile(gabarit))
        precedent = gabarit
    document.build(histoire)
    return chemin
