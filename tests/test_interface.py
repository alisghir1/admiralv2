"""Test d'intégration de l'interface sur une base et des exports Sage temporaires.

Ouvre brièvement une fenêtre Tk (masquée) ; ignoré si aucun affichage n'est disponible.
"""
import json
import os
import tempfile
import tkinter
import unittest
from tkinter import messagebox

from admiral import config
from admiral.db import schema
from admiral.db.depot import Depot

ENTETES = "DO_Piece,DO_Date,DO_Tiers\nCC1,12/10/2026,MIROITERIE DU NORD\nCC2,12/10/2026,MENUISERIE DU CENTRE\nCC3,12/10/2026,FACADES DE L'OUEST\n"
LIGNES = ("DO_Piece,DL_Ligne,AR_Ref,DL_Design,DL_Qte,LONG,LARG\n"
          "CC1,1000,VITR,Double Vitrage,5,1200,800\nCC1,2000,FEUILLE,Verre Trempé,2,2100,950\n"
          "CC2,1000,MIROIR,Miroir Argent,4,1500,600\nCC3,1000,VITR,Double Vitrage Argon,8,1800,1100\n")


def creer_donnees(dossier):
    os.makedirs(os.path.join(dossier, "data"))
    for nom, contenu in (("F-DOCENTETE.csv", ENTETES), ("F-DOCLIGNE.csv", LIGNES)):
        with open(os.path.join(dossier, "data", nom), "w", encoding="utf-8") as f:
            f.write(contenu)
    conn = schema.ouvrir(os.path.join(dossier, "test.db"))
    conn.executemany("INSERT INTO Produits VALUES (?, ?)", [("VITR", "Double Vitrage Isolant"), ("MIROIR", "Miroir Argent")])
    conn.executemany("INSERT INTO Gammes (RefProd, CodeOp, Ordre) VALUES (?, ?, ?)",
                     [("VITR", "DEC", 1), ("VITR", "FAC", 2), ("VITR", "TRE", 3), ("MIROIR", "DEC", 1), ("MIROIR", "FAC", 2)])
    conn.commit()
    depot = Depot(conn)
    depot.creer_of("CC1", "VITR", "Double Vitrage", "", 7, "CC1-1000,CC1-2000",
                   [("DEC", "DEC1"), ("FAC", "FAC1"), ("TRE", "TRE1")], 1200, 800, "4/16/4")  # OF-1000
    depot.creer_of("CC2", "MIROIR", "Miroir Argent", "1500 x 600 mm", 4, "CC2-1000",
                   [("DEC", "DEC1"), ("FAC", "FAC1")])                                      # OF-1001 (ancien format)
    conn.close()
    with open(os.path.join(dossier, "config_poste.json"), "w", encoding="utf-8") as f:
        json.dump({"poste": "DEC1 - Découpe Numérique SEKTOR", "base_de_donnees": os.path.join(dossier, "test.db"),
                   "dossier_sage": os.path.join(dossier, "data")}, f)


class Interface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import customtkinter as ctk
            cls.root = ctk.CTk()
        except tkinter.TclError as exc:
            raise unittest.SkipTest(f"pas d'affichage : {exc}")
        cls.root.withdraw()
        cls.tmp = tempfile.TemporaryDirectory()
        creer_donnees(cls.tmp.name)
        cls._config_origine = config.CONFIG_FILE
        config.CONFIG_FILE = os.path.join(cls.tmp.name, "config_poste.json")
        cls.messages = []
        cls.reponse_oui_non = True
        cls._messagebox = {}
        for nom in ("showinfo", "showwarning", "showerror", "askyesno"):
            cls._messagebox[nom] = getattr(messagebox, nom)
            setattr(messagebox, nom, lambda *a, nom=nom, **k: cls.messages.append(nom) or cls.reponse_oui_non)
        from admiral.ui.app import SotraglaceApp
        cls.app = SotraglaceApp(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        cls.app.depot.conn.close()  # sous Windows, un fichier ouvert ne peut pas être supprimé
        config.CONFIG_FILE = cls._config_origine
        for nom, fonction in cls._messagebox.items():
            setattr(messagebox, nom, fonction)
        cls.tmp.cleanup()

    # Outils
    def poste(self, code):
        self.app.poste_actuel = next(p for p in self.app.libelles_postes() if p.startswith(code + " "))

    def scans(self, id_of, op):
        return self.app.recharger_etat().compter(id_of, op)

    def bandeau(self):
        return self.app.lbl_scan_status.cget("text"), self.app.lbl_scan_detail.cget("text")

    # Les tests s'enchaînent dans l'ordre alphabétique et partagent la même base
    def test_01_creation_of(self):
        from admiral.ui.dialogs import AddOfDialog
        dlg = AddOfDialog(self.root, self.app.depot, "CC3", "FACADES", 8, "", lignes_sage="CC3-1000", longueur="1800", largeur="1100")
        dlg.choisir_produit("VITR")
        self.assertEqual(len(dlg.gamme_vars), 3)
        self.assertTrue(all(e['var_check'].get() for e in dlg.gamme_vars), "gamme standard pré-cochée")
        self.assertEqual(dlg.design_entry.get(), "Double Vitrage Isolant")
        dlg.save()
        self.assertEqual(dlg.result, "OF-1002")
        of = self.app.recharger_etat().ofs["OF-1002"]
        self.assertEqual((of.longueur, of.largeur, of.qte), (1800, 1100, 8))
        self.assertEqual(self.app.etat.gamme("OF-1002"), [("DEC", None), ("FAC", None), ("TRE", None)])

    def test_02_creation_of_erreurs_dans_la_fenetre(self):
        from admiral.ui.dialogs import AddOfDialog
        dlg = AddOfDialog(self.root, self.app.depot, "CC3")
        dlg.save()
        self.assertIn("produit", dlg.lbl_erreur.cget("text"))
        dlg.choisir_produit("VITR")
        dlg.qte_entry.delete(0, "end")
        dlg.qte_entry.insert(0, "abc")
        dlg.save()
        self.assertIn("quantité", dlg.lbl_erreur.cget("text"))
        dlg.qte_entry.delete(0, "end")
        dlg.qte_entry.insert(0, "2")
        dlg.longueur_entry.insert(0, "12,5")
        dlg.save()
        self.assertIn("longueur", dlg.lbl_erreur.cget("text"))
        self.assertIsNone(dlg.result)
        dlg.destroy()

    def test_03_scan_et_controles(self):
        self.poste("DEC1")
        self.app.process_scan("of-1000")
        self.assertEqual(self.scans("OF-1000", "DEC"), 1)
        self.assertEqual(self.bandeau()[0], "Pièce enregistrée")
        self.assertEqual(self.app.lbl_scan_compte.cget("text"), "1 / 7")
        self.poste("USI1")
        self.app.process_scan("OF-1000")
        self.assertEqual(self.bandeau()[0], "Scan refusé")
        self.assertIn("ne passe pas par l'opération USI", self.bandeau()[1])
        self.poste("FAC1")
        self.app.process_scan("OF-1000")
        self.assertEqual(self.scans("OF-1000", "FAC"), 1)
        self.app.process_scan("OF-1000")
        self.assertIn("Bloqué : étape précédente (DEC) à 1/7", self.bandeau()[1])
        self.app.process_scan("ART-CC1-1000")
        self.assertEqual(self.bandeau()[0], "Code inconnu")

    def test_04_terminer_avec_rattrapage(self):
        self.poste("TRE1")
        self.app.ajouter_scans_manuels("OF-1000", "all")
        self.assertEqual([self.scans("OF-1000", op) for op in ("DEC", "FAC", "TRE")], [7, 7, 7])

    def test_05_annulations(self):
        self.app.retirer_scans_manuels("OF-1000", 2)
        self.assertEqual(self.scans("OF-1000", "TRE"), 5)
        type(self).reponse_oui_non = False          # « Tout annuler » refusé : rien ne change
        self.app.retirer_scans_manuels("OF-1000", "all")
        self.assertEqual(self.scans("OF-1000", "TRE"), 5)
        type(self).reponse_oui_non = True
        self.app.retirer_scans_manuels("OF-1000", "all")
        self.assertEqual(self.scans("OF-1000", "TRE"), 0)
        self.assertEqual(self.messages[-1], "askyesno")

    def test_06_cartes_et_matrice_coherentes(self):
        self.poste("DEC1")
        self.app.process_scan("OF-1001")
        self.app.process_scan("OF-1001")
        carte = self.app.cartes["OF-1001"]
        widget_avant = carte
        vue = self.app._vue_of(self.app.etat.ofs["OF-1001"], "DEC", "DEC1", self.app.depot.libelles_operations())
        self.assertEqual((vue.lignes[0].scans, vue.lignes[0].qte), (2, 4))
        self.assertEqual(vue.dimensions, "1500 x 600 mm")          # ancien OF : dimensions en observation
        self.assertEqual(vue.etat, "encours")
        self.app.process_scan("OF-1001")
        self.assertIs(self.app.cartes["OF-1001"], widget_avant, "carte mise à jour sur place, pas recréée")
        self.app.refresh_be_matrice()
        ligne = self.app.tree_matrice.get_children(self.app.tree_matrice.get_children("CDE:CC2")[0])[0]
        colonnes = list(self.app.tree_matrice["columns"])
        self.assertEqual(self.app.tree_matrice.item(ligne, "values")[colonnes.index("DEC")], "◐ 3/4")

    def test_07_liste_des_commandes(self):
        self.app.refresh_dashboard()
        etats = [self.app.tree_cmd.item(i, "values")[3] for i in self.app.tree_cmd.get_children()]
        ordre = {"En cours": 0, "À faire": 1, "Terminée": 2}
        self.assertEqual(etats, sorted(etats, key=ordre.get))
        self.app.filtre_commandes.set("En cours")
        self.app._appliquer_recherche()
        self.assertTrue(all(self.app.tree_cmd.item(i, "values")[3] == "En cours" for i in self.app.tree_cmd.get_children()))
        self.app.filtre_commandes.set("Toutes")
        self.app._appliquer_recherche()

    def test_08_recherches_separees(self):
        self.app.search_entry.insert(0, "miroiterie")
        self.app.on_search_change()
        self.assertIsNotNone(self.app._recherche_timer)
        self.app._appliquer_recherche()
        self.assertEqual(self.app.tree_cmd.get_children(), ("CC1",))
        self.assertEqual(len(self.app.tree_be_cmd.get_children()), 3, "la recherche Atelier ne filtre pas le Bureau d'Étude")
        self.app.search_entry.delete(0, "end")
        self.app._appliquer_recherche()

    def test_09_creation_of_onglet(self):
        self.app.tree_be_cmd.selection_set("CC1")
        self.app.on_be_order_select()
        self.assertEqual(self.app.tree_be_sage.get_children(), ("CC1-1000", "CC1-2000"))
        self.assertEqual(len(self.app.tree_be_of.get_children("OF-1000")), 2)
        self.assertEqual(self.app.tree_be_of.item("OF-1000", "values")[3], "1200 × 800 mm · ép. 4/16/4")

    def test_10_charge_et_navigation(self):
        self.app.refresh_be_charge()
        self.assertEqual(self.app.poste_charge, "DEC1", "poste de ce PC par défaut")
        self.assertIn("OF-1001", self.app.contenu_charge["encours"])
        self.app.selectionner_of_be("OF-1001")
        self.assertEqual(self.app.notebook.get(), self.app.NOM_ONGLET_GENERATION)
        self.assertEqual(self.app.tree_be_of.selection(), ("OF-1001",))

    def test_11_bandeau_revient_au_repos(self):
        self.app.update_status_bar("error", "Scan refusé", "motif")
        self.assertIsNotNone(self.app._timer_bandeau)
        self.app._bandeau_au_repos()
        self.assertEqual(self.bandeau()[0], "Prêt à scanner")

    def test_12_douchette_hors_champ(self):
        class Evenement:
            char = "O"
        # Focus simulé dans un tableau : le test ne dépend pas du clavier réel de la machine
        focus_reel = self.app._focus_actuel
        self.app._focus_actuel = lambda: self.app.tree_cmd
        try:
            self.app.scan_var.set("")
            self.app.force_focus(Evenement())
            self.assertEqual(self.app.scan_var.get(), "O", "le premier caractère n'est pas perdu")
        finally:
            self.app._focus_actuel = focus_reel
            self.app.scan_var.set("")

    def test_13_scan_d_une_commande(self):
        self.app.process_scan("CMD-CC1")
        self.assertEqual(self.app.commande_affichee, "CC1")
        self.assertEqual(self.bandeau()[0], "Commande CC1")

    # --- Phase 4 : suivi des OF, synthèse, administration ---

    def test_14_modifier_of_urgent_en_retard(self):
        from admiral.ui.dialogs import ModifierOfDialog
        of = self.app.recharger_etat().ofs["OF-1002"]
        dlg = ModifierOfDialog(self.root, self.app.depot, of, deja_scannees=0)
        dlg.besoin_entry.insert(0, "01/01/2020")
        dlg.urgent_var.set(True)
        dlg.save()
        self.assertEqual(dlg.result, "OF-1002")
        of = self.app.recharger_etat().ofs["OF-1002"]
        self.assertEqual((of.date_besoin, of.priorite), ("2020-01-01", 1))
        self.poste("DEC1")
        self.app._afficher_commande("CC3")
        carte = self.app.cartes["OF-1002"]
        self.assertTrue(carte._urgent_visible)
        self.assertIn("En retard", carte.lbl_besoin.cget("text"))

    def test_15_quantite_minimum_a_la_modification(self):
        from admiral.ui.dialogs import ModifierOfDialog
        of = self.app.recharger_etat().ofs["OF-1001"]
        dlg = ModifierOfDialog(self.root, self.app.depot, of, deja_scannees=3)
        dlg.qte_entry.delete(0, "end")
        dlg.qte_entry.insert(0, "2")
        dlg.save()
        self.assertIn("au moins 3", dlg.lbl_erreur.cget("text"))
        dlg.destroy()

    def test_16_annuler_et_reactiver_of(self):
        self.app.notebook.set(self.app.NOM_ONGLET_GENERATION)
        self.app.tree_be_cmd.selection_set("CC3")
        self.app.on_be_order_select()
        self.app.tree_be_of.selection_set("OF-1002")
        self.app._maj_boutons_of()
        self.app.basculer_annulation_of()
        self.assertTrue(self.app.etat.ofs["OF-1002"].annule)
        self.assertEqual(self.app.tree_be_of.item("OF-1002", "values")[6], "Annulé")
        self.assertEqual(self.app.btn_annuler_of.cget("text"), "Réactiver l'OF")
        self.app.process_scan("OF-1002")
        self.assertIn("annulé", self.bandeau()[1])
        self.app.notebook.set(self.app.NOM_ONGLET_GENERATION)
        self.app.tree_be_of.selection_set("OF-1002")
        self.app.basculer_annulation_of()
        self.assertFalse(self.app.recharger_etat().ofs["OF-1002"].annule)

    def test_17_supprimer_of(self):
        self.app.tree_be_cmd.selection_set("CC1")
        self.app.on_be_order_select()
        self.app.tree_be_of.selection_set("OF-1000")
        self.app.supprimer_of_be()                                  # déjà scanné : refusé
        self.assertEqual(self.messages[-1], "showwarning")
        self.assertIn("OF-1000", self.app.recharger_etat().ofs)
        vierge = self.app.depot.creer_of("CC1", "VITR", "À supprimer", "", 1, "", [("DEC", None)])
        self.app.on_be_order_select()
        self.app.tree_be_of.selection_set(vierge)
        self.app.supprimer_of_be()
        self.assertNotIn(vierge, self.app.recharger_etat().ofs)

    def test_18_cloturer_commande(self):
        self.app.tree_be_cmd.selection_set("CC2")
        self.app.on_be_order_select()
        self.app.basculer_cloture()
        self.assertIn("CC2", self.app.etat.cloturees)
        self.assertNotIn("CC2", self.app.tree_be_cmd.get_children(), "masquée par défaut")
        self.assertFalse(self.app.tree_cmd.exists("CC2"), "absente de l'atelier")
        self.poste("DEC1")
        self.app.process_scan("OF-1001")
        self.assertIn("clôturée", self.bandeau()[1])
        self.app.voir_cloturees.set(True)
        self.app.refresh_dashboard()
        self.assertEqual(self.app.tree_be_cmd.item("CC2", "values")[2], "Clôturée")
        self.app.tree_be_cmd.selection_set("CC2")
        self.app.on_be_order_select()
        self.assertEqual(self.app.btn_cloture.cget("text"), "Rouvrir la commande")
        self.app.basculer_cloture()
        self.assertNotIn("CC2", self.app.recharger_etat().cloturees)
        self.app.voir_cloturees.set(False)

    def test_19_historique(self):
        from admiral.ui.dialogs import HistoriqueDialog
        lignes = self.app.depot.historique_scans("OF-1000")
        dlg = HistoriqueDialog(self.root, self.app.etat.ofs["OF-1000"], lignes)
        etats = [dlg.tree.item(i, "values")[4] for i in dlg.tree.get_children()]
        self.assertTrue(any(e.startswith("Annulé le") for e in etats), "les annulations de test_05 sont tracées")
        self.assertIn("Valide", etats)
        dlg.destroy()

    def test_20_synthese(self):
        self.app.notebook.set(self.app.NOM_ONGLET_SYNTHESE)
        self.app.on_main_tab_changed()
        s = self.app.derniere_synthese
        self.assertGreater(s.pieces_jour, 0)
        self.assertEqual(self.app.tuiles["pieces_jour"].cget("text"), str(s.pieces_jour))
        self.assertIn("OF-1002", self.app.tree_surveiller.get_children(), "OF urgent en retard à surveiller")
        self.assertEqual(len(self.app.tree_synthese_postes.get_children()), 5)
        self.app.tree_surveiller.selection_set("OF-1002")
        self.app._ouvrir_of_surveille()
        self.assertEqual(self.app.notebook.get(), self.app.NOM_ONGLET_GENERATION)

    def test_21_administration(self):
        self.app.notebook.set(self.app.NOM_ONGLET_ADMIN)
        self.app.on_main_tab_changed()
        self.app._nouvelle_operation()
        self.app.op_code.insert(0, "lav")
        self.app.op_libelle.insert(0, "Lavage")
        self.app._enregistrer_operation()
        self.assertEqual(self.app.depot.libelles_operations()["LAV"], "Lavage")
        self.app._nouveau_poste()
        self.app.poste_code.insert(0, "LAV1")
        self.app.poste_designation.insert(0, "Laveuse")
        self.app.poste_operation.set("LAV · Lavage")
        self.app._enregistrer_poste()
        self.assertIn(("LAV1", "Laveuse", "LAV"), self.app.depot.lister_postes_complets())
        self.app._nouveau_produit()
        self.app.produit_ref.insert(0, "FEUILLE")
        self.app.produit_designation.insert(0, "Verre trempé")
        for op in ("DEC · Découpe", "LAV · Lavage", "TRE · Trempe"):
            self.app.gamme_ajout.set(op)
            self.app._ajouter_etape()
        self.app._deplacer_etape(2, -1)                       # Trempe avant Lavage
        self.app._enregistrer_produit()
        self.assertEqual([op for _, op, _ in self.app.depot.gamme_produit("FEUILLE")], ["DEC", "TRE", "LAV"])
        self.app.tree_admin_ops.selection_set("DEC")
        self.app._supprimer_operation()                       # utilisée : refus affiché, rien supprimé
        self.assertIn("utilisée", self.app.lbl_admin_message.cget("text"))
        self.app.tree_admin_postes.selection_set("DEC1")
        self.app._supprimer_poste()                           # poste de ce PC
        self.assertIn("poste de ce PC", self.app.lbl_admin_message.cget("text"))

    def test_22_import_excel_illisible(self):
        self.app.preparer_import(os.path.join(self.tmp.name, "absent.xlsx"))
        self.assertIn("Lecture impossible", self.app.lbl_apercu_import.cget("text"))
        self.assertEqual(self.app.btn_importer.cget("state"), "disabled")

    def test_23_filtre_des_commandes_be(self):
        # À ce stade, les trois commandes du jeu de test ont toutes au moins un OF
        def etats():
            return [self.app.tree_be_cmd.item(i, "values")[2] for i in self.app.tree_be_cmd.get_children()]
        self.app.notebook.set(self.app.NOM_ONGLET_GENERATION)
        self.app.filtre_be.set("Sans OF")
        self.app.refresh_dashboard()
        self.assertEqual(self.app.tree_be_cmd.get_children(), ())
        self.assertEqual(self.app.lbl_nb_commandes_be.cget("text"), "0 commande")
        self.app.filtre_be.set("Avec OF")
        self.app.refresh_dashboard()
        self.assertEqual(len(self.app.tree_be_cmd.get_children()), 3)
        self.assertNotIn("Sans OF", etats())
        self.app.filtre_be.set("En cours")
        self.app.refresh_dashboard()
        self.assertTrue(all(e == "En cours" for e in etats()))
        # Une commande traitée reste visible même si le filtre l'aurait masquée
        self.app.filtre_be.set("Sans OF")
        self.app.refresh_dashboard()
        self.app._garder_commande_visible("CC1")
        self.assertEqual(self.app.filtre_be.get(), "Toutes les commandes")
        self.assertEqual(self.app.tree_be_cmd.selection(), ("CC1",))
    # --- Mode Bureau d'étude / poste machine ---

    def passer_en(self, poste):
        self.app.poste_actuel = poste
        self.app._maj_entete_poste()
        self.app._appliquer_mode()
        self.app.refresh_dashboard()
        self.root.update()

    def test_24_poste_machine_atelier_seul(self):
        self.passer_en(next(p for p in self.app.libelles_postes() if p.startswith("DEC1 ")))
        self.assertEqual(self.app.tab_atelier.winfo_manager(), "pack", "écran Atelier affiché")
        self.assertEqual(self.app.notebook.winfo_manager(), "", "onglets du Bureau d'étude masqués")
        self.assertIn("Poste DEC1", self.app.lbl_title.cget("text"))

    def test_25_bureau_etude_sans_atelier(self):
        from admiral.config import POSTE_BUREAU_ETUDE
        self.passer_en(POSTE_BUREAU_ETUDE)
        try:
            onglets = list(self.app.notebook._segmented_button.cget("values"))
            self.assertEqual(onglets, [self.app.NOM_ONGLET_SYNTHESE, self.app.NOM_ONGLET_GENERATION, self.app.NOM_ONGLET_MATRICE,
                                       self.app.NOM_ONGLET_CHARGE, self.app.NOM_ONGLET_ADMIN])
            self.assertEqual(self.app.notebook.winfo_manager(), "pack", "onglets affichés")
            self.assertEqual(self.app.tab_atelier.winfo_manager(), "", "écran Atelier masqué")
            self.assertEqual(self.app.lbl_title.cget("text").strip(), "Bureau d'étude")
            self.assertNotIn("Poste", self.app.lbl_title.cget("text"))
            # Pas de douchette : un caractère tapé ne part pas dans le champ de scan
            class Evenement:
                char = "O"
            self.app.scan_var.set("")
            self.app.force_focus(Evenement())
            self.assertEqual(self.app.scan_var.get(), "")
            self.app.process_scan("OF-1000")
            self.assertEqual(self.app.notebook.get(), self.app.NOM_ONGLET_SYNTHESE, "un scan ne ramène pas à l'Atelier")
            # Avancement global (tous postes) : CC1 a des pièces sorties de la dernière opération
            self.assertEqual(self.app.tree_be_cmd.item("CC1", "values")[2], "En cours")
            self.app.refresh_be_charge()
            self.assertEqual(self.app.poste_charge, "DEC1", "Charge ouverte sur le premier poste")
        finally:
            self.passer_en(next(p for p in self.app.libelles_postes() if p.startswith("DEC1 ")))

    def test_26_code_du_bureau_etude(self):
        from admiral.config import POSTE_BUREAU_ETUDE
        from admiral.ui.dialogs import ConfigDialog
        d = ConfigDialog(self.root, self.app.libelles_postes(), is_cancellable=True, actuel="DEC1 - Découpe Numérique SEKTOR",
                         code_bureau_etude="4321")
        self.assertEqual(d.cb.cget("values")[0], POSTE_BUREAU_ETUDE)
        d.cb.set(POSTE_BUREAU_ETUDE)
        d._maj_code()
        d.code_entry.insert(0, "0000")
        d.on_validate()
        self.assertIsNone(d.result)
        self.assertEqual(d.lbl_erreur.cget("text"), "Code incorrect.")
        d.code_entry.insert(0, "4321")
        d.on_validate()
        self.assertEqual(d.result, POSTE_BUREAU_ETUDE)
        # Déjà au Bureau d'étude : pas de code pour y rester
        d = ConfigDialog(self.root, self.app.libelles_postes(), is_cancellable=True, actuel=POSTE_BUREAU_ETUDE,
                         code_bureau_etude="4321")
        self.assertFalse(d._code_requis())
        d.on_validate()
        self.assertEqual(d.result, POSTE_BUREAU_ETUDE)
        # Un poste machine ne demande pas de code
        d = ConfigDialog(self.root, self.app.libelles_postes(), is_cancellable=True, actuel=POSTE_BUREAU_ETUDE)
        d.cb.set("USI1 - Centre Usinage 1")
        d._maj_code()
        d.on_validate()
        self.assertEqual(d.result, "USI1 - Centre Usinage 1")


if __name__ == "__main__":
    unittest.main()
