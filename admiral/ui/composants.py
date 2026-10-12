"""Composants visuels réutilisables : cartes, pastilles d'état, boutons, tableaux."""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from .. import theme as T

# Style de bouton -> (fond, survol, texte)
STYLES_BOUTON = {
    "primaire": (T.PRIMAIRE, T.PRIMAIRE_SURVOL, T.BLANC),
    "secondaire": (T.SECONDAIRE, T.SECONDAIRE_SURVOL, T.TEXTE),
    "succes": (T.SUCCES, T.SUCCES_SURVOL, T.BLANC),
    "alerte": (T.ALERTE, T.ALERTE_SURVOL, T.FOND),
    "danger": (T.ERREUR, T.ERREUR_SURVOL, T.BLANC),
    "fantome": ("transparent", T.SURFACE_SURVOL, T.TEXTE_ATTENUE),
}


def carte(parent, couleur=T.CARTE, **kwargs):
    """Conteneur arrondi sans bordure : le contraste de fond suffit à le distinguer."""
    return ctk.CTkFrame(parent, fg_color=couleur, corner_radius=T.RAYON_CARTE, border_width=0, **kwargs)


def titre(parent, texte, taille=T.TAILLE_SOUS_TITRE, couleur=T.TEXTE, anchor="w", **kwargs):
    return ctk.CTkLabel(parent, text=texte, font=T.police(taille, gras=True), text_color=couleur, anchor=anchor, **kwargs)


def texte(parent, contenu="", taille=T.TAILLE_CORPS, couleur=T.TEXTE_ATTENUE, gras=False, anchor="w", **kwargs):
    return ctk.CTkLabel(parent, text=contenu, font=T.police(taille, gras), text_color=couleur, anchor=anchor, **kwargs)


def bouton(parent, libelle, commande, style="primaire", atelier=False, icone=None, **kwargs):
    fond, survol, couleur_texte = STYLES_BOUTON[style]
    hauteur = T.HAUTEUR_BOUTON_ATELIER if atelier else T.HAUTEUR_BOUTON
    taille = T.TAILLE_SOUS_TITRE if atelier else T.TAILLE_CORPS
    options = dict(text=libelle, command=commande, fg_color=fond, hover_color=survol, text_color=couleur_texte,
                   height=hauteur, corner_radius=T.RAYON_CONTROLE, font=T.police(taille, gras=True))
    if icone is not None:
        options.update(image=icone, compound="left")
    options.update(kwargs)
    return ctk.CTkButton(parent, **options)


def champ(parent, placeholder="", largeur=200, **kwargs):
    return ctk.CTkEntry(parent, placeholder_text=placeholder, width=largeur, height=T.HAUTEUR_BOUTON,
                        corner_radius=T.RAYON_CONTROLE, border_width=1, border_color=T.BORDURE,
                        fg_color=T.SURFACE, text_color=T.TEXTE, placeholder_text_color=T.TEXTE_DESACTIVE,
                        font=T.police(T.TAILLE_CORPS), **kwargs)


class Pastille(ctk.CTkLabel):
    """État affiché par un mot sur fond coloré (jamais la couleur seule)."""

    def __init__(self, parent, etat="pas_demarre", **kwargs):
        super().__init__(parent, text="", height=26, corner_radius=13,
                         font=T.police(T.TAILLE_LEGENDE, gras=True), **kwargs)
        self.etat = None
        self.definir(etat)

    def definir(self, etat):
        if etat == self.etat:
            return
        self.etat = etat
        libelle, fond, couleur = T.ETATS[etat]
        self.configure(text=f"   {libelle}   ", fg_color=fond, text_color=couleur)


def configurer_styles_ttk(root):
    """Tableaux ttk accordés au thème. "Atelier.Treeview" : lignes plus hautes pour l'écran opérateur."""
    style = ttk.Style(root)
    style.theme_use('clam')
    for nom, hauteur, taille in (("Treeview", T.HAUTEUR_LIGNE_TABLEAU, T.TAILLE_CORPS),
                                 ("Atelier.Treeview", 48, T.TAILLE_SOUS_TITRE)):
        style.configure(nom, background=T.SURFACE, foreground=T.TEXTE, fieldbackground=T.SURFACE,
                        rowheight=hauteur, font=T.police(taille), borderwidth=0, relief="flat",
                        indicatorsize=14, indicatormargins=6)
        style.configure(f"{nom}.Heading", background=T.CARTE, foreground=T.TEXTE_ATTENUE,
                        font=T.police(T.TAILLE_LEGENDE, gras=True), relief="flat", padding=(8, 8))
        style.map(f"{nom}.Heading", background=[('active', T.SURFACE)])
        style.map(nom, background=[('selected', T.PRIMAIRE)], foreground=[('selected', T.BLANC)])
    style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])  # sans cadre
    style.layout("Atelier.Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
    style.configure("Vertical.TScrollbar", background=T.BORDURE, troughcolor=T.SURFACE, bordercolor=T.SURFACE,
                    arrowcolor=T.TEXTE_ATTENUE, lightcolor=T.BORDURE, darkcolor=T.BORDURE, gripcount=0)
    style.configure("Horizontal.TScrollbar", background=T.BORDURE, troughcolor=T.SURFACE, bordercolor=T.SURFACE,
                    arrowcolor=T.TEXTE_ATTENUE, lightcolor=T.BORDURE, darkcolor=T.BORDURE, gripcount=0)
    style.configure("TFrame", background=T.FOND)


def configurer_tags_etats(tree, gras_selection=True):
    """Lignes sur fond neutre, texte coloré selon l'état ; la colonne d'état porte aussi le mot.
    Les tags "<état>_sel" servent à la ligne sélectionnée (voir widgets.maj_tags_selection)."""
    police_sel = T.police(T.TAILLE_CORPS, gras=True) if gras_selection else None
    for etat, (_, _, couleur) in T.ETATS.items():
        tree.tag_configure(etat, background=T.SURFACE, foreground=T.TEXTE if etat == "pas_demarre" else couleur)
        tree.tag_configure(f"{etat}_sel", background=T.PRIMAIRE, foreground=T.BLANC, font=police_sel)
    tree.tag_configure("child", background=T.SURFACE, foreground=T.TEXTE_ENFANT)
    tree.tag_configure("child_sel", background=T.PRIMAIRE, foreground=T.BLANC, font=police_sel)
    tree.tag_configure("default_sel", background=T.PRIMAIRE, foreground=T.BLANC, font=police_sel)


def tableau(parent, colonnes, style="Treeview", hauteur=None, selection="browse", arbre=False, defilement_horizontal=False):
    """Treeview + barres de défilement dans un cadre arrondi. Retourne (cadre, tree).
    colonnes : [(id, titre, largeur, ancrage)]."""
    cadre = ctk.CTkFrame(parent, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE)
    interieur = tk.Frame(cadre, background=T.SURFACE)
    interieur.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    options = dict(columns=[c[0] for c in colonnes], show="tree headings" if arbre else "headings",
                   selectmode=selection, style=style)
    if hauteur:
        options["height"] = hauteur
    tree = ttk.Treeview(interieur, **options)
    defil = ttk.Scrollbar(interieur, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=defil.set)
    if defilement_horizontal:
        defil_h = ttk.Scrollbar(interieur, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=defil_h.set)
        defil_h.pack(side=tk.BOTTOM, fill=tk.X)
    defil.pack(side=tk.RIGHT, fill=tk.Y)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    for ident, titre_colonne, largeur, ancrage in colonnes:
        tree.heading(ident, text=titre_colonne, anchor=ancrage)
        tree.column(ident, width=largeur, anchor=ancrage, stretch=ancrage == "w")
    if arbre:
        tree.column("#0", width=36, stretch=False)
    configurer_tags_etats(tree)
    return cadre, tree


def lier_clic(widget, rappel):
    """Rend un conteneur cliquable, y compris ses étiquettes (pas ses boutons)."""
    widget.bind("<Button-1>", rappel, add="+")
    for enfant in widget.winfo_children():
        if not isinstance(enfant, (ctk.CTkButton, ctk.CTkEntry, ctk.CTkComboBox)):
            lier_clic(enfant, rappel)


def defiler_vers(cadre_defilant, widget):
    """Fait défiler un CTkScrollableFrame pour rendre `widget` visible."""
    canvas = cadre_defilant._parent_canvas
    cadre_defilant.update_idletasks()
    hauteur_totale = max(cadre_defilant.winfo_height(), 1)
    canvas.yview_moveto(max(0, widget.winfo_y() - T.ESPACE_S) / hauteur_totale)
