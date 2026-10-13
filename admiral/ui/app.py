"""Fenêtre principale : en-tête, onglets, état partagé, configuration du poste."""
import os
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import customtkinter as ctk

from .. import config as cfg
from .. import theme as T
from ..db import schema
from ..db.depot import Depot
from ..domain import sage
from ..journal import journal
from .administration import AdministrationMixin
from .atelier import AtelierMixin
from .be_charge import ChargeMixin
from .be_generation import GenerationOFMixin
from .be_matrice import MatriceMixin
from .composants import bouton, configurer_styles_ttk, texte
from .dialogs import ConfigDialog
from .synthese import SyntheseMixin
from .widgets import get_icon

DELAI_RECHERCHE_MS = 250


class Onglets(ctk.CTkTabview):
    """Barre d'onglets plus haute que celle de CustomTkinter (26 px) : cible confortable à l'atelier."""
    _button_height = 44
    ESPACE_SOUS_BARRE = 14  # air entre la barre d'onglets et le contenu (sinon ils se touchent)

    def _set_grid_current_tab(self):
        super()._set_grid_current_tab()
        self._tab_dict[self._current_name].grid_configure(pady=(self.ESPACE_SOUS_BARRE, 0))

    def set(self, name):
        super().set(name)
        # CustomTkinter retire les anciens onglets 100 ms plus tard : on force ensuite le redessin,
        # sinon des morceaux de l'onglet quitté peuvent rester affichés (macOS).
        self.after(160, self._redessiner)

    def _redessiner(self):
        try:
            self.update_idletasks()
            self._tab_dict[self._current_name].tkraise()
            self.winfo_toplevel().update_idletasks()
        except tk.TclError:
            pass


class SotraglaceApp(AtelierMixin, SyntheseMixin, GenerationOFMixin, MatriceMixin, ChargeMixin, AdministrationMixin):
    """Application. Les écrans sont des mixins qui partagent :
    - self.depot : accès à la base (toutes les requêtes SQL)
    - self.sage  : données Sage (DonneesSage)
    - self.etat  : photo de l'atelier (EtatAtelier), rechargée par recharger_etat()
    """

    NOM_ONGLET_ATELIER = "Atelier"
    NOM_ONGLET_SYNTHESE = "Synthèse"
    NOM_ONGLET_GENERATION = "Création d'OF"
    NOM_ONGLET_CHARGE = "Charge des postes"
    NOM_ONGLET_ADMIN = "Administration"

    def __init__(self, root, poste=None):
        """poste : impose le poste sans le demander ni l'enregistrer (auto-vérification)."""
        self.root = root
        self.config = cfg.lire_config()
        self.depot = Depot(schema.ouvrir(cfg.chemin_base(self.config)))
        self.dossier_sage = cfg.dossier_sage(self.config)
        self.sage = sage.DonneesSage()
        self.etat = self.depot.charger_etat()
        self._recherche_timer = None
        journal().info("Démarrage : base %s, données Sage %s", cfg.chemin_base(self.config), self.dossier_sage)

        self.poste_actuel = poste or self.load_config()

        self.root.title("Admiral · Suivi d'atelier Sotraglace")
        self.root.geometry("1366x820")
        self.root.minsize(1180, 720)
        def _maximize_safe():
            try:
                self.root.state('zoomed')
            except tk.TclError:
                try:
                    self.root.attributes('-zoomed', True)
                except tk.TclError:
                    pass
        self.root.after(100, _maximize_safe)

        self.root.configure(fg_color=T.FOND)
        configurer_styles_ttk(self.root)
        self.build_ui()
        self._appliquer_mode()
        self.load_sage_data()
        self.refresh_dashboard()

    # --- État partagé ---

    def recharger_etat(self):
        """Relit OF, gammes et scans depuis la base (à appeler en début d'action et après chaque écriture)."""
        self.etat = self.depot.charger_etat()
        return self.etat

    @property
    def est_bureau_etude(self):
        return self.poste_actuel == cfg.POSTE_BUREAU_ETUDE

    def _signaler(self, type_message, message, detail=""):
        """Message à l'utilisateur : bandeau de scan à l'atelier, ligne d'information au Bureau d'étude."""
        if self.est_bureau_etude:
            self._message_be(f"{message} · {detail}" if detail else message)
        else:
            self.update_status_bar(type_message, message, detail)

    def get_codpost(self):
        return self.poste_actuel.split(" - ")[0]

    def get_mon_op(self):
        return self.etat.operation_poste.get(self.get_codpost())

    def libelles_postes(self):
        return [f"{code} - {designation}" for code, designation in self.depot.lister_postes()]

    # --- Focus : la douchette tape comme un clavier dans le champ scan ---

    @staticmethod
    def _est_champ_saisie(widget):
        return isinstance(widget, (tk.Entry, tk.Text, ttk.Entry))

    def on_global_click(self, event):
        # Un clic dans un champ de saisie (recherche, etc.) garde le focus ; ailleurs, on revient au scan.
        if self._est_champ_saisie(event.widget):
            return
        self.root.after(100, self._refocus_scan_si_libre)

    def _focus_actuel(self):
        try:
            return self.root.focus_get()
        except KeyError:
            # focus_get() lève KeyError quand une liste déroulante est ouverte
            return None

    def _refocus_scan_si_libre(self):
        if not self.est_bureau_etude and not self._est_champ_saisie(self._focus_actuel()):
            self.scan_entry.focus_set()

    def force_focus(self, event):
        # La douchette tape comme un clavier : un caractère tapé hors d'un champ de saisie part au scan.
        # Ce premier caractère a déjà été livré au widget précédent : on le recopie pour ne pas le perdre.
        # Les touches sans caractère (flèches, Tab…) restent au widget qui a le focus.
        if self.est_bureau_etude or self._est_champ_saisie(self._focus_actuel()):
            return  # au Bureau d'étude, pas de douchette : le clavier reste à l'utilisateur
        if event.char and event.char.isprintable():
            self.scan_entry.focus_set()
            self.scan_entry.insert("end", event.char)

    # --- Poste de travail ---

    def load_config(self):
        poste = self.config.get('poste')
        if poste:
            return poste
        dialog = ConfigDialog(self.root, self.libelles_postes(), code_bureau_etude=cfg.code_bureau_etude(self.config))
        self.root.wait_window(dialog)
        poste = dialog.result
        cfg.ecrire_config({'poste': poste})
        self.config['poste'] = poste
        return poste

    def change_poste(self):
        dialog = ConfigDialog(self.root, self.libelles_postes(), is_cancellable=True, actuel=self.poste_actuel,
                              code_bureau_etude=cfg.code_bureau_etude(self.config))
        self.root.wait_window(dialog)

        if dialog.result and dialog.result != self.poste_actuel:
            self.poste_actuel = dialog.result
            cfg.ecrire_config({'poste': self.poste_actuel})
            journal().info("Changement de poste : %s", self.poste_actuel)
            self._maj_entete_poste()
            self._appliquer_mode()
            self.refresh_dashboard()
            if self.commande_affichee and not self.est_bureau_etude:
                self._afficher_commande(self.commande_affichee)
        elif not self.est_bureau_etude:
            self.scan_entry.focus_set()

    def _appliquer_mode(self):
        """Bureau d'étude : les onglets de pilotage (sans Atelier), sans douchette.
        Poste machine : l'écran Atelier seul, douchette active.
        Les deux écrans existent en permanence : on affiche l'un et on masque l'autre. Aucun élément
        n'est détruit ni recréé (recréer les boutons d'onglets faisait planter Tk sous Windows)."""
        if self.est_bureau_etude:
            self.tab_atelier.pack_forget()
            self.notebook.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_L, pady=(0, T.ESPACE_M))
            self.notebook.set(self.NOM_ONGLET_SYNTHESE)
            self.root.unbind("<Button-1>")
            self.root.unbind("<Any-KeyPress>")
            self.on_main_tab_changed()
        else:
            self.notebook.pack_forget()
            self.tab_atelier.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_L, pady=(10, T.ESPACE_M))
            self.root.bind("<Button-1>", self.on_global_click)
            self.root.bind("<Any-KeyPress>", self.force_focus)
            self.scan_entry.focus_set()

    # --- Données Sage ---

    def load_sage_data(self):
        donnees = sage.charger(self.dossier_sage)
        if donnees is None:
            try:
                os.makedirs(self.dossier_sage, exist_ok=True)
                self._signaler("error", "Dossier Sage créé", f"Placez les exports CSV dans {self.dossier_sage}")
            except OSError:
                self._signaler("error", "Dossier Sage introuvable", self.dossier_sage)
            self.lbl_sage.configure(text="Exports Sage absents")
            return
        self.sage = donnees
        self.lbl_sage.configure(text=f"Sage lu à {datetime.now():%H:%M} · {len(donnees.entetes)} commandes")
        journal().info("Sage : %d commandes, %d lignes", len(donnees.entetes), len(donnees.lignes))

    def action_refresh(self):
        self.load_sage_data()
        self.refresh_dashboard()
        if self.commande_affichee and not self.est_bureau_etude:
            self._afficher_commande(self.commande_affichee)
        self._signaler("progress", "Données Sage actualisées", f"{len(self.sage.entetes)} commandes lues")
        if not self.est_bureau_etude:
            self.scan_entry.focus_set()

    # --- Mise en page ---

    def build_ui(self):
        self._construire_entete()
        self.notebook = Onglets(
            self.root, command=self.on_main_tab_changed, fg_color=T.FOND, corner_radius=0,
            segmented_button_fg_color=T.CARTE,
            segmented_button_selected_color=T.PRIMAIRE,
            segmented_button_selected_hover_color=T.PRIMAIRE_SURVOL,
            segmented_button_unselected_color=T.CARTE,
            segmented_button_unselected_hover_color=T.SURFACE,
            text_color=T.TEXTE,
            text_color_disabled=T.TEXTE_DESACTIVE,
            anchor="w")
        # corner_radius=0 ci-dessus garde le fond des onglets plat, mais CTkTabview le transmet aussi
        # à sa barre d'onglets : on redonne à la barre ses propres coins arrondis (onglets en pilule).
        self.notebook._segmented_button.configure(font=T.police(T.TAILLE_SOUS_TITRE, gras=True),
                                                  corner_radius=T.RAYON_ONGLET, border_width=4)

        # Écran Atelier (postes machines) : panneau à part, affiché à la place des onglets
        self.tab_atelier = ctk.CTkFrame(self.root, fg_color=T.FOND, corner_radius=0)
        self.tab_synthese = self.notebook.add(self.NOM_ONGLET_SYNTHESE)
        self.tab_be_gen = self.notebook.add(self.NOM_ONGLET_GENERATION)
        self.tab_be_charge = self.notebook.add(self.NOM_ONGLET_CHARGE)
        self.tab_admin = self.notebook.add(self.NOM_ONGLET_ADMIN)

        self.build_atelier_ui(self.tab_atelier)
        self.build_synthese_ui()
        self.build_be_gen_ui()
        self.build_be_charge_ui()
        self.build_admin_ui()

    def _construire_entete(self):
        entete = ctk.CTkFrame(self.root, fg_color=T.FOND, height=64, corner_radius=0)
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_M, 0))

        ctk.CTkLabel(entete, text="Admiral", font=T.police(T.TAILLE_TITRE + 2, gras=True), text_color=T.TITRE).pack(side=tk.LEFT)
        texte(entete, "Sotraglace · suivi d'atelier").pack(side=tk.LEFT, padx=(T.ESPACE_S, T.ESPACE_XL))
        self.lbl_title = ctk.CTkLabel(entete, text="", height=34, corner_radius=17, fg_color=T.SURFACE,
                                      font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE)
        self.lbl_title.pack(side=tk.LEFT)

        bouton(entete, "Changer de poste", self.change_poste, style="secondaire",
               icone=get_icon("settings")).pack(side=tk.RIGHT)
        bouton(entete, "Actualiser Sage", self.action_refresh, style="secondaire",
               icone=get_icon("refresh")).pack(side=tk.RIGHT, padx=T.ESPACE_S)
        self.lbl_sage = texte(entete, "")
        self.lbl_sage.pack(side=tk.RIGHT, padx=T.ESPACE_M)
        self._maj_entete_poste()

    def _maj_entete_poste(self):
        if self.est_bureau_etude:
            self.lbl_title.configure(text=f"   {cfg.POSTE_BUREAU_ETUDE}   ")
            return
        code, _, designation = self.poste_actuel.partition(" - ")
        self.lbl_title.configure(text=f"   Poste {code} · {designation}   " if designation else f"   Poste {code}   ")

    def on_main_tab_changed(self, event=None):
        onglet = self.notebook.get()
        if onglet == self.NOM_ONGLET_CHARGE:
            self.refresh_be_charge()
        elif onglet == self.NOM_ONGLET_GENERATION:
            self.refresh_dashboard()
        elif onglet == self.NOM_ONGLET_SYNTHESE:
            self.refresh_synthese()
        elif onglet == self.NOM_ONGLET_ADMIN:
            self.refresh_admin()

    # --- Listes de commandes ---

    def on_search_change(self, *args):
        # On attend la fin de la frappe avant de recalculer les listes
        if self._recherche_timer is not None:
            self.root.after_cancel(self._recherche_timer)
        self._recherche_timer = self.root.after(DELAI_RECHERCHE_MS, self._appliquer_recherche)

    def _appliquer_recherche(self):
        self._recherche_timer = None
        self.refresh_dashboard()

    @staticmethod
    def _filtrer(entetes, recherche):
        recherche = recherche.strip().lower()
        return [(do_piece, entete) for do_piece, entete in entetes.items()
                if not recherche or recherche in do_piece.lower() or recherche in entete.get("DO_Tiers", "").lower()]

    def refresh_dashboard(self):
        self.recharger_etat()
        self._remplir_commandes_atelier(self._filtrer(self.sage.entetes, self.search_entry.get()))
        self._remplir_commandes_be(self._filtrer(self.sage.entetes, self.search_be.get()))
