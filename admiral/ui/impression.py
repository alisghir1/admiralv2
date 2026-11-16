"""Fenêtre d'impression : on coche les documents, puis « Aperçu / imprimer » (le PDF s'ouvre dans le lecteur
du PC, qui imprime) ou « Enregistrer en PDF… ». La même fenêtre sert partout : Création d'OF, Pilotage,
Charge des postes et écran Atelier ; chaque écran coche par défaut ce qui lui est utile."""
import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from .. import config as cfg
from .. import pdf
from .. import theme as T
from ..domain import documents
from ..journal import journal
from .composants import bouton, carte, champ, texte, titre
from .widgets import FenetreDialogue, capturer_focus, centrer_fenetre

DOSSIER_IMPRESSIONS = os.path.join(cfg.APP_DIR, "impressions")
CONSERVATION_JOURS = 7          # les PDF d'aperçu plus anciens sont supprimés
TOUTES_LES_ETAPES = "Toutes les étapes"
TOUS_LES_POSTES = "Tous les postes"
PAR_LIGNE, PAR_PIECE = "Une par ligne", "Une par pièce"


def ouvrir_fichier(chemin):
    """Ouvre le PDF avec le lecteur du PC (aperçu, choix de l'imprimante, Ctrl+P)."""
    if sys.platform == "win32":
        os.startfile(chemin)  # noqa: S606 - fichier généré par Admiral
    elif sys.platform == "darwin":
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])


def _nettoyer(dossier):
    limite = time.time() - CONSERVATION_JOURS * 86400
    try:
        for nom in os.listdir(dossier):
            chemin = os.path.join(dossier, nom)
            if nom.lower().endswith(".pdf") and os.path.getmtime(chemin) < limite:
                os.remove(chemin)
    except OSError:
        pass   # PDF encore ouvert dans le lecteur : il partira une autre fois


def nom_fichier(base):
    propre = "".join(c if c.isalnum() or c in "-_" else "_" for c in base) or "Admiral"
    return f"{propre}_{datetime.now():%Y-%m-%d_%H%M%S}.pdf"


def generer_apercu(docs, base, titre_pdf, dossier=None, ouvrir=True):
    """Écrit le PDF dans le dossier impressions/ et l'ouvre. Retourne son chemin."""
    dossier = dossier or DOSSIER_IMPRESSIONS
    try:
        os.makedirs(dossier, exist_ok=True)
    except OSError:   # dossier de l'application en lecture seule : dossier temporaire de Windows
        dossier = os.path.join(tempfile.gettempdir(), "Admiral_impressions")
        os.makedirs(dossier, exist_ok=True)
    _nettoyer(dossier)
    chemin = pdf.generer(os.path.join(dossier, nom_fichier(base)), docs, titre=titre_pdf)
    journal().info("Impression : %s (%d documents)", chemin, len(docs))
    if ouvrir:
        ouvrir_fichier(chemin)
    return chemin


def referentiel(depot):
    """(libellés des opérations, désignations des postes, désignations des produits)."""
    return depot.libelles_operations(), dict(depot.lister_postes()), dict(depot.lister_produits())


def imprimer_fiches(app, ids_of, base):
    """Impression directe des fiches suiveuses (après la création d'un OF), sans passer par la fenêtre."""
    etat = app.recharger_etat()
    docs = documents.assembler(documents.Choix(ids_of=tuple(ids_of), fiches_suiveuses=True), etat, app.sage,
                               *referentiel(app.depot))
    return generer_apercu(docs, base, base) if docs else None


class ImpressionDialog(FenetreDialogue):
    """app : l'application (état de l'atelier, données Sage, base) ; cde : commande (fiche commande) ;
    ids_of : OF concernés (fiches, étiquettes) ; postes : postes proposés pour la liste de travail (le premier
    est choisi) ; etape : opération proposée pour les fiches d'étape ; coches : documents cochés au départ,
    parmi "commande", "suiveuses", "etape", "etiquettes", "liste"."""

    def __init__(self, parent, app, titre_fenetre, cde=None, ids_of=(), postes=(), etape=None, coches=(),
                 tous_les_postes=False):
        super().__init__(parent)
        self.app = app
        self.cde = cde
        self.ids_of = tuple(ids_of)
        self.postes = list(postes)
        self.title(titre_fenetre)
        self.configure(fg_color=T.FOND)
        self.transient(parent)
        self.resultat = None   # chemin du dernier PDF produit
        libelles = app.depot.libelles_operations()
        self._libelles = libelles

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, titre_fenetre, taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_L, T.ESPACE_XS))
        texte(cadre, "Cochez les documents. Les PDF sont en noir et blanc, avec une case à cocher au stylo devant "
                     "chaque ligne et un code-barres unique par élément.", wraplength=600, justify="left").pack(
            fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_M))

        self.vars = {}
        if cde:
            self._section(cadre, f"Commande {cde}")
            self._case(cadre, "commande", "Fiche commande : ses OF et leur avancement, les lignes pas encore en OF",
                       "commande" in coches)
        if self.ids_of:
            resume = ", ".join(self.ids_of[:4]) + (f" et {len(self.ids_of) - 4} autres" if len(self.ids_of) > 4 else "")
            self._section(cadre, f"{len(self.ids_of)} OF · {resume}")
            self._case(cadre, "suiveuses", "Fiches suiveuses : tout le parcours de l'OF (vue générale)", "suiveuses" in coches)
            ligne = self._case(cadre, "etape", "Fiches d'étape : l'OF vu par un seul poste (demi-page)", "etape" in coches)
            operations = list(dict.fromkeys(op for i in self.ids_of for op, _ in app.etat.gamme(i)))
            self._etapes = {TOUTES_LES_ETAPES: None}
            self._etapes.update({libelles.get(op) or op: op for op in operations})
            choix_etape = next((l for l, op in self._etapes.items() if op == etape), TOUTES_LES_ETAPES)
            self.menu_etape = self._menu(ligne, list(self._etapes), choix_etape)
            ligne = self._case(cadre, "etiquettes", "Étiquettes des articles (planche de 21)", "etiquettes" in coches)
            self.mode_etiquettes = ctk.CTkSegmentedButton(
                ligne, values=[PAR_LIGNE, PAR_PIECE], height=32, font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE,
                unselected_color=T.SURFACE, unselected_hover_color=T.SURFACE_SURVOL, selected_color=T.PRIMAIRE,
                selected_hover_color=T.PRIMAIRE_SURVOL, text_color=T.TEXTE)
            self.mode_etiquettes.set(PAR_LIGNE)
            self.mode_etiquettes.pack(side=tk.LEFT, padx=(T.ESPACE_M, 0))
            texte(ligne, "à partir de l'étiquette n°").pack(side=tk.LEFT, padx=(T.ESPACE_M, T.ESPACE_XS))
            self.debut_etiquettes = champ(ligne, "1", largeur=56)
            self.debut_etiquettes.pack(side=tk.LEFT)
        if self.postes:
            self._section(cadre, "Postes")
            ligne = self._case(cadre, "liste", "Liste de travail : tous les OF qu'il reste à faire au poste", "liste" in coches)
            valeurs = self.postes + ([TOUS_LES_POSTES] if len(self.postes) > 1 else [])
            self.menu_poste = self._menu(ligne, valeurs, TOUS_LES_POSTES if tous_les_postes else valeurs[0])

        self.lbl_message = texte(cadre, "", couleur=T.ERREUR_TEXTE, wraplength=600, justify="left")
        self.lbl_message.pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_M, 0))
        pied = ctk.CTkFrame(cadre, fg_color="transparent")
        pied.pack(fill=tk.X, padx=T.ESPACE_XL, pady=T.ESPACE_L)
        bouton(pied, "Aperçu / imprimer", self.apercu, style="primaire", width=190).pack(side=tk.RIGHT)
        bouton(pied, "Enregistrer en PDF…", self.enregistrer, style="secondaire", width=190).pack(side=tk.RIGHT, padx=T.ESPACE_S)
        bouton(pied, "Fermer", self.destroy, style="fantome", width=100).pack(side=tk.LEFT)

        self.bind("<Escape>", lambda e: self.destroy())
        sections = bool(cde) + bool(self.ids_of) + bool(self.postes)
        centrer_fenetre(self, 840, 250 + 50 * len(self.vars) + 40 * sections)
        capturer_focus(self)

    # --- Construction ---

    def _section(self, parent, libelle):
        titre(parent, libelle, taille=T.TAILLE_CORPS, couleur=T.TEXTE_ATTENUE).pack(
            fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_S, T.ESPACE_XS))

    def _case(self, parent, cle, libelle, coche):
        ligne = ctk.CTkFrame(parent, fg_color="transparent")
        ligne.pack(fill=tk.X, padx=T.ESPACE_XL, pady=T.ESPACE_XS)
        self.vars[cle] = tk.BooleanVar(value=bool(coche))
        ctk.CTkCheckBox(ligne, text=libelle, variable=self.vars[cle], font=T.police(T.TAILLE_CORPS, gras=True),
                        text_color=T.TEXTE, fg_color=T.PRIMAIRE, hover_color=T.PRIMAIRE_SURVOL,
                        border_color=T.BORDURE_SURVOL).pack(side=tk.LEFT)
        return ligne

    def _menu(self, parent, valeurs, valeur):
        menu = ctk.CTkOptionMenu(parent, values=valeurs, height=32, width=190, corner_radius=T.RAYON_CONTROLE,
                                 font=T.police(T.TAILLE_CORPS), dropdown_font=T.police(T.TAILLE_CORPS),
                                 fg_color=T.SURFACE, button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL,
                                 text_color=T.TEXTE)
        menu.set(valeur)
        menu.pack(side=tk.RIGHT)
        return menu

    # --- Choix et production ---

    def coche(self, cle):
        return cle in self.vars and self.vars[cle].get()

    def choix(self):
        """Ce qui est coché (documents.Choix)."""
        try:
            debut = int(self.debut_etiquettes.get().strip() or 1) if self.ids_of else 1
        except ValueError:
            debut = 1
        postes = ()
        if self.coche("liste"):
            poste = self.menu_poste.get()
            postes = tuple(self.postes) if poste == TOUS_LES_POSTES else (poste,)
        return documents.Choix(
            cde=self.cde, ids_of=self.ids_of, fiche_commande=self.coche("commande"),
            fiches_suiveuses=self.coche("suiveuses"), fiches_etape=self.coche("etape"),
            etape=self._etapes.get(self.menu_etape.get()) if self.ids_of else None,
            etiquettes=self.coche("etiquettes"),
            par_piece=bool(self.ids_of) and self.mode_etiquettes.get() == PAR_PIECE, debut=max(1, debut), postes=postes)

    def documents(self):
        """Documents à imprimer, sur l'état de l'atelier relu à l'instant (scans des autres postes compris)."""
        etat = self.app.recharger_etat()
        return documents.assembler(self.choix(), etat, self.app.sage, *referentiel(self.app.depot))

    def _base(self):
        if self.cde:
            return self.cde
        if self.ids_of:
            return self.ids_of[0] if len(self.ids_of) == 1 else f"{len(self.ids_of)}_OF"
        return "Liste_de_travail"

    def _preparer(self):
        if self.choix().vide:
            self.lbl_message.configure(text="Cochez au moins un document.")
            return None
        docs = self.documents()
        if not docs:
            self.lbl_message.configure(text="Rien à imprimer : ces OF sont annulés ou leur commande est clôturée.")
            return None
        return docs

    def apercu(self):
        docs = self._preparer()
        if docs is None:
            return
        try:
            self.resultat = generer_apercu(docs, self._base(), self.title())
        except Exception as exc:   # dossier protégé, lecteur PDF absent…
            journal().exception("Impression")
            self.lbl_message.configure(text=f"Impression impossible : {exc}")
            return
        self.destroy()

    def enregistrer(self):
        docs = self._preparer()
        if docs is None:
            return
        chemin = filedialog.asksaveasfilename(parent=self, title="Enregistrer en PDF", defaultextension=".pdf",
                                              initialfile=nom_fichier(self._base()),
                                              filetypes=[("Document PDF", "*.pdf")])
        if not chemin:
            return
        try:
            self.resultat = pdf.generer(chemin, docs, titre=self.title())
        except Exception as exc:   # fichier ouvert dans un autre logiciel…
            journal().exception("Enregistrement PDF")
            self.lbl_message.configure(text=f"Enregistrement impossible : {exc}")
            return
        journal().info("PDF enregistré : %s", chemin)
        self.destroy()
