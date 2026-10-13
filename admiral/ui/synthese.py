"""Onglet Synthèse : indicateurs du jour, avancement des commandes, état des postes."""
import tkinter as tk
from datetime import date, datetime

import customtkinter as ctk

from .. import theme as T
from ..domain import synthese
from .composants import MARGE_COLONNE, abreger, bouton, carte, polices_tableau, tableau, texte, titre
from .widgets import get_icon, maj_tags_selection

ACTUALISATION_AUTO_MS = 60_000
# Colonnes chiffrées de « Par poste » : en-têtes courts, expliqués par la légende
COLONNES_POSTES = [("jour", "Auj."), ("a_faire", "À faire"), ("en_cours", "En cours"),
                   ("termines", "Finis"), ("reste", "Reste")]
LEGENDE_POSTES = "Auj. : pièces du jour · Reste : pièces à faire\nÀ faire, En cours, Finis : nombre d'OF"
LARGEUR_MIN_POSTE = 80


class SyntheseMixin:

    def build_synthese_ui(self):
        parent = self.tab_synthese
        self._timer_synthese = None

        entete = ctk.CTkFrame(parent, fg_color="transparent")
        entete.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        titre(entete, "Synthèse de l'atelier", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        bouton(entete, "Actualiser", self.refresh_synthese, style="secondaire", icone=get_icon("refresh")).pack(side=tk.RIGHT)
        self.lbl_synthese_maj = texte(entete, "")
        self.lbl_synthese_maj.pack(side=tk.RIGHT, padx=T.ESPACE_M)

        # Indicateurs : un chiffre par tuile, libellé en dessous
        tuiles = ctk.CTkFrame(parent, fg_color="transparent")
        tuiles.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        self.tuiles = {}
        for i, (cle, libelle) in enumerate([("pieces_jour", "Pièces du jour"), ("of_a_faire", "OF à faire"),
                                            ("of_en_cours", "OF en cours"), ("of_termines", "OF terminés"),
                                            ("of_retard", "OF en retard"), ("avancement", "Avancement global")]):
            tuiles.columnconfigure(i, weight=1, uniform="tuiles")
            tuile = carte(tuiles)
            tuile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else T.ESPACE_S // 2, 0 if i == 5 else T.ESPACE_S // 2))
            valeur = ctk.CTkLabel(tuile, text="—", font=T.police_chiffres(T.TAILLE_CHIFFRE), text_color=T.TEXTE, anchor="w")
            valeur.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, 0))
            texte(tuile, libelle).pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
            self.tuiles[cle] = valeur
        self.barre_avancement = ctk.CTkProgressBar(tuile, height=8, corner_radius=4, fg_color=T.BORDURE, progress_color=T.SUCCES_VIF)
        self.barre_avancement.set(0)
        self.barre_avancement.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))

        # Dessous : avancement des commandes (60 %) et état des postes (40 %)
        bas = ctk.CTkFrame(parent, fg_color="transparent")
        bas.pack(expand=True, fill=tk.BOTH)
        bas.columnconfigure(0, weight=60, uniform="synthese")
        bas.columnconfigure(1, weight=40, uniform="synthese")
        bas.rowconfigure(0, weight=1)

        bloc_avancement = ctk.CTkFrame(bas, fg_color="transparent")
        bloc_avancement.grid(row=0, column=0, sticky="nsew", padx=(0, T.ESPACE_S // 2))
        self.build_be_matrice_ui(bloc_avancement)

        bloc_postes = carte(bas)
        bloc_postes.grid(row=0, column=1, sticky="nsew", padx=(T.ESPACE_S // 2, 0))
        titre(bloc_postes, "Par poste", taille=T.TAILLE_SOUS_TITRE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, 0))
        texte(bloc_postes, LEGENDE_POSTES, taille=T.TAILLE_LEGENDE, justify="left").pack(
            fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))

        police, police_entete = polices_tableau()
        cadre, self.tree_synthese_postes = tableau(bloc_postes, [("poste", "Poste", 160, "w")] + [
            (ident, libelle, police_entete.measure(libelle) + MARGE_COLONNE, "center") for ident, libelle in COLONNES_POSTES])
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_synthese_postes.column("poste", minwidth=LARGEUR_MIN_POSTE)
        self._noms_postes_synthese = {}
        self.tree_synthese_postes.bind("<<TreeviewSelect>>", lambda e: maj_tags_selection(self.tree_synthese_postes))
        self.tree_synthese_postes.bind("<Configure>", lambda e: self.root.after_idle(self._abreger_noms_postes), add="+")

    def refresh_synthese(self):
        etat = self.recharger_etat()
        s = synthese.calculer(etat, self.depot.lister_postes_complets(), self.depot.libelles_operations(),
                              self.depot.scans_du_jour_par_poste(), date.today())
        self.derniere_synthese = s
        for cle in ("pieces_jour", "of_a_faire", "of_en_cours", "of_termines", "of_retard"):
            self.tuiles[cle].configure(text=str(getattr(s, cle)))
        self.tuiles["of_retard"].configure(text_color=T.ERREUR_TEXTE if s.of_retard else T.TEXTE)
        self.tuiles["avancement"].configure(text=f"{s.avancement * 100:.0f} %")
        self.barre_avancement.set(s.avancement)
        self.lbl_synthese_maj.configure(text=f"Mis à jour à {datetime.now():%H:%M}")

        selection = self.tree_synthese_postes.selection()
        for item in self.tree_synthese_postes.get_children():
            self.tree_synthese_postes.delete(item)
        self._noms_postes_synthese = {}
        for ligne in s.postes:
            tag = "encours" if ligne.en_cours else ("pas_demarre" if ligne.a_faire else "terminee")
            self._noms_postes_synthese[ligne.code] = f"{ligne.code} · {ligne.designation}"
            self.tree_synthese_postes.insert("", "end", iid=ligne.code, tags=(tag,), values=(
                self._noms_postes_synthese[ligne.code], ligne.pieces_jour, ligne.a_faire,
                ligne.en_cours, ligne.termines, ligne.reste_operation))
        selection = [i for i in selection if self.tree_synthese_postes.exists(i)]
        if selection:
            self.tree_synthese_postes.selection_set(selection)
        maj_tags_selection(self.tree_synthese_postes)
        self._abreger_noms_postes()
        self.refresh_be_matrice(etat)

        # Actualisation automatique tant que l'onglet est affiché
        if self._timer_synthese is not None:
            self.root.after_cancel(self._timer_synthese)
        self._timer_synthese = self.root.after(ACTUALISATION_AUTO_MS, self._actualisation_auto_synthese)

    def _abreger_noms_postes(self):
        """Nom complet du poste s'il tient dans la colonne, sinon abrégé avec « … » (le code reste visible)."""
        arbre = self.tree_synthese_postes
        if not arbre.winfo_exists():
            return
        police, _ = polices_tableau()
        largeur = arbre.column("poste", "width") - MARGE_COLONNE
        for code, nom in self._noms_postes_synthese.items():
            if arbre.exists(code):
                arbre.set(code, "poste", abreger(nom, police, largeur) if police.measure(code) <= largeur else code)

    def _actualisation_auto_synthese(self):
        self._timer_synthese = None
        if self.notebook.get() == self.NOM_ONGLET_SYNTHESE:
            self.refresh_synthese()
