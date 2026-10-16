"""Onglet Administration : produits et gammes, opérations, postes, import du référentiel Excel."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as T
from ..domain import referentiel
from ..journal import journal
from .composants import bouton, carte, champ, tableau, texte, titre
from .widgets import maj_tags_selection

SECTIONS = ["Produits et gammes", "Opérations", "Postes", "Import Excel"]


class AdministrationMixin:

    def build_admin_ui(self):
        parent = self.tab_admin
        entete = ctk.CTkFrame(parent, fg_color="transparent")
        entete.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        titre(entete, "Administration du référentiel", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        self.choix_section_admin = ctk.CTkSegmentedButton(
            entete, values=SECTIONS, command=self._afficher_section_admin, height=36, corner_radius=15, border_width=3,
            font=T.police(T.TAILLE_CORPS, gras=True), fg_color=T.SURFACE, unselected_color=T.SURFACE,
            unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE, selected_hover_color=T.PRIMAIRE_SURVOL,
            text_color=T.TEXTE)
        self.choix_section_admin.pack(side=tk.LEFT, padx=T.ESPACE_XL)
        self.lbl_admin_message = ctk.CTkLabel(entete, text="", font=T.police(T.TAILLE_CORPS, gras=True))
        self.lbl_admin_message.pack(side=tk.RIGHT)
        self._timer_admin = None

        self.zone_admin = ctk.CTkFrame(parent, fg_color="transparent")
        self.zone_admin.pack(expand=True, fill=tk.BOTH)
        self.sections_admin = {
            "Produits et gammes": self._construire_produits(),
            "Opérations": self._construire_operations(),
            "Postes": self._construire_postes(),
            "Import Excel": self._construire_import(),
        }
        self.choix_section_admin.set(SECTIONS[0])
        self._afficher_section_admin(SECTIONS[0])

    # ===================== Outils communs =====================

    def _afficher_section_admin(self, nom):
        for section in self.sections_admin.values():
            section.pack_forget()
        self.sections_admin[nom].pack(expand=True, fill=tk.BOTH)

    def _message_admin(self, message, erreur=False):
        if self._timer_admin is not None:
            self.root.after_cancel(self._timer_admin)
        self.lbl_admin_message.configure(text=message, text_color=T.ERREUR_TEXTE if erreur else T.SUCCES_VIF)
        duree = T.DUREE_MESSAGE_ERREUR if erreur else T.DUREE_MESSAGE_SUCCES
        self._timer_admin = self.root.after(duree, lambda: self.lbl_admin_message.configure(text=""))

    def _section_liste_formulaire(self, titre_liste, colonnes, titre_formulaire):
        """Mise en page commune : tableau à gauche, formulaire à droite. Retourne (section, tree, formulaire)."""
        section = ctk.CTkFrame(self.zone_admin, fg_color="transparent")
        section.columnconfigure(0, weight=55, uniform="admin")
        section.columnconfigure(1, weight=45, uniform="admin")
        section.rowconfigure(0, weight=1)
        gauche = carte(section)
        gauche.grid(row=0, column=0, sticky="nsew", padx=(0, T.ESPACE_S // 2))
        titre(gauche, titre_liste).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        cadre, tree = tableau(gauche, colonnes)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        tree.bind("<<TreeviewSelect>>", lambda e, t=tree: maj_tags_selection(t), add="+")
        droite = carte(section)
        droite.grid(row=0, column=1, sticky="nsew", padx=(T.ESPACE_S // 2, 0))
        titre(droite, titre_formulaire).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        formulaire = ctk.CTkFrame(droite, fg_color="transparent")
        formulaire.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        return section, tree, formulaire

    @staticmethod
    def _ligne_champ(formulaire, libelle, placeholder=""):
        texte(formulaire, libelle, gras=True).pack(fill=tk.X, pady=(T.ESPACE_S, T.ESPACE_XS))
        entree = champ(formulaire, placeholder)
        entree.pack(fill=tk.X)
        return entree

    @staticmethod
    def _remplir(entree, valeur, modifiable=True):
        entree.configure(state="normal")
        entree.delete(0, tk.END)
        if valeur:
            entree.insert(0, valeur)
        entree.configure(state="normal" if modifiable else "disabled",
                         fg_color=T.SURFACE if modifiable else T.CARTE)

    @staticmethod
    def _boutons_formulaire(formulaire, enregistrer, nouveau, supprimer, libelle_nouveau):
        ligne = ctk.CTkFrame(formulaire, fg_color="transparent")
        ligne.pack(side=tk.BOTTOM, fill=tk.X, pady=(T.ESPACE_M, 0))
        bouton(ligne, "Enregistrer", enregistrer, style="primaire", width=130).pack(side=tk.LEFT)
        bouton(ligne, libelle_nouveau, nouveau, style="secondaire", width=130).pack(side=tk.LEFT, padx=T.ESPACE_S)
        bouton(ligne, "Supprimer", supprimer, style="danger", width=110).pack(side=tk.RIGHT)

    def _apres_modification_referentiel(self, message):
        self._message_admin(message)
        self.refresh_admin()
        self.refresh_dashboard()

    def refresh_admin(self):
        self._remplir_operations()
        self._remplir_postes()
        self._remplir_produits()

    # ===================== Opérations =====================

    def _construire_operations(self):
        section, self.tree_admin_ops, form = self._section_liste_formulaire(
            "Opérations", [("code", "Code", 90, "w"), ("libelle", "Libellé", 220, "w"), ("postes", "Postes", 160, "w")],
            "Opération")
        self.tree_admin_ops.bind("<<TreeviewSelect>>", self._choisir_operation, add="+")
        self.op_code = self._ligne_champ(form, "Code", "ex. LAV")
        self.op_libelle = self._ligne_champ(form, "Libellé", "ex. Lavage")
        texte(form, "Le code relie l'opération aux postes et aux gammes : il ne se modifie plus une fois créé.",
              taille=T.TAILLE_LEGENDE, wraplength=420, justify="left").pack(fill=tk.X, pady=(T.ESPACE_S, 0))
        self._boutons_formulaire(form, self._enregistrer_operation, self._nouvelle_operation, self._supprimer_operation,
                                 "Nouvelle")
        return section

    def _remplir_operations(self):
        postes_par_op = {}
        for code, _, ref_op in self.depot.lister_postes_complets():
            postes_par_op.setdefault(ref_op, []).append(code)
        for item in self.tree_admin_ops.get_children():
            self.tree_admin_ops.delete(item)
        for ref, libelle in self.depot.lister_operations():
            self.tree_admin_ops.insert("", "end", iid=ref, values=(ref, libelle, ", ".join(postes_par_op.get(ref, [])) or "—"),
                                       tags=("pas_demarre",))

    def _choisir_operation(self, event=None):
        selection = self.tree_admin_ops.selection()
        if selection:
            ref, libelle, _ = self.tree_admin_ops.item(selection[0], "values")
            self._remplir(self.op_code, ref, modifiable=False)
            self._remplir(self.op_libelle, libelle)

    def _nouvelle_operation(self):
        self.tree_admin_ops.selection_set(())
        self._remplir(self.op_code, "")
        self._remplir(self.op_libelle, "")
        self.op_code.focus_set()

    def _enregistrer_operation(self):
        code, libelle = self.op_code.get().strip().upper(), self.op_libelle.get().strip()
        if not code or not libelle:
            self._message_admin("Renseignez le code et le libellé de l'opération.", erreur=True)
            return
        try:
            self.depot.enregistrer_operation(code, libelle, creation=not self.tree_admin_ops.selection())
        except ValueError as exc:
            self._message_admin(str(exc), erreur=True)
            return
        journal().info("Opération %s enregistrée", code)
        self._apres_modification_referentiel(f"Opération {code} enregistrée")
        self.tree_admin_ops.selection_set(code)

    def _supprimer_operation(self):
        selection = self.tree_admin_ops.selection()
        if not selection or not messagebox.askyesno("Supprimer", f"Supprimer l'opération {selection[0]} ?"):
            return
        try:
            self.depot.supprimer_operation(selection[0])
        except ValueError as exc:
            self._message_admin(str(exc), erreur=True)
            return
        self._nouvelle_operation()
        self._apres_modification_referentiel(f"Opération {selection[0]} supprimée")

    # ===================== Postes =====================

    def _construire_postes(self):
        section, self.tree_admin_postes, form = self._section_liste_formulaire(
            "Postes", [("code", "Code", 90, "w"), ("designation", "Désignation", 240, "w"), ("operation", "Opération", 150, "w")],
            "Poste")
        self.tree_admin_postes.bind("<<TreeviewSelect>>", self._choisir_poste, add="+")
        self.poste_code = self._ligne_champ(form, "Code", "ex. FAC2")
        self.poste_designation = self._ligne_champ(form, "Désignation", "ex. Ligne Façonnage 2")
        texte(form, "Opération réalisée", gras=True).pack(fill=tk.X, pady=(T.ESPACE_S, T.ESPACE_XS))
        self.poste_operation = ctk.CTkComboBox(form, values=[], state="readonly", height=T.HAUTEUR_BOUTON,
                                               corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS),
                                               fg_color=T.SURFACE, border_color=T.BORDURE, text_color=T.TEXTE,
                                               button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL)
        self.poste_operation.pack(fill=tk.X)
        self._boutons_formulaire(form, self._enregistrer_poste, self._nouveau_poste, self._supprimer_poste, "Nouveau")
        return section

    def _remplir_postes(self):
        libelles = self.depot.libelles_operations()
        self.poste_operation.configure(values=[f"{ref} · {lib}" for ref, lib in libelles.items()])
        for item in self.tree_admin_postes.get_children():
            self.tree_admin_postes.delete(item)
        for code, designation, ref_op in self.depot.lister_postes_complets():
            self.tree_admin_postes.insert("", "end", iid=code, tags=("pas_demarre",),
                                          values=(code, designation, f"{ref_op} · {libelles.get(ref_op, '?')}"))

    def _choisir_poste(self, event=None):
        selection = self.tree_admin_postes.selection()
        if selection:
            code, designation, operation = self.tree_admin_postes.item(selection[0], "values")
            self._remplir(self.poste_code, code, modifiable=False)
            self._remplir(self.poste_designation, designation)
            self.poste_operation.set(operation)

    def _nouveau_poste(self):
        self.tree_admin_postes.selection_set(())
        self._remplir(self.poste_code, "")
        self._remplir(self.poste_designation, "")
        self.poste_operation.set("")
        self.poste_code.focus_set()

    def _enregistrer_poste(self):
        code, designation = self.poste_code.get().strip().upper(), self.poste_designation.get().strip()
        operation = self.poste_operation.get().split(" · ")[0]
        if not code or not designation or not operation:
            self._message_admin("Renseignez le code, la désignation et l'opération du poste.", erreur=True)
            return
        try:
            self.depot.enregistrer_poste(code, designation, operation, creation=not self.tree_admin_postes.selection())
        except ValueError as exc:
            self._message_admin(str(exc), erreur=True)
            return
        journal().info("Poste %s enregistré", code)
        self._apres_modification_referentiel(f"Poste {code} enregistré")
        self.tree_admin_postes.selection_set(code)

    def _supprimer_poste(self):
        selection = self.tree_admin_postes.selection()
        if not selection:
            return
        if selection[0] == self.get_codpost():
            self._message_admin("C'est le poste de ce PC : changez de poste avant de le supprimer.", erreur=True)
            return
        if not messagebox.askyesno("Supprimer", f"Supprimer le poste {selection[0]} ?"):
            return
        try:
            self.depot.supprimer_poste(selection[0])
        except ValueError as exc:
            self._message_admin(str(exc), erreur=True)
            return
        self._nouveau_poste()
        self._apres_modification_referentiel(f"Poste {selection[0]} supprimé")

    # ===================== Produits et gammes =====================

    def _construire_produits(self):
        section, self.tree_admin_produits, form = self._section_liste_formulaire(
            "Produits", [("ref", "Référence", 150, "w"), ("designation", "Désignation", 220, "w"), ("gamme", "Gamme", 200, "w")],
            "Produit et gamme standard")
        self.tree_admin_produits.bind("<<TreeviewSelect>>", self._choisir_produit_admin, add="+")
        self.produit_ref = self._ligne_champ(form, "Référence", "ex. VITR-4-16-4")
        self.produit_designation = self._ligne_champ(form, "Désignation", "ex. Double vitrage 4/16/4")
        texte(form, "Gamme standard (proposée à la création des OF)", gras=True).pack(fill=tk.X, pady=(T.ESPACE_M, T.ESPACE_XS))
        self._boutons_formulaire(form, self._enregistrer_produit, self._nouveau_produit, self._supprimer_produit, "Nouveau")
        ajout = ctk.CTkFrame(form, fg_color="transparent")
        ajout.pack(side=tk.BOTTOM, fill=tk.X, pady=(T.ESPACE_S, 0))
        self.gamme_ajout = ctk.CTkComboBox(ajout, values=[], state="readonly", height=36, corner_radius=T.RAYON_CONTROLE,
                                           font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE, border_color=T.BORDURE,
                                           text_color=T.TEXTE, button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL)
        self.gamme_ajout.pack(side=tk.LEFT, fill=tk.X, expand=True)
        bouton(ajout, "Ajouter l'opération", self._ajouter_etape, style="secondaire", height=36).pack(side=tk.LEFT, padx=(T.ESPACE_S, 0))
        self.liste_gamme = ctk.CTkScrollableFrame(form, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE, height=150)
        self.liste_gamme.pack(fill=tk.BOTH, expand=True)
        self.gamme_edition = []
        return section

    def _remplir_produits(self):
        libelles = self.depot.libelles_operations()
        self.gamme_ajout.configure(values=[f"{ref} · {lib}" for ref, lib in libelles.items()])
        for item in self.tree_admin_produits.get_children():
            self.tree_admin_produits.delete(item)
        for ref, designation in self.depot.lister_produits():
            gamme = " › ".join(op for _, op, _ in self.depot.gamme_produit(ref)) or "—"
            self.tree_admin_produits.insert("", "end", iid=ref, values=(ref, designation, gamme), tags=("pas_demarre",))

    def _choisir_produit_admin(self, event=None):
        selection = self.tree_admin_produits.selection()
        if not selection:
            return
        ref = selection[0]
        self._remplir(self.produit_ref, ref, modifiable=False)
        self._remplir(self.produit_designation, self.tree_admin_produits.item(ref, "values")[1])
        self.gamme_edition = [op for _, op, _ in self.depot.gamme_produit(ref)]
        self._dessiner_gamme()

    def _dessiner_gamme(self):
        libelles = self.depot.libelles_operations()
        for widget in self.liste_gamme.winfo_children():
            widget.destroy()
        if not self.gamme_edition:
            texte(self.liste_gamme, "Aucune opération : ajoutez-en ci-dessous.", anchor="center").pack(fill=tk.X, pady=T.ESPACE_L)
        dernier = len(self.gamme_edition) - 1
        for i, op in enumerate(self.gamme_edition):
            rangee = ctk.CTkFrame(self.liste_gamme, fg_color="transparent")
            rangee.pack(fill=tk.X, padx=T.ESPACE_S, pady=2)
            ctk.CTkLabel(rangee, text=str(i + 1), width=24, font=T.police_chiffres(T.TAILLE_CORPS), text_color=T.TEXTE_ATTENUE).pack(side=tk.LEFT)
            ctk.CTkLabel(rangee, text=f"{libelles.get(op, op)}  ({op})", font=T.police(T.TAILLE_CORPS, gras=True),
                         text_color=T.TEXTE, anchor="w").pack(side=tk.LEFT, padx=T.ESPACE_S)
            bouton(rangee, "✕", lambda i=i: self._retirer_etape(i), style="fantome", width=36, height=32).pack(side=tk.RIGHT)
            bouton(rangee, "↓", lambda i=i: self._deplacer_etape(i, 1), style="secondaire", width=36, height=32,
                   state="normal" if i < dernier else "disabled").pack(side=tk.RIGHT, padx=2)
            bouton(rangee, "↑", lambda i=i: self._deplacer_etape(i, -1), style="secondaire", width=36, height=32,
                   state="normal" if i > 0 else "disabled").pack(side=tk.RIGHT, padx=2)

    def _ajouter_etape(self):
        choix = self.gamme_ajout.get().split(" · ")[0]
        if choix in self.gamme_edition:
            self._message_admin(f"L'opération {choix} est déjà dans la gamme : une pièce ne la fait qu'une fois.", erreur=True)
            return
        if choix:
            self.gamme_edition.append(choix)
            self._dessiner_gamme()

    def _retirer_etape(self, index):
        del self.gamme_edition[index]
        self._dessiner_gamme()

    def _deplacer_etape(self, index, sens):
        cible = index + sens
        self.gamme_edition[index], self.gamme_edition[cible] = self.gamme_edition[cible], self.gamme_edition[index]
        self._dessiner_gamme()

    def _nouveau_produit(self):
        self.tree_admin_produits.selection_set(())
        self._remplir(self.produit_ref, "")
        self._remplir(self.produit_designation, "")
        self.gamme_edition = []
        self._dessiner_gamme()
        self.produit_ref.focus_set()

    def _enregistrer_produit(self):
        ref, designation = self.produit_ref.get().strip(), self.produit_designation.get().strip()
        if not ref or not designation:
            self._message_admin("Renseignez la référence et la désignation du produit.", erreur=True)
            return
        try:
            self.depot.enregistrer_produit(ref, designation, list(self.gamme_edition),
                                           creation=not self.tree_admin_produits.selection())
        except ValueError as exc:
            self._message_admin(str(exc), erreur=True)
            return
        journal().info("Produit %s enregistré, gamme %s", ref, self.gamme_edition)
        self._apres_modification_referentiel(f"Produit {ref} enregistré")
        self.tree_admin_produits.selection_set(ref)

    def _supprimer_produit(self):
        selection = self.tree_admin_produits.selection()
        if not selection or not messagebox.askyesno("Supprimer", f"Supprimer le produit {selection[0]} et sa gamme ?"):
            return
        try:
            self.depot.supprimer_produit(selection[0])
        except ValueError as exc:
            self._message_admin(str(exc), erreur=True)
            return
        self._nouveau_produit()
        self._apres_modification_referentiel(f"Produit {selection[0]} supprimé")

    # ===================== Import Excel =====================

    def _construire_import(self):
        section = carte(self.zone_admin)
        titre(section, "Importer le référentiel depuis Excel", taille=T.TAILLE_SOUS_TITRE).pack(
            fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_XL, T.ESPACE_XS))
        texte(section, "Lit les feuilles PRODUIT, OPERATION, POSTE et GAMPROD de l'export Sage. Les éléments existants "
                       "sont mis à jour, les nouveaux ajoutés, et la gamme des produits présents dans GAMPROD est remplacée. "
                       "Les OF et les scans ne sont jamais touchés.", wraplength=820, justify="left").pack(fill=tk.X, padx=T.ESPACE_XL)
        ligne = ctk.CTkFrame(section, fg_color="transparent")
        ligne.pack(fill=tk.X, padx=T.ESPACE_XL, pady=T.ESPACE_L)
        bouton(ligne, "Choisir un fichier Excel…", self._choisir_fichier_import, style="secondaire").pack(side=tk.LEFT)
        self.lbl_fichier_import = texte(ligne, "Aucun fichier choisi")
        self.lbl_fichier_import.pack(side=tk.LEFT, padx=T.ESPACE_M)
        self.lbl_apercu_import = texte(section, "", couleur=T.TEXTE, wraplength=820, justify="left")
        self.lbl_apercu_import.pack(fill=tk.X, padx=T.ESPACE_XL)
        self.btn_importer = bouton(section, "Importer", self._importer_referentiel, style="primaire", width=160, state="disabled")
        self.btn_importer.pack(anchor="w", padx=T.ESPACE_XL, pady=T.ESPACE_L)
        self._referentiel_a_importer = None
        return section

    def _choisir_fichier_import(self):
        chemin = filedialog.askopenfilename(title="Référentiel Sage (Excel)",
                                            filetypes=[("Classeurs Excel", "*.xlsx *.xlsm"), ("Tous les fichiers", "*.*")])
        if chemin:
            self.preparer_import(chemin)

    def preparer_import(self, chemin):
        """Lit le fichier et affiche ce qui sera importé, sans rien écrire."""
        self._referentiel_a_importer = None
        self.btn_importer.configure(state="disabled")
        self.lbl_fichier_import.configure(text=os.path.basename(chemin))
        try:
            ref = referentiel.analyser(referentiel.lire_classeur(chemin))
        except Exception as exc:  # fichier illisible, openpyxl absent…
            journal().warning("Import Excel impossible (%s) : %s", chemin, exc)
            self.lbl_apercu_import.configure(text=f"Lecture impossible : {exc}", text_color=T.ERREUR_TEXTE)
            return
        if ref.vide:
            self.lbl_apercu_import.configure(text="Aucune donnée trouvée : le classeur doit contenir au moins une des feuilles "
                                                  "PRODUIT, OPERATION, POSTE ou GAMPROD.", text_color=T.ERREUR_TEXTE)
            return
        self._referentiel_a_importer = ref
        self.lbl_apercu_import.configure(
            text=f"Prêt à importer : {len(ref.operations)} opérations, {len(ref.postes)} postes, "
                 f"{len(ref.produits)} produits et {len(ref.gammes)} gammes.", text_color=T.TEXTE)
        self.btn_importer.configure(state="normal")

    def _importer_referentiel(self):
        if not self._referentiel_a_importer:
            return
        compte = self.depot.importer_referentiel(self._referentiel_a_importer)
        avertissements = compte.pop("avertissements", [])
        resume = ", ".join(f"{n} {quoi}" for quoi, n in compte.items())
        journal().info("Référentiel importé : %s ; non appliqué : %s", resume, avertissements)
        message = f"Import terminé : {resume}."
        if avertissements:
            message += "\nNon appliqué : " + " ; ".join(avertissements) + "."
        self.lbl_apercu_import.configure(text=message, text_color=T.ALERTE_TEXTE if avertissements else T.SUCCES_VIF)
        self.btn_importer.configure(state="disabled")
        self._referentiel_a_importer = None
        self._apres_modification_referentiel("Référentiel importé")
