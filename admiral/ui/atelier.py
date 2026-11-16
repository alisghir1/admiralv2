"""Écran Atelier : commandes du poste, cartes d'OF, bandeau de scan."""
import sys
import time
import tkinter as tk
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from .. import theme as T
from ..domain import codes, progression, sage, tri
from ..domain.synthese import format_date
from ..journal import journal
from .carte_of import CarteOF, VueEtape, VueLigne, VueOF
from .composants import BandeauCommande, bouton, carte, champ, defiler_vers, menu_tri, tableau, texte, titre
from .dialogs import HistoriqueDialog
from .impression import ImpressionDialog
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
MESSAGE_ATTENTE = ("Prêt à scanner", "Scannez le code-barres d'un OF, d'un article ou d'une commande")


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

        # Recherche, et à côté l'impression du poste (liste de travail, fiches d'étape de la commande affichée)
        ligne_recherche = ctk.CTkFrame(panneau, fg_color="transparent")
        ligne_recherche.pack(fill=tk.X, padx=T.ESPACE_L)
        bouton(ligne_recherche, "Imprimer", self.imprimer_poste, style="secondaire", width=96).pack(side=tk.RIGHT)
        self.search_entry = champ(ligne_recherche, "Rechercher : commande, client, réf. client…")
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, T.ESPACE_S))
        self.search_entry.bind("<KeyRelease>", self.on_search_change)

        self.filtre_commandes = ctk.CTkSegmentedButton(
            panneau, values=list(FILTRES_COMMANDES), command=lambda _: self._appliquer_recherche(),
            height=36, corner_radius=15, border_width=3, font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE, unselected_color=T.SURFACE,
            unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE, selected_hover_color=T.PRIMAIRE_SURVOL,
            text_color=T.TEXTE)
        self.filtre_commandes.set("Toutes")
        self.filtre_commandes.pack(fill=tk.X, padx=T.ESPACE_L, pady=T.ESPACE_S)
        ligne_tri, self.tri_commandes = menu_tri(panneau, tri.TRIS_COMMANDES, self._appliquer_recherche)
        ligne_tri.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))

        cadre, self.tree_cmd = tableau(panneau, [
            ("commande", "Commande", 120, "w"), ("client", "Client", 160, "w"),
            ("avancement", "Pièces", 80, "center"), ("etat", "État", 100, "center")], style="Atelier.Treeview")
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_cmd.bind("<<TreeviewSelect>>", self.on_order_select)

    def _construire_detail_commande(self, parent):
        panneau = carte(parent)
        panneau.grid(row=0, column=1, sticky="nsew", pady=(0, T.ESPACE_S))

        entete = ctk.CTkFrame(panneau, fg_color="transparent")
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, 0))
        self.lbl_commande = titre(entete, "Aucune commande sélectionnée", taille=T.TAILLE_TITRE)
        self.lbl_commande.pack(side=tk.LEFT)
        self.lbl_client = texte(entete, "", taille=T.TAILLE_SOUS_TITRE, couleur=T.TEXTE)
        self.lbl_client.pack(side=tk.LEFT, padx=(T.ESPACE_M, 0))
        self.lbl_resume = texte(entete, "", taille=T.TAILLE_CORPS)
        self.lbl_resume.pack(side=tk.RIGHT)
        bloc_tri, self.tri_cartes = menu_tri(entete, tri.TRIS_OF[:-1], self._retrier_cartes, largeur=160)
        bloc_tri.pack(side=tk.RIGHT, padx=(0, T.ESPACE_L))
        # Réf. client, délai et observation de Sage (la date de commande ne sert pas à l'atelier)
        # Sous le titre : infos Sage, et « Terminer la commande » (tous ses OF à ce poste, après confirmation)
        ligne_bandeau = ctk.CTkFrame(panneau, fg_color="transparent")
        ligne_bandeau.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_XS, T.ESPACE_S))
        self.btn_terminer_commande = bouton(ligne_bandeau, "Terminer la commande", self.terminer_commande_poste,
                                            style="secondaire", width=180, height=32, state="disabled")
        self.btn_terminer_commande.pack(side=tk.RIGHT)
        self.bandeau_commande = BandeauCommande(ligne_bandeau, avec_date=False)
        self.bandeau_commande.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.zone_cartes = ctk.CTkScrollableFrame(panneau, fg_color="transparent", scrollbar_button_color=T.BORDURE,
                                                  scrollbar_button_hover_color=T.BORDURE_SURVOL)
        self.zone_cartes.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_S, pady=(0, T.ESPACE_S))
        self.lbl_vide = ctk.CTkLabel(self.zone_cartes, text="", font=T.police(T.TAILLE_SOUS_TITRE),
                                     text_color=T.TEXTE_ATTENUE, wraplength=520, justify="center")
        self._afficher_vide("Sélectionnez une commande à gauche, ou scannez le code-barres d'une commande")

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

    def _maj_etat_douchette(self):
        """Douchette en port COM : son état remplace l'indicateur de focus (le focus ne compte plus)."""
        com = self.douchette_com
        texte_etat = "Douchette COM connectée" if com.connectee else "Douchette COM absente"
        if self.lbl_focus_scan.cget("text") != texte_etat:
            self.lbl_focus_scan.configure(text=texte_etat, text_color=T.SUCCES_VIF if com.connectee else T.ALERTE_TEXTE)
            self.scan_entry.configure(border_color=T.PRIMAIRE if com.connectee else T.ALERTE)

    def _maj_indicateur_focus(self, actif):
        # Sans focus, la douchette tape dans le vide : on le signale clairement.
        if getattr(self, "douchette_com", None) is not None:
            self._maj_etat_douchette()
            return
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
            self._son_erreur()
        # Un message de résultat s'efface seul ; l'erreur reste un peu plus longtemps
        if self._timer_bandeau is not None:
            self.root.after_cancel(self._timer_bandeau)
            self._timer_bandeau = None
        if status_type != "default":
            duree = T.DUREE_MESSAGE_ERREUR if status_type == "error" else T.DUREE_MESSAGE_SUCCES
            self._timer_bandeau = self.root.after(duree, self._bandeau_au_repos)

    def _son_erreur(self):
        """Son d'erreur : l'opérateur ne regarde pas toujours l'écran quand il scanne (rien sur une fenêtre masquée)."""
        try:
            if not self.root.winfo_viewable():
                return
            if sys.platform == "win32":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND)
            else:
                self.root.bell()
        except Exception:   # pas de carte son, fenêtre en fermeture : le bandeau rouge suffit
            pass

    def _bandeau_au_repos(self):
        self._timer_bandeau = None
        self.update_status_bar("default", *MESSAGE_ATTENTE)

    # ===================== Liste des commandes =====================

    def _remplir_commandes_atelier(self, commandes):
        """Commandes dont au moins un OF passe par ce poste, dans l'ordre choisi (par numéro au départ)."""
        selection = self.tree_cmd.selection()
        for item in self.tree_cmd.get_children():
            self.tree_cmd.delete(item)
        filtre_etat = FILTRES_COMMANDES.get(self.filtre_commandes.get())
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        lignes = []
        for do_piece, _ in commandes:
            if do_piece in self.etat.cloturees:
                continue  # commande livrée : plus rien à faire en atelier
            scanned, total, pct_str = progression.avancement_commande(self.etat, do_piece, mon_op, codpost)
            if total == 0:
                continue  # aucun OF de cette commande ne passe par ce poste
            tag = progression.tag_avancement(scanned, total)
            if filtre_etat and tag != filtre_etat:
                continue
            valeurs = (do_piece, self.sage.client(do_piece, ""), f"{scanned} / {total}", LIBELLES_AVANCEMENT[tag])
            lignes.append((progression.ORDRE_ETATS.get(tag, 1), valeurs, tag))
        lignes = tri.trier(lignes, self.tri_commandes.get(), numero=lambda l: l[1][0],
                           client=lambda l: self.sage.client_pour_tri(l[1][0]),
                           etat=lambda l: l[0])
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
        validation = self.etat.validation(of.id, mon_op)
        if validation and self.etat.scans_reels(of.id, mon_op) < of.qte:
            # Terminé ici par le chef d'atelier, sans scan complet : dit clairement, et plus de +/− possible
            etat_poste = "valide"
            situation = f"Validé par {validation.chef} (chef d'atelier) · {validation.motif}"

        enfants = sage.lignes_enfants(self.sage, of.cde, of.lignes_sage)
        repartis = progression.repartir_scans(self.etat, of.id, mon_op, enfants)
        lignes = []
        for cle, l_qte, ligne in enfants:
            # Chants à poser (« Chants 1H+2L ») et quantité seulement si elle n'est pas en pièces (« 7,6 ML »)
            chants = sage.chants(ligne)
            qte_unite = sage.quantite(ligne) if (ligne.get("EU_Enumere") or "U").upper() != "U" else ""
            details = " · ".join(filter(None, [ligne.get("DL_Design", ""), sage.dimensions(ligne),
                                               f"Chants {chants}" if chants else "", qte_unite]))
            lignes.append(VueLigne(cle, f"Ligne {ligne.get('DL_Ligne', '')} · {ligne.get('AR_Ref', '')}", details,
                                   l_qte, repartis[cle], progression.statut_ligne(repartis[cle], l_qte)[1]))

        retard = self.etat.en_retard(of, date.today())
        besoin = ""
        if of.date_besoin:
            besoin = f"En retard · besoin le {format_date(of.date_besoin)}" if retard else f"Besoin le {format_date(of.date_besoin)}"
        return VueOF(of.id, of.prod, of.design, of.dimensions, of.observations, of.qte, mes_scans,
                     etat_poste, situation, etapes, lignes, of.urgent, besoin, retard, self.etat.consigne(of.id, mon_op))

    def update_lines_view(self, do_piece):
        """Affiche (ou met à jour sur place) les cartes des OF de la commande qui passent par ce poste."""
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        self.btn_terminer_commande.configure(state="disabled")
        if do_piece in self.etat.cloturees:
            self._afficher_vide(f"La commande {do_piece} est clôturée : plus rien à produire.")
            self.lbl_resume.configure(text="")
            return
        libelles = self.depot.libelles_operations()
        vues = [v for v in (self._vue_of(of, mon_op, codpost, libelles) for of in self.etat.ofs_par_cde.get(do_piece, [])) if v]
        besoins = {of.id: of.date_besoin for of in self.etat.ofs_par_cde.get(do_piece, [])}
        vues = tri.trier(vues, self.tri_cartes.get(), numero=lambda v: v.id, besoin=lambda v: besoins[v.id],
                         urgent=lambda v: v.urgent)

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
        if any(v.etat not in ("terminee", "valide") for v in vues):
            self.btn_terminer_commande.configure(state="normal")
        self.lbl_resume.configure(text=f"{len(vues)} OF · {faites} / {prevues} pièces")
        if self.of_selectionne not in self.cartes:
            self.of_selectionne = None
        for id_of, carte_of in self.cartes.items():
            carte_of.selectionner(id_of == self.of_selectionne)

    def _retrier_cartes(self):
        if self.commande_affichee:
            self.update_lines_view(self.commande_affichee)

    def _afficher_commande(self, do_piece):
        if do_piece != self.commande_affichee:
            self.of_selectionne = None
        self.commande_affichee = do_piece
        self.lbl_commande.configure(text=f"Commande {do_piece}")
        self.lbl_client.configure(text=self.sage.client(do_piece, ""))
        self.bandeau_commande.maj(self.sage.infos_commande(do_piece))
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
        self._detecteur_scan.oublier()   # déjà traité ici : la détection globale ne le refait pas
        if qr_text:
            self.scan_douchette(qr_text)

    def scan_douchette(self, code):
        """Scan venant de la douchette (champ de scan, frappe reconnue ailleurs, port COM) : le même code relu
        dans la seconde est une double lecture de la douchette, ignorée."""
        if self._anti_doublon.doublon(codes.lire_scan(code)[0], time.monotonic()):
            journal().info("Double lecture de la douchette ignorée : %s", code)
            return
        self.process_scan(code)

    def process_scan(self, qr_code):
        """Code lu par la douchette (ou le simulateur) : commande, OF, article (ligne de commande) ou page d'essai."""
        if self.est_pilotage:
            return  # pas de scan au Bureau d'étude ni au Chef d'atelier (l'écran Atelier n'y est pas affiché)
        code, clavier_corrige = codes.lire_scan(qr_code)
        if clavier_corrige:
            journal().warning("Douchette en clavier américain : « %s » relu « %s »", qr_code, code)
        self.recharger_etat()

        if code == codes.CODE_ESSAI:
            if clavier_corrige:
                self.update_status_bar("warning", "Douchette en clavier anglais",
                                       "Admiral corrige la lecture, mais réglez la douchette en clavier français (AZERTY) : "
                                       "code de configuration dans sa notice.")
            else:
                self.update_status_bar("success", "Douchette bien réglée", "Le code d'essai est lu sans erreur.")
            return

        # Code OF : le numéro de l'OF (« OF261234-01 », ou « OF-1001 » avant la numérotation par commande)
        of = self.etat.ofs.get(code)
        if of:
            self._scanner_of(of)
            return

        # Code commande : son numéro (« CC261234 ») ou l'ancien « CMD-CC261234 » : affiche la commande, sans scan
        cde = codes.commande_du_code(code)
        if cde in self.sage.entetes or code.startswith(codes.PREFIXE_ANCIEN_COMMANDE):
            self._scanner_commande(cde)
            return

        # Code article : « CC261234-1000 », une ligne de commande, comptée dans l'OF qui la contient
        cde_article = codes.commande_de_l_article(code)
        if cde_article and code in self.sage.lignes and cde_article not in self.sage.anterieures:
            self._scanner_article(cde_article, code)
            return

        # Commande (ou article) d'avant la remise à zéro : elle existe dans Sage, mais n'est plus suivie
        anterieure = next((c for c in (cde, cde_article) if c and c in self.sage.anterieures), None)
        if anterieure:
            self.update_status_bar("error", "Commande d'avant la remise à zéro",
                                   f"La commande {anterieure} date d'avant la remise à zéro de l'atelier : "
                                   "elle n'est pas suivie dans Admiral.")
            return

        self.update_status_bar("error", "Code inconnu",
                               f"« {code} » ne correspond à aucun OF, article ou commande."
                               + (" La douchette tape en clavier anglais : réglez-la en français." if clavier_corrige else ""))

    def _scanner_commande(self, do_piece):
        """Commande scannée : affichée avec ses OF de ce poste (« Terminer la commande » les termine tous),
        ou erreur si aucun de ses OF ne passe par ce poste."""
        if do_piece not in self.sage.entetes:
            self.load_sage_data()
        if do_piece not in self.sage.entetes:
            self.update_status_bar("error", "Commande introuvable", f"{do_piece} n'est pas dans les commandes Sage en cours.")
            return
        ofs = self.etat.ofs_par_cde.get(do_piece, [])
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        ici = [of for of in ofs if progression.index_etape(self.etat.gamme(of.id), mon_op, codpost) != -1]
        if do_piece in self.etat.cloturees:
            self.update_status_bar("error", "Commande clôturée", f"La commande {do_piece} est clôturée : plus rien à produire.")
            return
        if not ofs:
            self.update_status_bar("error", "Commande sans OF",
                                   f"La commande {do_piece} n'a pas encore d'OF : le bureau d'étude doit les créer.")
            return
        if not ici:
            libelles = self.depot.libelles_operations()
            parcours = sorted({progression.texte_parcours(self.etat.gamme(of.id), libelles) for of in ofs})
            self.update_status_bar("error", "Pas pour ce poste",
                                   f"Aucun OF de la commande {do_piece} ne passe par ce poste ({codpost}). "
                                   f"Parcours prévu par le bureau d'étude : {' / '.join(parcours)}")
            return
        if self.tree_cmd.exists(do_piece):
            self.tree_cmd.selection_set(do_piece)
            self.tree_cmd.see(do_piece)
            maj_tags_selection(self.tree_cmd)
        self._afficher_commande(do_piece)
        restes = sum(max(of.qte - self.etat.compter(of.id, mon_op), 0) for of in ici)
        self.update_status_bar("progress", f"Commande {do_piece}",
                               f"{self.sage.client(do_piece, '')} · {len(ici)} OF à ce poste · {restes} pièce"
                               f"{'s' if restes > 1 else ''} à faire · « Terminer la commande » pour tout terminer ici")

    def terminer_commande_poste(self):
        """Termine à ce poste tous les OF de la commande affichée (comme « Terminer » sur chaque carte : les étapes
        précédentes non finies sont complétées), après confirmation."""
        cde = self.commande_affichee
        if not cde:
            return
        self.recharger_etat()
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        a_finir = [of for of in self.etat.ofs_par_cde.get(cde, [])
                   if self.etat.en_service(of) and progression.index_etape(self.etat.gamme(of.id), mon_op, codpost) != -1
                   and not self.etat.validation(of.id, mon_op) and self.etat.compter(of.id, mon_op) < of.qte]
        if not a_finir:
            self.update_status_bar("warning", "Rien à terminer", f"Les OF de la commande {cde} sont déjà terminés à ce poste.")
            return
        pieces = sum(of.qte - self.etat.compter(of.id, mon_op) for of in a_finir)
        if not messagebox.askyesno(
                "Terminer la commande", f"Terminer à ce poste {len(a_finir)} OF de la commande {cde} ({pieces} pièce"
                f"{'s' if pieces > 1 else ''}) ?\n\n" + ", ".join(of.id for of in a_finir[:6])
                + (" …" if len(a_finir) > 6 else "")
                + "\n\nLes étapes précédentes non finies sont complétées, comme avec « Terminer » sur une carte."):
            return
        for of in a_finir:
            reste = of.qte - self.etat.compter(of.id, mon_op)
            plan = progression.plan_rattrapage(self.etat, of, mon_op, codpost, reste)
            self.depot.ajouter_scans(of.id, plan)
            journal().info("Commande %s terminée au poste %s : %s %s", cde, codpost, of.id, plan)
            self.recharger_etat()
        self._update_single_cmd_in_tree(cde)
        self.update_lines_view(cde)
        self.update_status_bar("success", "Commande terminée à ce poste", f"{cde} · {len(a_finir)} OF · {pieces} pièces")

    def _scanner_article(self, cde, code):
        """Une pièce de la ligne de commande scannée, comptée sur cette ligne dans son OF."""
        id_of = self.depot.lignes_affectees(cde).get(code)
        of = self.etat.ofs.get(id_of) if id_of else None
        numero = code.rsplit("-", 1)[-1]
        if of is None:
            self.update_status_bar("error", "Article sans OF", f"La ligne {numero} de la commande {cde} n'est dans aucun OF "
                                                               "en cours : le Bureau d'étude doit d'abord créer l'OF.")
            return
        enfants = sage.lignes_enfants(self.sage, of.cde, of.lignes_sage)
        ligne = next(((cle, qte, l) for cle, qte, l in enfants if codes.code_article(of.cde, cle) == code), None)
        if ligne is None:
            self._scanner_of(of)
            return
        self._scanner_of(of, ligne, enfants)

    def _scanner_of(self, of, ligne=None, enfants=()):
        """Enregistre une pièce de l'OF à ce poste ; ligne : (clé stockée, quantité, ligne Sage) pour un article."""
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        ok, motif, scans_actuels = progression.verifier_scan(self.etat, of, mon_op, codpost, self.depot.libelles_operations())
        child_key, compte = None, f"{scans_actuels + 1} / {of.qte}"
        if ok and ligne is not None:
            child_key, qte_ligne, _ = ligne
            faites_ligne = progression.repartir_scans(self.etat, of.id, mon_op, list(enfants)).get(child_key, 0)
            if faites_ligne >= qte_ligne:
                ok, motif = False, f"Ligne {child_key.rsplit('-', 1)[-1]} déjà complète à ce poste ({faites_ligne}/{qte_ligne})"
            compte = f"{faites_ligne + 1} / {qte_ligne}"
        if not ok:
            if ligne is not None:   # article : on cite la ligne scannée
                motif = f"Article {codes.code_article(of.cde, ligne[0])} · {motif}"
            hors_parcours = progression.index_etape(self.etat.gamme(of.id), mon_op, codpost) == -1
            self.update_status_bar("error", "Pas pour ce poste" if hors_parcours else "Scan refusé", f"{motif}",
                                   f"{scans_actuels} / {of.qte}")
            self._montrer_of(of)
            if of.id in self.cartes:
                self.cartes[of.id].surligner(T.ERREUR)
            return

        self.depot.ajouter_scans(of.id, [(codpost, 1)], child_key)
        journal().info("Scan %s%s au poste %s", of.id, f" (ligne {child_key})" if child_key else "", codpost)
        self.recharger_etat()
        nouveau_count = scans_actuels + 1

        self._update_single_cmd_in_tree(of.cde)
        self._montrer_of(of)
        if of.id in self.cartes:
            self.cartes[of.id].surligner()

        detail = f"{of.id} · {of.design} · {of.dimensions}"
        if child_key is not None:
            detail = f"{of.id} · ligne {child_key.rsplit('-', 1)[-1]} · {ligne[2].get('DL_Design', '')}"
        if nouveau_count == of.qte:
            self.update_status_bar("success", "OF terminé à ce poste", detail, f"{nouveau_count} / {of.qte}")
        else:
            self.update_status_bar("success", "Pièce enregistrée", detail, compte)

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

    def _of_modifiable(self, of):
        """Un OF annulé ou d'une commande clôturée ne se travaille plus (même si sa carte est encore affichée :
        le Bureau d'étude a pu l'annuler depuis un autre PC)."""
        if of.annule:
            motif = f"{of.id} a été annulé par le Bureau d'étude."
        elif of.cde in self.etat.cloturees:
            motif = f"La commande {of.cde} est clôturée."
        elif self.etat.validation(of.id, self.get_mon_op()):
            motif = f"{of.id} a été validé par {self.etat.validation(of.id, self.get_mon_op()).chef} (chef d'atelier) à ce poste."
        else:
            return True
        self.update_status_bar("error", "Action refusée", motif)
        self.update_lines_view(of.cde)
        return False

    def ajouter_scans_manuels(self, id_of, amount, child_key=None):
        """Ajout manuel (+1, Terminer) : complète aussi les étapes précédentes si besoin."""
        self.recharger_etat()
        of = self.etat.ofs.get(id_of)
        if not of or not self._of_modifiable(of):
            return
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        motif = progression.motif_hors_gamme(of.id, self.etat.gamme(of.id), mon_op, codpost, self.depot.libelles_operations())
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
        to_add = min(to_add, of.qte - self.etat.compter(of.id, mon_op))   # jamais plus que la quantité de l'OF
        if to_add <= 0:
            self.update_status_bar("warning", "Quantité déjà atteinte", f"{of.id} est complet à ce poste.")
            return

        plan = progression.plan_rattrapage(self.etat, of, mon_op, codpost, to_add, child_key, enfants)
        self.depot.ajouter_scans(of.id, plan, child_key)
        journal().info("Scan manuel %s : %s (ligne %s)", of.id, plan, child_key)
        self._apres_scan_manuel(of, f"{to_add} pièce{'s' if to_add > 1 else ''} ajoutée{'s' if to_add > 1 else ''}")

    def retirer_scans_manuels(self, id_of, amount, child_key=None):
        """Annulation (−1, Tout annuler) des scans de ce poste ; « Tout annuler » demande confirmation.
        Une pièce déjà passée à l'étape suivante ne peut pas être défaite, ni une pièce faite à un autre poste."""
        self.recharger_etat()
        of = self.etat.ofs.get(id_of)
        if not of or not self._of_modifiable(of):
            return
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        enfants = sage.lignes_enfants(self.sage, of.cde, of.lignes_sage) if child_key is not None else []

        if child_key is not None:
            # Les scans généraux (douchette, +1 de l'OF) sont affichés répartis sur les lignes, de haut en bas.
            # On les rattache d'abord à la ligne où ils sont affichés : le −1 retire alors bien une pièce de
            # la ligne cliquée, et les autres lignes ne bougent pas.
            repartition = progression.scans_generaux_par_ligne(self.etat, of.id, mon_op, enfants)
            if repartition:
                self.depot.rattacher_scans_generaux(of.id, mon_op, repartition)
                self.recharger_etat()
            scans = self.depot.ids_scans(of.id, mon_op, child_key, poste=codpost)
            quoi = f"la ligne {child_key.rsplit('-', 1)[-1]} de {of.id}"
        else:
            scans = self.depot.ids_scans(of.id, mon_op, poste=codpost)
            quoi = of.id

        if not scans:
            self.update_status_bar("warning", "Rien à annuler", f"Aucune pièce de {quoi} à ce poste.")
            return
        possible = progression.retrait_max(self.etat, of, mon_op, codpost, child_key, enfants)
        if possible <= 0:
            self.update_status_bar("warning", "Annulation impossible",
                                   f"Les pièces de {quoi} sont déjà passées à l'étape suivante : annulez d'abord là-bas.")
            return

        to_remove = min(len(scans), possible, len(scans) if amount == "all" else amount)
        if amount == "all" and not messagebox.askyesno(
                "Tout annuler", f"Annuler {to_remove} pièce{'s' if to_remove > 1 else ''} de {quoi} à ce poste ?"
                + ("" if to_remove == len(scans) else f"\n\nLes {len(scans) - to_remove} autres sont déjà passées à l'étape suivante.")
                + "\n\nCette action est définitive."):
            return
        self.depot.annuler_scans(scans[:to_remove])
        journal().info("Annulation de %d scan(s) %s (ligne %s)", to_remove, of.id, child_key)
        self._apres_scan_manuel(of, f"{to_remove} scan{'s' if to_remove > 1 else ''} annulé{'s' if to_remove > 1 else ''}")

    # ===================== Impression =====================

    def imprimer_poste(self):
        """Liste de travail du poste, et les fiches d'étape de la commande affichée pour ce poste."""
        self.recharger_etat()
        mon_op, codpost = self.get_mon_op(), self.get_codpost()
        ids = []
        if self.commande_affichee:
            ids = [of.id for of in self.etat.ofs_par_cde.get(self.commande_affichee, [])
                   if progression.index_etape(self.etat.gamme(of.id), mon_op, codpost) != -1]
        dialogue = ImpressionDialog(self.root, self, f"Impression · poste {codpost}", ids_of=ids, postes=[codpost],
                                    etape=mon_op, coches=("liste",))
        self.root.wait_window(dialogue)
        self.scan_entry.focus_set()

    def imprimer_of(self, id_of):
        """Fiche d'étape de cet OF pour ce poste (ou sa fiche suiveuse, ses étiquettes)."""
        if id_of not in self.etat.ofs:
            return
        dialogue = ImpressionDialog(self.root, self, f"Impression · {id_of}", ids_of=[id_of], etape=self.get_mon_op(),
                                    coches=("etape",))
        self.root.wait_window(dialogue)
        self.scan_entry.focus_set()

    def ouvrir_historique(self, id_of):
        of = self.etat.ofs.get(id_of)
        if of:
            HistoriqueDialog(self.root, of, self.depot.historique_scans(id_of), self.depot.historique_validations(id_of),
                             self.depot.libelles_operations())

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
