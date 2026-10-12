"""Bureau d'Étude : commandes Sage, lignes commerciales et création des OF."""
import tkinter as tk
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from .. import theme as T
from ..domain import progression, sage
from ..domain.synthese import format_date
from ..journal import journal
from .composants import bouton, carte, champ, tableau, texte, titre
from .dialogs import AddOfDialog, HistoriqueDialog, ModifierOfDialog
from .widgets import get_icon, maj_tags_selection

LIBELLES_AVANCEMENT = {"encours": "En cours", "pas_demarre": "À faire", "terminee": "Terminée"}

# Filtre de la liste des commandes : libellé -> test sur (nombre d'OF, texte de la colonne Avancement).
# L'avancement est global : pièces sorties de la dernière opération de leur gamme, tous postes confondus.
FILTRES_BE = {
    "Toutes les commandes": lambda nb_of, etat: True,
    "Sans OF": lambda nb_of, etat: nb_of == 0,
    "Avec OF": lambda nb_of, etat: nb_of > 0,
    "À faire": lambda nb_of, etat: nb_of > 0 and etat == "À faire",
    "En cours": lambda nb_of, etat: etat == "En cours",
    "Terminées": lambda nb_of, etat: etat == "Terminée",
}


class GenerationOFMixin:

    def build_be_gen_ui(self):
        parent = self.tab_be_gen
        parent.columnconfigure(0, weight=30, uniform="generation")
        parent.columnconfigure(1, weight=70, uniform="generation")
        parent.rowconfigure(0, weight=1)
        self._timer_message_be = None

        # --- Gauche : commandes Sage ---
        gauche = carte(parent)
        gauche.grid(row=0, column=0, sticky="nsew", padx=(0, T.ESPACE_S))
        ligne_titre = ctk.CTkFrame(gauche, fg_color="transparent")
        ligne_titre.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        titre(ligne_titre, "Commandes Sage", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        self.lbl_nb_commandes_be = texte(ligne_titre, "")
        self.lbl_nb_commandes_be.pack(side=tk.RIGHT)
        self.search_be = champ(gauche, "Rechercher une commande ou un client")
        self.search_be.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        self.search_be.bind("<KeyRelease>", self.on_search_change)
        ligne_filtre = ctk.CTkFrame(gauche, fg_color="transparent")
        ligne_filtre.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        texte(ligne_filtre, "Afficher").pack(side=tk.LEFT)
        self.filtre_be = ctk.CTkOptionMenu(
            ligne_filtre, values=list(FILTRES_BE), command=lambda _: self.refresh_dashboard(), height=36, width=190,
            corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS, gras=True), dropdown_font=T.police(T.TAILLE_CORPS),
            fg_color=T.SURFACE, button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL, text_color=T.TEXTE)
        self.filtre_be.set("Toutes les commandes")
        self.filtre_be.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(T.ESPACE_S, 0))
        self.voir_cloturees = tk.BooleanVar(value=False)
        ctk.CTkSwitch(gauche, text="Afficher les commandes clôturées", variable=self.voir_cloturees,
                      command=self.refresh_dashboard, font=T.police(T.TAILLE_CORPS), text_color=T.TEXTE_ATTENUE,
                      progress_color=T.PRIMAIRE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        self.btn_cloture = bouton(gauche, "Clôturer la commande", self.basculer_cloture, style="secondaire", state="disabled")
        self.btn_cloture.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        cadre, self.tree_be_cmd = tableau(gauche, [("cmd", "Commande", 110, "w"), ("client", "Client", 150, "w"),
                                                   ("etat", "Avancement", 100, "center")])
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        self.tree_be_cmd.bind("<<TreeviewSelect>>", self.on_be_order_select)

        # --- Droite : lignes Sage puis OF ---
        droite = ctk.CTkFrame(parent, fg_color="transparent")
        droite.grid(row=0, column=1, sticky="nsew")
        droite.rowconfigure(0, weight=2)
        droite.rowconfigure(1, weight=3)
        droite.columnconfigure(0, weight=1)

        bloc_sage = carte(droite)
        bloc_sage.grid(row=0, column=0, sticky="nsew", pady=(0, T.ESPACE_S))
        entete = ctk.CTkFrame(bloc_sage, fg_color="transparent")
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_XS))
        self.lbl_be_commande = titre(entete, "Lignes de la commande", taille=T.TAILLE_TITRE)
        self.lbl_be_commande.pack(side=tk.LEFT)
        bouton(entete, "Créer un OF", self.add_of_dialog, style="primaire", icone=get_icon("plus")).pack(side=tk.RIGHT)
        self.lbl_be_message = ctk.CTkLabel(entete, text="", font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.SUCCES_VIF)
        self.lbl_be_message.pack(side=tk.RIGHT, padx=T.ESPACE_M)
        texte(bloc_sage, "Sélectionnez une ou plusieurs lignes (Ctrl/Cmd + clic), puis « Créer un OF ».").pack(
            fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        cadre, self.tree_be_sage = tableau(bloc_sage, [
            ("ligne", "Ligne", 70, "center"), ("ref", "Référence", 140, "w"), ("designation", "Désignation", 280, "w"),
            ("dim", "Dimensions", 120, "center"), ("qte", "Qté", 60, "center")], selection="extended")
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_be_sage.bind("<<TreeviewSelect>>", lambda e: maj_tags_selection(self.tree_be_sage))

        bloc_of = carte(droite)
        bloc_of.grid(row=1, column=0, sticky="nsew")
        entete_of = ctk.CTkFrame(bloc_of, fg_color="transparent")
        entete_of.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        titre(entete_of, "OF de la commande", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        self.btn_supprimer_of = bouton(entete_of, "Supprimer", self.supprimer_of_be, style="danger", width=110, state="disabled")
        self.btn_supprimer_of.pack(side=tk.RIGHT)
        self.btn_annuler_of = bouton(entete_of, "Annuler l'OF", self.basculer_annulation_of, style="secondaire", width=130, state="disabled")
        self.btn_annuler_of.pack(side=tk.RIGHT, padx=T.ESPACE_S)
        self.btn_historique_of = bouton(entete_of, "Historique", self.historique_of_be, style="secondaire", width=110, state="disabled")
        self.btn_historique_of.pack(side=tk.RIGHT)
        self.btn_modifier_of = bouton(entete_of, "Modifier", self.modifier_of_be, style="primaire", width=110, state="disabled")
        self.btn_modifier_of.pack(side=tk.RIGHT, padx=T.ESPACE_S)
        cadre, self.tree_be_of = tableau(bloc_of, [
            ("id", "OF", 90, "center"), ("prod", "Produit", 120, "w"), ("design", "Désignation", 200, "w"),
            ("dim", "Dimensions", 150, "center"), ("qte", "Qté", 50, "center"), ("besoin", "Besoin", 70, "center"),
            ("etat", "État", 110, "center"), ("parcours", "Gamme (poste assigné)", 220, "w")],
            arbre=True)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_be_of.bind("<<TreeviewSelect>>", lambda e: (maj_tags_selection(self.tree_be_of), self._maj_boutons_of()))
        self.tree_be_of.bind("<Double-1>", lambda e: self.modifier_of_be())

    def _message_be(self, message):
        """Confirmation discrète à côté du bouton, effacée au bout de quelques secondes."""
        if self._timer_message_be is not None:
            self.root.after_cancel(self._timer_message_be)
        self.lbl_be_message.configure(text=message)
        self._timer_message_be = self.root.after(T.DUREE_MESSAGE_SUCCES, lambda: self.lbl_be_message.configure(text=""))

    def _remplir_commandes_be(self, commandes):
        """Toutes les commandes Sage, avec leur avancement global."""
        selection = self.tree_be_cmd.selection()
        for item in self.tree_be_cmd.get_children():
            self.tree_be_cmd.delete(item)
        filtre = FILTRES_BE.get(self.filtre_be.get(), FILTRES_BE["Toutes les commandes"])
        lignes = []
        for do_piece, entete in commandes:
            cloturee = do_piece in self.etat.cloturees
            if cloturee and not self.voir_cloturees.get():
                continue
            nb_of = len(self.etat.ofs_par_cde.get(do_piece, []))
            _, _, tag = progression.avancement_global_commande(self.etat, do_piece)
            etat_texte = "Sans OF" if nb_of == 0 else LIBELLES_AVANCEMENT[tag]
            if not filtre(nb_of, etat_texte):
                continue
            if cloturee:
                tag, etat_texte = "cloturee", "Clôturée"
            lignes.append((progression.ORDRE_ETATS.get(tag, 1), (do_piece, entete.get("DO_Tiers", ""), etat_texte), tag))
        lignes.sort(key=lambda ligne: (ligne[2] == "cloturee", ligne[0]))
        for _, valeurs, tag in lignes:
            self.tree_be_cmd.insert("", "end", iid=valeurs[0], values=valeurs, tags=(tag,))
        self.lbl_nb_commandes_be.configure(text=f"{len(lignes)} commande{'s' if len(lignes) > 1 else ''}")
        if selection and self.tree_be_cmd.exists(selection[0]):
            self.tree_be_cmd.selection_set(selection[0])
        maj_tags_selection(self.tree_be_cmd)
        self._maj_bouton_cloture()

    def on_be_order_select(self, event=None):
        maj_tags_selection(self.tree_be_cmd)
        self._maj_bouton_cloture()
        selected = self.tree_be_cmd.selection()
        if not selected: return
        do_piece = selected[0]
        self.recharger_etat()
        client = self.sage.client(do_piece, "")
        self.lbl_be_commande.configure(text=f"Commande {do_piece}" + (f" · {client}" if client else ""))

        # 1. Lignes commerciales Sage de la commande
        for item in self.tree_be_sage.get_children():
            self.tree_be_sage.delete(item)
        lignes_cmd = sorted(self.sage.lignes_commande(do_piece), key=lambda x: x[1].get('DL_Ligne', ''))
        for key, ligne in lignes_cmd:
            self.tree_be_sage.insert("", "end", iid=key, values=(ligne.get("DL_Ligne", ""), ligne.get("AR_Ref", ""),
                                                                 ligne.get("DL_Design", ""), sage.dimensions(ligne),
                                                                 sage.lire_qte(ligne.get("DL_Qte", "1"))))

        # 2. OF existants de la commande, avec leurs lignes Sage en enfants
        for item in self.tree_be_of.get_children():
            self.tree_be_of.delete(item)
        for of in self.etat.tous_ofs_par_cde.get(do_piece, []):
            parcours = " › ".join(op + (f" ({poste})" if poste else "") for op, poste in self.etat.gamme(of.id))
            etat_texte, tag = self._etat_of_be(of)
            self.tree_be_of.insert("", "end", iid=of.id, values=(of.id, of.prod, of.design, of.dimensions, of.qte,
                                                                 format_date(of.date_besoin), etat_texte, parcours),
                                   open=False, tags=(tag,))
            for cle, l_qte, ligne in sage.lignes_enfants(self.sage, do_piece, of.lignes_sage):
                self.tree_be_of.insert(of.id, "end", iid=f"{of.id}_{cle}",
                                       values=(f"Ligne {ligne.get('DL_Ligne', '')}", ligne.get("AR_Ref", ""), ligne.get("DL_Design", ""),
                                               sage.dimensions(ligne), l_qte, "", "", ""),
                                       tags=('child',))
        self._maj_boutons_of()

    def selectionner_of_be(self, id_of):
        """Ouvre l'onglet Création d'OF sur la commande de cet OF, OF sélectionné."""
        of = self.etat.ofs.get(id_of)
        if not of:
            return
        self.notebook.set(self.NOM_ONGLET_GENERATION)
        self.search_be.delete(0, tk.END)
        self.filtre_be.set("Toutes les commandes")
        self.refresh_dashboard()
        if self.tree_be_cmd.exists(of.cde):
            self.tree_be_cmd.selection_set(of.cde)
            self.tree_be_cmd.see(of.cde)
            self.on_be_order_select()
        if self.tree_be_of.exists(of.id):
            self.tree_be_of.selection_set(of.id)
            self.tree_be_of.see(of.id)
            maj_tags_selection(self.tree_be_of)

    def _garder_commande_visible(self, cde):
        """Après une action, la commande traitée reste affichée et sélectionnée, même si le filtre l'aurait masquée."""
        if not self.tree_be_cmd.exists(cde) and (cde not in self.etat.cloturees or self.voir_cloturees.get()):
            self.filtre_be.set("Toutes les commandes")
            self.refresh_dashboard()
        if self.tree_be_cmd.exists(cde):
            self.tree_be_cmd.selection_set(cde)
            self.tree_be_cmd.see(cde)

    def add_of_dialog(self):
        selected = self.tree_be_cmd.selection()
        if not selected:
            messagebox.showwarning("Créer un OF", "Sélectionnez d'abord une commande dans la liste de gauche.")
            return

        do_piece = selected[0]
        valeurs = {"qte": 1, "design": "", "longueur": "", "largeur": ""}

        # Lignes Sage sélectionnées : désignation et dimensions de la première, somme des quantités
        selected_sage = self.tree_be_sage.selection()
        if selected_sage:
            premiere = self.sage.lignes.get(selected_sage[0], {})
            valeurs.update(design=premiere.get("DL_Design", ""), longueur=premiere.get("LONG", ""), largeur=premiere.get("LARG", ""),
                           qte=sum(sage.lire_qte(self.sage.lignes.get(s, {}).get("DL_Qte", "1"), 0) for s in selected_sage) or 1)

        dialog = AddOfDialog(self.root, self.depot, do_piece, self.sage.client(do_piece, ""), valeurs["qte"], valeurs["design"],
                             lignes_sage=",".join(selected_sage), longueur=valeurs["longueur"], largeur=valeurs["largeur"])
        self.root.wait_window(dialog)

        if dialog.result:
            journal().info("OF %s créé pour la commande %s", dialog.result, do_piece)
            self.refresh_dashboard()
            self._garder_commande_visible(do_piece)
            self.on_be_order_select()
            if self.tree_be_of.exists(dialog.result):
                self.tree_be_of.selection_set(dialog.result)
                self.tree_be_of.see(dialog.result)
                maj_tags_selection(self.tree_be_of)
            self._message_be(f"{dialog.result} créé")

    # --- État et actions sur les OF ---

    def _etat_of_be(self, of):
        """(texte, tag) de l'OF dans le tableau du Bureau d'Étude."""
        if of.annule:
            return "Annulé", "annule"
        if self.etat.termine(of):
            return "Terminé", "terminee"
        if self.etat.en_retard(of, date.today()):
            return "En retard", "bloque"
        en_cours = any(self.etat.compter(of.id, op) for op, _ in self.etat.gamme(of.id))
        texte_etat = "En cours" if en_cours else "À faire"
        if of.urgent:
            return f"Urgent · {texte_etat.lower()}", "bloque"
        return texte_etat, "encours" if en_cours else "pas_demarre"

    def _of_be_selectionne(self):
        selection = self.tree_be_of.selection()
        if not selection:
            return None
        item = selection[0]
        return self.etat.ofs.get(self.tree_be_of.parent(item) or item)

    def _maj_boutons_of(self):
        of = self._of_be_selectionne()
        etat = "normal" if of else "disabled"
        for btn in (self.btn_modifier_of, self.btn_historique_of, self.btn_annuler_of, self.btn_supprimer_of):
            btn.configure(state=etat)
        self.btn_annuler_of.configure(text="Réactiver l'OF" if of and of.annule else "Annuler l'OF")

    def _maj_bouton_cloture(self):
        selection = self.tree_be_cmd.selection()
        if not selection:
            self.btn_cloture.configure(state="disabled", text="Clôturer la commande")
            return
        cloturee = selection[0] in self.etat.cloturees
        self.btn_cloture.configure(state="normal", text="Rouvrir la commande" if cloturee else "Clôturer la commande")

    def _apres_action_of(self, message, id_of=None):
        selection = self.tree_be_cmd.selection()
        self.refresh_dashboard()
        if selection:
            self._garder_commande_visible(selection[0])
        self.on_be_order_select()
        if id_of and self.tree_be_of.exists(id_of):
            self.tree_be_of.selection_set(id_of)
            maj_tags_selection(self.tree_be_of)
            self._maj_boutons_of()
        self._message_be(message)
        if self.commande_affichee:
            self._afficher_commande(self.commande_affichee)

    def modifier_of_be(self):
        of = self._of_be_selectionne()
        if not of:
            return
        deja = max((self.etat.compter(of.id, op) for op, _ in self.etat.gamme(of.id)), default=0)
        dialog = ModifierOfDialog(self.root, self.depot, of, deja)
        self.root.wait_window(dialog)
        if dialog.result:
            journal().info("OF %s modifié", of.id)
            self._apres_action_of(f"{of.id} modifié", of.id)

    def historique_of_be(self):
        of = self._of_be_selectionne()
        if of:
            HistoriqueDialog(self.root, of, self.depot.historique_scans(of.id))

    def basculer_annulation_of(self):
        of = self._of_be_selectionne()
        if not of:
            return
        if of.annule:
            self.depot.changer_statut_of(of.id, "actif")
            journal().info("OF %s réactivé", of.id)
            self._apres_action_of(f"{of.id} réactivé", of.id)
            return
        if not messagebox.askyesno("Annuler l'OF", f"Annuler {of.id} ?\n\nIl disparaît de l'atelier et ne peut plus être "
                                                   "scanné. Ses scans restent dans l'historique ; vous pourrez le réactiver."):
            return
        self.depot.changer_statut_of(of.id, "annule")
        journal().info("OF %s annulé", of.id)
        self._apres_action_of(f"{of.id} annulé", of.id)

    def supprimer_of_be(self):
        of = self._of_be_selectionne()
        if not of:
            return
        if self.depot.nombre_scans(of.id):
            messagebox.showwarning("Supprimer l'OF", f"{of.id} a déjà été scanné : il ne peut pas être supprimé.\n\n"
                                                     "Utilisez « Annuler l'OF » pour le retirer de l'atelier.")
            return
        if not messagebox.askyesno("Supprimer l'OF", f"Supprimer définitivement {of.id} ?"):
            return
        self.depot.supprimer_of(of.id)
        journal().info("OF %s supprimé", of.id)
        self._apres_action_of(f"{of.id} supprimé")

    def basculer_cloture(self):
        selection = self.tree_be_cmd.selection()
        if not selection:
            return
        cde = selection[0]
        if cde in self.etat.cloturees:
            self.depot.rouvrir_commande(cde)
            journal().info("Commande %s rouverte", cde)
            self._apres_action_of(f"{cde} rouverte")
            return
        if not messagebox.askyesno("Clôturer la commande", f"Clôturer la commande {cde} ?\n\nElle disparaît de l'atelier "
                                                           "et ses OF ne peuvent plus être scannés. Vous pourrez la rouvrir."):
            return
        self.depot.cloturer_commande(cde)
        journal().info("Commande %s clôturée", cde)
        if not self.voir_cloturees.get():
            self.tree_be_cmd.selection_set(())
        self._apres_action_of(f"{cde} clôturée")
