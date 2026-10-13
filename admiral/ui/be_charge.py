"""Charge des postes : OF à faire / en cours / terminés pour un poste, en colonnes de cartes."""
import tkinter as tk

import customtkinter as ctk

from .. import theme as T
from .composants import bouton, carte, lier_clic, texte, titre
from .widgets import get_icon

# Colonnes : état -> (titre, couleur d'accent de la colonne)
COLONNES = [
    ("pas_demarre", "À faire", T.NEUTRE_TEXTE),
    ("encours", "En cours", T.ALERTE_TEXTE),
    ("terminee", "Terminé sur ce poste", T.SUCCES_TEXTE),
]
MAX_CARTES_PAR_COLONNE = 60  # au-delà, CustomTkinter devient lent : on indique le reste
MAX_POSTES_BOUTONS = 8


class ChargeMixin:

    def build_be_charge_ui(self):
        parent = self.tab_be_charge
        self.poste_charge = None
        self.contenu_charge = {etat: [] for etat, _, _ in COLONNES}

        entete = carte(parent)
        entete.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        ligne = ctk.CTkFrame(entete, fg_color="transparent")
        ligne.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_XS))
        titre(ligne, "Charge des postes", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        bouton(ligne, "Actualiser", self.refresh_be_charge, style="secondaire", icone=get_icon("refresh")).pack(side=tk.RIGHT)
        self.cadre_choix_poste = ctk.CTkFrame(ligne, fg_color="transparent")
        self.cadre_choix_poste.pack(side=tk.LEFT, padx=T.ESPACE_XL)
        self.choix_poste = None
        self.lbl_charge_poste = texte(entete, "")
        self.lbl_charge_poste.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_M))

        colonnes = ctk.CTkFrame(parent, fg_color="transparent")
        colonnes.pack(expand=True, fill=tk.BOTH)
        self.colonnes_charge = {}
        for i, (etat, libelle, accent) in enumerate(COLONNES):
            colonnes.columnconfigure(i, weight=1, uniform="charge")
            colonne = carte(colonnes)
            colonne.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else T.ESPACE_S // 2, 0 if i == 2 else T.ESPACE_S // 2))
            haut = ctk.CTkFrame(colonne, fg_color="transparent")
            haut.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
            ctk.CTkLabel(haut, text=libelle, font=T.police(T.TAILLE_SOUS_TITRE, gras=True), text_color=accent).pack(side=tk.LEFT)
            compteur = ctk.CTkLabel(haut, text="0", height=26, corner_radius=13, fg_color=T.SURFACE,
                                    font=T.police_chiffres(T.TAILLE_CORPS), text_color=T.TEXTE, width=40)
            compteur.pack(side=tk.RIGHT)
            liste = ctk.CTkScrollableFrame(colonne, fg_color="transparent", scrollbar_button_color=T.BORDURE,
                                           scrollbar_button_hover_color=T.BORDURE_SURVOL)
            liste.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_S, pady=(0, T.ESPACE_S))
            self.colonnes_charge[etat] = {"compteur": compteur, "liste": liste}
        colonnes.rowconfigure(0, weight=1)

    def _construire_choix_poste(self, postes):
        """Boutons segmentés s'il y a peu de postes, liste déroulante sinon."""
        for widget in self.cadre_choix_poste.winfo_children():
            widget.destroy()
        codes = [code for code, _ in postes]
        if len(codes) <= MAX_POSTES_BOUTONS:
            self.choix_poste = ctk.CTkSegmentedButton(
                self.cadre_choix_poste, values=codes, command=self._on_choix_poste, height=36, corner_radius=15, border_width=3,
                font=T.police(T.TAILLE_CORPS, gras=True), fg_color=T.SURFACE, unselected_color=T.SURFACE,
                unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE, selected_hover_color=T.PRIMAIRE_SURVOL,
                text_color=T.TEXTE)
        else:
            self.choix_poste = ctk.CTkOptionMenu(
                self.cadre_choix_poste, values=codes, command=self._on_choix_poste, height=36, width=160,
                font=T.police(T.TAILLE_CORPS, gras=True), fg_color=T.SURFACE, button_color=T.BORDURE,
                button_hover_color=T.BORDURE_SURVOL, text_color=T.TEXTE)
        self.choix_poste.pack()

    def refresh_be_charge(self):
        postes = self.depot.lister_postes(trier=True)
        self._postes_charge = dict(postes)
        if self.choix_poste is None or list(self.choix_poste.cget("values")) != [c for c, _ in postes]:
            self._construire_choix_poste(postes)
        if not postes:
            return
        if self.poste_charge not in self._postes_charge:
            # Par défaut : le poste de ce PC s'il existe, sinon le premier
            self.poste_charge = self.get_codpost() if self.get_codpost() in self._postes_charge else postes[0][0]
        self.choix_poste.set(self.poste_charge)
        self.on_machine_select()

    def _on_choix_poste(self, codpost):
        self.poste_charge = codpost
        self.on_machine_select()

    def on_machine_select(self, event=None):
        codpost = self.poste_charge
        etat = self.recharger_etat()
        ref_op = etat.operation_poste.get(codpost)

        # OF dont une étape de gamme correspond à l'opération du poste (assignée à ce poste ou libre)
        par_colonne = {cle: [] for cle, _, _ in COLONNES}
        if ref_op:
            for of in etat.ofs.values():
                if any(code_op == ref_op and (not assigne or assigne == codpost) for code_op, assigne in etat.gamme(of.id)):
                    scans = etat.compter_poste(of.id, codpost)
                    cle = "pas_demarre" if scans == 0 else ("terminee" if scans >= of.qte else "encours")
                    par_colonne[cle].append((of, scans))

        total = sum(len(v) for v in par_colonne.values())
        libelle_op = self.depot.libelles_operations().get(ref_op, ref_op or "aucune opération")
        self.lbl_charge_poste.configure(
            text=f"Poste {codpost} · {self._postes_charge.get(codpost, '')} · opération {libelle_op} · {total} OF")

        for cle, _, _ in COLONNES:
            colonne = self.colonnes_charge[cle]
            for widget in colonne["liste"].winfo_children():
                widget.destroy()
            elements = par_colonne[cle]
            colonne["compteur"].configure(text=str(len(elements)))
            self.contenu_charge[cle] = [of.id for of, _ in elements]
            for of, scans in elements[:MAX_CARTES_PAR_COLONNE]:
                self._carte_charge(colonne["liste"], of, scans, cle)
            if len(elements) > MAX_CARTES_PAR_COLONNE:
                texte(colonne["liste"], f"… et {len(elements) - MAX_CARTES_PAR_COLONNE} autres OF").pack(fill=tk.X, padx=T.ESPACE_S, pady=T.ESPACE_S)
            if not elements:
                texte(colonne["liste"], "Aucun OF", anchor="center").pack(fill=tk.X, pady=T.ESPACE_XL)

    def _carte_charge(self, parent, of, scans, etat_colonne):
        mini = ctk.CTkFrame(parent, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE)
        mini.pack(fill=tk.X, padx=T.ESPACE_XS, pady=(0, T.ESPACE_S))
        haut = ctk.CTkFrame(mini, fg_color="transparent")
        haut.pack(fill=tk.X, padx=T.ESPACE_M, pady=(T.ESPACE_S, 0))
        ctk.CTkLabel(haut, text=of.id, font=T.police_chiffres(T.TAILLE_CORPS), text_color=T.TEXTE).pack(side=tk.LEFT)
        ctk.CTkLabel(haut, text=f"{scans} / {of.qte}", font=T.police_chiffres(T.TAILLE_CORPS), text_color=T.TEXTE).pack(side=tk.RIGHT)
        texte(mini, f"{of.cde} · {of.design}", taille=T.TAILLE_LEGENDE).pack(fill=tk.X, padx=T.ESPACE_M)
        barre = ctk.CTkProgressBar(mini, height=6, corner_radius=3, fg_color=T.BORDURE,
                                   progress_color=T.SUCCES_VIF if etat_colonne == "terminee" else T.ALERTE)
        barre.set(min(scans / of.qte, 1) if of.qte else 0)
        barre.pack(fill=tk.X, padx=T.ESPACE_M, pady=(T.ESPACE_XS, T.ESPACE_S))
        # Le changement d'onglet masque cette carte : on le fait après la fin du clic, jamais pendant
        # (sinon le contenu de l'onglet quitté reste dessiné par-dessus le nouvel onglet).
        lier_clic(mini, lambda e, id_of=of.id: self.root.after(30, self.selectionner_of_be, id_of))
