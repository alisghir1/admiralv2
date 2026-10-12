"""Avancement : matrice commandes × opérations (commande > OF > ligne de commande)."""
import tkinter as tk

import customtkinter as ctk

from .. import theme as T
from ..domain import progression, sage
from .composants import bouton, carte, tableau, texte, titre
from .widgets import get_icon, maj_tags_selection

LEGENDE = "✓ terminé    ◐ en cours    ○ à faire    — hors gamme"


def cellule(scans, qte):
    """Texte d'une cellule : symbole d'état + compteur (l'état ne repose pas sur la couleur seule)."""
    if qte > 0 and scans >= qte:
        return f"✓ {scans}/{qte}"
    return f"◐ {scans}/{qte}" if scans else f"○ 0/{qte}"


class MatriceMixin:

    def build_be_matrice_ui(self):
        panneau = carte(self.tab_be_matrice)
        panneau.pack(expand=True, fill=tk.BOTH)

        entete = ctk.CTkFrame(panneau, fg_color="transparent")
        entete.pack(fill=tk.X, padx=T.ESPACE_L, pady=(T.ESPACE_L, T.ESPACE_XS))
        titre(entete, "Avancement des commandes par opération", taille=T.TAILLE_TITRE).pack(side=tk.LEFT)
        bouton(entete, "Actualiser", self.refresh_be_matrice, style="secondaire", icone=get_icon("refresh")).pack(side=tk.RIGHT)
        texte(panneau, f"Dépliez une commande pour voir ses OF et leurs lignes.    {LEGENDE}").pack(
            fill=tk.X, padx=T.ESPACE_L, pady=(0, T.ESPACE_S))

        cadre, self.tree_matrice = tableau(panneau, [], arbre=True, defilement_horizontal=True)
        cadre.pack(expand=True, fill=tk.BOTH, padx=T.ESPACE_L, pady=(0, T.ESPACE_L))
        self.tree_matrice.heading("#0", text="Commande / OF / ligne", anchor="w")
        self.tree_matrice.column("#0", width=420, stretch=True)
        self.tree_matrice.bind("<<TreeviewSelect>>", lambda e: maj_tags_selection(self.tree_matrice))

    def refresh_be_matrice(self):
        ouverts = {item for item in self.tree_matrice.get_children() if self.tree_matrice.item(item, "open")}
        for item in self.tree_matrice.get_children():
            self.tree_matrice.delete(item)
        etat = self.recharger_etat()

        operations = self.depot.lister_operations()
        self.tree_matrice["columns"] = [ref for ref, _ in operations]
        for ref, libelle in operations:
            self.tree_matrice.heading(ref, text=libelle, anchor="center")
            self.tree_matrice.column(ref, width=130, anchor="center", stretch=False)

        for cde in etat.commandes():
            client = self.sage.client(cde, "")
            cde_node = self.tree_matrice.insert("", "end", iid=f"CDE:{cde}", text=f"Commande {cde}" + (f" · {client}" if client else ""),
                                                open=f"CDE:{cde}" in ouverts)
            cde_total_scans = 0
            cde_all_done = True
            cde_has_ops = False
            totaux_cde = {ref: [0, 0] for ref, _ in operations}  # opération -> [faits, prévus]

            for of in etat.ofs_par_cde[cde]:
                of_node = self.tree_matrice.insert(cde_node, "end", text=f"{of.id} · {of.design}", open=False)
                of_ops = [op for op, _ in etat.gamme(of.id)]
                if not of_ops:
                    continue
                cde_has_ops = True

                # Pour chaque opération de la gamme : scans de l'OF et répartition par ligne Sage
                enfants = sage.lignes_enfants(self.sage, cde, of.lignes_sage)
                scans_of = {r: etat.compter(of.id, r) for r, _ in operations if r in of_ops}
                scans_lignes = {r: progression.repartir_scans(etat, of.id, r, enfants) for r in scans_of}
                for r, n in scans_of.items():
                    totaux_cde[r][0] += min(n, of.qte)
                    totaux_cde[r][1] += of.qte

                of_total_scans = sum(scans_of.values())
                of_all_done = all(n >= of.qte for n in scans_of.values())
                self.tree_matrice.item(of_node, values=[cellule(scans_of[r], of.qte) if r in scans_of else "—" for r, _ in operations],
                                       tags=(progression.tag_etat(of_total_scans, of_all_done),))
                cde_total_scans += of_total_scans
                cde_all_done = cde_all_done and of_all_done

                for cle, l_qte, ligne in enfants:
                    c_scans = {r: scans_lignes[r][cle] for r in scans_lignes}
                    c_node = self.tree_matrice.insert(of_node, "end", text=f"Ligne {ligne.get('DL_Ligne', cle)} · {ligne.get('DL_Design', '')}", open=False)
                    self.tree_matrice.item(c_node, values=[cellule(c_scans[r], l_qte) if r in c_scans else "—" for r, _ in operations],
                                           tags=(progression.tag_etat(sum(c_scans.values()), all(n >= l_qte for n in c_scans.values())),))

            # Ligne de commande : total des pièces par opération
            self.tree_matrice.item(cde_node, values=[cellule(*totaux_cde[r]) if totaux_cde[r][1] else "—" for r, _ in operations])
            tag = progression.tag_etat(cde_total_scans, cde_all_done) if cde_has_ops else "pas_demarre"
            self.tree_matrice.item(cde_node, tags=(tag,))
        maj_tags_selection(self.tree_matrice)
