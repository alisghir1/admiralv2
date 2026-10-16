"""Fenêtres de dialogue : choix du poste, création d'OF."""
import sqlite3
import sys
import tkinter as tk
from datetime import date

import customtkinter as ctk

from .. import theme as T
from ..config import CODE_BUREAU_ETUDE_DEFAUT, POSTE_BUREAU_ETUDE
from ..db.depot import LigneDejaAffectee
from .composants import bouton, carte, champ, tableau, texte, titre
from .widgets import FenetreDialogue, capturer_focus, centrer_fenetre, maj_tags_selection

HAUTEUR_LISTE_PRODUITS = 4   # lignes visibles au minimum dans la liste des produits (elle prend la place libre)
POSTE_LIBRE = "Libre (n'importe quel poste)"


class ConfigDialog(FenetreDialogue):
    """Choix du poste de ce PC : « Bureau d'étude » (protégé par un code) ou un poste machine.
    postes : libellés "CODE - Désignation" des machines. result = libellé choisi ou None."""

    def __init__(self, parent, postes, is_cancellable=False, actuel=None, code_bureau_etude=None):
        super().__init__(parent)
        self.is_cancellable = is_cancellable
        self.actuel = actuel
        self.code_bureau_etude = code_bureau_etude or CODE_BUREAU_ETUDE_DEFAUT
        self.title("Poste de travail")
        centrer_fenetre(self, 600, 400)
        self.configure(fg_color=T.FOND)
        self.poste_choisi = tk.StringVar()
        self.result = None

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, "Quel est le poste de ce PC ?", taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_XL, T.ESPACE_XS))
        texte(cadre, "Machine : écran Atelier. Bureau d'étude : pilotage.").pack(
            fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_L))

        postes_list = [POSTE_BUREAU_ETUDE] + list(postes)
        self.cb = ctk.CTkComboBox(cadre, variable=self.poste_choisi, values=postes_list, state="readonly",
                                  command=lambda _: self._maj_code(),
                                  font=T.police(T.TAILLE_SOUS_TITRE, gras=True), dropdown_font=T.police(T.TAILLE_CORPS),
                                  fg_color=T.SURFACE, border_color=T.BORDURE, text_color=T.TEXTE,
                                  button_color=T.BORDURE, button_hover_color=T.BORDURE_SURVOL,
                                  height=T.HAUTEUR_BOUTON_ATELIER, corner_radius=T.RAYON_CONTROLE)
        self.cb.pack(fill=tk.X, padx=T.ESPACE_XL)
        # Par défaut : le poste actuel, sinon la première machine (un PC d'atelier est le cas le plus courant)
        self.cb.set(actuel if actuel in postes_list else postes_list[1 if len(postes_list) > 1 else 0])

        # Code du Bureau d'étude, affiché seulement quand on choisit ce mode
        self.cadre_code = ctk.CTkFrame(cadre, fg_color="transparent")
        texte(self.cadre_code, "Code d'accès du Bureau d'étude", gras=True).pack(fill=tk.X, pady=(T.ESPACE_M, T.ESPACE_XS))
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
        # Pas de code pour rester en Bureau d'étude, seulement pour y entrer
        return self.poste_choisi.get() == POSTE_BUREAU_ETUDE and self.actuel != POSTE_BUREAU_ETUDE

    def _maj_code(self):
        self.lbl_erreur.configure(text="")
        if self._code_requis():
            self.cadre_code.pack(fill=tk.X, padx=T.ESPACE_XL)
            self.code_entry.focus_set()
        else:
            self.cadre_code.pack_forget()

    def on_validate(self):
        if not self.poste_choisi.get():
            return
        if self._code_requis() and self.code_entry.get().strip() != self.code_bureau_etude:
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
        saisissent pas, leurs champs sont retirés. L'épaisseur reste à saisir (elle n'est pas dans Sage)."""
        self._quantite_fixe = qte
        self._dimensions_imposees = (longueur or None, largeur or None)
        self._lbl_qte.grid_remove()
        self._ligne_qte.grid_remove()
        for widget in self._widgets_longueur_largeur:
            widget.pack_forget()
        self._lbl_dims.configure(text="Épaisseur")

    def champs_communs(self, ligne, design="", qte=1, longueur="", largeur="", epaisseur="", observ="",
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
        ligne_dims = ctk.CTkFrame(self.form, fg_color="transparent")
        ligne_dims.grid(row=ligne + 2, column=1, sticky="ew", pady=(T.ESPACE_S, 0))
        self.longueur_entry = champ(ligne_dims, "Longueur", largeur=110)
        self.longueur_entry.pack(side=tk.LEFT)
        fois = texte(ligne_dims, "×")
        fois.pack(side=tk.LEFT, padx=T.ESPACE_S)
        self.largeur_entry = champ(ligne_dims, "Largeur", largeur=110)
        self.largeur_entry.pack(side=tk.LEFT)
        mm = texte(ligne_dims, "mm     Épaisseur")
        mm.pack(side=tk.LEFT, padx=T.ESPACE_S)
        self._widgets_longueur_largeur = (self.longueur_entry, fois, self.largeur_entry, mm)
        self.epaisseur_entry = champ(ligne_dims, "ex. 6 ou 4/16/4", largeur=130)
        self.epaisseur_entry.pack(side=tk.LEFT)
        for entree, valeur in ((self.longueur_entry, longueur), (self.largeur_entry, largeur), (self.epaisseur_entry, epaisseur)):
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
        return ligne + 5

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
                       epaisseur=self.epaisseur_entry.get().strip(), priorite=1 if self.urgent_var.get() else 0)
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
                 lignes_sage="", longueur="", largeur="", dimensions_sage=False):
        """dimensions_sage : OF issu de lignes de commande, quantité (somme des lignes) et dimensions (Sage)
        imposées : leurs champs ne sont pas proposés, le sous-titre les rappelle."""
        sous_titre = f"Commande {cde}" + (f" · {client}" if client else "")
        if lignes_sage:
            sous_titre += f" · lignes {', '.join(l.rsplit('-', 1)[-1] for l in lignes_sage.split(','))}"
        if dimensions_sage:
            sous_titre += f" · {resume_quantite_dimensions(default_qte, longueur, largeur)}"
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
                                              valeurs["epaisseur"], valeurs["date_besoin"], valeurs["priorite"])
        except LigneDejaAffectee as exc:   # un autre poste a pris la ligne pendant la saisie
            self.erreur(str(exc))
            return
        except sqlite3.IntegrityError:     # numéro d'OF pris au même instant par un autre PC
            self.erreur("Un autre poste vient de créer un OF : cliquez à nouveau sur « Créer l'OF ».")
            return
        self.destroy()


class ModifierOfDialog(_FormulaireOF):
    """Modification d'un OF existant. result = ID de l'OF si enregistré, sinon None.
    Les opérations de la gamme ne changent pas (seuls les postes assignés) : pour cela,
    supprimer l'OF (s'il n'a pas de scan) et le recréer."""

    def __init__(self, parent, depot, of, deja_scannees=0):
        sous_titre = f"Commande {of.cde} · produit {of.prod}"
        if of.lignes_sage:
            sous_titre += f" · {resume_quantite_dimensions(of.qte, of.longueur, of.largeur)}"
        super().__init__(parent, f"Modifier {of.id}", f"Modifier {of.id}", sous_titre, "Enregistrer")
        self.depot = depot
        self.of = of
        self.deja_scannees = deja_scannees
        aide = f"pièces (au moins {deja_scannees}, déjà scannées)" if deja_scannees else "pièces"
        self.champs_communs(0, design=of.design, qte=of.qte, longueur=of.longueur, largeur=of.largeur,
                            epaisseur=of.epaisseur, observ=of.observ, date_besoin=of.date_besoin,
                            urgent=of.urgent, aide_qte=aide)
        if of.lignes_sage:   # OF issu de lignes de commande : quantité et dimensions suivent les lignes
            self.fixer_depuis_lignes(of.qte, of.longueur, of.largeur)
        self.zone_gamme("Vous pouvez changer le poste de chaque opération. Pour ajouter ou retirer une "
                        "opération, supprimez l'OF (s'il n'a pas encore de scan) et recréez-le.")
        libelles = depot.libelles_operations()
        self.postes_vars = {}
        for ordre, code_op, poste in depot.gamme_of(of.id):
            rangee = ctk.CTkFrame(self.gamme_frame, fg_color="transparent")
            rangee.pack(fill=tk.X, padx=T.ESPACE_S, pady=T.ESPACE_XS)
            ctk.CTkLabel(rangee, text=str(ordre), width=24, font=T.police_chiffres(T.TAILLE_CORPS), text_color=T.TEXTE_ATTENUE).pack(side=tk.LEFT)
            ctk.CTkLabel(rangee, text=libelles.get(code_op, code_op), font=T.police(T.TAILLE_CORPS, gras=True),
                         text_color=T.TEXTE, anchor="w").pack(side=tk.LEFT, padx=T.ESPACE_S)
            postes = [POSTE_LIBRE] + [f"{c} - {d}" for c, d in depot.postes_pour_operation(code_op)]
            actuel = next((p for p in postes if p.split(" - ")[0] == poste), POSTE_LIBRE)
            var_poste, combo = self.combo_poste(rangee, postes, actuel)
            combo.pack(side=tk.RIGHT)
            self.postes_vars[ordre] = var_poste
        capturer_focus(self)
        self.design_entry.focus_set()

    def save(self):
        valeurs = self.lire_champs_communs(qte_min=self.deja_scannees)
        if valeurs is None:
            return
        self.depot.modifier_of(self.of.id, valeurs["design"], valeurs["observ"], valeurs["qte"], valeurs["longueur"],
                               valeurs["largeur"], valeurs["epaisseur"], valeurs["date_besoin"], valeurs["priorite"],
                               {ordre: self.poste_choisi(var) for ordre, var in self.postes_vars.items()})
        self.result = self.of.id
        self.destroy()


class HistoriqueDialog(FenetreDialogue):
    """Historique des scans d'un OF (lecture seule). lignes : Depot.historique_scans()."""

    def __init__(self, parent, of, lignes):
        super().__init__(parent)
        self.title(f"Historique · {of.id}")
        centrer_fenetre(self, 860, 620)
        self.configure(fg_color=T.FOND)
        self.transient(parent)

        cadre = carte(self)
        cadre.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_L, pady=T.ESPACE_L)
        titre(cadre, f"Historique des scans · {of.id}", taille=T.TAILLE_TITRE).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(T.ESPACE_L, 0))
        valides = sum(1 for l in lignes if not l[5])
        annules = len(lignes) - valides
        resume = f"{of.design} · {valides} scan{'s' if valides > 1 else ''} valide{'s' if valides > 1 else ''}"
        if annules:
            resume += f", {annules} annulé{'s' if annules > 1 else ''}"
        texte(cadre, resume).pack(fill=tk.X, padx=T.ESPACE_XL, pady=(0, T.ESPACE_M))

        bouton(cadre, "Fermer", self.destroy, style="secondaire", width=120).pack(side=tk.BOTTOM, anchor="e", padx=T.ESPACE_XL, pady=T.ESPACE_L)
        cadre_tableau, self.tree = tableau(cadre, [
            ("date", "Date et heure", 160, "w"), ("poste", "Poste", 80, "center"), ("operation", "Opération", 140, "w"),
            ("ligne", "Ligne Sage", 140, "w"), ("etat", "État", 200, "w")], hauteur=8)
        cadre_tableau.pack(fill=tk.BOTH, expand=True, padx=T.ESPACE_XL)
        for id_scan, horodatage, poste, operation, cle, annule, date_annulation in lignes:
            etat = f"Annulé le {_date_heure(date_annulation)}" if annule else "Valide"
            self.tree.insert("", "end", iid=str(id_scan), values=(_date_heure(horodatage), poste, operation, cle or "—", etat),
                             tags=("annule" if annule else "pas_demarre",))
        if not lignes:
            self.tree.insert("", "end", values=("", "", "Aucun scan pour cet OF", "", ""), tags=("annule",))
        self.bind("<Escape>", lambda e: self.destroy())
        capturer_focus(self)


def _date_heure(valeur):
    """ "2026-10-12 14:03:55" -> "12/10/2026 14:03" """
    if not valeur:
        return ""
    jour, heure = str(valeur).split(" ") if " " in str(valeur) else (str(valeur), "")
    return f"{afficher_date(jour)} {heure[:5]}".strip()
