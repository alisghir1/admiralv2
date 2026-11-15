"""Test d'intégration de l'interface sur une base et des exports Sage temporaires.

Ouvre brièvement une fenêtre Tk (masquée) ; ignoré si aucun affichage n'est disponible.
"""
import json
import os
import sys
import tempfile
import tkinter
import unittest
from tkinter import messagebox

from admiral import config
from admiral.db import schema
from admiral.db.depot import Depot
from admiral.domain import tri

# Code et nom du client, comme dans le classeur Sage (l'ordre des codes n'est pas celui des noms) ;
# CC1 a une réf. client, un délai dépassé et une observation
ENTETES = ("DO_Piece,DO_Date,DO_Tiers,CT_Intitule,DO_Coord01,DO_DateLivr,OBSERV\n"
           "CC1,12/10/2025,C0101,MIROITERIE DU NORD,Villa des Pins,09/01/2026,EN ATTENTE MESURE\n"
           "CC2,12/10/2026,C0104,MENUISERIE DU CENTRE,,,\nCC3,12/10/2026,C0102,FACADES DE L'OUEST,,,\n"
           "CC4,12/10/2026,C0103,AGENCEMENT DU SUD,,,\n")
# Lignes de CC1 : unité, surface et métrage de chant par pièce, chants à poser
LIGNES = ("DO_Piece,DL_Ligne,AR_Ref,DL_Design,DL_Qte,LONG,LARG,EU_Enumere,SURF,CHANT,Chant-L,Chant-H\n"
          "CC1,1000,VITR,Double Vitrage,5,1200,800,U,0.96,4,2,2\nCC1,2000,FEUILLE,Verre Trempé,2,2100,950,U,1.995,6.1,1,2\n"
          "CC2,1000,MIROIR,Miroir Argent,4,1500,600\nCC3,1000,VITR,Double Vitrage Argon,8,1800,1100\n"
          "CC4,1000,CAIS,Caisson bas,2,600,560\nCC4,2000,CAIS,Caisson haut,2,600,350\nCC4,3000,CAIS,Caisson colonne,2,600,2000\n")


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
                   [("DEC", "DEC1"), ("FAC", "FAC1"), ("TRE", "TRE1")], 1200, 800, "4/16/4")  # OF1-01
    depot.creer_of("CC2", "MIROIR", "Miroir Argent", "1500 x 600 mm", 4, "CC2-1000",
                   [("DEC", "DEC1"), ("FAC", "FAC1")])                                      # OF2-01 (ancien format)
    conn.close()
    with open(os.path.join(dossier, "config_poste.json"), "w", encoding="utf-8") as f:
        json.dump({"poste": "DEC1 - Découpe Numérique SEKTOR", "base_de_donnees": os.path.join(dossier, "test.db"),
                   "dossier_sage": os.path.join(dossier, "data")}, f)


SAUT_WINDOWS_CI = unittest.skipIf(sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS"),
                                  "vérifié par l'auto-vérification de l'exe sous Windows")


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
        self.assertEqual(dlg.result, "OF3-01")
        of = self.app.recharger_etat().ofs["OF3-01"]
        self.assertEqual((of.longueur, of.largeur, of.qte), (1800, 1100, 8))
        self.assertEqual(self.app.etat.gamme("OF3-01"), [("DEC", None), ("FAC", None), ("TRE", None)])

    def test_01_creation_of_ligne_deja_prise(self):
        # La ligne CC3-1000 est dans OF3-01 (test_01) : elle porte l'indicateur et ne peut pas servir à un 2e OF
        self.app.refresh_dashboard()
        self.app.tree_be_cmd.selection_set("CC3")
        self.app.on_be_order_select()
        self.assertEqual(self.app.tree_be_sage.item("CC3-1000", "values")[-1], "✓ OF3-01")
        self.assertEqual(self.app.tree_be_sage.item("CC3-1000", "tags")[0], "affectee")
        self.app.tree_be_sage.selection_set("CC3-1000")
        del self.messages[:]
        self.app.add_of_dialog()
        self.assertEqual(self.messages, ["showwarning"], "création refusée avant même d'ouvrir la fenêtre")
        self.assertEqual(len(self.app.recharger_etat().ofs_par_cde["CC3"]), 1)

        # Même si la fenêtre a été ouverte avant (autre poste), l'enregistrement est refusé avec un message
        from admiral.ui.dialogs import AddOfDialog
        dlg = AddOfDialog(self.root, self.app.depot, "CC3", lignes_sage="CC3-1000")
        dlg.choisir_produit("VITR")
        dlg.save()
        self.assertIsNone(dlg.result)
        self.assertIn("OF3-01", dlg.lbl_erreur.cget("text"))
        dlg.destroy()

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
        self.app.process_scan("of1-01")   # douchette en minuscules
        self.assertEqual(self.scans("OF1-01", "DEC"), 1)
        self.assertEqual(self.bandeau()[0], "Pièce enregistrée")
        self.assertEqual(self.app.lbl_scan_compte.cget("text"), "1 / 7")
        self.poste("USI1")
        self.app.process_scan("OF1-01")
        self.assertEqual(self.bandeau()[0], "Scan refusé")
        self.assertIn("ne passe pas par l'opération USI", self.bandeau()[1])
        self.poste("FAC1")
        self.app.process_scan("OF1-01")
        self.assertEqual(self.scans("OF1-01", "FAC"), 1)
        self.app.process_scan("OF1-01")
        self.assertIn("Bloqué : étape précédente (DEC) à 1/7", self.bandeau()[1])
        self.app.process_scan("ART-CC1-1000")
        self.assertEqual(self.bandeau()[0], "Code inconnu")

    def test_04_terminer_avec_rattrapage(self):
        self.poste("TRE1")
        self.app.ajouter_scans_manuels("OF1-01", "all")
        self.assertEqual([self.scans("OF1-01", op) for op in ("DEC", "FAC", "TRE")], [7, 7, 7])

    def test_05_annulations(self):
        self.app.retirer_scans_manuels("OF1-01", 2)
        self.assertEqual(self.scans("OF1-01", "TRE"), 5)
        type(self).reponse_oui_non = False          # « Tout annuler » refusé : rien ne change
        self.app.retirer_scans_manuels("OF1-01", "all")
        self.assertEqual(self.scans("OF1-01", "TRE"), 5)
        type(self).reponse_oui_non = True
        self.app.retirer_scans_manuels("OF1-01", "all")
        self.assertEqual(self.scans("OF1-01", "TRE"), 0)
        self.assertEqual(self.messages[-1], "askyesno")

    def lignes_au_poste(self, id_of, op, poste):
        self.app.recharger_etat()
        vue = self.app._vue_of(self.app.etat.ofs[id_of], op, poste, self.app.depot.libelles_operations())
        return [l.scans for l in vue.lignes]

    def test_05_b_moins_un_sur_la_ligne_cliquee(self):
        # OF de 3 lignes de 2 pièces, scanné 4 fois à la douchette : lignes 2 / 2 / 0
        id_of = self.app.depot.creer_of("CC4", "VITR", "Caissons", "", 6, "CC4-1000,CC4-2000,CC4-3000",
                                        [("DEC", "DEC1"), ("FAC", "FAC1")])
        self.cc4 = id_of
        self.poste("DEC1")
        for _ in range(4):
            self.app.process_scan(id_of)
        self.assertEqual(self.lignes_au_poste(id_of, "DEC", "DEC1"), [2, 2, 0])
        # −1 sur la 1re ligne : c'est elle qui baisse, pas la dernière remplie
        self.app.retirer_scans_manuels(id_of, 1, "CC4-1000")
        self.assertEqual(self.lignes_au_poste(id_of, "DEC", "DEC1"), [1, 2, 0])
        self.app.retirer_scans_manuels(id_of, 1, "CC4-2000")
        self.assertEqual(self.lignes_au_poste(id_of, "DEC", "DEC1"), [1, 1, 0])
        self.app.ajouter_scans_manuels(id_of, 1, "CC4-2000")
        self.assertEqual(self.lignes_au_poste(id_of, "DEC", "DEC1"), [1, 2, 0])

        # Une pièce déjà passée à l'étape suivante ne peut pas être défaite
        self.poste("FAC1")
        self.app.ajouter_scans_manuels(id_of, 1, "CC4-1000")
        self.assertEqual(self.lignes_au_poste(id_of, "FAC", "FAC1"), [1, 0, 0])
        self.poste("DEC1")
        self.app.retirer_scans_manuels(id_of, 1, "CC4-1000")
        self.assertEqual(self.bandeau()[0], "Annulation impossible")
        self.assertEqual(self.lignes_au_poste(id_of, "DEC", "DEC1"), [1, 2, 0])
        self.app.retirer_scans_manuels(id_of, "all")      # OF entier : 3 à DEC dont 1 déjà en FAC -> 2 annulées
        self.assertEqual(self.scans(id_of, "DEC"), 1)
        self.app.ajouter_scans_manuels(id_of, 2, "CC4-2000")   # remet la commande dans un état connu
        self.assertEqual(self.lignes_au_poste(id_of, "DEC", "DEC1"), [1, 2, 0])

    def test_05_c_ajouter_et_retirer_des_lignes_d_un_of(self):
        id_of = next(of.id for of in self.app.recharger_etat().ofs_par_cde["CC4"])
        self.app.refresh_dashboard()
        self.app.tree_be_cmd.selection_set("CC4")
        self.app.on_be_order_select()
        # Ligne 3000 sans pièce : retirée, l'OF passe de 6 à 4 pièces et la ligne redevient libre
        self.app.tree_be_of.selection_set(f"{id_of}_CC4-3000")
        self.app._maj_boutons_of()
        self.assertEqual(self.app.btn_supprimer_of.cget("text"), "Retirer la ligne")
        self.app.supprimer_of_be()
        of = self.app.recharger_etat().ofs[id_of]
        self.assertEqual((of.qte, of.lignes_sage), (4, "CC4-1000,CC4-2000"))
        self.assertEqual(self.app.tree_be_sage.item("CC4-3000", "values")[-1], "")
        # Ligne 1000 déjà commencée : refus
        del self.messages[:]
        self.app.tree_be_of.selection_set(f"{id_of}_CC4-1000")
        self.app.supprimer_of_be()
        self.assertEqual(self.messages, ["showwarning"])
        self.assertIn("CC4-1000", self.app.recharger_etat().ofs[id_of].lignes_sage)
        # On la rajoute : lignes sélectionnées en haut + OF sélectionné en bas
        self.app.tree_be_sage.selection_set("CC4-3000")
        self.app.tree_be_of.selection_set(id_of)
        self.app._maj_boutons_of()
        self.assertEqual(self.app.btn_ajouter_lignes.cget("text"), f"Ajouter à {id_of}")
        self.app.ajouter_lignes_be()
        of = self.app.recharger_etat().ofs[id_of]
        self.assertEqual(of.qte, 6)
        self.assertEqual(self.app.depot.lignes_affectees("CC4")["CC4-3000"], id_of)
        self.assertEqual(self.app.tree_be_sage.item("CC4-3000", "values")[-1], f"✓ {id_of}")

    def test_05_d_designation_du_produit(self):
        from admiral.ui.dialogs import AddOfDialog
        dlg = AddOfDialog(self.root, self.app.depot, "CC4", lignes_sage="CC4-1000")
        dlg.choisir_produit("MIROIR")
        self.assertEqual(dlg.design_entry.get(), "Miroir Argent")
        dlg.choisir_produit("VITR")
        self.assertEqual(dlg.design_entry.get(), "Double Vitrage Isolant", "suit le produit tant qu'on n'y touche pas")
        dlg.design_entry.delete(0, "end")
        dlg.design_entry.insert(0, "Caisson spécial")
        dlg.choisir_produit("MIROIR")
        self.assertEqual(dlg.design_entry.get(), "Caisson spécial", "texte saisi à la main conservé")
        dlg.destroy()

    def test_05_e_dimensions_de_la_commande_non_modifiables(self):
        from admiral.ui.dialogs import AddOfDialog
        dlg = AddOfDialog(self.root, self.app.depot, "CC4", default_qte=2, lignes_sage="CC4-1000", longueur=600, largeur=560,
                          dimensions_sage=True)
        # Quantité et longueur × largeur : pas de champ, valeurs des lignes de commande (plus d'épaisseur du tout)
        self.assertEqual(dlg.qte_entry.master.winfo_manager(), "")
        self.assertEqual(dlg.longueur_entry.master.winfo_manager(), "", "ligne des dimensions retirée")
        self.assertFalse(hasattr(dlg, "epaisseur_entry"))
        valeurs = dlg.lire_champs_communs()
        self.assertEqual((valeurs["qte"], valeurs["longueur"], valeurs["largeur"]), (2, 600, 560))
        dlg.destroy()
        sans_ligne = AddOfDialog(self.root, self.app.depot, "CC4")   # OF sans ligne : tout se saisit
        self.assertEqual(sans_ligne.qte_entry.master.winfo_manager(), "grid")
        sans_ligne.destroy()
        from admiral.domain import sage
        self.assertEqual(sage.dimensions_communes([{"LONG": "600", "LARG": "560"}, {"LONG": "600.0", "LARG": "560"}]), (600, 560))
        self.assertEqual(sage.dimensions_communes([{"LONG": "600", "LARG": "560"}, {"LONG": "600", "LARG": "350"}]), (None, None))

    def test_05_f_of_annule_depuis_un_autre_pc(self):
        # La carte est encore affichée au poste quand le Bureau d'étude annule l'OF : +1, Terminer et −1 refusés
        id_of = next(of.id for of in self.app.recharger_etat().ofs_par_cde["CC4"])
        avant = self.scans(id_of, "DEC")
        self.app.depot.changer_statut_of(id_of, "annule")
        self.poste("DEC1")
        self.app.ajouter_scans_manuels(id_of, "all")
        self.assertEqual(self.bandeau()[0], "Action refusée")
        self.app.retirer_scans_manuels(id_of, 1)
        self.assertEqual(self.scans(id_of, "DEC"), avant)
        self.app.depot.changer_statut_of(id_of, "actif")

    def test_06_cartes_et_matrice_coherentes(self):
        self.poste("DEC1")
        self.app.process_scan("OF2-01")
        self.app.process_scan("OF2-01")
        carte = self.app.cartes["OF2-01"]
        widget_avant = carte
        vue = self.app._vue_of(self.app.etat.ofs["OF2-01"], "DEC", "DEC1", self.app.depot.libelles_operations())
        self.assertEqual((vue.lignes[0].scans, vue.lignes[0].qte), (2, 4))
        self.assertEqual(vue.dimensions, "1500 x 600 mm")          # ancien OF : dimensions en observation
        self.assertEqual(vue.etat, "encours")
        self.app.process_scan("OF2-01")
        self.assertIs(self.app.cartes["OF2-01"], widget_avant, "carte mise à jour sur place, pas recréée")
        self.app.refresh_be_matrice()
        ligne = self.app.tree_matrice.get_children(self.app.tree_matrice.get_children("CDE:CC2")[0])[0]
        colonnes = list(self.app.tree_matrice["columns"])
        self.assertEqual(self.app.tree_matrice.item(ligne, "values")[colonnes.index("DEC")], "◐ 3/4")

    def test_07_liste_des_commandes(self):
        self.app.refresh_dashboard()
        numeros = list(self.app.tree_cmd.get_children())
        self.assertEqual(numeros, sorted(numeros, key=tri.cle_naturelle, reverse=True), "numéro décroissant par défaut")
        self.app.tri_commandes.set(tri.ETAT)
        self.app._appliquer_recherche()
        etats = [self.app.tree_cmd.item(i, "values")[3] for i in self.app.tree_cmd.get_children()]
        ordre = {"En cours": 0, "À faire": 1, "Terminée": 2}
        self.assertEqual(etats, sorted(etats, key=ordre.get))
        self.app.tri_commandes.set(tri.NUMERO)
        self.app._appliquer_recherche()
        self.assertEqual(list(self.app.tree_cmd.get_children()), numeros[::-1])
        self.app.tri_commandes.set(tri.DEFAUT)
        self.app.filtre_commandes.set("En cours")
        self.app._appliquer_recherche()
        self.assertTrue(all(self.app.tree_cmd.item(i, "values")[3] == "En cours" for i in self.app.tree_cmd.get_children()))
        self.app.filtre_commandes.set("Toutes")
        self.app._appliquer_recherche()

    def test_07_b_client_code_et_nom(self):
        # Partout où le code client apparaît, le nom du client l'accompagne ; le tri « Client » suit les noms
        self.app.refresh_dashboard()
        self.assertEqual(self.app.tree_cmd.item("CC1", "values")[1], "MIROITERIE DU NORD (C0101)")
        self.assertEqual(self.app.tree_be_cmd.item("CC4", "values")[1], "AGENCEMENT DU SUD (C0103)")
        self.app.tri_be_cmd.set(tri.CLIENT)
        self.app.refresh_dashboard()
        self.assertEqual(list(self.app.tree_be_cmd.get_children()), ["CC4", "CC3", "CC2", "CC1"])
        self.app.tri_be_cmd.set(tri.DEFAUT)
        self.app.refresh_dashboard()
        self.app.tree_be_cmd.selection_set("CC2")
        self.app.on_be_order_select()
        self.assertEqual(self.app.lbl_be_commande.cget("text"), "Commande CC2 · MENUISERIE DU CENTRE (C0104)")
        self.app.tree_cmd.selection_set("CC1")
        self.app.on_order_select()
        self.assertEqual(self.app.lbl_client.cget("text"), "MIROITERIE DU NORD (C0101)")

    def test_07_c_infos_sage_de_la_commande(self):
        # Atelier : réf. client, délai et observation sous le titre (pas la date de commande) ; chants dans les lignes
        self.poste("DEC1")
        self.app.refresh_dashboard()
        self.app.tree_cmd.selection_set("CC1")
        self.app.on_order_select()
        self.assertEqual(self.app.bandeau_commande.texte_affiche,
                         "EN ATTENTE MESURE Réf. client : Villa des Pins · Délai dépassé : 09/01")
        of = self.app.recharger_etat().ofs["OF1-01"]
        vue = self.app._vue_of(of, self.app.get_mon_op(), self.app.get_codpost(), self.app.depot.libelles_operations())
        self.assertEqual([l.details for l in vue.lignes],
                         ["Double Vitrage · 1200x800 · Chants 2H+2L", "Verre Trempé · 2100x950 · Chants 2H+1L"])
        # Bureau d'étude : avec la date de commande ; colonne Chants ; résumé de la sélection de lignes
        self.app.tree_be_cmd.selection_set("CC1")
        self.app.on_be_order_select()
        self.assertEqual(self.app.bandeau_be.texte_affiche,
                         "EN ATTENTE MESURE Réf. client : Villa des Pins · Commandée le 12/10/2025 · Délai dépassé : 09/01")
        colonnes = list(self.app.tree_be_sage["columns"])
        valeurs = self.app.tree_be_sage.item("CC1-2000", "values")
        self.assertEqual((valeurs[colonnes.index("chants")], valeurs[colonnes.index("qte")]), ("2H+1L", "2"))
        self.assertIn("Sélectionnez des lignes", self.app.lbl_be_aide.cget("text"))
        self.app.tree_be_sage.selection_set(("CC1-1000", "CC1-2000"))
        self.app._on_select_lignes_be()
        self.assertEqual(self.app.lbl_be_aide.cget("text"), "Sélection : 2 lignes · 7 pièces · 8,79 m² · 32,2 ml de chant")
        self.app.tree_be_sage.selection_remove(self.app.tree_be_sage.selection())
        self.app._on_select_lignes_be()
        self.assertIn("Sélectionnez des lignes", self.app.lbl_be_aide.cget("text"))
        self.app.tree_be_cmd.selection_set("CC2")
        self.app.on_be_order_select()
        self.assertEqual(self.app.bandeau_be.texte_affiche, "Commandée le 12/10")
        # Pilotage : vue de production, sans la date de commande
        self.app.filtre_pilotage.set("Toutes")
        self.app.refresh_pilotage()
        self.app.tree_pil_cmd.selection_set("CC1")
        self.app._afficher_commande_pilotage()
        self.assertEqual(self.app.bandeau_pilotage.texte_affiche,
                         "EN ATTENTE MESURE Réf. client : Villa des Pins · Délai dépassé : 09/01")
        self.app.tree_pil_cmd.selection_remove("CC1")
        self.app._afficher_commande_pilotage()
        self.assertEqual(self.app.bandeau_pilotage.texte_affiche, "")
        self.app.filtre_pilotage.set("À traiter")

    @SAUT_WINDOWS_CI
    def test_07_d_infos_sage_dans_la_modification_d_of(self):
        # Délai rappelé à côté de la date de besoin, chants dans les lignes (fenêtre avec les données Sage,
        # comme test_27 : ouverte par l'auto-vérification de l'exe sous Windows)
        from admiral.ui.dialogs import ModifierOfDialog
        of = self.app.recharger_etat().ofs["OF1-01"]
        dlg = ModifierOfDialog(self.root, self.app.depot, of, sage=self.app.sage, cloturees=self.app.etat.cloturees)
        self.assertEqual(dlg.lbl_aide_besoin.cget("text"), "Délai Sage dépassé : 09/01")
        textes = [case.cget("text") for case in dlg.cadre_lignes.winfo_children()]
        self.assertIn("Ligne 1000 · VITR · 5 p. · 1200x800 · chants 2H+2L", textes)
        dlg.destroy()

    def test_08_recherches_separees(self):
        self.app.search_entry.insert(0, "miroiterie")
        self.app.on_search_change()
        self.assertIsNotNone(self.app._recherche_timer)
        self.app._appliquer_recherche()
        self.assertEqual(self.app.tree_cmd.get_children(), ("CC1",))
        self.assertEqual(len(self.app.tree_be_cmd.get_children()), 4, "la recherche Atelier ne filtre pas le Bureau d'Étude")
        self.app.search_entry.delete(0, "end")
        self.app.search_entry.insert(0, "c0104")   # par le code client aussi
        self.app._appliquer_recherche()
        self.assertEqual(self.app.tree_cmd.get_children(), ("CC2",))
        for recherche in ("villa des pins", "attente mesure"):   # par la réf. client et l'observation de Sage
            self.app.search_entry.delete(0, "end")
            self.app.search_entry.insert(0, recherche)
            self.app._appliquer_recherche()
            self.assertEqual(self.app.tree_cmd.get_children(), ("CC1",), recherche)
        self.app.search_entry.delete(0, "end")
        self.app._appliquer_recherche()

    def test_09_creation_of_onglet(self):
        self.app.tree_be_cmd.selection_set("CC1")
        self.app.on_be_order_select()
        self.assertEqual(self.app.tree_be_sage.get_children(), ("CC1-1000", "CC1-2000"))
        self.assertEqual(len(self.app.tree_be_of.get_children("OF1-01")), 2)
        self.assertEqual(self.app.tree_be_of.item("OF1-01", "values")[3], "1200 × 800 mm", "épaisseur plus affichée")
        commandes = list(self.app.tree_be_cmd.get_children())
        self.assertEqual(commandes, sorted(commandes, key=tri.cle_naturelle, reverse=True), "numéro décroissant par défaut")
        # Changer le tri des OF garde l'OF sélectionné
        self.app.tree_be_of.selection_set("OF1-01")
        self.app.tri_be_of.set(tri.NUMERO)
        self.app.on_be_order_select()
        ofs = list(self.app.tree_be_of.get_children())
        self.assertEqual(ofs, sorted(ofs, key=tri.cle_naturelle))
        self.assertEqual(self.app.tree_be_of.selection(), ("OF1-01",))
        self.app.tri_be_of.set(tri.DEFAUT)

    def test_10_charge_et_navigation(self):
        self.app.refresh_be_charge()
        self.assertEqual(self.app.poste_charge, "DEC1", "poste de ce PC par défaut")
        self.assertIn("OF2-01", self.app.contenu_charge["encours"])
        self.app.selectionner_of_be("OF2-01")
        self.assertEqual(self.app.notebook.get(), self.app.NOM_ONGLET_GENERATION)
        self.assertEqual(self.app.tree_be_of.selection(), ("OF2-01",))

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
        of = self.app.recharger_etat().ofs["OF3-01"]
        dlg = ModifierOfDialog(self.root, self.app.depot, of, deja_scannees=0)
        dlg.besoin_entry.insert(0, "01/01/2020")
        dlg.urgent_var.set(True)
        dlg.save()
        self.assertEqual(dlg.result, "OF3-01")
        of = self.app.recharger_etat().ofs["OF3-01"]
        self.assertEqual((of.date_besoin, of.priorite), ("2020-01-01", 1))
        self.poste("DEC1")
        self.app._afficher_commande("CC3")
        carte = self.app.cartes["OF3-01"]
        self.assertTrue(carte._urgent_visible)
        self.assertIn("En retard", carte.lbl_besoin.cget("text"))

    def test_15_quantite_minimum_a_la_modification(self):
        from admiral.ui.dialogs import ModifierOfDialog
        # OF saisi sans ligne de commande : sa quantité se modifie, jamais sous les pièces déjà faites
        id_of = self.app.depot.creer_of("CC2", "MIROIR", "Miroir hors commande", "", 4, "", [("DEC", None)])
        of = self.app.recharger_etat().ofs[id_of]
        dlg = ModifierOfDialog(self.root, self.app.depot, of, deja_scannees=3)
        dlg.qte_entry.delete(0, "end")
        dlg.qte_entry.insert(0, "2")
        dlg.save()
        self.assertIn("au moins 3", dlg.lbl_erreur.cget("text"))
        dlg.destroy()
        self.app.depot.supprimer_of(id_of)
        avec_lignes = ModifierOfDialog(self.root, self.app.depot, self.app.recharger_etat().ofs["OF2-01"], 3)
        self.assertEqual(avec_lignes.qte_entry.master.winfo_manager(), "", "quantité = somme des lignes")
        avec_lignes.destroy()

    def test_16_annuler_et_reactiver_of(self):
        self.app.notebook.set(self.app.NOM_ONGLET_GENERATION)
        self.app.tree_be_cmd.selection_set("CC3")
        self.app.on_be_order_select()
        self.app.tree_be_of.selection_set("OF3-01")
        self.app._maj_boutons_of()
        self.app.basculer_annulation_of()
        self.assertTrue(self.app.etat.ofs["OF3-01"].annule)
        self.assertEqual(self.app.tree_be_of.item("OF3-01", "values")[6], "Annulé")
        self.assertEqual(self.app.btn_annuler_of.cget("text"), "Réactiver l'OF")
        self.app.process_scan("OF3-01")
        self.assertIn("annulé", self.bandeau()[1])
        self.app.notebook.set(self.app.NOM_ONGLET_GENERATION)
        self.app.tree_be_of.selection_set("OF3-01")
        self.app.basculer_annulation_of()
        self.assertFalse(self.app.recharger_etat().ofs["OF3-01"].annule)

    def test_17_supprimer_of(self):
        self.app.tree_be_cmd.selection_set("CC1")
        self.app.on_be_order_select()
        self.app.tree_be_of.selection_set("OF1-01")
        self.app.supprimer_of_be()                                  # déjà scanné : refusé
        self.assertEqual(self.messages[-1], "showwarning")
        self.assertIn("OF1-01", self.app.recharger_etat().ofs)
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
        self.app.process_scan("OF2-01")
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
        lignes = self.app.depot.historique_scans("OF1-01")
        dlg = HistoriqueDialog(self.root, self.app.etat.ofs["OF1-01"], lignes)
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
        self.assertEqual(len(self.app.tree_synthese_postes.get_children()), 5)

        # Avancement des commandes, dans la Synthèse : par numéro au départ, puis tri par état sur demande
        from admiral.domain.progression import ORDRE_ETATS
        arbre = self.app.tree_matrice
        numeros = [arbre.item(i, "text") for i in arbre.get_children()]
        self.assertEqual(numeros, sorted(numeros, key=tri.cle_naturelle, reverse=True), "numéro décroissant par défaut")
        self.app.tri_matrice.set(tri.ETAT)
        self.app.refresh_be_matrice()
        rangs = [ORDRE_ETATS[arbre.item(i, "tags")[0]] for i in arbre.get_children()]
        self.assertEqual(rangs, sorted(rangs), "tri : en cours, à faire, terminées")
        self.app.tri_matrice.set(tri.DEFAUT)
        self.assertTrue(arbre.exists("OF:OF3-01"), "OF rattaché à sa commande")

        # Ce qui est déplié, sélectionné et défilé survit à l'actualisation (automatique chaque minute)
        cde = arbre.parent("OF:OF3-01")
        arbre.item(cde, open=True)
        arbre.item("OF:OF3-01", open=True)
        arbre.selection_set("OF:OF3-01")
        self.app.refresh_synthese()
        self.assertTrue(arbre.item(cde, "open"))
        self.assertTrue(arbre.item("OF:OF3-01", "open"))
        self.assertEqual(arbre.selection(), ("OF:OF3-01",))
        autres = [i for i in arbre.get_children() if i != cde]
        self.assertTrue(autres and not any(arbre.item(i, "open") for i in autres), "les autres restent repliées")

        # Colonnes compactes mais en-têtes lisibles ; noms de poste abrégés avec « … » si la place manque
        from admiral.ui.composants import MARGE_COLONNE, abreger, polices_tableau
        police, police_entete = polices_tableau()
        for ref in arbre["columns"]:
            self.assertGreaterEqual(arbre.column(ref, "width"), police_entete.measure(arbre.heading(ref, "text")) + MARGE_COLONNE)
        self.assertEqual(abreger("DEC1 · Découpe", police, 1000), "DEC1 · Découpe")
        court = abreger("DEC1 · Découpe Numérique SEKTOR", police, police.measure("DEC1 · Découpe"))
        self.assertTrue(court.startswith("DEC1") and court.endswith("…"))
        self.assertLessEqual(police.measure(court), police.measure("DEC1 · Découpe"))

        # Double-clic sur un OF : ouverture dans Création d'OF
        self.app._ouvrir_depuis_avancement()
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
        # À ce stade, les quatre commandes du jeu de test ont toutes au moins un OF
        def etats():
            return [self.app.tree_be_cmd.item(i, "values")[2] for i in self.app.tree_be_cmd.get_children()]
        self.app.notebook.set(self.app.NOM_ONGLET_GENERATION)
        self.app.filtre_be.set("Sans OF")
        self.app.refresh_dashboard()
        self.assertEqual(self.app.tree_be_cmd.get_children(), ())
        self.assertEqual(self.app.lbl_nb_commandes_be.cget("text"), "0 commande")
        self.app.filtre_be.set("Avec OF")
        self.app.refresh_dashboard()
        self.assertEqual(len(self.app.tree_be_cmd.get_children()), 4)
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
    # Sur le serveur Windows de GitHub, ces tests font planter Tk (fenêtre masquée, après des dizaines de
    # fenêtres ouvertes et fermées en rafale). Les deux modes y sont vérifiés par l'auto-vérification
    # de l'exécutable réel (étape « Auto-vérification de l'exe »).

    def passer_en(self, poste):
        # Sans root.update() : sous Windows, traiter ici les événements laissés par les fenêtres ouvertes
        # et fermées en rafale par les tests précédents fait planter Tk (artefact propre aux tests).
        self.app.poste_actuel = poste
        self.app._maj_entete_poste()
        self.app._appliquer_mode()
        self.app.refresh_dashboard()

    @SAUT_WINDOWS_CI
    def test_24_poste_machine_atelier_seul(self):
        self.passer_en(next(p for p in self.app.libelles_postes() if p.startswith("DEC1 ")))
        self.assertEqual(self.app.tab_atelier.winfo_manager(), "pack", "écran Atelier affiché")
        self.assertEqual(self.app.notebook.winfo_manager(), "", "onglets du Bureau d'étude masqués")
        self.assertIn("Poste DEC1", self.app.lbl_title.cget("text"))

    @SAUT_WINDOWS_CI
    def test_25_bureau_etude_sans_atelier(self):
        from admiral.config import POSTE_BUREAU_ETUDE
        self.passer_en(POSTE_BUREAU_ETUDE)
        try:
            onglets = list(self.app.notebook._segmented_button.cget("values"))
            self.assertEqual(onglets, [self.app.NOM_ONGLET_SYNTHESE, self.app.NOM_ONGLET_PILOTAGE, self.app.NOM_ONGLET_GENERATION,
                                       self.app.NOM_ONGLET_CHARGE, self.app.NOM_ONGLET_ADMIN, self.app.NOM_ONGLET_VALIDATIONS])
            barre = self.app.notebook._segmented_button
            self.assertTrue(all(barre._buttons_dict[o].winfo_manager() for o in onglets), "tous visibles au Bureau d'étude")
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
            self.app.process_scan("OF1-01")
            self.assertEqual(self.app.notebook.get(), self.app.NOM_ONGLET_SYNTHESE, "un scan ne ramène pas à l'Atelier")
            # Avancement global (tous postes) : CC1 a des pièces sorties de la dernière opération
            self.assertEqual(self.app.tree_be_cmd.item("CC1", "values")[2], "En cours")
            self.app.refresh_be_charge()
            self.assertEqual(self.app.poste_charge, "DEC1", "Charge ouverte sur le premier poste")
        finally:
            self.passer_en(next(p for p in self.app.libelles_postes() if p.startswith("DEC1 ")))

    @SAUT_WINDOWS_CI
    def test_27_correction_complete_d_un_of(self):
        from admiral.ui.dialogs import ModifierOfDialog
        self.poste("DEC1")
        id_of = self.app.depot.creer_of("CC3", "MIROIR", "Miroir Argent", "", 8, "", [("DEC", None), ("FAC", None)])
        of = self.app.recharger_etat().ofs[id_of]
        dlg = ModifierOfDialog(self.root, self.app.depot, of, sage=self.app.sage, cloturees=self.app.etat.cloturees)
        # Mauvais produit : le bon produit reprend sa gamme standard et sa désignation
        dlg.var_prod.set(next(l for l in dlg._libelles_produits if l.startswith("VITR ")))
        dlg._changer_produit()
        self.assertEqual([e["code"] for e in dlg.etapes], ["DEC", "FAC", "TRE"])
        self.assertEqual(dlg.design_entry.get(), "Double Vitrage Isolant")
        # Gamme : TRE remonte en premier, FAC est retirée
        dlg._deplacer(2, -1)
        dlg._deplacer(1, -1)
        dlg._retirer_operation(2)
        self.assertEqual([e["code"] for e in dlg.etapes], ["TRE", "DEC"])
        # Mauvaise commande : on passe sur CC5 (commande sans OF, en mémoire le temps du test) et on prend deux lignes
        sage = self.app.sage
        lignes_cc5 = [(f"CC5-{n}", {"DO_Piece": "CC5", "DL_Ligne": str(n), "AR_Ref": "VITR", "DL_Design": "Vitrage",
                                    "DL_Qte": "2", "LONG": "500", "LARG": "400"}) for n in (1000, 2000)]
        sage.entetes["CC5"] = {"DO_Piece": "CC5", "DO_Tiers": "Client cinq"}
        sage.lignes_par_piece["CC5"] = lignes_cc5
        sage.lignes.update(lignes_cc5)
        self.addCleanup(lambda: (sage.entetes.pop("CC5"), sage.lignes_par_piece.pop("CC5"),
                                 [sage.lignes.pop(c) for c, _ in lignes_cc5]))
        dlg.combo_cde.configure(values=["CC3", "CC5"])
        dlg.var_cde.set("CC5")
        dlg._changer_commande()
        libres = ["CC5-1000", "CC5-2000"]
        self.assertEqual(list(dlg.vars_lignes), libres)
        for cle in libres[:2]:
            dlg.vars_lignes[cle].set(True)
        dlg._maj_selon_lignes()
        self.assertIn("4 pièces", dlg.lbl_total_lignes.cget("text"))
        # Plus aucune ligne : la quantité redevient saisissable
        for var in dlg.vars_lignes.values():
            var.set(False)
        dlg._maj_selon_lignes()
        self.assertEqual(dlg._ligne_qte.winfo_manager(), "grid")
        dlg.vars_lignes[libres[0]].set(True)
        dlg._maj_selon_lignes()
        dlg.save()
        # Nouvelle commande, nouveau numéro : le numéro d'un OF contient toujours celui de sa commande
        self.assertEqual(dlg.result, "OF5-01", dlg.lbl_erreur.cget("text"))
        self.assertIn("commande CC3 → CC5", dlg.resume)
        self.assertIn(f"numéro {id_of} → OF5-01", dlg.resume)
        etat = self.app.recharger_etat()
        self.assertNotIn(id_of, etat.ofs)
        of = etat.ofs["OF5-01"]
        self.assertEqual((of.cde, of.prod, of.qte, of.lignes_sage), ("CC5", "VITR", 2, libres[0]))
        self.assertEqual([c for c, _ in self.app.etat.gamme("OF5-01")], ["TRE", "DEC"])
        self.app.depot.supprimer_of("OF5-01")

    @SAUT_WINDOWS_CI   # ouvre des fenêtres : vérifiées par l'auto-vérification de l'exe sous Windows
    def test_28_operation_scannee_non_retirable(self):
        from admiral.ui.dialogs import ModifierOfDialog
        id_of = self.app.depot.creer_of("CC2", "MIROIR", "Miroir", "", 3, "", [("DEC", None), ("FAC", None)])
        self.app.depot.ajouter_scans(id_of, [("DEC1", 1)])
        dlg = ModifierOfDialog(self.root, self.app.depot, self.app.recharger_etat().ofs[id_of], sage=self.app.sage)
        self.assertEqual(str(dlg.combo_cde.cget("state")), "disabled", "OF scanné : commande figée")
        dlg._retirer_operation(0)
        self.assertEqual([e["code"] for e in dlg.etapes], ["DEC", "FAC"], "DEC a un scan : elle reste")
        dlg.destroy()

    def test_29_ecrans_suivent_les_autres_postes(self):
        """Un autre PC corrige un OF : ce poste le voit sans rien toucher (surveillance de la base)."""
        import sqlite3
        self.poste("DEC1")
        self.app._appliquer_mode()
        self.app.refresh_dashboard()
        self.app._afficher_commande("CC1")
        self.assertIn("OF1-01", self.app.cartes)
        autre_pc = Depot(sqlite3.connect(os.path.join(self.tmp.name, "test.db")))
        of = self.app.etat.ofs["OF1-01"]
        gamme = [(c, p) for _, c, p in autre_pc.gamme_of("OF1-01")]
        corriger = lambda design, etapes: autre_pc.corriger_of(
            "OF1-01", of.cde, of.prod, of.lignes_sage.split(","), etapes, design, of.observ, of.qte, of.longueur,
            of.largeur, of.epaisseur, of.date_besoin, of.priorite)
        id_nouveau = autre_pc.creer_of("CC1", "VITR", "Ajout", "", 1, "", [("DEC", None)])
        corriger("Corrigé au bureau", gamme + [("EMB", None)])
        self.app._surveiller_base()
        self.assertIn(id_nouveau, self.app.cartes, "OF créé sur un autre PC : sa carte apparaît")
        self.assertEqual(self.app.cartes["OF1-01"].lbl_design.cget("text"), "Corrigé au bureau")
        self.assertEqual(len(self.app.cartes["OF1-01"]._etapes), len(gamme) + 1, "frise à jour")
        corriger(of.design, gamme)
        autre_pc.supprimer_of(id_nouveau)
        autre_pc.conn.close()
        self.app._surveiller_base()
        self.assertNotIn(id_nouveau, self.app.cartes, "OF supprimé ailleurs : la carte disparaît")
        self.assertEqual(self.app.cartes["OF1-01"].lbl_design.cget("text"), of.design)

    @SAUT_WINDOWS_CI   # ouvre des fenêtres : vérifiées par l'auto-vérification de l'exe sous Windows
    def test_30_profil_chef_d_atelier(self):
        """Chef d'atelier : code personnel, onglets de pilotage seulement, validation reprise partout."""
        from admiral.config import POSTE_CHEF_ATELIER
        from admiral.ui.dialogs import ConfigDialog
        from admiral.ui.pilotage import ValidationDialog
        depot = self.app.depot
        # Premier accès : code par défaut tant qu'aucun chef n'existe ; ensuite, seulement les codes personnels
        self.assertEqual(self.app._chef_par_code("1111"), "Chef d'atelier")
        depot.enregistrer_chef("Karim", "4321")
        self.addCleanup(depot.supprimer_chef, "Karim")
        self.assertIsNone(self.app._chef_par_code("1111"))
        d = ConfigDialog(self.root, self.app.libelles_postes(), is_cancellable=True, actuel="DEC1 - Découpe Numérique SEKTOR",
                         chef_par_code=self.app._chef_par_code)
        d.cb.set(POSTE_CHEF_ATELIER)
        d._maj_code()
        d.code_entry.insert(0, "0000")
        d.on_validate()
        self.assertEqual(d.lbl_erreur.cget("text"), "Code incorrect.")
        d.code_entry.insert(0, "4321")
        d.on_validate()
        self.assertEqual((d.result, d.chef), (POSTE_CHEF_ATELIER, "Karim"))

        self.app.chef_actuel = "Karim"
        self.passer_en(POSTE_CHEF_ATELIER)
        try:
            barre = self.app.notebook._segmented_button
            visibles = [o for o in barre.cget("values") if barre._buttons_dict[o].winfo_manager()]
            self.assertEqual(visibles, [self.app.NOM_ONGLET_SYNTHESE, self.app.NOM_ONGLET_PILOTAGE,
                                        self.app.NOM_ONGLET_CHARGE, self.app.NOM_ONGLET_VALIDATIONS])
            self.assertEqual(self.app.notebook.get(), self.app.NOM_ONGLET_PILOTAGE)
            self.assertIn("Karim", self.app.lbl_title.cget("text"))
            self.assertEqual(self.app.signataire, "Karim")

            # Un OF neuf de CC2 (Découpe puis Façonnage), rien de scanné : le chef le valide en entier
            id_of = depot.creer_of("CC2", "MIROIR", "Miroir", "", 3, "", [("DEC", None), ("FAC", None)])
            self.addCleanup(depot.changer_statut_of, id_of, "annule")
            depot.ajouter_scans(id_of, [("DEC1", 1)])
            self.app.filtre_pilotage.set("Toutes")
            self.app.refresh_pilotage()
            self.app.tree_pil_cmd.selection_set("CC2")
            self.app._afficher_commande_pilotage()
            self.app.tree_pil_of.selection_set(id_of)
            self.app._maj_selection_pilotage()
            self.assertIn("○ Façonnage 0/3", self.app.tree_pil_of.item(id_of, "values")[3])
            dlg = ValidationDialog(self.root, depot, self.app.etat, [self.app.etat.ofs[id_of]], "Karim")
            dlg.save()
            self.assertEqual(dlg.lbl_erreur.cget("text"), "Choisissez un motif.", "motif obligatoire")
            dlg.choix_motif.set("Douchette en panne")
            dlg.save()
            self.assertEqual(dlg.result, [id_of])
            etat = self.app.recharger_etat()
            of = etat.ofs[id_of]
            self.assertTrue(etat.termine(of))
            self.assertEqual(etat.scans_reels(of.id, "DEC"), 1, "aucun faux scan")
            self.app._afficher_commande_pilotage()
            self.assertEqual(self.app.tree_pil_of.item(id_of, "values")[4], "Validé")
            self.assertIn("✓ Façonnage validée", self.app.tree_pil_of.item(id_of, "values")[3])
            self.app.refresh_validations()
            self.assertIn("Karim", [self.app.tree_validations.item(i, "values")[4] for i in self.app.tree_validations.get_children()])
        finally:
            self.passer_en(next(p for p in self.app.libelles_postes() if p.startswith("DEC1 ")))

        # Atelier : la carte dit qui a validé, plus de scan ni de +/−
        self.app._afficher_commande("CC2")
        carte = self.app.cartes[id_of]
        self.assertIn("Validé par Karim", carte.lbl_situation.cget("text"))
        self.assertEqual(str(carte.btn_moins.cget("state")), "disabled")
        self.app.process_scan(id_of)
        self.assertIn("validé par Karim", self.bandeau()[1])
        # Bureau d'étude : l'OF apparaît « Validé · Karim »
        self.assertEqual(self.app._etat_of_be(self.app.etat.ofs[id_of]), ("Validé · Karim", "valide"))
        # Annulation tracée : retour aux vrais scans, partout
        depot.annuler_validation([v.id for v in self.app.etat.validations[id_of]], "Karim")
        etat = self.app.recharger_etat()
        self.assertFalse(etat.termine(etat.ofs[id_of]))
        self.app._afficher_commande("CC2")
        self.assertNotIn("Validé", self.app.cartes[id_of].lbl_situation.cget("text"))
        self.assertEqual(depot.historique_validations(id_of)[0][8], 1, "annulation gardée dans l'historique")

    @SAUT_WINDOWS_CI   # ouvre des fenêtres : vérifiées par l'auto-vérification de l'exe sous Windows
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
