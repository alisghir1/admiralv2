"""Fenêtre principale : en-tête, onglets, état partagé, configuration du poste."""
import os
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import customtkinter as ctk

from .. import __version__, config as cfg
from .. import theme as T
from ..db import schema
from ..db.depot import Depot
from ..domain import lecture_sage, sage
from ..journal import journal
from .administration import AdministrationMixin
from .atelier import AtelierMixin
from .be_charge import ChargeMixin
from .be_generation import GenerationOFMixin
from .be_matrice import MatriceMixin
from .composants import bouton, configurer_styles_ttk, texte
from .dialogs import ConfigDialog
from .pilotage import PilotageMixin
from .synthese import SyntheseMixin
from .widgets import get_icon

DELAI_RECHERCHE_MS = 250
SURVEILLANCE_BASE_MS = 5000   # les écritures des autres postes (OF corrigé, scans…) apparaissent ici en 5 s au plus
DELAI_SUIVI_LECTURE_MS = 500     # relecture automatique de Sage : la lecture en arrière-plan est-elle finie ?
DELAI_REPORT_ECRANS_MS = 5_000   # écrans occupés (fenêtre ouverte, lignes sélectionnées) : nouvel essai


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
            # Redessin forcé sur macOS seulement : sous Windows, update_idletasks() peut s'exécuter au milieu
            # d'un autre rafraîchissement (une fenêtre qui s'ouvre colore sa barre de titre) et Tk plante.
            if sys.platform == "darwin":
                self.update_idletasks()
            self._tab_dict[self._current_name].tkraise()
            if sys.platform == "darwin":
                self.winfo_toplevel().update_idletasks()
        except tk.TclError:
            pass


class SotraglaceApp(AtelierMixin, SyntheseMixin, GenerationOFMixin, MatriceMixin, ChargeMixin, AdministrationMixin,
                    PilotageMixin):
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
    NOM_ONGLET_PILOTAGE = "Pilotage"
    NOM_ONGLET_VALIDATIONS = "Validations"
    ONGLETS_BUREAU_ETUDE = (NOM_ONGLET_GENERATION, NOM_ONGLET_ADMIN)   # masqués au Chef d'atelier

    def __init__(self, root, poste=None):
        """poste : impose le poste sans le demander ni l'enregistrer (auto-vérification)."""
        self.root = root
        self.config = cfg.lire_config()
        self.depot = Depot(schema.ouvrir(cfg.chemin_base(self.config)))
        self.dossier_sage = cfg.dossier_sage(self.config)
        self.sage = sage.DonneesSage()
        self._lecture_sage = lecture_sage.LectureEnFond()
        self._ecrans_sage_a_rafraichir = None  # détail du message, quand la mise à jour des écrans est reportée
        self.etat = self.depot.charger_etat()
        self._recherche_timer = None
        journal().info("Démarrage : base %s, données Sage %s", cfg.chemin_base(self.config), self.dossier_sage)

        self.chef_actuel = self.config.get('chef_atelier') or cfg.CHEF_PAR_DEFAUT
        self.poste_actuel = poste or self.load_config()

        self.root.title(f"Admiral {__version__} · Suivi d'atelier Sotraglace")   # version visible : bonne livraison
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
        self._planifier_lecture_sage()
        self._version_base = self.depot.version_donnees()
        self._apres(SURVEILLANCE_BASE_MS, self._surveiller_base)

    # --- État partagé ---

    def recharger_etat(self):
        """Relit OF, gammes et scans depuis la base (à appeler en début d'action et après chaque écriture)."""
        self.etat = self.depot.charger_etat()
        return self.etat

    @property
    def est_bureau_etude(self):
        return self.poste_actuel == cfg.POSTE_BUREAU_ETUDE

    @property
    def est_chef(self):
        return self.poste_actuel == cfg.POSTE_CHEF_ATELIER

    @property
    def est_pilotage(self):
        """PC de pilotage (Bureau d'étude ou Chef d'atelier) : onglets, pas de douchette ni d'écran Atelier."""
        return self.est_bureau_etude or self.est_chef

    @property
    def signataire(self):
        """Nom inscrit sur les validations faites depuis ce PC."""
        return self.chef_actuel if self.est_chef else cfg.POSTE_BUREAU_ETUDE

    def _chef_par_code(self, code):
        """Chef reconnu par son code. Tant qu'aucun chef n'est créé (Administration), le code par défaut ouvre l'accès."""
        nom = self.depot.chef_par_code(code)
        if nom is None and not self.depot.lister_chefs() and code == cfg.code_chef_atelier(self.config):
            nom = cfg.CHEF_PAR_DEFAUT
        return nom

    def _signaler(self, type_message, message, detail=""):
        """Message à l'utilisateur : bandeau de scan à l'atelier, ligne d'information au pilotage."""
        if self.est_chef:
            self._message_pilotage(f"{message} · {detail}" if detail else message)
        elif self.est_pilotage:
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
        if not self.est_pilotage and not self._est_champ_saisie(self._focus_actuel()):
            self.scan_entry.focus_set()

    def force_focus(self, event):
        # La douchette tape comme un clavier : un caractère tapé hors d'un champ de saisie part au scan.
        # Ce premier caractère a déjà été livré au widget précédent : on le recopie pour ne pas le perdre.
        # Les touches sans caractère (flèches, Tab…) restent au widget qui a le focus.
        if self.est_pilotage or self._est_champ_saisie(self._focus_actuel()):
            return  # au Bureau d'étude, pas de douchette : le clavier reste à l'utilisateur
        if event.char and event.char.isprintable():
            self.scan_entry.focus_set()
            self.scan_entry.insert("end", event.char)

    # --- Poste de travail ---

    def load_config(self):
        poste = self.config.get('poste')
        if poste:
            return poste
        dialog = ConfigDialog(self.root, self.libelles_postes(), code_bureau_etude=cfg.code_bureau_etude(self.config),
                              chef_par_code=self._chef_par_code)
        self.root.wait_window(dialog)
        poste = dialog.result
        self._memoriser_poste(poste, dialog.chef)
        return poste

    def _memoriser_poste(self, poste, chef=None):
        valeurs = {'poste': poste}
        if poste == cfg.POSTE_CHEF_ATELIER:
            valeurs['chef_atelier'] = chef
            self.chef_actuel = chef
        cfg.ecrire_config(valeurs)
        self.config.update(valeurs)

    def change_poste(self):
        dialog = ConfigDialog(self.root, self.libelles_postes(), is_cancellable=True, actuel=self.poste_actuel,
                              code_bureau_etude=cfg.code_bureau_etude(self.config), chef_par_code=self._chef_par_code)
        self.root.wait_window(dialog)

        autre_chef = dialog.result == cfg.POSTE_CHEF_ATELIER and dialog.chef != self.chef_actuel
        if dialog.result and (dialog.result != self.poste_actuel or autre_chef):
            self.poste_actuel = dialog.result
            self._memoriser_poste(self.poste_actuel, dialog.chef)
            journal().info("Changement de poste : %s%s", self.poste_actuel, f" ({dialog.chef})" if dialog.chef else "")
            self._maj_entete_poste()
            self._appliquer_mode()
            self.refresh_dashboard()
            if self.commande_affichee and not self.est_pilotage:
                self._afficher_commande(self.commande_affichee)
        elif not self.est_pilotage:
            self.scan_entry.focus_set()

    def _appliquer_mode(self):
        """Bureau d'étude : les onglets de pilotage (sans Atelier), sans douchette.
        Poste machine : l'écran Atelier seul, douchette active.
        Les deux écrans existent en permanence : on affiche l'un et on masque l'autre. Aucun élément
        n'est détruit ni recréé (recréer les boutons d'onglets faisait planter Tk sous Windows)."""
        if self.est_pilotage:
            self.tab_atelier.pack_forget()
            self._onglets_du_profil()
            self.notebook.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_L, pady=(0, T.ESPACE_M))
            self.notebook.set(self.NOM_ONGLET_PILOTAGE if self.est_chef else self.NOM_ONGLET_SYNTHESE)
            self.root.unbind("<Button-1>")
            self.root.unbind("<Any-KeyPress>")
            self.on_main_tab_changed()
        else:
            self.notebook.pack_forget()
            self.tab_atelier.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_L, pady=(10, T.ESPACE_M))
            self.root.bind("<Button-1>", self.on_global_click)
            self.root.bind("<Any-KeyPress>", self.force_focus)
            self.scan_entry.focus_set()

    def _onglets_du_profil(self):
        """Chef d'atelier : sans Création d'OF ni Administration (Bureau d'étude). Les boutons d'onglets sont
        masqués, jamais recréés (recréer la barre d'onglets fait planter Tk sous Windows)."""
        barre = self.notebook._segmented_button
        for index, nom in enumerate(barre.cget("values")):
            bouton_onglet = barre._buttons_dict[nom]
            if self.est_chef and nom in self.ONGLETS_BUREAU_ETUDE:
                bouton_onglet.grid_remove()
                barre.grid_columnconfigure(index, minsize=0)
            else:
                bouton_onglet.grid()
                barre.grid_columnconfigure(index, minsize=barre._current_height)

    # --- Données Sage ---

    def load_sage_data(self):
        """Lit le dossier Sage, recopie la lecture dans la base, puis charge les commandes depuis la base.
        Sans lecture possible, la copie de la base (faite par ce poste ou un autre) reste utilisée.
        Retourne le bilan de la recopie (BilanSynchro), ou None si une erreur a été signalée."""
        erreur = None
        empreinte = lecture_sage.signature(self.dossier_sage)  # avant la lecture : un enregistrement pendant sera relu
        try:
            lu = sage.charger(self.dossier_sage)
            self._lecture_sage.noter(empreinte)
        except sage.SageIllisible as exc:
            # Classeur en cours d'enregistrement ou abîmé : la copie de la base reste en place
            journal().warning("Classeur Sage illisible : %s", exc)
            lu, erreur = None, ("Classeur Sage illisible", f"{exc} · copie précédente conservée")
        bilan = self.depot.synchroniser_sage(lu) if lu is not None else None
        if bilan and bilan.ignoree:
            journal().info("Lecture Sage non recopiée : %s", bilan.ignoree)
            if not (lu.entetes or lu.lignes):
                erreur = ("Aucune commande Sage lue", f"{bilan.ignoree} · copie précédente conservée")
        elif bilan:
            journal().info("Sage : %d commandes, %d lignes lues (%s) : %s",
                           len(lu.entetes), len(lu.lignes), lu.source, bilan.resume())

        self.sage = self.depot.charger_sage()
        if lu is None and erreur is None and self.sage.entetes:
            bilan = sage.BilanSynchro(ignoree=f"dossier Sage absent : {self.dossier_sage}")  # poste sans fichier
        elif lu is None and erreur is None:
            try:
                os.makedirs(self.dossier_sage, exist_ok=True)
                erreur = ("Dossier Sage créé", f"Placez le classeur Sage ou les exports CSV dans {self.dossier_sage}")
            except OSError:
                erreur = ("Dossier Sage introuvable", self.dossier_sage)
        self._maj_libelle_sage()
        if erreur:
            self._signaler("error", *erreur)
            return None
        return bilan

    def _maj_libelle_sage(self):
        if self.sage.date_source:
            self.lbl_sage.configure(text=f"Sage au {datetime.fromisoformat(self.sage.date_source):%d/%m %H:%M}"
                                         f" · {len(self.sage.entetes)} commandes")
        else:
            self.lbl_sage.configure(text="Exports Sage absents")

    # --- Relecture automatique de Sage ---

    def _planifier_lecture_sage(self):
        minutes = cfg.actualisation_sage_minutes(self.config)
        if minutes:
            self._apres(int(minutes * 60_000), self._lecture_sage_auto)

    def _apres(self, delai_ms, fonction):
        """root.after sans erreur quand la fenêtre est en cours de fermeture."""
        try:
            self.root.after(delai_ms, fonction)
        except tk.TclError:
            pass

    def _lecture_sage_auto(self):
        """Relit le dossier Sage en arrière-plan (seulement si un fichier a changé), puis suit la lecture."""
        self._lecture_sage.lancer(self.dossier_sage)
        self._suivre_lecture_sage()

    def _suivre_lecture_sage(self):
        resultat = self._lecture_sage.resultat()
        if resultat is lecture_sage.EN_COURS:
            self._apres(DELAI_SUIVI_LECTURE_MS, self._suivre_lecture_sage)
            return
        try:
            self.appliquer_lecture_sage(resultat)
        except Exception:  # base partagée verrouillée trop longtemps… : la relecture suivante réessaiera
            journal().exception("Relecture automatique de Sage")
        self._planifier_lecture_sage()

    def appliquer_lecture_sage(self, resultat):
        """Recopie dans la base une lecture faite en arrière-plan (résultat de LectureEnFond), puis met les écrans
        à jour si la copie de la base a changé, par cette lecture ou par un autre poste."""
        bilan = None
        if isinstance(resultat, Exception):
            journal().warning("Relecture automatique de Sage impossible : %s", resultat)
        elif resultat is not None:
            bilan = self.depot.synchroniser_sage(resultat)
            if bilan.ignoree:
                journal().info("Lecture Sage non recopiée : %s", bilan.ignoree)
                bilan = None
            else:
                journal().info("Sage (relecture automatique) : %s", bilan.resume())
        if self.depot.date_source_sage() == self.sage.date_source:
            return  # la copie de la base n'a pas changé
        self.sage = self.depot.charger_sage()
        self._maj_libelle_sage()
        if bilan is None:
            self._rafraichir_ecrans_sage("copie mise à jour par un autre poste")
        elif bilan.changements:
            self._rafraichir_ecrans_sage(bilan.resume())

    def _rafraichir_ecrans_sage(self, detail):
        """Met les listes à jour sans déranger : reporté tant qu'une fenêtre est ouverte ou que le Bureau d'étude
        a sélectionné des lignes de commande (la sélection serait perdue)."""
        occupe = self.root.grab_current() is not None or (self.est_pilotage and self.tree_be_sage.selection())
        if occupe:
            if self._ecrans_sage_a_rafraichir is None:
                self._apres(DELAI_REPORT_ECRANS_MS, self._rafraichissement_sage_reporte)
            self._ecrans_sage_a_rafraichir = detail
            return
        self.refresh_dashboard()
        if self.commande_affichee and not self.est_pilotage:
            self._afficher_commande(self.commande_affichee)
        if self.est_pilotage:  # à l'atelier, le bandeau reste aux scans : seul le libellé Sage change
            self._signaler("progress", "Commandes Sage mises à jour", f"{len(self.sage.entetes)} commandes · {detail}")

    # --- Écrans toujours à jour : écritures des autres postes ---

    def _surveiller_base(self):
        """Toutes les 5 s : si un autre poste a écrit dans la base (OF créé, corrigé, annulé, scans…),
        tous les écrans affichés sont remis à jour."""
        try:
            version = self.depot.version_donnees()
            if version != self._version_base:
                self._version_base = version
                self.rafraichir_ecrans_ouverts()
        except tk.TclError:   # fenêtre en cours de fermeture
            return
        except Exception:     # base partagée momentanément verrouillée : on réessaie au tour suivant
            journal().exception("Surveillance de la base")
        self._apres(SURVEILLANCE_BASE_MS, self._surveiller_base)

    def rafraichir_ecrans_ouverts(self):
        """Remet à jour tout ce qui est affiché, sans perdre sélections ni OF dépliés. Reporté si une fenêtre
        est ouverte ou si le Bureau d'étude a coché des lignes de commande (la saisie serait perdue)."""
        if self.root.grab_current() is not None or (self.est_pilotage and self.tree_be_sage.selection()):
            self._version_base = None   # on réessaiera au prochain tour
            return
        self.refresh_dashboard()
        if not self.est_pilotage:
            if self.commande_affichee:
                self._afficher_commande(self.commande_affichee)
            return
        onglet = self.notebook.get()
        if onglet == self.NOM_ONGLET_GENERATION and self.tree_be_cmd.selection():
            self.on_be_order_select()
        elif onglet == self.NOM_ONGLET_SYNTHESE:
            self.refresh_synthese()
        elif onglet == self.NOM_ONGLET_CHARGE:
            self.refresh_be_charge()
        elif onglet == self.NOM_ONGLET_PILOTAGE:
            self.refresh_pilotage()
        elif onglet == self.NOM_ONGLET_VALIDATIONS:
            self.refresh_validations()

    def _rafraichissement_sage_reporte(self):
        detail, self._ecrans_sage_a_rafraichir = self._ecrans_sage_a_rafraichir, None
        if detail is not None:
            self._rafraichir_ecrans_sage(detail)

    def action_refresh(self):
        bilan = self.load_sage_data()
        self.refresh_dashboard()
        if self.commande_affichee and not self.est_pilotage:
            self._afficher_commande(self.commande_affichee)
        if bilan:  # sinon, le message d'erreur de la lecture reste affiché
            detail = "copie de la base utilisée" if bilan.ignoree else bilan.resume()
            self._signaler("progress", "Données Sage actualisées", f"{len(self.sage.entetes)} commandes · {detail}")
        if not self.est_pilotage:
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
        # Onglets masqués au Chef d'atelier placés au milieu : la barre garde ses deux bouts arrondis
        self.tab_synthese = self.notebook.add(self.NOM_ONGLET_SYNTHESE)
        self.tab_pilotage = self.notebook.add(self.NOM_ONGLET_PILOTAGE)
        self.tab_be_gen = self.notebook.add(self.NOM_ONGLET_GENERATION)
        self.tab_be_charge = self.notebook.add(self.NOM_ONGLET_CHARGE)
        self.tab_admin = self.notebook.add(self.NOM_ONGLET_ADMIN)
        self.tab_validations = self.notebook.add(self.NOM_ONGLET_VALIDATIONS)

        self.build_atelier_ui(self.tab_atelier)
        self.build_synthese_ui()
        self.build_be_gen_ui()
        self.build_be_charge_ui()
        self.build_admin_ui()
        self.build_pilotage_ui()
        self.build_validations_ui()

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
        if self.est_chef:
            self.lbl_title.configure(text=f"   {cfg.POSTE_CHEF_ATELIER} · {self.chef_actuel}   ")
            return
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
        elif onglet == self.NOM_ONGLET_PILOTAGE:
            self.refresh_pilotage()
        elif onglet == self.NOM_ONGLET_VALIDATIONS:
            self.refresh_validations()

    # --- Listes de commandes ---

    def on_search_change(self, *args):
        # On attend la fin de la frappe avant de recalculer les listes
        if self._recherche_timer is not None:
            self.root.after_cancel(self._recherche_timer)
        self._recherche_timer = self.root.after(DELAI_RECHERCHE_MS, self._appliquer_recherche)

    def _appliquer_recherche(self):
        self._recherche_timer = None
        self.refresh_dashboard()

    def _filtrer(self, entetes, recherche):
        """Commandes dont le numéro, le client, la réf. client ou l'observation de Sage contient la recherche."""
        recherche = recherche.strip().lower()
        return [(do_piece, entete) for do_piece, entete in entetes.items()
                if not recherche or recherche in self.sage.texte_recherche(do_piece)]

    def refresh_dashboard(self):
        self.recharger_etat()
        self._remplir_commandes_atelier(self._filtrer(self.sage.entetes, self.search_entry.get()))
        self._remplir_commandes_be(self._filtrer(self.sage.entetes, self.search_be.get()))
