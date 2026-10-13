"""Avancement des commandes : matrice commandes × opérations (commande > OF > ligne de commande).

Section affichée dans l'onglet Synthèse. Elle se reconstruit à chaque actualisation (automatique
chaque minute) en conservant ce que l'utilisateur a déplié, sélectionné et fait défiler.
"""
import tkinter as tk

import customtkinter as ctk

from .. import theme as T
from ..domain import progression, sage
from .composants import MARGE_COLONNE, abreger, carte, polices_tableau, tableau, texte, titre
from .widgets import maj_tags_selection

LEGENDE = "✓ terminé   ◐ en cours   ○ à faire   — hors gamme"
RETRAIT_NIVEAU = 20           # décalage d'un niveau de l'arbre (commande > OF > ligne)
LARGEUR_MIN_IDENTIFIANT = 144   # tient l'en-tête « Commande / OF »
LARGEUR_MIN_OPERATION = 76    # colonne d'opération : au moins « ○ 0/4 » et un en-tête court
LARGEUR_MAX_OPERATION = 136   # au-delà, l'en-tête est abrégé (« Montage, Assemb… »)


def cellule(scans, qte):
    """Texte d'une cellule : symbole d'état + compteur (l'état ne repose pas sur la couleur seule)."""
    if qte > 0 and scans >= qte:
        return f"✓ {scans}/{qte}"
    return f"◐ {scans}/{qte}" if scans else f"○ 0/{qte}"


class MatriceMixin:

    def build_be_matrice_ui(self, parent):
        panneau = carte(parent)
        panneau.pack(expand=True, fill=tk.BOTH)

        entete = ctk.CTkFrame(panneau, fg_color="transparent")
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, 0))
        titre(entete, "Avancement des commandes", taille=T.TAILLE_SOUS_TITRE).pack(side=tk.LEFT)
        texte(entete, LEGENDE, taille=T.TAILLE_LEGENDE).pack(side=tk.RIGHT)
        texte(panneau, "Dépliez une commande pour voir ses OF. Double-clic sur un OF : l'ouvrir.",
              taille=T.TAILLE_LEGENDE).pack(fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))

        cadre, self.tree_matrice = tableau(panneau, [], arbre=True, defilement_horizontal=True)
        cadre.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_matrice.heading("#0", text="Commande / OF", anchor="w")
        self.tree_matrice.column("#0", width=LARGEUR_MIN_IDENTIFIANT, minwidth=LARGEUR_MIN_IDENTIFIANT, stretch=False)
        self.tree_matrice.bind("<<TreeviewSelect>>", lambda e: maj_tags_selection(self.tree_matrice))
        self.tree_matrice.bind("<Double-1>", self._ouvrir_depuis_avancement)
        # Largeurs nécessaires au contenu ; la place en plus est répartie entre les colonnes d'opération
        self._largeurs_matrice = {}
        self.tree_matrice.bind("<Configure>", lambda e: self.root.after_idle(self._ajuster_colonnes_matrice), add="+")

    def refresh_be_matrice(self, etat=None):
        """etat : instantané déjà chargé par l'appelant (la Synthèse), sinon rechargé ici."""
        # Ce que l'utilisateur voit, à restituer après la reconstruction
        ouverts = set()
        pile = list(self.tree_matrice.get_children())
        while pile:
            item = pile.pop()
            if self.tree_matrice.item(item, "open"):
                ouverts.add(item)
            pile.extend(self.tree_matrice.get_children(item))
        selection = self.tree_matrice.selection()
        defilement = self.tree_matrice.yview()[0]

        for item in self.tree_matrice.get_children():
            self.tree_matrice.delete(item)
        etat = etat or self.recharger_etat()

        operations = self.depot.lister_operations()
        # Commandes en cours d'abord, puis à faire, puis terminées (ordre de création à état égal)
        commandes = [self._donnees_commande(etat, cde, operations) for cde in etat.commandes()]
        commandes.sort(key=lambda c: progression.ORDRE_ETATS.get(c["tag"], 1))

        # Colonnes compactes : chacune à la largeur de son en-tête et de ses cellules les plus longues
        police, police_entete = polices_tableau()
        cellules = [cmd["cellules"] for cmd in commandes]
        for cmd in commandes:
            for of_ligne in cmd["ofs"]:
                cellules.append(of_ligne["cellules"])
                cellules.extend(l[2] for l in of_ligne["lignes"])
        # Première colonne : juste la place du plus long identifiant, en tenant compte du retrait par niveau
        niveaux = [(0, cmd["cde"]) for cmd in commandes]
        for cmd in commandes:
            for of_ligne in cmd["ofs"]:
                niveaux.append((1, of_ligne["of"].id))
                niveaux.extend((2, l[1]) for l in of_ligne["lignes"])
        largeur_id = max((n * RETRAIT_NIVEAU + police.measure(t) for n, t in niveaux), default=0)
        self._largeurs_matrice = {"#0": max(LARGEUR_MIN_IDENTIFIANT, largeur_id + RETRAIT_NIVEAU + MARGE_COLONNE)}
        self.tree_matrice["columns"] = [ref for ref, _ in operations]
        for i, (ref, libelle) in enumerate(operations):
            contenu = max((police.measure(c[i]) for c in cellules), default=0) + MARGE_COLONNE
            entete = abreger(libelle, police_entete, LARGEUR_MAX_OPERATION - MARGE_COLONNE)
            largeur = max(LARGEUR_MIN_OPERATION, contenu, police_entete.measure(entete) + MARGE_COLONNE)
            self.tree_matrice.heading(ref, text=entete, anchor="center")
            self._largeurs_matrice[ref] = min(largeur, LARGEUR_MAX_OPERATION)
            self.tree_matrice.column(ref, anchor="center", stretch=False)
        self._ajuster_colonnes_matrice()

        for cmd in commandes:
            cde = cmd["cde"]
            cde_node = self.tree_matrice.insert("", "end", iid=f"CDE:{cde}", open=f"CDE:{cde}" in ouverts,
                                                text=cde,
                                                values=cmd["cellules"], tags=(cmd["tag"],))
            for of_ligne in cmd["ofs"]:
                of = of_ligne["of"]
                of_node = self.tree_matrice.insert(cde_node, "end", iid=f"OF:{of.id}", open=f"OF:{of.id}" in ouverts,
                                                   text=of.id, values=of_ligne["cellules"],
                                                   tags=(of_ligne["tag"],))
                for cle, texte_ligne, cellules, tag in of_ligne["lignes"]:
                    self.tree_matrice.insert(of_node, "end", iid=f"L:{of.id}:{cle}", text=texte_ligne,
                                             values=cellules, tags=(tag,))

        selection = [i for i in selection if self.tree_matrice.exists(i)]
        if selection:
            self.tree_matrice.selection_set(selection)
        maj_tags_selection(self.tree_matrice)
        # Pas d'update_idletasks() ici : sous Windows, traiter les tâches en attente (fenêtres fermées
        # juste avant) fait planter Tk. yview_moveto n'en a pas besoin.
        self.tree_matrice.yview_moveto(defilement)

    def _ajuster_colonnes_matrice(self):
        """Colonnes à leur largeur utile ; si le tableau est plus large, le surplus est partagé
        entre les colonnes d'opération (le tableau occupe toute la section, quelle que soit l'écran).
        S'il est plus étroit, les largeurs utiles sont gardées et la barre horizontale apparaît."""
        arbre = self.tree_matrice
        if not self._largeurs_matrice or not arbre.winfo_exists():
            return
        operations = [c for c in self._largeurs_matrice if c != "#0"]
        surplus = max(0, arbre.winfo_width() - sum(self._largeurs_matrice.values()) - 2)
        part, reste = divmod(surplus, len(operations)) if operations else (0, 0)
        arbre.column("#0", width=self._largeurs_matrice["#0"] + (surplus if not operations else 0), stretch=False)
        for i, ref in enumerate(operations):
            arbre.column(ref, width=self._largeurs_matrice[ref] + part + (1 if i < reste else 0), stretch=False)

    def _donnees_commande(self, etat, cde, operations):
        """Cellules et état d'une commande, de ses OF et de leurs lignes Sage."""
        totaux = {ref: [0, 0] for ref, _ in operations}  # opération -> [pièces faites, pièces prévues]
        total_scans = 0
        tout_fini = True
        a_des_operations = False
        ofs = []

        for of in etat.ofs_par_cde[cde]:
            of_ops = [op for op, _ in etat.gamme(of.id)]
            if not of_ops:
                ofs.append({"of": of, "cellules": ["—"] * len(operations), "tag": "pas_demarre", "lignes": []})
                continue
            a_des_operations = True

            # Pour chaque opération de la gamme : scans de l'OF et répartition par ligne Sage
            enfants = sage.lignes_enfants(self.sage, cde, of.lignes_sage)
            scans_of = {r: etat.compter(of.id, r) for r, _ in operations if r in of_ops}
            scans_lignes = {r: progression.repartir_scans(etat, of.id, r, enfants) for r in scans_of}
            for r, n in scans_of.items():
                totaux[r][0] += min(n, of.qte)
                totaux[r][1] += of.qte

            of_scans = sum(scans_of.values())
            of_fini = all(n >= of.qte for n in scans_of.values())
            total_scans += of_scans
            tout_fini = tout_fini and of_fini

            lignes = []
            for cle, l_qte, ligne in enfants:
                c_scans = {r: scans_lignes[r][cle] for r in scans_lignes}
                lignes.append((cle, str(ligne.get('DL_Ligne', cle)),
                               [cellule(c_scans[r], l_qte) if r in c_scans else "—" for r, _ in operations],
                               progression.tag_etat(sum(c_scans.values()), all(n >= l_qte for n in c_scans.values()))))
            ofs.append({"of": of, "lignes": lignes, "tag": progression.tag_etat(of_scans, of_fini),
                        "cellules": [cellule(scans_of[r], of.qte) if r in scans_of else "—" for r, _ in operations]})

        tag = progression.tag_etat(total_scans, tout_fini) if a_des_operations else "pas_demarre"
        return {"cde": cde, "tag": tag, "ofs": ofs,
                "cellules": [cellule(*totaux[r]) if totaux[r][1] else "—" for r, _ in operations]}

    def _ouvrir_depuis_avancement(self, event=None):
        """Double-clic sur un OF (ou une de ses lignes) : l'ouvrir dans Création d'OF."""
        selection = self.tree_matrice.selection()
        if not selection:
            return
        item = selection[0]
        if item.startswith("L:"):
            item = self.tree_matrice.parent(item)
        if item.startswith("OF:"):
            self.selectionner_of_be(item[3:])
            return "break"  # sinon le double-clic déplierait aussi la ligne
