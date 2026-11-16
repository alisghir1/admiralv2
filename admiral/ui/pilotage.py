"""Chef d'atelier : onglet Pilotage (valider des OF, une étape ou une commande entière sans scan)
et onglet Validations (historique, annulation).

Une validation n'écrit aucun scan : elle est enregistrée à part (qui, quand, motif) et EtatAtelier.compter
la compte comme des pièces faites. Tous les écrans (Atelier, Synthèse, Charge, Bureau d'étude) la voient
donc sans traitement particulier, y compris sur les autres PC (surveillance de la base).
"""
import tkinter as tk
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from .. import theme as T
from ..domain import pilotage, tri
from ..domain.synthese import format_date
from ..journal import journal
from .composants import BandeauCommande, bouton, carte, champ, lier_clic, menu_tri, tableau, texte, titre
from .impression import ImpressionDialog
from .widgets import FenetreDialogue, capturer_focus, centrer_fenetre, maj_tags_selection

# Filtre des commandes : libellé -> test sur ResumeCommande (et part moyenne faite)
FILTRES_PILOTAGE = {
    "À traiter": lambda r, part: r.tag != "terminee" and (part > 0 or r.tag == "retard"),
    "En retard": lambda r, part: r.tag == "retard",
    "Presque finies": lambda r, part: r.tag != "terminee" and part >= pilotage.SEUIL_PRESQUE_FINI,
    "Terminées": lambda r, part: r.tag == "terminee",
    "Toutes": lambda r, part: True,
}
LIBELLES_ETAT_COMMANDE = {"retard": "En retard", "encours": "En cours", "pas_demarre": "À faire", "terminee": "Terminée"}
RANG_ETAT = {"retard": 0, "encours": 1, "pas_demarre": 2, "terminee": 3}
TUILES = [("en_cours", "OF en cours", "À traiter"), ("retard", "OF en retard", "En retard"),
          ("presque_finis", "OF presque finis", "Presque finies"), ("valides_jour", "Validés aujourd'hui", None)]


def _date_heure(valeur):
    """ "2026-11-09 14:32:05" -> "09/11/2026 14:32" """
    if not valeur:
        return ""
    jour, _, heure = valeur.partition(" ")
    return f"{format_date(jour)} {heure[:5]}".strip()


class PilotageMixin:

    # ===================== Onglet Pilotage =====================

    def build_pilotage_ui(self):
        parent = self.tab_pilotage
        self._timer_message_pilotage = None

        entete = ctk.CTkFrame(parent, fg_color="transparent")
        entete.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        titre(entete, "Pilotage de l'atelier", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        texte(entete, "Validez des OF, une étape ou une commande entière, même sans scan.").pack(side=tk.LEFT, padx=T.ESPACE_L)
        self.lbl_pilotage_message = ctk.CTkLabel(entete, text="", font=T.police(T.TAILLE_CORPS, gras=True),
                                                 text_color=T.SUCCES_VIF)
        self.lbl_pilotage_message.pack(side=tk.RIGHT)

        # Indicateurs : un clic filtre la liste des commandes
        bandeau = ctk.CTkFrame(parent, fg_color="transparent")
        bandeau.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        self.tuiles_pilotage = {}
        for i, (cle, libelle, filtre) in enumerate(TUILES):
            bandeau.columnconfigure(i, weight=1, uniform="tuiles_pilotage")
            tuile = carte(bandeau)
            tuile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else T.ESPACE_S // 2, 0 if i == len(TUILES) - 1 else T.ESPACE_S // 2))
            valeur = ctk.CTkLabel(tuile, text="—", font=T.police_chiffres(T.TAILLE_CHIFFRE), text_color=T.TEXTE, anchor="w")
            valeur.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_M, 0))
            texte(tuile, libelle).pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_M))
            self.tuiles_pilotage[cle] = valeur
            action = (lambda e, f=filtre: self._filtrer_pilotage(f)) if filtre else \
                (lambda e: self.notebook.set(self.NOM_ONGLET_VALIDATIONS) or self.refresh_validations())
            lier_clic(tuile, action)

        corps = ctk.CTkFrame(parent, fg_color="transparent")
        corps.pack(expand=True, fill=tk.BOTH)
        corps.columnconfigure(0, weight=34, uniform="pilotage")
        corps.columnconfigure(1, weight=66, uniform="pilotage")
        corps.rowconfigure(0, weight=1)

        # --- Gauche : commandes ---
        gauche = carte(corps)
        gauche.grid(row=0, column=0, sticky="nsew", padx=(0, T.ESPACE_S))
        ligne_titre = ctk.CTkFrame(gauche, fg_color="transparent")
        ligne_titre.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        titre(ligne_titre, "Commandes", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        self.lbl_nb_commandes_pilotage = texte(ligne_titre, "")
        self.lbl_nb_commandes_pilotage.pack(side=tk.RIGHT)
        self.search_pilotage = champ(gauche, "Rechercher : commande, client, réf. client…")
        self.search_pilotage.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        self.search_pilotage.bind("<KeyRelease>", lambda e: self._remplir_commandes_pilotage())
        self.filtre_pilotage = ctk.CTkOptionMenu(
            gauche, values=list(FILTRES_PILOTAGE), command=lambda _: self._remplir_commandes_pilotage(), height=36,
            corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS, gras=True), dropdown_font=T.police(T.TAILLE_CORPS),
            fg_color=T.SURFACE, button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL, text_color=T.TEXTE)
        self.filtre_pilotage.set("À traiter")
        self.filtre_pilotage.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        ligne_tri, self.tri_pilotage = menu_tri(gauche, tri.TRIS_COMMANDES, self._remplir_commandes_pilotage)
        ligne_tri.pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        cadre, self.tree_pil_cmd = tableau(gauche, [("cmd", "Commande", 100, "w"), ("client", "Client", 130, "w"),
                                                    ("avance", "Pièces", 90, "center"), ("etat", "État", 90, "center")])
        self.tree_pil_cmd.column("cmd", minwidth=100)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_pil_cmd.bind("<<TreeviewSelect>>", lambda e: self._afficher_commande_pilotage())

        # --- Droite : OF de la commande ---
        droite = carte(corps)
        droite.grid(row=0, column=1, sticky="nsew")
        entete_cmd = ctk.CTkFrame(droite, fg_color="transparent")
        entete_cmd.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, 0))
        bloc_titre = ctk.CTkFrame(entete_cmd, fg_color="transparent")
        bloc_titre.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_pil_commande = titre(bloc_titre, "Choisissez une commande à gauche", taille=T.TAILLE_TITRE)
        self.lbl_pil_commande.pack(fill=tk.X)
        # Observation, réf. client et délai de Sage (vue de production : sans la date de commande)
        self.bandeau_pilotage = BandeauCommande(bloc_titre, avec_date=False)
        self.bandeau_pilotage.pack(fill=tk.X)
        self.lbl_pil_resume = texte(bloc_titre, "")
        self.lbl_pil_resume.pack(fill=tk.X)
        self.btn_valider_commande = bouton(entete_cmd, "Valider la commande", self.valider_commande_pilotage,
                                           style="secondaire", state="disabled", width=180)
        self.btn_valider_commande.pack(side=tk.RIGHT)
        self.btn_imprimer_pilotage = bouton(entete_cmd, "Imprimer", self.imprimer_pilotage, style="secondaire",
                                            state="disabled", width=100)
        self.btn_imprimer_pilotage.pack(side=tk.RIGHT, padx=T.ESPACE_S)
        bloc_titre.pack_forget()   # replacé après les boutons : un nom de client long ne les écrase plus
        bloc_titre.pack(side=tk.LEFT, fill=tk.X, expand=True)
        texte(droite, "Sélectionnez un ou plusieurs OF (Ctrl ou Maj + clic), puis validez-les en entier ou une seule étape.",
              taille=T.TAILLE_LEGENDE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_XS, T.ESPACE_S))

        # Barre d'actions et détail des validations en bas (posés avant le tableau pour rester visibles)
        actions = ctk.CTkFrame(droite, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE)
        actions.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.lbl_pil_selection = texte(actions, "Aucun OF sélectionné", couleur=T.TEXTE)
        self.lbl_pil_selection.pack(side=tk.LEFT, padx=T.ESPACE_M, pady=T.ESPACE_S)
        self.btn_valider_ofs = bouton(actions, "Valider les OF", self.valider_ofs_pilotage, style="primaire",
                                      state="disabled", width=150)
        self.btn_valider_ofs.pack(side=tk.RIGHT, padx=(0, T.ESPACE_S), pady=T.ESPACE_S)
        self.btn_valider_etape = bouton(actions, "Valider une étape…", self.valider_etape_pilotage, style="secondaire",
                                        state="disabled", width=160)
        self.btn_valider_etape.pack(side=tk.RIGHT, padx=T.ESPACE_S, pady=T.ESPACE_S)
        self.btn_annuler_validation = bouton(actions, "Annuler la validation", self.annuler_validation_pilotage,
                                             style="fantome", state="disabled", width=170)
        self.btn_annuler_validation.pack(side=tk.RIGHT, pady=T.ESPACE_S)
        self.lbl_pil_detail = ctk.CTkLabel(droite, text="", font=T.police(T.TAILLE_CORPS), text_color=T.INFO_TEXTE,
                                           anchor="w", justify="left", wraplength=760)
        self.lbl_pil_detail.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_XS))

        cadre, self.tree_pil_of = tableau(droite, [
            ("of", "OF", 140, "w"), ("design", "Désignation", 170, "w"), ("qte", "Qté", 50, "center"),
            ("etapes", "Étapes (pièces faites)", 360, "w"), ("etat", "État", 120, "center")], selection="extended")
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))
        self.tree_pil_of.bind("<<TreeviewSelect>>", lambda e: self._maj_selection_pilotage())

    def _message_pilotage(self, message, erreur=False):
        """Confirmation discrète en haut à droite, effacée au bout de quelques secondes."""
        if self._timer_message_pilotage is not None:
            self.root.after_cancel(self._timer_message_pilotage)
        self.lbl_pilotage_message.configure(text=message, text_color=T.ERREUR_TEXTE if erreur else T.SUCCES_VIF)
        self._timer_message_pilotage = self.root.after(
            T.DUREE_MESSAGE_ERREUR if erreur else T.DUREE_MESSAGE_SUCCES,
            lambda: self.lbl_pilotage_message.configure(text=""))

    def _filtrer_pilotage(self, filtre):
        self.filtre_pilotage.set(filtre)
        self._remplir_commandes_pilotage()

    def refresh_pilotage(self):
        self.recharger_etat()
        for cle, valeur in pilotage.indicateurs(self.etat).items():
            self.tuiles_pilotage[cle].configure(text=str(valeur))
        self.tuiles_pilotage["retard"].configure(text_color=T.ERREUR_TEXTE if self.tuiles_pilotage["retard"].cget("text") != "0" else T.TEXTE)
        self._remplir_commandes_pilotage()

    def _remplir_commandes_pilotage(self):
        selection = self.tree_pil_cmd.selection()
        for item in self.tree_pil_cmd.get_children():
            self.tree_pil_cmd.delete(item)
        recherche = self.search_pilotage.get().strip().lower()
        filtre = FILTRES_PILOTAGE.get(self.filtre_pilotage.get(), FILTRES_PILOTAGE["Toutes"])
        lignes = []
        for cde in self.etat.commandes():
            client = self.sage.client(cde, "")
            if recherche and recherche not in self.sage.texte_recherche(cde):
                continue
            resume = pilotage.resume_commande(self.etat, cde)
            ofs = self.etat.ofs_par_cde.get(cde, [])
            part = sum(pilotage.part_faite(self.etat, of) for of in ofs) / len(ofs) if ofs else 0
            if not filtre(resume, part):
                continue
            lignes.append((resume, client))
        lignes = tri.trier(lignes, self.tri_pilotage.get(), numero=lambda l: l[0].cde,
                           client=lambda l: self.sage.client_pour_tri(l[0].cde),
                           etat=lambda l: RANG_ETAT.get(l[0].tag, 2))
        for resume, client in lignes:
            avance = f"{resume.faites}/{resume.prevues} · {resume.pourcentage} %" if resume.prevues else "—"
            self.tree_pil_cmd.insert("", "end", iid=resume.cde, tags=(resume.tag,),
                                     values=(resume.cde, client, avance, LIBELLES_ETAT_COMMANDE.get(resume.tag, "")))
        self.lbl_nb_commandes_pilotage.configure(text=f"{len(lignes)} commande{'s' if len(lignes) > 1 else ''}")
        if selection and self.tree_pil_cmd.exists(selection[0]):
            self.tree_pil_cmd.selection_set(selection[0])
        maj_tags_selection(self.tree_pil_cmd)
        self._afficher_commande_pilotage()

    def _commande_pilotage(self):
        selection = self.tree_pil_cmd.selection()
        return selection[0] if selection else None

    def _afficher_commande_pilotage(self):
        """OF de la commande choisie ; la sélection d'OF est gardée d'une actualisation à l'autre."""
        maj_tags_selection(self.tree_pil_cmd)
        cde = self._commande_pilotage()
        ofs_selectionnes = self.tree_pil_of.selection()
        for item in self.tree_pil_of.get_children():
            self.tree_pil_of.delete(item)
        if cde is None:
            self.lbl_pil_commande.configure(text="Choisissez une commande à gauche")
            self.bandeau_pilotage.maj(None)
            self.lbl_pil_resume.configure(text="")
            self.btn_valider_commande.configure(state="disabled")
            self.btn_imprimer_pilotage.configure(state="disabled")
            self._maj_selection_pilotage()
            return
        client = self.sage.client(cde, "")
        resume = pilotage.resume_commande(self.etat, cde)
        self.lbl_pil_commande.configure(text=f"Commande {cde}" + (f" · {client}" if client else ""))
        self.bandeau_pilotage.maj(self.sage.infos_commande(cde))
        details = [f"{resume.nb_of} OF", f"{resume.faites} / {resume.prevues} pièces terminées"]
        if resume.besoin:
            details.append(f"besoin le {format_date(resume.besoin)}")
        self.lbl_pil_resume.configure(text=" · ".join(details))
        libelles = self.depot.libelles_operations()
        ofs = tri.trier(self.etat.ofs_par_cde.get(cde, []), tri.DEFAUT, numero=lambda of: of.id)
        for of in ofs:
            libelle, tag = pilotage.etat_of(self.etat, of)
            self.tree_pil_of.insert("", "end", iid=of.id, tags=(tag,),
                                    values=(of.id, of.design, of.qte, pilotage.texte_etapes(self.etat, of, libelles), libelle))
        restes = [of for of in ofs if not self.etat.termine(of)]
        self.btn_valider_commande.configure(state="normal" if restes else "disabled")
        self.btn_imprimer_pilotage.configure(state="normal")
        garder = [i for i in ofs_selectionnes if self.tree_pil_of.exists(i)]
        if garder:
            self.tree_pil_of.selection_set(garder)
        self._maj_selection_pilotage()

    def imprimer_pilotage(self):
        """Commande choisie : sa fiche, ou les fiches des OF sélectionnés (tous ses OF si aucun n'est sélectionné)."""
        cde = self._commande_pilotage()
        if cde is None:
            return
        choisis = [of.id for of in self._ofs_pilotage_selectionnes()]
        ids = choisis or [of.id for of in self.etat.ofs_par_cde.get(cde, [])]
        ImpressionDialog(self.root, self, f"Impression · commande {cde}", cde=cde, ids_of=ids,
                         coches=("suiveuses",) if choisis else ("commande",))

    def _ofs_pilotage_selectionnes(self):
        return [self.etat.ofs[i] for i in self.tree_pil_of.selection() if i in self.etat.ofs]

    def _maj_selection_pilotage(self):
        maj_tags_selection(self.tree_pil_of)
        ofs = self._ofs_pilotage_selectionnes()
        a_valider = [of for of in ofs if pilotage.changements(self.etat, of)]
        valides = [v for of in ofs for v in self.etat.validations.get(of.id, ())]
        if ofs:
            pieces = sum(of.qte for of in ofs)
            self.lbl_pil_selection.configure(text=f"{len(ofs)} OF sélectionné{'s' if len(ofs) > 1 else ''} · {pieces} pièces")
        else:
            self.lbl_pil_selection.configure(text="Aucun OF sélectionné")
        self.btn_valider_ofs.configure(state="normal" if a_valider else "disabled",
                                       text=f"Valider {len(a_valider)} OF" if len(a_valider) > 1 else "Valider l'OF")
        self.btn_valider_etape.configure(state="normal" if a_valider else "disabled")
        self.btn_annuler_validation.configure(state="normal" if valides else "disabled")
        # Qui a validé quoi, pour les OF sélectionnés
        libelles = self.depot.libelles_operations()
        lignes = [f"{v.id_of} · {'OF entier' if v.code_op is None else libelles.get(v.code_op) or v.code_op} validé par "
                  f"{v.chef} le {_date_heure(v.date)} · {v.motif}" + (f" · {v.commentaire}" if v.commentaire else "")
                  for v in valides[:3]]
        if len(valides) > 3:
            lignes.append(f"… et {len(valides) - 3} autre(s) validation(s) : voir l'onglet Validations")
        self.lbl_pil_detail.configure(text="\n".join(lignes))

    # --- Actions ---

    def _ouvrir_validation(self, ofs, par_etape=False, titre_fenetre=None):
        dialog = ValidationDialog(self.root, self.depot, self.etat, ofs, self.signataire, par_etape=par_etape,
                                  titre_fenetre=titre_fenetre)
        self.root.wait_window(dialog)
        if dialog.result:
            etape = f" (étape {dialog.code_op})" if dialog.code_op else ""
            journal().info("Validation chef : %s%s par %s · %s", ", ".join(dialog.result), etape, self.signataire, dialog.motif)
            self.refresh_pilotage()
            self.refresh_dashboard()
            n = len(dialog.result)
            self._message_pilotage(f"{n} OF validé{'s' if n > 1 else ''}{etape}")

    def valider_ofs_pilotage(self):
        ofs = self._ofs_pilotage_selectionnes()
        if ofs:
            self._ouvrir_validation(ofs)

    def valider_etape_pilotage(self):
        ofs = self._ofs_pilotage_selectionnes()
        if ofs:
            self._ouvrir_validation(ofs, par_etape=True)

    def valider_commande_pilotage(self):
        cde = self._commande_pilotage()
        if cde:
            self.recharger_etat()
            self._ouvrir_validation(self.etat.ofs_par_cde.get(cde, []), titre_fenetre=f"Valider la commande {cde}")

    def annuler_validation_pilotage(self):
        ofs = self._ofs_pilotage_selectionnes()
        valides = [v for of in ofs for v in self.etat.validations.get(of.id, ())]
        if not valides:
            return
        noms = ", ".join(sorted({v.id_of for v in valides}, key=tri.cle_naturelle))
        if not messagebox.askyesno("Annuler la validation",
                                   f"Annuler {len(valides)} validation(s) sur {noms} ?\n\n"
                                   "Les étapes reviennent aux pièces réellement scannées. L'annulation reste tracée."):
            return
        self.depot.annuler_validation([v.id for v in valides], self.signataire)
        journal().info("Validation(s) annulée(s) sur %s par %s", noms, self.signataire)
        self.refresh_pilotage()
        self.refresh_dashboard()
        self._message_pilotage(f"Validation annulée · {noms}")

    # ===================== Onglet Validations =====================

    def build_validations_ui(self):
        parent = self.tab_validations
        entete = ctk.CTkFrame(parent, fg_color="transparent")
        entete.pack(fill=tk.X, pady=(0, T.ESPACE_S))
        titre(entete, "Validations des chefs d'atelier", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        self.lbl_validations_message = texte(entete, "")
        self.lbl_validations_message.pack(side=tk.RIGHT)

        panneau = carte(parent)
        panneau.pack(expand=True, fill=tk.BOTH)
        outils = ctk.CTkFrame(panneau, fg_color="transparent")
        outils.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_S))
        self.search_validations = champ(outils, "Rechercher un OF, une commande ou un chef", largeur=320)
        self.search_validations.pack(side=tk.LEFT)
        self.search_validations.bind("<KeyRelease>", lambda e: self.refresh_validations())
        self.filtre_validations = ctk.CTkSegmentedButton(
            outils, values=["Actives", "Toutes"], command=lambda _: self.refresh_validations(), height=36, corner_radius=15,
            border_width=3, font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE, unselected_color=T.SURFACE,
            unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE, selected_hover_color=T.PRIMAIRE_SURVOL,
            text_color=T.TEXTE)
        self.filtre_validations.set("Actives")
        self.filtre_validations.pack(side=tk.LEFT, padx=T.ESPACE_L)
        self.btn_annuler_validation_hist = bouton(outils, "Annuler la validation", self.annuler_validation_historique,
                                                  style="secondaire", state="disabled", width=180)
        self.btn_annuler_validation_hist.pack(side=tk.RIGHT)
        bouton(outils, "Voir l'OF", self.voir_of_validation, style="secondaire", width=110).pack(side=tk.RIGHT, padx=T.ESPACE_S)

        cadre, self.tree_validations = tableau(panneau, [
            ("date", "Date", 130, "w"), ("of", "OF", 140, "w"), ("cde", "Commande", 100, "w"),
            ("etape", "Étape", 120, "w"), ("chef", "Validé par", 130, "w"), ("motif", "Motif", 150, "w"),
            ("commentaire", "Commentaire", 200, "w"), ("statut", "Statut", 220, "w")], selection="extended")
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_validations.bind("<<TreeviewSelect>>", lambda e: self._maj_selection_validations())
        self.tree_validations.bind("<Double-1>", lambda e: self.voir_of_validation())

    def refresh_validations(self):
        selection = self.tree_validations.selection()
        for item in self.tree_validations.get_children():
            self.tree_validations.delete(item)
        recherche = self.search_validations.get().strip().lower()
        actives = self.filtre_validations.get() == "Actives"
        libelles = self.depot.libelles_operations()
        lignes = self.depot.historique_validations()
        nb = 0
        for id_v, quand, id_of, cde, code_op, chef, motif, commentaire, annulee, date_annul, annulee_par in lignes:
            if actives and annulee:
                continue
            if recherche and not any(recherche in str(x).lower() for x in (id_of, cde, chef, motif, commentaire)):
                continue
            statut = f"Annulée le {_date_heure(date_annul)}" + (f" par {annulee_par}" if annulee_par else "") if annulee else "Active"
            etape = "OF entier" if code_op is None else libelles.get(code_op) or code_op
            self.tree_validations.insert("", "end", iid=str(id_v), tags=("annule" if annulee else "valide",),
                                         values=(_date_heure(quand), id_of, cde, etape, chef, motif, commentaire, statut))
            nb += 1
        if not nb:
            self.tree_validations.insert("", "end", iid="vide", tags=("annule",),
                                         values=("", "", "", "Aucune validation", "", "", "", ""))
        self.lbl_validations_message.configure(text=f"{nb} validation{'s' if nb > 1 else ''}")
        garder = [i for i in selection if self.tree_validations.exists(i)]
        if garder:
            self.tree_validations.selection_set(garder)
        self._maj_selection_validations()

    def _validations_choisies(self, actives_seulement=True):
        choix = []
        for item in self.tree_validations.selection():
            if item == "vide":
                continue
            statut = self.tree_validations.item(item, "values")[7]
            if not actives_seulement or statut == "Active":
                choix.append(item)
        return choix

    def _maj_selection_validations(self):
        maj_tags_selection(self.tree_validations)
        self.btn_annuler_validation_hist.configure(state="normal" if self._validations_choisies() else "disabled")

    def annuler_validation_historique(self):
        ids = self._validations_choisies()
        if not ids:
            return
        if not messagebox.askyesno("Annuler la validation", f"Annuler {len(ids)} validation(s) ?\n\n"
                                   "Les étapes reviennent aux pièces réellement scannées. L'annulation reste tracée."):
            return
        self.depot.annuler_validation([int(i) for i in ids], self.signataire)
        journal().info("Validation(s) %s annulée(s) par %s", ", ".join(ids), self.signataire)
        self.refresh_validations()
        self.refresh_dashboard()

    def voir_of_validation(self):
        """Ouvre le Pilotage sur la commande de l'OF choisi, OF sélectionné."""
        choix = self._validations_choisies(actives_seulement=False)
        if not choix:
            return
        id_of = self.tree_validations.item(choix[0], "values")[1]
        self.recharger_etat()
        of = self.etat.ofs.get(id_of)
        if of is None or of.cde not in self.etat.commandes():
            messagebox.showinfo("Voir l'OF", f"{id_of} n'est plus suivi (annulé, supprimé ou commande clôturée).")
            return
        self.notebook.set(self.NOM_ONGLET_PILOTAGE)
        self.search_pilotage.delete(0, tk.END)
        self.filtre_pilotage.set("Toutes")
        self.refresh_pilotage()
        if self.tree_pil_cmd.exists(of.cde):
            self.tree_pil_cmd.selection_set(of.cde)
            self.tree_pil_cmd.see(of.cde)
            self._afficher_commande_pilotage()
        if self.tree_pil_of.exists(of.id):
            self.tree_pil_of.selection_set(of.id)
            self.tree_pil_of.see(of.id)
            self._maj_selection_pilotage()


class ValidationDialog(FenetreDialogue):
    """Confirmation d'une validation : ce qui va changer, motif, commentaire.
    result = OF validés (liste) ou None ; code_op = étape validée (None : OF entiers)."""

    def __init__(self, parent, depot, etat, ofs, signataire, par_etape=False, titre_fenetre=None):
        super().__init__(parent)
        self.depot, self.etat, self.signataire = depot, etat, signataire
        self.ofs = [of for of in ofs if not of.annule]
        self.par_etape = par_etape
        self.result = None
        self.code_op = None
        self.motif = ""
        self.libelles = depot.libelles_operations()
        titre_fenetre = titre_fenetre or ("Valider une étape" if par_etape else
                                          f"Valider {len(self.ofs)} OF" if len(self.ofs) > 1 else f"Valider {self.ofs[0].id}")
        self.title(titre_fenetre)
        centrer_fenetre(self, 640, 600)
        self.configure(fg_color=T.FOND)
        self.transient(parent)

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, titre_fenetre, taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_L, 0))
        texte(cadre, f"Ces étapes passent à « terminé » sans scan, au nom de {signataire}. Les scans déjà faits sont gardés.",
              wraplength=560, justify="left").pack(fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_M))

        # Boutons en bas (posés en premier pour rester visibles)
        pied = ctk.CTkFrame(cadre, fg_color="transparent")
        pied.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_XL, pady=T.ESPACE_L)
        self.btn_valider = bouton(pied, "Valider", self.save, style="primaire", width=170)
        self.btn_valider.pack(side=tk.RIGHT)
        bouton(pied, "Annuler", self.destroy, style="secondaire", width=120).pack(side=tk.RIGHT, padx=T.ESPACE_S)
        self.lbl_erreur = ctk.CTkLabel(cadre, text="", font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.ERREUR_TEXTE,
                                       anchor="w", wraplength=560, justify="left")
        self.lbl_erreur.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_XL)

        # Commentaire et motif
        self.commentaire_entry = champ(cadre, "Commentaire (obligatoire pour « Autre »)")
        self.commentaire_entry.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_XL)
        self.choix_motif = ctk.CTkSegmentedButton(
            cadre, values=list(pilotage.MOTIFS), command=lambda _: self.lbl_erreur.configure(text=""), height=36,
            corner_radius=15, border_width=3, font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE, unselected_color=T.SURFACE,
            unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE, selected_hover_color=T.PRIMAIRE_SURVOL,
            text_color=T.TEXTE)
        self.choix_motif.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_S))
        texte(cadre, "Motif", gras=True).pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_M, T.ESPACE_XS))

        # Étape (validation d'une seule étape) : celles des OF choisis, dans l'ordre de la gamme
        if par_etape:
            ligne = ctk.CTkFrame(cadre, fg_color="transparent")
            ligne.pack(fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_S))
            texte(ligne, "Étape", gras=True).pack(side=tk.LEFT)
            etapes = []
            for of in self.ofs:
                for op, _ in etat.gamme(of.id):
                    if op not in etapes:
                        etapes.append(op)
            self._etapes = {f"{self.libelles.get(op) or op}": op for op in etapes}
            a_faire = next((l for l, op in self._etapes.items()
                            if any(pilotage.changements(etat, of, op) for of in self.ofs)), next(iter(self._etapes), ""))
            self.var_etape = tk.StringVar(value=a_faire)
            ctk.CTkOptionMenu(ligne, values=list(self._etapes), variable=self.var_etape, command=lambda _: self._maj_resume(),
                              height=36, width=220, corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS, gras=True),
                              dropdown_font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE, button_color=T.BORDURE,
                              button_hover_color=T.BORDURE_SURVOL, text_color=T.TEXTE).pack(side=tk.LEFT, padx=T.ESPACE_M)

        texte(cadre, "Ce qui va changer", gras=True).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_XS))
        self.zone_resume = ctk.CTkScrollableFrame(cadre, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE, height=150)
        self.zone_resume.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_XL)
        self._maj_resume()

        self.bind("<Escape>", lambda e: self.destroy())
        capturer_focus(self)

    def etape_choisie(self):
        return self._etapes.get(self.var_etape.get()) if self.par_etape else None

    def a_valider(self):
        """OF qui ont encore quelque chose à valider pour l'étape (ou l'OF entier) choisie."""
        code_op = self.etape_choisie()
        return [of for of in self.ofs if pilotage.changements(self.etat, of, code_op)]

    def _maj_resume(self):
        for widget in self.zone_resume.winfo_children():
            widget.destroy()
        code_op = self.etape_choisie()
        for of in self.ofs:
            modifs = pilotage.changements(self.etat, of, code_op)
            if modifs:
                detail = " · ".join(f"{self.libelles.get(op) or op} {avant} → {apres}" for op, avant, apres in modifs)
                couleur = T.TEXTE
            elif code_op and code_op not in [op for op, _ in self.etat.gamme(of.id)]:
                detail, couleur = "n'a pas cette étape : inchangé", T.TEXTE_ATTENUE
            else:
                detail, couleur = "déjà terminé : rien à changer", T.TEXTE_ATTENUE
            ctk.CTkLabel(self.zone_resume, text=f"{of.id} · {detail}", font=T.police(T.TAILLE_CORPS), text_color=couleur,
                         anchor="w", justify="left", wraplength=540).pack(fill=tk.X, padx=T.ESPACE_S, pady=2)
        n = len(self.a_valider())
        self.btn_valider.configure(text=f"Valider {n} OF" if n > 1 else "Valider l'OF" if n else "Rien à valider",
                                   state="normal" if n else "disabled")

    def save(self):
        ofs = self.a_valider()
        if not ofs:
            self.lbl_erreur.configure(text="Rien à valider : ces OF sont déjà terminés.")
            return
        motif = self.choix_motif.get()
        commentaire = self.commentaire_entry.get().strip()
        if motif not in pilotage.MOTIFS:
            self.lbl_erreur.configure(text="Choisissez un motif.")
            return
        if motif == "Autre" and not commentaire:
            self.lbl_erreur.configure(text="Précisez le motif dans le commentaire.")
            self.commentaire_entry.focus_set()
            return
        self.code_op = self.etape_choisie()
        self.motif = motif
        self.result = self.depot.valider([of.id for of in ofs], self.code_op, self.signataire, motif, commentaire)
        self.destroy()
