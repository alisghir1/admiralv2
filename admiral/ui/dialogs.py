"""Fenêtres de dialogue : choix du poste, création d'OF."""
import sqlite3
import sys
import tkinter as tk
from datetime import date

import customtkinter as ctk

from .. import theme as T
from ..config import CODE_BUREAU_ETUDE_DEFAUT, POSTE_BUREAU_ETUDE, POSTE_CHEF_ATELIER
from ..db.depot import LigneDejaAffectee
from ..domain import sage as sage_mod, tri
from ..domain.synthese import format_date
from .composants import bouton, carte, champ, tableau, texte, titre
from .widgets import FenetreDialogue, capturer_focus, centrer_fenetre, maj_tags_selection

HAUTEUR_LISTE_PRODUITS = 4   # lignes visibles au minimum dans la liste des produits (elle prend la place libre)
POSTE_LIBRE = "Libre (n'importe quel poste)"


class ConfigDialog(FenetreDialogue):
    """Choix du poste de ce PC : « Bureau d'étude » (code commun), « Chef d'atelier » (code personnel du chef)
    ou un poste machine. postes : libellés "CODE - Désignation" des machines.
    result = libellé choisi ou None ; chef = nom du chef reconnu par son code (profil Chef d'atelier)."""

    def __init__(self, parent, postes, is_cancellable=False, actuel=None, code_bureau_etude=None, chef_par_code=None):
        super().__init__(parent)
        self.is_cancellable = is_cancellable
        self.actuel = actuel
        self.code_bureau_etude = code_bureau_etude or CODE_BUREAU_ETUDE_DEFAUT
        self.chef_par_code = chef_par_code or (lambda code: None)
        self.chef = None
        self.title("Poste de travail")
        centrer_fenetre(self, 600, 400)
        self.configure(fg_color=T.FOND)
        self.poste_choisi = tk.StringVar()
        self.result = None

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, "Quel est le poste de ce PC ?", taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_XL, T.ESPACE_XS))
        texte(cadre, "Machine : écran Atelier. Chef d'atelier : pilotage et validation. Bureau d'étude : OF et référentiel.").pack(
            fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_L))

        postes_list = [POSTE_BUREAU_ETUDE, POSTE_CHEF_ATELIER] + list(postes)
        self.cb = ctk.CTkComboBox(cadre, variable=self.poste_choisi, values=postes_list, state="readonly",
                                  command=lambda _: self._maj_code(),
                                  font=T.police(T.TAILLE_SOUS_TITRE, gras=True), dropdown_font=T.police(T.TAILLE_CORPS),
                                  fg_color=T.SURFACE, border_color=T.BORDURE, text_color=T.TEXTE,
                                  button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL,
                                  height=T.HAUTEUR_BOUTON_ATELIER, corner_radius=T.RAYON_CONTROLE)
        self.cb.pack(fill=tk.X, padx=T.ESPACE_XL)
        # Par défaut : le poste actuel, sinon la première machine (un PC d'atelier est le cas le plus courant)
        self.cb.set(actuel if actuel in postes_list else postes_list[2 if len(postes_list) > 2 else 0])

        # Code du Bureau d'étude, affiché seulement quand on choisit ce mode
        self.cadre_code = ctk.CTkFrame(cadre, fg_color="transparent")
        self.lbl_code = texte(self.cadre_code, "Code d'accès du Bureau d'étude", gras=True)
        self.lbl_code.pack(fill=tk.X, pady=(T.ESPACE_M, T.ESPACE_XS))
        self.code_entry = champ(self.cadre_code, "Code")
        self.code_entry.configure(show="•")
        self.code_entry.pack(fill=tk.X)
        self.lbl_erreur = ctk.CTkLabel(cadre, text="", font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.ERREUR_TEXTE, anchor="w")

        boutons = ctk.CTkFrame(cadre, fg_color="transparent")
        boutons.pack(fill=tk.X, side=tk.BOTTOM, padx=T.ESPACE_XL, pady=T.ESPACE_XL)
        bouton(boutons, "Valider", self.on_validate, style="primaire", width=140).pack(side=tk.RIGHT)
        if self.is_cancellable:
            bouton(boutons, "Annuler", self.on_close, style="secondaire", width=120).pack(side=tk.RIGHT, padx=T.ESPACE_S)
        self.lbl_erreur.pack(side=tk.BOTTOM, fill=tk.X, padx=T.ESPACE_XL)
        self._maj_code()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Return>", lambda e: self.on_validate())
        self.bind("<Escape>", lambda e: self.on_close() if self.is_cancellable else None)
        capturer_focus(self)

    def _code_requis(self):
        # Pas de code pour rester en Bureau d'étude, seulement pour y entrer. Le chef donne toujours son code :
        # c'est lui qui signe les validations faites depuis ce PC.
        choix = self.poste_choisi.get()
        return (choix == POSTE_BUREAU_ETUDE and self.actuel != POSTE_BUREAU_ETUDE) or choix == POSTE_CHEF_ATELIER

    def _maj_code(self):
        self.lbl_erreur.configure(text="")
        self.lbl_code.configure(text="Votre code personnel de chef d'atelier" if self.poste_choisi.get() == POSTE_CHEF_ATELIER
                                else "Code d'accès du Bureau d'étude")
        if self._code_requis():
            self.cadre_code.pack(fill=tk.X, padx=T.ESPACE_XL)
            self.code_entry.focus_set()
        else:
            self.cadre_code.pack_forget()

    def on_validate(self):
        if not self.poste_choisi.get():
            return
        code = self.code_entry.get().strip()
        if self.poste_choisi.get() == POSTE_CHEF_ATELIER:
            self.chef = self.chef_par_code(code)
            correct = self.chef is not None
        else:
            correct = not self._code_requis() or code == self.code_bureau_etude
        if not correct:
            self.lbl_erreur.configure(text="Code incorrect.")
            self.code_entry.delete(0, tk.END)
            self.code_entry.focus_set()
            return
        self.result = self.poste_choisi.get()
        self.destroy()

    def on_close(self):
        self.destroy()
        if not self.is_cancellable:
            sys.exit(0)


def _entier_positif(valeur):
    """Dimension saisie ("1200", "1200,0") -> entier > 0 ; "" -> None ; sinon ValueError."""
    valeur = str(valeur).strip().replace(',', '.')
    if not valeur:
        return None
    nombre = float(valeur)
    if nombre <= 0 or nombre != int(nombre):
        raise ValueError
    return int(nombre)


def resume_quantite_dimensions(qte, longueur, largeur):
    """ "6 pièces · 600 × 560 mm" (quantité et dimensions imposées par les lignes de commande)."""
    pieces = f"{qte} pièce{'s' if int(qte) > 1 else ''}"
    dims = f"{longueur} × {largeur} mm" if longueur and largeur else "dimensions selon les lignes"
    return f"{pieces} · {dims}"


def lire_date(texte, aujourd_hui=None):
    """ "15/10", "15/10/26" ou "15/10/2026" -> "2026-10-15" ; "" -> None ; sinon ValueError.
    Sans année : la prochaine occurrence (le 05/01 saisi en décembre est en janvier suivant),
    sauf une date passée de moins de deux mois (OF déjà en retard)."""
    aujourd_hui = aujourd_hui or date.today()
    texte = texte.strip()
    if not texte:
        return None
    morceaux = texte.replace("-", "/").replace(".", "/").split("/")
    if len(morceaux) == 2:
        jour, mois = (int(m) for m in morceaux)
        resultat = date(aujourd_hui.year, mois, jour)
        if (aujourd_hui - resultat).days > 60:
            resultat = date(aujourd_hui.year + 1, mois, jour)
        return resultat.isoformat()
    if len(morceaux) != 3:
        raise ValueError
    jour, mois, annee = (int(m) for m in morceaux)
    if annee < 100:
        annee += 2000
    return date(annee, mois, jour).isoformat()


def afficher_date(iso):
    """ "2026-10-15" -> "15/10/2026" """
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


class _FormulaireOF(FenetreDialogue):
    """Squelette commun à la création et à la modification d'un OF : en-tête, champs, erreurs, boutons."""

    def __init__(self, parent, titre_fenetre, titre_formulaire, sous_titre, libelle_valider, largeur=1160, hauteur=730):
        super().__init__(parent)
        self.title(titre_fenetre)
        centrer_fenetre(self, largeur, hauteur)
        self.configure(fg_color=T.FOND)
        self.result = None

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, titre_formulaire, taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_L, 0))
        texte(cadre, sous_titre).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_M))

        # Deux colonnes : informations de l'OF à gauche, gamme à droite
        corps = ctk.CTkFrame(cadre, fg_color="transparent")
        corps.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_XL, pady=(0, T.ESPACE_L))
        self.form = ctk.CTkFrame(corps, fg_color="transparent")
        self.form.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.form.columnconfigure(1, weight=1)
        self.colonne_gamme = ctk.CTkFrame(corps, fg_color="transparent", width=420)
        self.colonne_gamme.pack(side=tk.LEFT, fill=tk.BOTH, padx=(T.ESPACE_XL, 0))

        # Boutons en bas de la colonne de droite, à la hauteur de la dernière ligne du formulaire.
        # Posés avant la gamme (côté bas) : ils restent visibles, la gamme prend la place restante.
        pied = ctk.CTkFrame(self.colonne_gamme, fg_color="transparent")
        pied.pack(side=tk.BOTTOM, fill=tk.X, pady=(T.ESPACE_S, 0))
        bouton(pied, libelle_valider, self.save, style="succes", width=170).pack(side=tk.RIGHT)
        bouton(pied, "Annuler", self.destroy, style="secondaire", width=120).pack(side=tk.RIGHT, padx=T.ESPACE_S)
        self.lbl_erreur = ctk.CTkLabel(self.colonne_gamme, text="", font=T.police(T.TAILLE_CORPS, gras=True),
                                       text_color=T.ERREUR_TEXTE, anchor="w", justify="left", wraplength=400)
        self.lbl_erreur.pack(side=tk.BOTTOM, fill=tk.X)

        self.transient(parent)
        self.bind("<Escape>", lambda e: self.destroy())

    def etiquette(self, ligne, libelle):
        label = ctk.CTkLabel(self.form, text=libelle, font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE_ATTENUE,
                             anchor="w")
        label.grid(row=ligne, column=0, sticky="nw", pady=(T.ESPACE_S + 6, 0), padx=(0, T.ESPACE_M))
        return label

    def fixer_depuis_lignes(self, qte, longueur, largeur):
        """OF issu de lignes de commande : la quantité (somme des lignes) et les dimensions (Sage) ne se
        saisissent pas, leurs champs sont retirés."""
        self._quantite_fixe = qte
        self._dimensions_imposees = (longueur or None, largeur or None)
        for widget in (self._lbl_qte, self._ligne_qte, self._lbl_dims, self._ligne_dims):
            widget.grid_remove()

    def liberer_quantite_dimensions(self):
        """Inverse de fixer_depuis_lignes (plus aucune ligne de commande) : quantité et dimensions se saisissent,
        pré-remplies avec les dernières valeurs connues."""
        if self._quantite_fixe is None:
            return
        qte, (longueur, largeur) = self._quantite_fixe, self._dimensions_imposees
        self._quantite_fixe = self._dimensions_imposees = None
        for widget in (self._lbl_qte, self._ligne_qte, self._lbl_dims, self._ligne_dims):
            widget.grid()
        self.qte_entry.delete(0, tk.END)
        self.qte_entry.insert(0, str(qte))
        for entree, valeur in ((self.longueur_entry, longueur), (self.largeur_entry, largeur)):
            entree.delete(0, tk.END)
            if valeur:
                entree.insert(0, str(valeur))

    def champs_communs(self, ligne, design="", qte=1, longueur="", largeur="", observ="",
                       date_besoin=None, urgent=False, aide_qte="pièces"):
        """Désignation, quantité, dimensions, observations, besoin. Retourne la ligne suivante de la grille."""
        self.etiquette(ligne, "Désignation")
        self.design_entry = champ(self.form)
        self.design_entry.grid(row=ligne, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        if design:
            self.design_entry.insert(0, design)

        self._quantite_fixe = None
        self._dimensions_imposees = None
        self._lbl_qte = self.etiquette(ligne + 1, "Quantité")
        ligne_qte = self._ligne_qte = ctk.CTkFrame(self.form, fg_color="transparent")
        ligne_qte.grid(row=ligne + 1, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        self.qte_entry = champ(ligne_qte, largeur=100)
        self.qte_entry.pack(side=tk.LEFT)
        self.qte_entry.insert(0, str(qte))
        texte(ligne_qte, aide_qte).pack(side=tk.LEFT, padx=T.ESPACE_S)

        self._lbl_dims = self.etiquette(ligne + 2, "Dimensions")
        ligne_dims = self._ligne_dims = ctk.CTkFrame(self.form, fg_color="transparent")
        ligne_dims.grid(row=ligne + 2, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        self.longueur_entry = champ(ligne_dims, "Longueur", largeur=110)
        self.longueur_entry.pack(side=tk.LEFT)
        texte(ligne_dims, "×").pack(side=tk.LEFT, padx=T.ESPACE_S)
        self.largeur_entry = champ(ligne_dims, "Largeur", largeur=110)
        self.largeur_entry.pack(side=tk.LEFT)
        texte(ligne_dims, "mm").pack(side=tk.LEFT, padx=T.ESPACE_S)
        for entree, valeur in ((self.longueur_entry, longueur), (self.largeur_entry, largeur)):
            if valeur is not None and str(valeur).strip():
                entree.insert(0, str(valeur).strip())

        self.etiquette(ligne + 3, "Observations")
        self.obs_entry = champ(self.form, "Facultatif")
        self.obs_entry.grid(row=ligne + 3, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        if observ:
            self.obs_entry.insert(0, observ)

        self.etiquette(ligne + 4, "Besoin")
        ligne_besoin = ctk.CTkFrame(self.form, fg_color="transparent")
        ligne_besoin.grid(row=ligne + 4, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        self.besoin_entry = champ(ligne_besoin, "JJ/MM/AAAA (facultatif)", largeur=200)
        self.besoin_entry.pack(side=tk.LEFT)
        if date_besoin:
            self.besoin_entry.insert(0, afficher_date(date_besoin))
        self.urgent_var = tk.BooleanVar(value=bool(urgent))
        ctk.CTkCheckBox(ligne_besoin, text="Urgent", variable=self.urgent_var,
                        font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE, fg_color=T.ERREUR,
                        hover_color=T.ERREUR_SURVOL, border_color=T.BORDURE_SURVOL).pack(side=tk.LEFT, padx=T.ESPACE_L)
        # Rappel du délai de la commande dans Sage, pour fixer la date de besoin en connaissance de cause
        self.lbl_aide_besoin = texte(ligne_besoin, "")
        self.lbl_aide_besoin.pack(side=tk.LEFT)
        return ligne + 5

    def maj_aide_besoin(self, infos):
        """infos : InfosCommande de la commande de l'OF (ou None) ; « Délai Sage : 10/11 » à côté du besoin."""
        delai = infos.delai if infos else ""
        depasse = bool(delai) and delai < date.today().isoformat()
        self.lbl_aide_besoin.configure(
            text=f"Délai Sage{' dépassé' if depasse else ''} : {format_date(delai)}" if delai else "",
            text_color=T.ERREUR_TEXTE if depasse else T.TEXTE_ATTENUE)

    def erreur(self, message, champ_fautif=None):
        self.lbl_erreur.configure(text=message)
        for entree in (self.qte_entry, self.longueur_entry, self.largeur_entry, self.besoin_entry):
            entree.configure(border_color=T.ERREUR if entree is champ_fautif else T.BORDURE)
        if champ_fautif is not None:
            champ_fautif.focus_set()

    def lire_champs_communs(self, qte_min=1):
        """Valeurs saisies, ou None après avoir affiché l'erreur."""
        if self._quantite_fixe is not None:   # somme des lignes de commande
            qte = self._quantite_fixe
        else:
            try:
                qte = int(self.qte_entry.get().strip())
                if qte < max(qte_min, 1):
                    raise ValueError
            except ValueError:
                minimum = f"au moins {qte_min} (pièces déjà scannées)" if qte_min > 1 else "supérieur à 0"
                self.erreur(f"La quantité doit être un nombre entier {minimum}.", self.qte_entry)
                return None
        valeurs = {"qte": qte}
        imposees = self._dimensions_imposees
        for nom, entree in (("longueur", self.longueur_entry), ("largeur", self.largeur_entry)):
            if imposees is not None:   # dimensions de la commande Sage : jamais celles du champ
                valeurs[nom] = imposees[0 if nom == "longueur" else 1]
                continue
            try:
                valeurs[nom] = _entier_positif(entree.get())
            except ValueError:
                self.erreur(f"La {nom} doit être un nombre entier de millimètres.", entree)
                return None
        try:
            valeurs["date_besoin"] = lire_date(self.besoin_entry.get())
        except ValueError:
            self.erreur("La date de besoin doit être au format JJ/MM/AAAA.", self.besoin_entry)
            return None
        valeurs.update(design=self.design_entry.get().strip(), observ=self.obs_entry.get().strip(),
                       priorite=1 if self.urgent_var.get() else 0)
        return valeurs

    def zone_gamme(self, aide):
        ctk.CTkLabel(self.colonne_gamme, text="Gamme", font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE_ATTENUE,
                     anchor="w").pack(fill=tk.X, pady=(T.ESPACE_S + 6, 0))
        texte(self.colonne_gamme, aide, taille=T.TAILLE_LEGENDE, wraplength=400, justify="left").pack(fill=tk.X)
        self.gamme_frame = ctk.CTkScrollableFrame(self.colonne_gamme, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE,
                                                  width=400, height=200)
        self.gamme_frame.pack(fill=tk.BOTH, expand=True, pady=(T.ESPACE_XS, 0))

    def combo_poste(self, parent, postes, valeur):
        var_poste = tk.StringVar(value=valeur)
        combo = ctk.CTkComboBox(parent, variable=var_poste, values=postes, state="readonly", width=200, height=36,
                                corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS),
                                fg_color=T.CARTE, border_color=T.BORDURE, text_color=T.TEXTE,
                                button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL)
        return var_poste, combo

    @staticmethod
    def poste_choisi(var_poste):
        valeur = var_poste.get()
        return None if valeur == POSTE_LIBRE else valeur.split(" - ")[0]

    def save(self):
        raise NotImplementedError


class AddOfDialog(_FormulaireOF):
    """Création d'un OF pour une commande. result = ID de l'OF créé, ou None si annulé."""

    def __init__(self, parent, depot, cde, client="", default_qte=1, default_design="", default_obs="",
                 lignes_sage="", longueur="", largeur="", dimensions_sage=False, chants="", infos=None):
        """dimensions_sage : OF issu de lignes de commande, quantité (somme des lignes) et dimensions (Sage)
        imposées : leurs champs ne sont pas proposés, le sous-titre les rappelle, avec leurs chants communs.
        infos : InfosCommande de la commande (délai rappelé à côté de la date de besoin)."""
        sous_titre = f"Commande {cde}" + (f" · {client}" if client else "")
        if lignes_sage:
            sous_titre += f" · lignes {', '.join(l.rsplit('-', 1)[-1] for l in lignes_sage.split(','))}"
        if dimensions_sage:
            sous_titre += f" · {resume_quantite_dimensions(default_qte, longueur, largeur)}"
        if chants:
            sous_titre += f" · chants {chants}"
        super().__init__(parent, f"Nouvel OF · commande {cde}", "Nouvel ordre de fabrication", sous_titre, "Créer l'OF")
        self.depot = depot
        self.cde = cde
        self.lignes_sage = lignes_sage
        self.gamme_vars = []

        # Produit : filtre + liste
        self.etiquette(0, "Produit")
        bloc_produit = ctk.CTkFrame(self.form, fg_color="transparent")
        bloc_produit.grid(row=0, column=1, sticky="nsew", pady=(T.ESPACE_S, 0))
        self.form.rowconfigure(0, weight=1)   # la liste des produits occupe la hauteur disponible
        self.filtre_produit = champ(bloc_produit, "Filtrer par référence ou désignation")
        self.filtre_produit.pack(fill=tk.X)
        self.filtre_produit.bind("<KeyRelease>", lambda e: self._remplir_produits())
        cadre_liste, self.liste_produits = tableau(bloc_produit, [("produit", "Produit", 400, "w")], hauteur=HAUTEUR_LISTE_PRODUITS)
        cadre_liste.pack(fill=tk.BOTH, expand=True, pady=(T.ESPACE_XS, 0))
        self.liste_produits.bind("<<TreeviewSelect>>", self.on_prod_select)
        self.produits_map = {ref: des for ref, des in self.depot.lister_produits()}
        self._remplir_produits()

        self.champs_communs(1, design=default_design, qte=default_qte, longueur=longueur, largeur=largeur, observ=default_obs)
        # Désignation proposée = nom du produit choisi ; elle suit le produit tant qu'on ne l'a pas retapée
        self._design_auto = self.design_entry.get()
        self.maj_aide_besoin(infos)
        if dimensions_sage:
            self.fixer_depuis_lignes(default_qte, longueur, largeur)
        self.zone_gamme("Décochez les opérations à ne pas faire. Choisissez un poste ou laissez « Libre ».")
        self._message_gamme("Choisissez d'abord un produit.")

        capturer_focus(self)
        self.filtre_produit.focus_set()

    # --- Produit et gamme ---

    def _remplir_produits(self):
        filtre = self.filtre_produit.get().strip().lower()
        selection = self.liste_produits.selection()
        for item in self.liste_produits.get_children():
            self.liste_produits.delete(item)
        for ref, des in self.produits_map.items():
            libelle = f"{ref} · {des}"
            if not filtre or filtre in libelle.lower():
                self.liste_produits.insert("", "end", iid=ref, values=(libelle,))
        if selection and self.liste_produits.exists(selection[0]):
            self.liste_produits.selection_set(selection[0])
        maj_tags_selection(self.liste_produits)

    def produit_choisi(self):
        selection = self.liste_produits.selection()
        return selection[0] if selection else None

    def choisir_produit(self, ref):
        self.liste_produits.selection_set(ref)
        self.on_prod_select()

    def _message_gamme(self, message):
        for widget in self.gamme_frame.winfo_children():
            widget.destroy()
        texte(self.gamme_frame, message, anchor="center").pack(fill=tk.X, pady=T.ESPACE_L)

    def on_prod_select(self, event=None):
        maj_tags_selection(self.liste_produits)
        ref = self.produit_choisi()
        if ref is None:
            return
        if self.design_entry.get().strip() in ("", self._design_auto.strip()):
            self._design_auto = self.produits_map.get(ref, "")
            self.design_entry.delete(0, tk.END)
            self.design_entry.insert(0, self._design_auto)

        for widget in self.gamme_frame.winfo_children():
            widget.destroy()
        self.gamme_vars = []
        gammes = self.depot.gamme_produit(ref)
        if not gammes:
            self._message_gamme("Aucune gamme définie pour ce produit (onglet Administration).")
            return
            
        for numero, (_, code_op, libel_op) in enumerate(gammes, start=1):
            libel_op = libel_op or f"{code_op} (sans libellé)"
            rangee = ctk.CTkFrame(self.gamme_frame, fg_color="transparent")
            rangee.pack(fill=tk.X, padx=T.ESPACE_S, pady=T.ESPACE_XS)
            ctk.CTkLabel(rangee, text=str(numero), width=24, font=T.police_chiffres(T.TAILLE_CORPS), text_color=T.TEXTE_ATTENUE).pack(side=tk.LEFT)

            # Gamme standard cochée par défaut : on décoche les exceptions
            var_check = tk.BooleanVar(value=True)
            postes = [POSTE_LIBRE] + [f"{c} - {d}" for c, d in self.depot.postes_pour_operation(code_op)]
            var_poste, cb_poste = self.combo_poste(rangee, postes, postes[0])
            def basculer(v=var_check, c=cb_poste):
                c.configure(state="readonly" if v.get() else "disabled")
            ctk.CTkCheckBox(rangee, text=libel_op, variable=var_check, command=basculer, width=150,
                            font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE,
                            fg_color=T.PRIMAIRE, hover_color=T.PRIMAIRE_SURVOL, border_color=T.BORDURE_SURVOL).pack(side=tk.LEFT)
            cb_poste.pack(side=tk.RIGHT)
            self.gamme_vars.append({'code_op': code_op, 'var_check': var_check, 'var_poste': var_poste, 'libel': libel_op})

    def save(self):
        ref_prod = self.produit_choisi()
        if not ref_prod:
            self.erreur("Choisissez un produit dans la liste.")
            return
        valeurs = self.lire_champs_communs()
        if valeurs is None:
            return
        # Étapes cochées, dans l'ordre de la gamme, avec leur poste assigné (None = libre)
        etapes = [(step['code_op'], self.poste_choisi(step['var_poste'])) for step in self.gamme_vars if step['var_check'].get()]
        if not etapes:
            self.erreur("Gardez au moins une opération dans la gamme.")
            return
        try:
            self.result = self.depot.creer_of(self.cde, ref_prod, valeurs["design"], valeurs["observ"], valeurs["qte"],
                                              self.lignes_sage, etapes, valeurs["longueur"], valeurs["largeur"],
                                              "", valeurs["date_besoin"], valeurs["priorite"])
        except LigneDejaAffectee as exc:   # un autre poste a pris la ligne pendant la saisie
            self.erreur(str(exc))
            return
        except sqlite3.IntegrityError:     # numéro d'OF pris au même instant par un autre PC
            self.erreur("Un autre poste vient de créer un OF : cliquez à nouveau sur « Créer l'OF ».")
            return
        self.destroy()


class ModifierOfDialog(_FormulaireOF):
    """Correction complète d'un OF par le Bureau d'étude : commande, produit, lignes de commande, gamme
    (ajout, retrait, ordre, postes) et tous les champs. result = ID de l'OF si enregistré, sinon None.

    Ce qui a déjà été fabriqué reste protégé : une opération ou une ligne qui a des scans ne se retire pas,
    un OF scanné ne change pas de commande, la quantité ne descend pas sous les pièces déjà faites."""

    def __init__(self, parent, depot, of, deja_scannees=0, sage=None, cloturees=()):
        """sage : données Sage (commandes et lignes) ; sans elles, commande et lignes restent celles de l'OF."""
        super().__init__(parent, f"Modifier {of.id}", f"Modifier {of.id}",
                         "Tout peut être corrigé. Ce qui a déjà été scanné à l'atelier reste protégé.",
                         "Enregistrer", hauteur=780)
        self.depot = depot
        self.of = of
        self.sage = sage
        self.cloturees = set(cloturees)
        self.scans_op, self.scans_ligne = depot.scans_valides_of(of.id)
        self.deja_scannees = max([deja_scannees, *self.scans_op.values()])
        self.libelles = depot.libelles_operations()
        self.produits = {ref: des for ref, des in depot.lister_produits()}
        self.resume = ""

        # --- Commande ---
        self.etiquette(0, "Commande")
        ligne_cde = ctk.CTkFrame(self.form, fg_color="transparent")
        ligne_cde.grid(row=0, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        commandes = [of.cde]
        if sage is not None:
            commandes = sorted({c for c in sage.entetes if c not in self.cloturees} | {of.cde}, key=tri.cle_naturelle)
        self.var_cde = tk.StringVar(value=of.cde)
        self.combo_cde = ctk.CTkComboBox(ligne_cde, variable=self.var_cde, values=commandes, state="readonly", width=200,
                                         height=36, command=lambda _: self._changer_commande(),
                                         corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS),
                                         fg_color=T.SURFACE, border_color=T.BORDURE, text_color=T.TEXTE,
                                         button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL)
        self.combo_cde.pack(side=tk.LEFT)
        self.lbl_client = texte(ligne_cde, "")
        self.lbl_client.pack(side=tk.LEFT, padx=T.ESPACE_M)
        if sum(self.scans_op.values()) or of.annule or sage is None:
            self.combo_cde.configure(state="disabled")
            raison = ("déjà scanné : la commande ne change plus" if sum(self.scans_op.values())
                      else "OF annulé : réactivez-le pour changer de commande" if of.annule else "")
            if raison:
                texte(ligne_cde, raison, taille=T.TAILLE_LEGENDE).pack(side=tk.LEFT)

        # --- Produit ---
        self.etiquette(1, "Produit")
        self._libelles_produits = {f"{ref} · {des}": ref for ref, des in self.produits.items()}
        actuel = next((l for l, r in self._libelles_produits.items() if r == of.prod), of.prod)
        if actuel not in self._libelles_produits:   # produit supprimé depuis : on le garde tel quel
            self._libelles_produits[actuel] = of.prod
        self.var_prod = tk.StringVar(value=actuel)
        ctk.CTkComboBox(self.form, variable=self.var_prod, values=sorted(self._libelles_produits, key=tri.cle_naturelle),
                        state="readonly", height=36, command=lambda _: self._changer_produit(),
                        corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS), fg_color=T.SURFACE,
                        border_color=T.BORDURE, text_color=T.TEXTE, button_color=T.BORDURE,
                        button_hover_color=T.BORDURE_SURVOL).grid(row=1, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        self._prod_courant = of.prod

        # --- Lignes de commande ---
        self.etiquette(2, "Lignes")
        bloc_lignes = ctk.CTkFrame(self.form, fg_color="transparent")
        bloc_lignes.grid(row=2, column=1, sticky="nsew", pady=(T.ESPACE_S, 0))
        self.form.rowconfigure(2, weight=1)
        self.cadre_lignes = ctk.CTkScrollableFrame(bloc_lignes, fg_color=T.SURFACE, corner_radius=T.RAYON_CONTROLE, height=130)
        self.cadre_lignes.pack(fill=tk.BOTH, expand=True)
        self.lbl_total_lignes = texte(bloc_lignes, "", taille=T.TAILLE_LEGENDE)
        self.lbl_total_lignes.pack(fill=tk.X)
        # Clés complètes des lignes de l'OF -> clé telle que stockée (les scans y font référence)
        self.lignes_of = {sage_mod.cle_complete(of.cde, j): j.strip() for j in (of.lignes_sage or "").split(",") if j.strip()}
        self.vars_lignes = {}

        aide = f"pièces (au moins {self.deja_scannees}, déjà scannées)" if self.deja_scannees else "pièces"
        self.champs_communs(3, design=of.design, qte=of.qte, longueur=of.longueur, largeur=of.largeur,
                            observ=of.observ, date_besoin=of.date_besoin,
                            urgent=of.urgent, aide_qte=aide)
        self._afficher_lignes(of.cde, cochees=set(self.lignes_of))

        # --- Gamme : outils sous la liste (posés avant elle pour rester visibles) ---
        outils = ctk.CTkFrame(self.colonne_gamme, fg_color="transparent")
        outils.pack(side=tk.BOTTOM, fill=tk.X, pady=(T.ESPACE_S, 0))
        self.var_ajout = tk.StringVar(value="")
        self.combo_ajout = ctk.CTkComboBox(outils, variable=self.var_ajout, values=[], state="readonly", width=200, height=32,
                                           corner_radius=T.RAYON_CONTROLE, font=T.police(T.TAILLE_CORPS),
                                           fg_color=T.SURFACE, border_color=T.BORDURE, text_color=T.TEXTE,
                                           button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL)
        self.combo_ajout.pack(side=tk.LEFT)
        bouton(outils, "Ajouter", self._ajouter_operation, style="secondaire", width=90, height=32).pack(side=tk.LEFT, padx=T.ESPACE_S)
        bouton(outils, "Gamme du produit", self._gamme_du_produit, style="fantome", height=32).pack(side=tk.RIGHT)
        self.zone_gamme("Ajoutez, retirez, déplacez (▲ ▼) les opérations et choisissez leur poste. "
                        "Une opération déjà scannée ne peut pas être retirée.")
        self.etapes = [self._etape(code, poste) for _, code, poste in depot.gamme_of(of.id)]
        self._gamme_initiale = [e["code"] for e in self.etapes]
        self._dessiner_gamme()

        capturer_focus(self)
        self.design_entry.focus_set()

    # --- Commande et lignes ---

    def _afficher_lignes(self, cde, cochees):
        for widget in self.cadre_lignes.winfo_children():
            widget.destroy()
        self.vars_lignes = {}
        self.lbl_client.configure(text=self.sage.client(cde, "") if self.sage is not None else "")
        self.maj_aide_besoin(self.sage.infos_commande(cde) if self.sage is not None else None)
        lignes = sorted(self.sage.lignes_commande(cde), key=lambda x: sage_mod.numero_ligne(x[1])) if self.sage else []
        lignes = [(cle, l) for cle, l in lignes if sage_mod.fabricable(l)]
        affectees = self.depot.lignes_affectees(cde)
        for cle, ligne in lignes:
            ailleurs = affectees.get(cle) if affectees.get(cle) != self.of.id else None
            scannees = self.scans_ligne.get(self.lignes_of.get(cle), 0) if cde == self.of.cde else 0
            unite = (ligne.get("EU_Enumere") or "U").upper()
            chants = sage_mod.chants(ligne)
            details = [f"Ligne {ligne.get('DL_Ligne', '')}", ligne.get("AR_Ref", ""),
                       f"{sage_mod.lire_qte(ligne.get('DL_Qte', '1'))} p." if unite == "U" else sage_mod.quantite(ligne),
                       sage_mod.dimensions(ligne), f"chants {chants}" if chants else ""]
            libelle = " · ".join(d for d in details if d)
            if ailleurs:
                libelle += f"  — dans {ailleurs}"
            elif scannees:
                libelle += f"  — {scannees} scannée(s)"
            var = tk.BooleanVar(value=cle in cochees and not ailleurs)
            case = ctk.CTkCheckBox(self.cadre_lignes, text=libelle, variable=var, command=self._maj_selon_lignes,
                                   font=T.police(T.TAILLE_CORPS), text_color=T.TEXTE, fg_color=T.PRIMAIRE,
                                   hover_color=T.PRIMAIRE_SURVOL, border_color=T.BORDURE_SURVOL)
            case.pack(fill=tk.X, padx=T.ESPACE_S, pady=2)
            if ailleurs or scannees or self.of.annule:
                case.configure(state="disabled")
            self.vars_lignes[cle] = var
        if not lignes:
            texte(self.cadre_lignes, "Aucune ligne à fabriquer dans cette commande." if self.sage is not None
                  else "Lignes inchangées.", anchor="center").pack(fill=tk.X, pady=T.ESPACE_M)
        self._maj_selon_lignes()

    def lignes_choisies(self):
        """Clés complètes des lignes de l'OF après correction (les lignes de l'OF absentes de la liste,
        sorties de Sage par exemple, sont conservées tant que la commande ne change pas)."""
        cles = [cle for cle, var in self.vars_lignes.items() if var.get()]
        if self.var_cde.get() == self.of.cde:
            cles += [c for c in self.lignes_of if c not in self.vars_lignes]
        return cles

    def _maj_selon_lignes(self):
        """Quantité et dimensions suivent les lignes cochées ; sans ligne, elles se saisissent."""
        cles = self.lignes_choisies()
        if self.sage is None or not cles:
            if self.sage is None and cles:   # pas de données Sage : on garde l'état de l'OF
                self.fixer_depuis_lignes(self.of.qte, self.of.longueur, self.of.largeur)
                return
            self.liberer_quantite_dimensions()
            self.lbl_total_lignes.configure(text="Aucune ligne : quantité et dimensions se saisissent ci-dessous.")
            return
        if set(cles) == set(self.lignes_of) and self.of.lignes_sage:   # lignes inchangées : l'OF garde ses valeurs
            qte, longueur, largeur = self.of.qte, self.of.longueur, self.of.largeur
        else:
            lignes = [self.sage.lignes.get(c, {}) for c in cles]
            qte = sum(sage_mod.lire_qte(l.get("DL_Qte", "1"), 0) for l in lignes) or 1
            longueur, largeur = sage_mod.dimensions_communes(lignes)
        self.fixer_depuis_lignes(qte, longueur, largeur)
        chants = sage_mod.chants_communs([self.sage.lignes.get(c, {}) for c in cles])
        self.lbl_total_lignes.configure(text=f"Total : {resume_quantite_dimensions(qte, longueur, largeur)}"
                                             + (f" · chants {chants}" if chants else ""))

    def _changer_commande(self):
        cde = self.var_cde.get()
        self._afficher_lignes(cde, cochees=set(self.lignes_of) if cde == self.of.cde else set())

    # --- Produit et gamme ---

    def _changer_produit(self):
        ancien, ref = self._prod_courant, self._libelles_produits.get(self.var_prod.get(), self.of.prod)
        if ref == ancien:
            return
        self._prod_courant = ref
        # La désignation suit le produit si elle était celle de l'ancien produit (ou vide)
        if self.design_entry.get().strip() in ("", self.produits.get(ancien, "").strip()):
            self.design_entry.delete(0, tk.END)
            self.design_entry.insert(0, self.produits.get(ref, ""))
        # Mauvais produit à la création : la gamme standard du bon produit est reprise
        if self.depot.gamme_produit(ref):
            self._gamme_du_produit()

    def _etape(self, code, poste):
        postes = [POSTE_LIBRE] + [f"{c} - {d}" for c, d in self.depot.postes_pour_operation(code)]
        valeur = next((p for p in postes if poste and p.split(" - ")[0] == poste), POSTE_LIBRE)
        return {"code": code, "postes": postes, "var_poste": tk.StringVar(value=valeur)}

    def _dessiner_gamme(self):
        for widget in self.gamme_frame.winfo_children():
            widget.destroy()
        for i, etape in enumerate(self.etapes):
            code = etape["code"]
            rangee = ctk.CTkFrame(self.gamme_frame, fg_color="transparent")
            rangee.pack(fill=tk.X, padx=T.ESPACE_XS, pady=T.ESPACE_XS)
            ctk.CTkLabel(rangee, text=str(i + 1), width=20, font=T.police_chiffres(T.TAILLE_CORPS),
                         text_color=T.TEXTE_ATTENUE).pack(side=tk.LEFT)
            scans = self.scans_op.get(code, 0)
            libelle = self.libelles.get(code) or code
            ctk.CTkLabel(rangee, text=libelle + (f"\n{scans} scannée(s)" if scans else ""), justify="left", anchor="w",
                         font=T.police(T.TAILLE_CORPS, gras=True), text_color=T.TEXTE).pack(side=tk.LEFT, padx=T.ESPACE_XS)
            for symbole, action, actif in (("✕", lambda i=i: self._retirer_operation(i), not scans),
                                           ("▼", lambda i=i: self._deplacer(i, 1), i < len(self.etapes) - 1),
                                           ("▲", lambda i=i: self._deplacer(i, -1), i > 0)):
                bouton(rangee, symbole, action, style="danger" if symbole == "✕" else "secondaire", width=28, height=28,
                       state="normal" if actif else "disabled").pack(side=tk.RIGHT, padx=1)
            _, combo = self.combo_poste(rangee, etape["postes"], etape["var_poste"].get())
            combo.configure(variable=etape["var_poste"], width=150)
            combo.pack(side=tk.RIGHT, padx=(0, T.ESPACE_XS))
        if not self.etapes:
            texte(self.gamme_frame, "Aucune opération : ajoutez-en au moins une.", anchor="center").pack(fill=tk.X, pady=T.ESPACE_L)
        presentes = {e["code"] for e in self.etapes}
        self._ajoutables = {f"{self.libelles.get(c) or c} ({c})": c for c in self.libelles if c not in presentes}
        self.combo_ajout.configure(values=list(self._ajoutables))
        self.var_ajout.set(next(iter(self._ajoutables), ""))

    def _deplacer(self, i, sens):
        j = i + sens
        if 0 <= j < len(self.etapes):
            self.etapes[i], self.etapes[j] = self.etapes[j], self.etapes[i]
            self._dessiner_gamme()

    def _retirer_operation(self, i):
        if self.scans_op.get(self.etapes[i]["code"]):
            return
        del self.etapes[i]
        self._dessiner_gamme()

    def _ajouter_operation(self):
        code = self._ajoutables.get(self.var_ajout.get())
        if code:
            self.etapes.append(self._etape(code, None))
            self._dessiner_gamme()

    def _gamme_du_produit(self):
        """Remplace la gamme par la gamme standard du produit choisi (postes gardés pour les opérations communes)."""
        ref = self._libelles_produits.get(self.var_prod.get(), self.of.prod)
        standard = [code for _, code, _ in self.depot.gamme_produit(ref)]
        if not standard:
            self.erreur(f"Le produit {ref} n'a pas de gamme standard (onglet Administration).")
            return
        manquantes = [c for c in self.scans_op if c not in standard and self.scans_op[c]]
        if manquantes:
            self.erreur("Gamme du produit non appliquée : "
                        + ", ".join(self.libelles.get(c) or c for c in manquantes)
                        + " a déjà des pièces scannées et n'y figure pas.")
            return
        postes = {e["code"]: self.poste_choisi(e["var_poste"]) for e in self.etapes}
        self.etapes = [self._etape(code, postes.get(code)) for code in dict.fromkeys(standard)]
        self._dessiner_gamme()
        self.lbl_erreur.configure(text="")

    # --- Enregistrement ---

    def save(self):
        valeurs = self.lire_champs_communs(qte_min=self.deja_scannees)
        if valeurs is None:
            return
        cde = self.var_cde.get()
        prod = self._libelles_produits.get(self.var_prod.get(), self.of.prod)
        etapes = [(e["code"], self.poste_choisi(e["var_poste"])) for e in self.etapes]
        if not etapes:
            self.erreur("Gardez au moins une opération dans la gamme.")
            return
        lignes = self.lignes_choisies() if self.sage is not None else list(self.lignes_of)
        try:
            id_of = self.depot.corriger_of(self.of.id, cde, prod, lignes, etapes, valeurs["design"], valeurs["observ"],
                                           valeurs["qte"], valeurs["longueur"], valeurs["largeur"], self.of.epaisseur,
                                           valeurs["date_besoin"], valeurs["priorite"])
        except (ValueError, LigneDejaAffectee) as exc:   # un poste a pu scanner ou prendre une ligne entre-temps
            self.erreur(str(exc))
            return
        changements = []
        if cde != self.of.cde:
            changements.append(f"commande {self.of.cde} → {cde}")
        if id_of != self.of.id:
            changements.append(f"numéro {self.of.id} → {id_of}")
        if prod != self.of.prod:
            changements.append(f"produit {self.of.prod} → {prod}")
        if [c for c, _ in etapes] != self._gamme_initiale:
            changements.append("gamme " + " › ".join(self._gamme_initiale) + " → " + " › ".join(c for c, _ in etapes))
        if set(lignes) != set(self.lignes_of):
            changements.append(f"lignes {len(self.lignes_of)} → {len(lignes)}")
        if valeurs["qte"] != self.of.qte:
            changements.append(f"quantité {self.of.qte} → {valeurs['qte']}")
        self.resume = ", ".join(changements) or "informations"
        self.result = id_of   # nouveau numéro si l'OF a changé de commande
        self.cde = cde
        self.destroy()


class HistoriqueDialog(FenetreDialogue):
    """Historique d'un OF (lecture seule) : scans (Depot.historique_scans()) et validations des chefs d'atelier
    (Depot.historique_validations(id_of)), mêlés du plus récent au plus ancien."""

    def __init__(self, parent, of, lignes, validations=(), libelles=None):
        super().__init__(parent)
        self.title(f"Historique · {of.id}")
        centrer_fenetre(self, 860, 620)
        self.configure(fg_color=T.FOND)
        self.transient(parent)

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, f"Historique · {of.id}", taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_L, 0))
        valides = sum(1 for l in lignes if not l[5])
        annules = len(lignes) - valides
        resume = f"{of.design} · {valides} scan{'s' if valides > 1 else ''} valide{'s' if valides > 1 else ''}"
        if annules:
            resume += f", {annules} annulé{'s' if annules > 1 else ''}"
        actives = sum(1 for v in validations if not v[8])
        if validations:
            resume += f" · {actives} validation{'s' if actives > 1 else ''} chef d'atelier"
        texte(cadre, resume).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_M))

        bouton(cadre, "Fermer", self.destroy, style="secondaire", width=120).pack(side=tk.BOTTOM, anchor="e", padx=T.ESPACE_XL, pady=T.ESPACE_L)
        cadre_tableau, self.tree = tableau(cadre, [
            ("date", "Date et heure", 160, "w"), ("poste", "Poste", 80, "center"), ("operation", "Opération", 140, "w"),
            ("ligne", "Ligne Sage", 140, "w"), ("etat", "État", 260, "w")], hauteur=8)
        cadre_tableau.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_XL)
        evenements = [(horodatage or "", str(id_scan), (_date_heure(horodatage), poste, operation, cle or "—",
                       f"Annulé le {_date_heure(date_annulation)}" if annule else "Valide"), "annule" if annule else "pas_demarre")
                      for id_scan, horodatage, poste, operation, cle, annule, date_annulation in lignes]
        libelles = libelles or {}
        for id_v, quand, _, _, code_op, chef, motif, commentaire, annulee, date_annul, par in validations:
            etape = "OF entier" if code_op is None else libelles.get(code_op) or code_op
            etat = f"Validé par {chef} · {motif}" + (f" · {commentaire}" if commentaire else "")
            if annulee:
                etat = f"Validation annulée le {_date_heure(date_annul)}" + (f" par {par}" if par else "")
            evenements.append((quand or "", f"V{id_v}", (_date_heure(quand), "Chef", etape, "—", etat),
                               "annule" if annulee else "valide"))
        evenements.sort(key=lambda e: e[0], reverse=True)
        for _, iid, valeurs, tag in evenements:
            self.tree.insert("", "end", iid=iid, values=valeurs, tags=(tag,))
        if not lignes and not validations:
            self.tree.insert("", "end", values=("", "", "Aucun scan pour cet OF", "", ""), tags=("annule",))
        self.bind("<Escape>", lambda e: self.destroy())
        capturer_focus(self)


def _date_heure(valeur):
    """ "2026-10-12 14:03:55" -> "12/10/2026 14:03" """
    if not valeur:
        return ""
    jour, heure = str(valeur).split(" ") if " " in str(valeur) else (str(valeur), "")
    return f"{afficher_date(jour)} {heure[:5]}".strip()
