"""Écran Atelier : commandes du poste, cartes d'OF, bandeau de scan."""
import tkinter as tk
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from .. import theme as T
from ..domain import progression, sage
from ..domain.synthese import format_date
from ..journal import journal
from .carte_of import CarteOF, VueEtape, VueLigne, VueOF
from .composants import bouton, carte, champ, defiler_vers, tableau, texte, titre
from .dialogs import HistoriqueDialog
from .widgets import FenetreDialogue, get_icon, maj_tags_selection

FILTRES_COMMANDES = {"Toutes": None, "En cours": "encours", "À faire": "pas_demarre", "Terminées": "terminee"}
LIBELLES_AVANCEMENT = {"encours": "En cours", "pas_demarre": "À faire", "terminee": "Terminée"}

# Bandeau de scan : type de message -> (fond, texte principal, texte secondaire)
COULEURS_BANDEAU = {
    "error": (T.ERREUR, T.BLANC, T.BLANC),
    "success": (T.SUCCES, T.BLANC, T.BLANC),
    "progress": (T.PRIMAIRE, T.BLANC, T.BLANC),
    "warning": (T.ALERTE, T.FOND, T.FOND),
    "default": (T.CARTE, T.TEXTE, T.TEXTE_ATTENUE),
}
MESSAGE_ATTENTE = ("Prêt à scanner", "Scannez le code d'un OF (OF-1001) ou d'une commande (CMD-CC240001)")


class AtelierMixin:

    # ===================== Construction =====================

    def build_atelier_ui(self, parent):
        self.cartes = {}
        self.of_selectionne = None
        self.commande_affichee = None
        self._timer_bandeau = None

        parent.columnconfigure(0, weight=36, uniform="atelier")
        parent.columnconfigure(1, weight=64, uniform="atelier")
        parent.rowconfigure(0, weight=1)

        self._construire_liste_commandes(parent)
        self._construire_detail_commande(parent)
        self._construire_bandeau_scan(parent)

    def _construire_liste_commandes(self, parent):
        panneau = carte(parent)
        panneau.grid(row=0, column=0, sticky="nsew", padx=(0, T.ESPACE_S), pady=(0, T.ESPACE_S))

        entete = ctk.CTkFrame(panneau, fg_color="transparent")
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        titre(entete, "Commandes du poste", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        self.lbl_nb_commandes = texte(entete, "", taille=T.TAILLE_CORPS)
        self.lbl_nb_commandes.pack(side=tk.RIGHT)

        self.search_entry = champ(panneau, "Rechercher une commande ou un client")
        self.search_entry.pack(fill=tk.X, padx=T.ESPACE_L)
        self.search_entry.bind("<KeyRelease>", self.on_search_change)

        self.filtre_commandes = ctk.CTkSegmentedButton(
            panneau, values=list(FILTRES_COMMANDES), command=lambda _: self._appliquer_recherche(),
            height=36, corner_radius=15, border_width=3, font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE, unselected_color=T.SURFACE,
            unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE, selected_hover_color=T.PRIMAIRE_SURVOL,
            text_color=T.TEXTE)
        self.filtre_commandes.set("Toutes")
        self.filtre_commandes.pack(fill=tk.X, padx=T.ESPACE_L, pady=T.ESPACE_S)

        cadre, self.tree_cmd = tableau(panneau, [
            ("commande", "Commande", 120, "w"), ("client", "Client", 160, "w"),
            ("avancement", "Pièces", 80, "center"), ("etat", "État", 100, "center")], style="Atelier.Treeview")
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_cmd.bind("<<TreeviewSelect>>", self.on_order_select)

    def _construire_detail_commande(self, parent):
        panneau = carte(parent)
        panneau.grid(row=0, column=1, sticky="nsew", pady=(0, T.ESPACE_S))

        entete = ctk.CTkFrame(panneau, fg_color="transparent")
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        self.lbl_commande = titre(entete, "Aucune commande sélectionnée", taille=T.TAILLE_TITRE)
        self.lbl_commande.pack(side=tk.LEFT)
        self.lbl_client = texte(entete, "", taille=T.TAILLE_SOUS_TITRE, couleur=T.TEXTE)
        self.lbl_client.pack(side=tk.LEFT, padx=(T.ESPACE_M, 0))
        self.lbl_resume = texte(entete, "", taille=T.TAILLE_CORPS)
        self.lbl_resume.pack(side=tk.RIGHT)

        self.zone_cartes = ctk.CTkScrollableFrame(panneau, fg_color="transparent", scrollbar_button_color=T.BORDURE,
                                                  scrollbar_button_hover_color=T.BORDURE_SURVOL)
        self.zone_cartes.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_S, pady=(0, T.ESPACE_S))
        self.lbl_vide = ctk.CTkLabel(self.zone_cartes, text="", font=T.police(T.TAILLE_SOUS_TITRE),
                                     text_color=T.TEXTE_ATTENUE, wraplength=520, justify="center")
        self._afficher_vide("Sélectionnez une commande à gauche, ou scannez un code CMD-…")

    def _construire_bandeau_scan(self, parent):
        self.status_frame = ctk.CTkFrame(parent, fg_color=T.CARTE, corner_radius=T.RAYON_CARTE, height=112)
        self.status_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status_frame.grid_propagate(False)
        self.status_frame.columnconfigure(0, weight=1)

        messages = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        messages.grid(row=0, column=0, sticky="w", padx=T.ESPACE_XL)
        self.lbl_scan_status = ctk.CTkLabel(messages, text="", font=T.police(T.TAILLE_TITRE, gras=True), anchor="w")
        self.lbl_scan_status.pack(fill=tk.X)
        self.lbl_scan_detail = ctk.CTkLabel(messages, text="", font=T.police(T.TAILLE_SOUS_TITRE), anchor="w", wraplength=620, justify="left")
        self.lbl_scan_detail.pack(fill=tk.X)

        saisie = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        saisie.grid(row=0, column=1, padx=T.ESPACE_L)
        self.scan_var = tk.StringVar()
        self.scan_entry = ctk.CTkEntry(saisie, textvariable=self.scan_var, font=T.police_chiffres(22), justify="center",
                                       width=360, height=52, corner_radius=T.RAYON_CONTROLE, border_width=2,
                                       border_color=T.PRIMAIRE, fg_color=T.SURFACE, text_color=T.TEXTE)
        self.scan_entry.pack()
        self.lbl_focus_scan = ctk.CTkLabel(saisie, text="", font=T.police(T.TAILLE_LEGENDE, gras=True), height=18)
        self.lbl_focus_scan.pack(pady=(T.ESPACE_XS, 0))
        self.scan_entry.bind("<Return>", self.on_scan)
        self.scan_entry.bind("<FocusIn>", lambda e: self._maj_indicateur_focus(True))
        self.scan_entry.bind("<FocusOut>", lambda e: self._maj_indicateur_focus(False))

        droite = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        droite.grid(row=0, column=2, padx=(0, T.ESPACE_XL))
        self.lbl_scan_compte = ctk.CTkLabel(droite, text="", font=T.police_chiffres(T.TAILLE_CHIFFRE_SCAN), width=170)
        self.lbl_scan_compte.pack()
        self.btn_simulateur = bouton(droite, "Simuler un scan", self.open_scan_simulator, style="fantome",
                                     icone=get_icon("barcode"), height=30)
        self.btn_simulateur.pack()

        self.status_frame.rowconfigure(0, weight=1)
        self.update_status_bar("default", *MESSAGE_ATTENTE)

    def _maj_indicateur_focus(self, actif):
        # Sans focus, la douchette tape dans le vide : on le signale clairement.
        if actif:
            self.scan_entry.configure(border_color=T.PRIMAIRE)
            self.lbl_focus_scan.configure(text="Douchette active", text_color=T.SUCCES_VIF)
        else:
            self.scan_entry.configure(border_color=T.ALERTE)
            self.lbl_focus_scan.configure(text="Cliquez ici pour scanner", text_color=T.ALERTE_TEXTE)

    # ===================== Bandeau de scan =====================

    def update_status_bar(self, status_type, message, detail="", compte=""):
        fond, couleur, couleur_detail = COULEURS_BANDEAU.get(status_type, COULEURS_BANDEAU["default"])
        self.status_frame.configure(fg_color=fond)
        self.lbl_scan_status.configure(text=message, text_color=couleur)
        self.lbl_scan_detail.configure(text=detail, text_color=couleur_detail)
        self.lbl_scan_compte.configure(text=compte, text_color=couleur)
        self.btn_simulateur.configure(text_color=couleur_detail)
        if status_type == "error":
            journal().warning("%s %s", message, detail)
        # Un message de résultat s'efface seul ; l'erreur reste un peu plus longtemps
        if self._timer_bandeau is not None:
            self.root.after_cancel(self._timer_bandeau)
            self._timer_bandeau = None
        if status_type != "default":
            duree = T.DUREE_MESSAGE_ERREUR if status_type == "error" else T.DUREE_MESSAGE_SUCCES
            self._timer_bandeau = self.root.after(duree, self._bandeau_au_repos)

    def _bandeau_au_repos(self):
        self._timer_bandeau = None
        self.update_status_bar("default", *MESSAGE_ATTENTE)

    # ===================== Liste des commandes =====================

    def _remplir_commandes_atelier(self, commandes):
        """Commandes dont au moins un OF passe par ce poste, triées En cours > À faire > Terminées."""
        selection = self.tree_cmd.selection()
        for item in self.tree_cmd.get_children():
            self.tree_cmd.delete(item)
        filtre_etat = FILTRES_COMMANDES.get(self.filtre_commandes.get())
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        lignes = []
        for do_piece, entete in commandes:
            if do_piece in self.etat.cloturees:
                continue  # commande livrée : plus rien à faire en atelier
            scanned, total, pct_str = progression.avancement_commande(self.etat, do_piece, mon_op, codpost)
            if total == 0:
                continue  # aucun OF de cette commande ne passe par ce poste
            tag = progression.tag_avancement(scanned, total)
            if filtre_etat and tag != filtre_etat:
                continue
            valeurs = (do_piece, entete.get("DO_Tiers", ""), f"{scanned} / {total}", LIBELLES_AVANCEMENT[tag])
            lignes.append((progression.ORDRE_ETATS.get(tag, 1), valeurs, tag))
        lignes.sort(key=lambda ligne: ligne[0])
        for _, valeurs, tag in lignes:
            self.tree_cmd.insert("", "end", iid=valeurs[0], values=valeurs, tags=(tag,))
        self.lbl_nb_commandes.configure(text=f"{len(lignes)} commande{'s' if len(lignes) > 1 else ''}")
        if selection and self.tree_cmd.exists(selection[0]):
            self.tree_cmd.selection_set(selection[0])
        maj_tags_selection(self.tree_cmd)

    def _update_single_cmd_in_tree(self, do_piece):
        if not self.tree_cmd.exists(do_piece):
            return
        scanned, total, _ = progression.avancement_commande(self.etat, do_piece, self.get_mon_op(), self.get_codpost())
        tag = progression.tag_avancement(scanned, total)
        valeurs = self.tree_cmd.item(do_piece, "values")
        self.tree_cmd.item(do_piece, values=(valeurs[0], valeurs[1], f"{scanned} / {total}", LIBELLES_AVANCEMENT[tag]), tags=(tag,))
        maj_tags_selection(self.tree_cmd)

    def on_order_select(self, event=None):
        maj_tags_selection(self.tree_cmd)
        selected = self.tree_cmd.selection()
        if not selected:
            return
        self.recharger_etat()
        self._afficher_commande(selected[0])
        self.scan_entry.focus_set()

    # ===================== Cartes d'OF =====================

    def _afficher_vide(self, message):
        for carte_of in self.cartes.values():
            carte_of.destroy()
        self.cartes = {}
        self.lbl_vide.configure(text=message)
        self.lbl_vide.pack(fill=tk.X, pady=80)

    def _vue_of(self, of, mon_op, codpost, libelles):
        """Données d'affichage d'un OF vu depuis ce poste, ou None s'il ne passe pas par ce poste."""
        gamme = self.etat.gamme(of.id)
        index = progression.index_etape(gamme, mon_op, codpost)
        if index == -1:
            return None
        mes_scans = self.etat.compter(of.id, mon_op)
        dispo = progression.disponibles(self.etat, of, gamme, index, mon_op)
        etat_poste = progression.etat_au_poste(of.qte, mes_scans, dispo)
        prev_op = gamme[index - 1][0] if index > 0 else None
        situation = progression.situation_au_poste(
            etat_poste, dispo, libelles.get(prev_op, prev_op) if prev_op else None,
            self.etat.compter(of.id, prev_op) if prev_op else 0, of.qte)

        etapes = [VueEtape(libelles.get(op, op), self.etat.compter(of.id, op), of.qte, i == index)
                  for i, (op, _) in enumerate(gamme)]

        enfants = sage.lignes_enfants(self.sage, of.cde, of.lignes_sage)
        repartis = progression.repartir_scans(self.etat, of.id, mon_op, enfants)
        lignes = []
        for cle, l_qte, ligne in enfants:
            details = " · ".join(filter(None, [ligne.get("DL_Design", ""), sage.dimensions(ligne)]))
            lignes.append(VueLigne(cle, f"Ligne {ligne.get('DL_Ligne', '')} · {ligne.get('AR_Ref', '')}", details,
                                   l_qte, repartis[cle], progression.statut_ligne(repartis[cle], l_qte)[1]))

        retard = self.etat.en_retard(of, date.today())
        besoin = ""
        if of.date_besoin:
            besoin = f"En retard · besoin le {format_date(of.date_besoin)}" if retard else f"Besoin le {format_date(of.date_besoin)}"
        return VueOF(of.id, of.prod, of.design, of.dimensions, of.observations, of.qte, mes_scans,
                     etat_poste, situation, etapes, lignes, of.urgent, besoin, retard)

    def update_lines_view(self, do_piece):
        """Affiche (ou met à jour sur place) les cartes des OF de la commande qui passent par ce poste."""
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        if do_piece in self.etat.cloturees:
            self._afficher_vide(f"La commande {do_piece} est clôturée : plus rien à produire.")
            self.lbl_resume.configure(text="")
            return
        libelles = self.depot.libelles_operations()
        vues = [v for v in (self._vue_of(of, mon_op, codpost, libelles) for of in self.etat.ofs_par_cde.get(do_piece, [])) if v]
        # Urgents d'abord, puis par date de besoin (sans date à la fin), puis ordre de création
        ordre = {v.id: i for i, v in enumerate(vues)}
        besoins = {of.id: of.date_besoin or "9999" for of in self.etat.ofs_par_cde.get(do_piece, [])}
        vues.sort(key=lambda v: (not v.urgent, besoins[v.id], ordre[v.id]))

        if not vues:
            raison = "Ce poste n'a pas d'opération configurée." if not mon_op else \
                f"Aucun OF de cette commande ne passe par le poste {codpost}."
            self._afficher_vide(raison)
            self.lbl_resume.configure(text="")
            return

        self.lbl_vide.pack_forget()
        if [v.id for v in vues] == list(self.cartes):
            for vue in vues:
                self.cartes[vue.id].maj(vue)
        else:
            for carte_of in self.cartes.values():
                carte_of.destroy()
            self.cartes = {}
            for vue in vues:
                carte_of = CarteOF(self.zone_cartes, vue, self)
                carte_of.pack(fill=tk.X, padx=T.ESPACE_S, pady=(0, T.ESPACE_M))
                self.cartes[vue.id] = carte_of

        faites = sum(min(v.scans, v.qte) for v in vues)
        prevues = sum(v.qte for v in vues)
        self.lbl_resume.configure(text=f"{len(vues)} OF · {faites} / {prevues} pièces")
        if self.of_selectionne not in self.cartes:
            self.of_selectionne = None
        for id_of, carte_of in self.cartes.items():
            carte_of.selectionner(id_of == self.of_selectionne)

    def _afficher_commande(self, do_piece):
        if do_piece != self.commande_affichee:
            self.of_selectionne = None
        self.commande_affichee = do_piece
        self.lbl_commande.configure(text=f"Commande {do_piece}")
        self.lbl_client.configure(text=self.sage.client(do_piece, ""))
        self.update_lines_view(do_piece)

    def selectionner_of(self, id_of):
        self.of_selectionne = id_of
        for ident, carte_of in self.cartes.items():
            carte_of.selectionner(ident == id_of)
        self.scan_entry.focus_set()

    # ===================== Scans =====================

    def on_scan(self, event):
        qr_text = self.scan_var.get().strip()
        self.scan_var.set("")
        if qr_text:
            self.process_scan(qr_text)

    def process_scan(self, qr_code):
        if self.est_bureau_etude:
            return  # pas de scan au Bureau d'étude (l'écran Atelier n'y est pas affiché)
        qr_code = qr_code.strip().upper()
        self.recharger_etat()

        # Code commande (CMD-xxxx) : affiche la commande sans enregistrer de scan
        if qr_code.startswith("CMD-"):
            do_piece = qr_code[4:]
            if do_piece not in self.sage.entetes:
                self.load_sage_data()
            if do_piece not in self.sage.entetes:
                self.update_status_bar("error", "Commande introuvable", f"{do_piece} n'est pas dans les exports Sage.")
                return
            if self.tree_cmd.exists(do_piece):
                self.tree_cmd.selection_set(do_piece)
                self.tree_cmd.see(do_piece)
                maj_tags_selection(self.tree_cmd)
            self._afficher_commande(do_piece)
            self.update_status_bar("progress", f"Commande {do_piece}", self.sage.client(do_piece, ""))
            return

        # Code OF : le code-barres est l'identifiant de l'OF (ex. "OF-1001")
        of = self.etat.ofs.get(qr_code)
        if not of:
            self.update_status_bar("error", "Code inconnu", f"« {qr_code} » ne correspond à aucun OF ni aucune commande.")
            return

        ok, motif, scans_actuels = progression.verifier_scan(self.etat, of, self.get_mon_op(), self.get_codpost())
        if not ok:
            self.update_status_bar("error", "Scan refusé", f"{motif}", f"{scans_actuels} / {of.qte}")
            self._montrer_of(of)
            if of.id in self.cartes:
                self.cartes[of.id].surligner(T.ERREUR)
            return

        self.depot.ajouter_scans(of.id, [(self.get_codpost(), 1)])
        journal().info("Scan %s au poste %s", of.id, self.get_codpost())
        self.recharger_etat()
        nouveau_count = scans_actuels + 1

        self._update_single_cmd_in_tree(of.cde)
        self._montrer_of(of)
        if of.id in self.cartes:
            self.cartes[of.id].surligner()

        detail = f"{of.id} · {of.design} · {of.dimensions}"
        if nouveau_count == of.qte:
            self.update_status_bar("success", "OF terminé à ce poste", detail, f"{nouveau_count} / {of.qte}")
        else:
            self.update_status_bar("success", "Pièce enregistrée", detail, f"{nouveau_count} / {of.qte}")

    def _montrer_of(self, of):
        """Affiche la commande de l'OF, sélectionne sa carte et la fait défiler à l'écran."""
        if self.tree_cmd.exists(of.cde):
            self.tree_cmd.selection_set(of.cde)
            self.tree_cmd.see(of.cde)
            maj_tags_selection(self.tree_cmd)
        self._afficher_commande(of.cde)
        if of.id in self.cartes:
            self.selectionner_of(of.id)
            defiler_vers(self.zone_cartes, self.cartes[of.id])

    def _apres_scan_manuel(self, of, message):
        self.recharger_etat()
        self._update_single_cmd_in_tree(of.cde)
        self.update_lines_view(of.cde)
        self.selectionner_of(of.id)
        self.update_status_bar("success", message, f"{of.id} · {of.design}",
                               f"{self.etat.compter(of.id, self.get_mon_op())} / {of.qte}")

    def ajouter_scans_manuels(self, id_of, amount, child_key=None):
        """Ajout manuel (+1, Terminer) : complète aussi les étapes précédentes si besoin."""
        self.recharger_etat()
        of = self.etat.ofs.get(id_of)
        if not of:
            return
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        motif = progression.motif_hors_gamme(of.id, self.etat.gamme(of.id), mon_op, codpost)
        if motif:
            messagebox.showwarning("Scan impossible", motif)
            return

        enfants = []
        if child_key is not None:
            enfants = sage.lignes_enfants(self.sage, of.cde, of.lignes_sage)
            target_qte = next((q for cle, q, _ in enfants if cle == child_key), 1)
            scans_actuels = progression.repartir_scans(self.etat, of.id, mon_op, enfants).get(child_key, 0)
        else:
            target_qte = of.qte
            scans_actuels = self.etat.compter(of.id, mon_op)

        to_add = target_qte - scans_actuels if amount == "all" else min(amount, target_qte - scans_actuels)
        if to_add <= 0:
            self.update_status_bar("warning", "Quantité déjà atteinte", f"{of.id} est complet à ce poste.")
            return

        plan = progression.plan_rattrapage(self.etat, of, mon_op, codpost, to_add, child_key, enfants)
        self.depot.ajouter_scans(of.id, plan, child_key)
        journal().info("Scan manuel %s : %s (ligne %s)", of.id, plan, child_key)
        self._apres_scan_manuel(of, f"{to_add} pièce{'s' if to_add > 1 else ''} ajoutée{'s' if to_add > 1 else ''}")

    def retirer_scans_manuels(self, id_of, amount, child_key=None):
        """Annulation (−1, Tout annuler) des scans de ce poste ; « Tout annuler » demande confirmation."""
        self.recharger_etat()
        of = self.etat.ofs.get(id_of)
        if not of:
            return
        mon_op = self.get_mon_op()

        if child_key is not None:
            # Scans propres à la ligne d'abord, sinon scans généraux de l'OF
            scans = self.depot.ids_scans(of.id, mon_op, child_key) or self.depot.ids_scans(of.id, mon_op, None)
            lignes = dict(self.sage.lignes_commande(of.cde))
            target_qte = sage.lire_qte(lignes.get(child_key, {}).get("DL_Qte", "1"))
        else:
            scans = self.depot.ids_scans(of.id, mon_op)
            target_qte = len(scans)

        if not scans:
            self.update_status_bar("warning", "Rien à annuler", f"Aucun scan de {of.id} à ce poste.")
            return

        to_remove = min(len(scans), target_qte if amount == "all" else amount)
        if amount == "all" and not messagebox.askyesno(
                "Tout annuler", f"Annuler les {to_remove} scans de {of.id} à ce poste ?\n\nCette action est définitive."):
            return
        self.depot.annuler_scans(scans[:to_remove])
        journal().info("Annulation de %d scan(s) %s (ligne %s)", to_remove, of.id, child_key)
        self._apres_scan_manuel(of, f"{to_remove} scan{'s' if to_remove > 1 else ''} annulé{'s' if to_remove > 1 else ''}")

    def ouvrir_historique(self, id_of):
        of = self.etat.ofs.get(id_of)
        if of:
            HistoriqueDialog(self.root, of, self.depot.historique_scans(id_of))

    # ===================== Simulateur =====================

    def open_scan_simulator(self):
        of = self.etat.ofs.get(self.of_selectionne) if self.of_selectionne else None
        if not of:
            messagebox.showinfo("Simuler un scan", "Cliquez d'abord sur une carte d'OF pour choisir la pièce à scanner.")
            return

        fenetre = FenetreDialogue(self.root)
        fenetre.title("Simuler un scan")
        fenetre.geometry("460x300")
        fenetre.configure(fg_color=T.FOND)
        fenetre.transient(self.root)

        cadre = carte(fenetre)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, "Simuler un scan de douchette", taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_XS))
        texte(cadre, "Enregistre une pièce exactement comme la douchette.").pack(fill=tk.X, padx=T.ESPACE_L)

        infos = carte(cadre, couleur=T.SURFACE)
        infos.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_M)
        ctk.CTkLabel(infos, text=of.id, font=T.police_chiffres(T.TAILLE_TITRE), text_color=T.TITRE).pack(pady=(T.ESPACE_M, 0))
        texte(infos, f"{of.design} · {of.dimensions}", couleur=T.TEXTE, anchor="center").pack(fill=tk.X, padx=T.ESPACE_M, pady=(0, T.ESPACE_M))

        def scanner():
            fenetre.destroy()
            self.process_scan(of.id)

        bouton(cadre, f"Scanner {of.id}", scanner, style="succes", atelier=True, icone=get_icon("barcode")).pack(
            fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
