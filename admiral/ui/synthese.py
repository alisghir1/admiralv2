"""Onglet Synthèse : indicateurs du jour, charge par poste, OF à surveiller."""
import tkinter as tk
from datetime import date, datetime

import customtkinter as ctk

from .. import theme as T
from ..domain import synthese
from .composants import bouton, carte, tableau, texte, titre
from .widgets import get_icon, maj_tags_selection

ACTUALISATION_AUTO_MS = 60_000


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

        bas = ctk.CTkFrame(parent, fg_color="transparent")
        bas.pack(expand=True, fill=tk.BOTH)
        bas.columnconfigure(0, weight=1, uniform="synthese")
        bas.columnconfigure(1, weight=1, uniform="synthese")
        bas.rowconfigure(0, weight=1)

        bloc_postes = carte(bas)
        bloc_postes.grid(row=0, column=0, sticky="nsew", padx=(0, T.ESPACE_S // 2))
        titre(bloc_postes, "Par poste", taille=T.TAILLE_SOUS_TITRE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        cadre, self.tree_synthese_postes = tableau(bloc_postes, [
            ("poste", "Poste", 160, "w"), ("operation", "Opération", 110, "w"), ("jour", "Aujourd'hui", 90, "center"),
            ("a_faire", "À faire", 70, "center"), ("en_cours", "En cours", 80, "center"), ("termines", "Terminés", 80, "center"),
            ("reste", "Pièces restantes", 120, "center")])
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_synthese_postes.bind("<<TreeviewSelect>>", lambda e: maj_tags_selection(self.tree_synthese_postes))

        bloc_alertes = carte(bas)
        bloc_alertes.grid(row=0, column=1, sticky="nsew", padx=(T.ESPACE_S // 2, 0))
        titre(bloc_alertes, "OF à surveiller", taille=T.TAILLE_SOUS_TITRE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, 0))
        texte(bloc_alertes, "En retard ou urgents, pas encore terminés. Double-clic : ouvrir l'OF.").pack(
            fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        cadre, self.tree_surveiller = tableau(bloc_alertes, [
            ("of", "OF", 90, "center"), ("cde", "Commande", 100, "w"), ("design", "Désignation", 170, "w"),
            ("motif", "Motif", 190, "w"), ("etape", "Prochaine étape", 140, "w")])
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_surveiller.bind("<<TreeviewSelect>>", lambda e: maj_tags_selection(self.tree_surveiller))
        self.tree_surveiller.bind("<Double-1>", self._ouvrir_of_surveille)

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

        for tree in (self.tree_synthese_postes, self.tree_surveiller):
            for item in tree.get_children():
                tree.delete(item)
        for ligne in s.postes:
            tag = "encours" if ligne.en_cours else ("pas_demarre" if ligne.a_faire else "terminee")
            self.tree_synthese_postes.insert("", "end", iid=ligne.code, tags=(tag,), values=(
                f"{ligne.code} · {ligne.designation}", ligne.operation, ligne.pieces_jour, ligne.a_faire,
                ligne.en_cours, ligne.termines, ligne.reste_operation))
        for alerte in s.a_surveiller:
            of = alerte.of
            self.tree_surveiller.insert("", "end", iid=of.id, tags=("bloque" if alerte.retard else "encours",),
                                        values=(of.id, of.cde, of.design, alerte.motif, alerte.etape))
        if not s.a_surveiller:
            self.tree_surveiller.insert("", "end", values=("", "", "Rien à signaler", "", ""), tags=("terminee",))

        # Actualisation automatique tant que l'onglet est affiché
        if self._timer_synthese is not None:
            self.root.after_cancel(self._timer_synthese)
        self._timer_synthese = self.root.after(ACTUALISATION_AUTO_MS, self._actualisation_auto_synthese)

    def _actualisation_auto_synthese(self):
        self._timer_synthese = None
        if self.notebook.get() == self.NOM_ONGLET_SYNTHESE:
            self.refresh_synthese()

    def _ouvrir_of_surveille(self, event=None):
        selection = self.tree_surveiller.selection()
        if selection and selection[0] in self.etat.ofs:
            self.selectionner_of_be(selection[0])
