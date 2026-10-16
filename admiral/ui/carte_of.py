"""Carte d'un OF sur l'écran Atelier : état, dimensions, compteur, gamme et actions.

La carte se met à jour sur place (maj) : la reconstruire à chaque scan serait lent.
"""
import tkinter as tk
from dataclasses import dataclass, field
from typing import List

import customtkinter as ctk

from .. import theme as T
from .composants import Pastille, bouton, lier_clic

ETAPES_PAR_RANGEE = 4  # la frise passe à la ligne au-delà, pour ne jamais déborder de la carte

COULEUR_SITUATION = {
    "pret": T.INFO_TEXTE, "encours": T.ALERTE_TEXTE, "attente": T.TEXTE_ATTENUE,
    "bloque": T.ERREUR_TEXTE, "terminee": T.SUCCES_TEXTE, "pas_demarre": T.TEXTE_ATTENUE,
}


@dataclass
class VueEtape:
    libelle: str
    scans: int
    qte: int
    ici: bool        # étape traitée par ce poste

    @property
    def faite(self):
        return self.qte > 0 and self.scans >= self.qte


@dataclass
class VueLigne:
    cle: str         # clé de la ligne Sage (Child_Key des scans)
    titre: str
    details: str
    qte: int
    scans: int
    etat: str        # terminee / encours / pas_demarre


@dataclass
class VueOF:
    id: str
    prod: str
    design: str
    dimensions: str
    observations: str
    qte: int
    scans: int
    etat: str        # pret / encours / attente / bloque / terminee
    situation: str
    etapes: List[VueEtape] = field(default_factory=list)
    lignes: List[VueLigne] = field(default_factory=list)
    urgent: bool = False
    besoin: str = ""      # "Besoin le 15/10" ou "En retard · besoin le 10/10"
    retard: bool = False


class CarteOF(ctk.CTkFrame):
    """actions : objet fournissant selectionner_of(id), ajouter_scans_manuels(id, n, cle),
    retirer_scans_manuels(id, n, cle) et ouvrir_historique(id)."""

    def __init__(self, parent, vue, actions):
        super().__init__(parent, fg_color=T.SURFACE, corner_radius=T.RAYON_CARTE, border_width=2, border_color=T.SURFACE)
        self.actions = actions
        self.id_of = vue.id
        self._selectionnee = False
        self._timer_surbrillance = None
        self.columnconfigure(0, weight=1)

        # Ligne 1 : état, numéro d'OF, référence … compteur
        haut = ctk.CTkFrame(self, fg_color="transparent")
        haut.grid(row=0, column=0, sticky="ew", padx=T.ESPACE_L, pady=(T.ESPACE_M, 0))
        self.pastille = Pastille(haut)
        self.pastille.pack(side=tk.LEFT)
        ctk.CTkLabel(haut, text=vue.id, font=T.police_chiffres(T.TAILLE_SOUS_TITRE), text_color=T.TEXTE).pack(side=tk.LEFT, padx=(T.ESPACE_M, 0))
        self.lbl_ref = ctk.CTkLabel(haut, text="", font=T.police(T.TAILLE_LEGENDE), text_color=T.TEXTE_ATTENUE)
        self.lbl_ref.pack(side=tk.LEFT, padx=(T.ESPACE_S, 0))
        self.pastille_urgent = Pastille(haut, "urgent")
        self._urgent_visible = False
        self.lbl_compte = ctk.CTkLabel(haut, text="", font=T.police_chiffres(T.TAILLE_CHIFFRE), text_color=T.TEXTE)
        self.lbl_compte.pack(side=tk.RIGHT)

        # Ligne 2 : désignation … date de besoin ; puis dimensions en grand (contrôle visuel de la pièce)
        ligne_design = ctk.CTkFrame(self, fg_color="transparent")
        ligne_design.grid(row=1, column=0, sticky="ew", padx=T.ESPACE_L, pady=(T.ESPACE_XS, 0))
        self.lbl_design = ctk.CTkLabel(ligne_design, text="", font=T.police(T.TAILLE_SOUS_TITRE, gras=True), text_color=T.TEXTE, anchor="w")
        self.lbl_design.pack(side=tk.LEFT)
        self.lbl_besoin = ctk.CTkLabel(ligne_design, text="", font=T.police(T.TAILLE_CORPS, gras=True))
        self.lbl_besoin.pack(side=tk.RIGHT)
        dims = ctk.CTkFrame(self, fg_color="transparent")
        dims.grid(row=2, column=0, sticky="ew", padx=T.ESPACE_L)
        self.lbl_dims = ctk.CTkLabel(dims, text="", font=T.police(T.TAILLE_TITRE, gras=True), text_color=T.TITRE)
        self.lbl_dims.pack(side=tk.LEFT)
        self.lbl_obs = ctk.CTkLabel(dims, text="", font=T.police(T.TAILLE_CORPS), text_color=T.TEXTE_ATTENUE)
        self.lbl_obs.pack(side=tk.LEFT, padx=(T.ESPACE_M, 0))

        self.barre = ctk.CTkProgressBar(self, height=8, corner_radius=4, fg_color=T.BORDURE, progress_color=T.ALERTE)
        self.barre.grid(row=3, column=0, sticky="ew", padx=T.ESPACE_L, pady=(T.ESPACE_S, T.ESPACE_S))

        # Ligne 4 : situation … actions
        bas = ctk.CTkFrame(self, fg_color="transparent")
        bas.grid(row=4, column=0, sticky="ew", padx=T.ESPACE_L)
        self.lbl_situation = ctk.CTkLabel(bas, text="", font=T.police(T.TAILLE_CORPS, gras=True), anchor="w")
        self.lbl_situation.pack(side=tk.LEFT)
        self.btn_terminer = bouton(bas, "Terminer", lambda: actions.ajouter_scans_manuels(self.id_of, "all"),
                                   style="succes", atelier=True, width=120)
        self.btn_terminer.pack(side=tk.RIGHT, padx=(T.ESPACE_S, 0))
        self.btn_plus = bouton(bas, "+1", lambda: actions.ajouter_scans_manuels(self.id_of, 1),
                               style="primaire", atelier=True, width=64)
        self.btn_plus.pack(side=tk.RIGHT, padx=(T.ESPACE_S, 0))
        self.btn_moins = bouton(bas, "−1", lambda: actions.retirer_scans_manuels(self.id_of, 1),
                                style="secondaire", atelier=True, width=64)
        self.btn_moins.pack(side=tk.RIGHT, padx=(T.ESPACE_S, 0))
        # Actions secondaires regroupées dans un menu : historique, tout annuler
        self.btn_plus_actions = bouton(bas, "Plus ▾", self._ouvrir_menu, style="fantome", width=80)
        self.btn_plus_actions.pack(side=tk.RIGHT, padx=(T.ESPACE_S, 0))
        self.menu = tk.Menu(self, tearoff=0, bg=T.SURFACE, fg=T.TEXTE, activebackground=T.PRIMAIRE,
                            activeforeground=T.BLANC, font=T.police(T.TAILLE_CORPS))
        self.menu.add_command(label="Historique des scans", command=lambda: actions.ouvrir_historique(self.id_of))
        self.menu.add_separator()
        self.menu.add_command(label="Tout annuler à ce poste…", command=lambda: actions.retirer_scans_manuels(self.id_of, "all"))

        # Ligne 5 : gamme (une pastille par opération)
        self.frise = ctk.CTkFrame(self, fg_color="transparent")
        self.frise.grid(row=5, column=0, sticky="ew", padx=T.ESPACE_L, pady=(T.ESPACE_M, 0))
        self._etapes = []

        # Ligne 6 : lignes de commande Sage rattachées
        self.cadre_lignes = ctk.CTkFrame(self, fg_color="transparent")
        self.cadre_lignes.grid(row=6, column=0, sticky="ew", padx=T.ESPACE_L, pady=(0, T.ESPACE_M))
        self._lignes = {}

        self.maj(vue)
        lier_clic(self, lambda e: actions.selectionner_of(self.id_of))

    # --- Mise à jour ---

    def maj(self, vue):
        self.pastille.definir(vue.etat)
        self.lbl_ref.configure(text=vue.prod)
        if vue.urgent != self._urgent_visible:
            self._urgent_visible = vue.urgent
            if vue.urgent:
                self.pastille_urgent.pack(side=tk.LEFT, padx=(T.ESPACE_S, 0))
            else:
                self.pastille_urgent.pack_forget()
        self.lbl_besoin.configure(text=vue.besoin, text_color=T.ERREUR_TEXTE if vue.retard else T.TEXTE_ATTENUE)
        self.lbl_compte.configure(text=f"{vue.scans} / {vue.qte}")
        self.lbl_design.configure(text=vue.design)
        self.lbl_dims.configure(text=vue.dimensions)
        self.lbl_obs.configure(text=vue.observations)
        self.barre.set(min(vue.scans / vue.qte, 1) if vue.qte else 0)
        self.barre.configure(progress_color=T.SUCCES_VIF if vue.etat == "terminee" else T.ALERTE)
        self.lbl_situation.configure(text=vue.situation, text_color=COULEUR_SITUATION.get(vue.etat, T.TEXTE))
        termine = vue.etat == "terminee"
        self.btn_plus.configure(state="disabled" if termine else "normal")
        self.btn_terminer.configure(state="disabled" if termine else "normal")
        self.btn_moins.configure(state="normal" if vue.scans else "disabled")
        self.menu.entryconfigure(2, state="normal" if vue.scans else "disabled")
        self._maj_frise(vue.etapes)
        self._maj_lignes(vue.lignes, of_termine=termine)

    def _maj_frise(self, etapes):
        cles = [(e.libelle, e.ici) for e in etapes]
        if cles != [(lbl.libelle, lbl.ici) for lbl in self._etapes]:
            for widget in self.frise.winfo_children():
                widget.destroy()
            self._etapes = []
            for i, etape in enumerate(etapes):
                rangee, colonne = divmod(i, ETAPES_PAR_RANGEE)
                if colonne:
                    ctk.CTkLabel(self.frise, text="›", font=T.police(T.TAILLE_SOUS_TITRE, gras=True),
                                 text_color=T.TEXTE_DESACTIVE).grid(row=rangee, column=2 * colonne - 1, padx=T.ESPACE_XS)
                label = ctk.CTkLabel(self.frise, text="", height=28, corner_radius=14, font=T.police(T.TAILLE_LEGENDE, gras=True))
                label.grid(row=rangee, column=2 * colonne, sticky="w", pady=(0, T.ESPACE_XS))
                label.libelle, label.ici = etape.libelle, etape.ici
                self._etapes.append(label)
        for label, etape in zip(self._etapes, etapes):
            if etape.faite:
                fond, couleur, prefixe = T.SUCCES_FOND, T.SUCCES_TEXTE, "✓ "
            elif etape.ici:
                fond, couleur, prefixe = T.PRIMAIRE, T.BLANC, ""
            elif etape.scans:
                fond, couleur, prefixe = T.ALERTE_FOND, T.ALERTE_TEXTE, ""
            else:
                fond, couleur, prefixe = T.NEUTRE_FOND, T.NEUTRE_TEXTE, ""
            suffixe = " · ce poste" if etape.ici else ""
            label.configure(text=f"   {prefixe}{etape.libelle} {etape.scans}/{etape.qte}{suffixe}   ", fg_color=fond, text_color=couleur)

    def _maj_lignes(self, lignes, of_termine=False):
        if [l.cle for l in lignes] != list(self._lignes):
            for widget in self.cadre_lignes.winfo_children():
                widget.destroy()
            self._lignes = {}
            if lignes:
                ctk.CTkLabel(self.cadre_lignes, text="Lignes de commande", font=T.police(T.TAILLE_LEGENDE, gras=True),
                             text_color=T.TEXTE_ATTENUE, anchor="w").pack(fill=tk.X, pady=(T.ESPACE_M, T.ESPACE_XS))
            for ligne in lignes:
                self._lignes[ligne.cle] = self._creer_ligne(ligne)
        for ligne in lignes:
            widgets = self._lignes[ligne.cle]
            widgets["pastille"].definir(ligne.etat)
            widgets["compte"].configure(text=f"{ligne.scans} / {ligne.qte}")
            widgets["plus"].configure(state="disabled" if of_termine or ligne.scans >= ligne.qte else "normal")
            widgets["moins"].configure(state="normal" if ligne.scans else "disabled")

    def _creer_ligne(self, ligne):
        rangee = ctk.CTkFrame(self.cadre_lignes, fg_color=T.CARTE, corner_radius=T.RAYON_CONTROLE)
        rangee.pack(fill=tk.X, pady=(0, T.ESPACE_XS))
        textes = ctk.CTkFrame(rangee, fg_color="transparent")
        textes.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=T.ESPACE_M, pady=T.ESPACE_XS)
        ctk.CTkLabel(textes, text=ligne.titre, font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE, anchor="w").pack(fill=tk.X)
        ctk.CTkLabel(textes, text=ligne.details, font=T.police(T.TAILLE_LEGENDE), text_color=T.TEXTE_ATTENUE, anchor="w").pack(fill=tk.X)
        plus = bouton(rangee, "+1", lambda: self.actions.ajouter_scans_manuels(self.id_of, 1, ligne.cle), style="primaire", width=48)
        plus.pack(side=tk.RIGHT, padx=(T.ESPACE_XS, T.ESPACE_S), pady=T.ESPACE_XS)
        moins = bouton(rangee, "−1", lambda: self.actions.retirer_scans_manuels(self.id_of, 1, ligne.cle), style="secondaire", width=48)
        moins.pack(side=tk.RIGHT, padx=T.ESPACE_XS, pady=T.ESPACE_XS)
        compte = ctk.CTkLabel(rangee, text="", font=T.police_chiffres(T.TAILLE_SOUS_TITRE), text_color=T.TEXTE, width=70)
        compte.pack(side=tk.RIGHT, padx=T.ESPACE_S)
        pastille = Pastille(rangee)
        pastille.pack(side=tk.RIGHT)
        lier_clic(rangee, lambda e: self.actions.selectionner_of(self.id_of))
        return {"pastille": pastille, "compte": compte, "plus": plus, "moins": moins}

    def _ouvrir_menu(self):
        bouton_menu = self.btn_plus_actions
        self.menu.tk_popup(bouton_menu.winfo_rootx(), bouton_menu.winfo_rooty() + bouton_menu.winfo_height())

    # --- Sélection et retour visuel ---

    def selectionner(self, actif):
        self._selectionnee = actif
        if self._timer_surbrillance is None:
            self.configure(border_color=T.PRIMAIRE if actif else T.SURFACE)

    def surligner(self, couleur=T.SUCCES_VIF):
        """Bordure colorée quelques instants (pièce qui vient d'être scannée)."""
        if self._timer_surbrillance is not None:
            self.after_cancel(self._timer_surbrillance)
        self.configure(border_color=couleur)
        self._timer_surbrillance = self.after(T.DUREE_SURBRILLANCE, self._fin_surbrillance)

    def _fin_surbrillance(self):
        self._timer_surbrillance = None
        if self.winfo_exists():
            self.configure(border_color=T.PRIMAIRE if self._selectionnee else T.SURFACE)
