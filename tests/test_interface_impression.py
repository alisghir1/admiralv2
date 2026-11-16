"""Interface : scan des articles et de la page d'essai, consigne à l'écran Atelier, fenêtre d'impression,
douchette reconnue partout (recherche, port COM), scan d'une commande, remise à zéro de l'atelier.

Base et exports Sage temporaires (ceux de test_interface) ; ignoré si aucun affichage n'est disponible.
Sur le serveur Windows de GitHub, une seconde fenêtre Tk dans le même processus est évitée : la logique est
vérifiée sans interface par test_impression, et l'auto-vérification de l'exe ouvre la fenêtre d'impression,
scanne le code d'essai et produit un PDF de chaque document."""
import os
import tempfile
import tkinter
import unittest
from tkinter import messagebox

from admiral import config
from admiral.domain import codes
from tests.test_interface import SAUT_WINDOWS_CI, creer_donnees


@SAUT_WINDOWS_CI
class AtelierEtImpression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import customtkinter as ctk
            cls.root = ctk.CTk()
        except tkinter.TclError as exc:
            raise unittest.SkipTest(f"pas d'affichage : {exc}")
        cls.root.withdraw()
        from admiral.ui import widgets
        widgets._ICONS_CACHE.clear()   # icônes d'une fenêtre Tk précédente (autre classe de tests) : à recréer
        cls.tmp = tempfile.TemporaryDirectory()
        creer_donnees(cls.tmp.name)
        cls._config_origine = config.CONFIG_FILE
        config.CONFIG_FILE = os.path.join(cls.tmp.name, "config_poste.json")
        cls._messagebox = {}
        for nom in ("showinfo", "showwarning", "showerror", "askyesno"):
            cls._messagebox[nom] = getattr(messagebox, nom)
            setattr(messagebox, nom, lambda *a, **k: True)
        from admiral.ui import impression
        cls._ouvrir, cls._dossier = impression.ouvrir_fichier, impression.DOSSIER_IMPRESSIONS
        cls.ouverts = []
        impression.ouvrir_fichier = cls.ouverts.append          # pas de lecteur PDF pendant les tests
        impression.DOSSIER_IMPRESSIONS = os.path.join(cls.tmp.name, "impressions")
        from admiral.ui.app import AdmiralApp
        cls.app = AdmiralApp(cls.root)

    @classmethod
    def tearDownClass(cls):
        from admiral.ui import impression
        impression.ouvrir_fichier, impression.DOSSIER_IMPRESSIONS = cls._ouvrir, cls._dossier
        cls.root.destroy()
        cls.app.depot.conn.close()
        config.CONFIG_FILE = cls._config_origine
        for nom, fonction in cls._messagebox.items():
            setattr(messagebox, nom, fonction)
        cls.tmp.cleanup()

    def poste(self, code):
        self.app.poste_actuel = next(p for p in self.app.libelles_postes() if p.startswith(code + " "))

    def bandeau(self):
        return self.app.lbl_scan_status.cget("text"), self.app.lbl_scan_detail.cget("text")

    def test_1_scan_d_un_article(self):
        self.poste("DEC1")
        self.app.process_scan("cc1-2000")
        self.assertEqual(self.bandeau()[0], "Pièce enregistrée")
        self.assertIn("ligne 2000", self.bandeau()[1])
        self.assertEqual(self.app.lbl_scan_compte.cget("text"), "1 / 2")
        self.assertEqual(self.app.recharger_etat().compter("OF1-01", "DEC", "CC1-2000"), 1, "compté sur la ligne")
        self.app.process_scan("CC1-2000")
        self.app.process_scan("CC1-2000")
        self.assertEqual(self.bandeau()[0], "Scan refusé")
        self.assertIn("Ligne 2000 déjà complète", self.bandeau()[1])
        self.app.process_scan("CC3-1000")
        self.assertEqual(self.bandeau()[0], "Article sans OF")

    def test_2_douchette_en_clavier_americain(self):
        self.poste("DEC1")
        self.app.process_scan(codes.CODE_ESSAI)
        self.assertEqual(self.bandeau()[0], "Douchette bien réglée")
        self.app.process_scan("TEST)à&é\"'(-è_ç)QWAZ?")
        self.assertEqual(self.bandeau()[0], "Douchette en clavier anglais")
        avant = self.app.recharger_etat().compter("OF1-01", "DEC")
        self.app.process_scan("OF&)à&")   # « OF1-01 » tapé en clavier américain
        self.assertEqual(self.bandeau()[0], "Pièce enregistrée")
        self.assertEqual(self.app.recharger_etat().compter("OF1-01", "DEC"), avant + 1)

    def test_3_scan_d_une_commande_par_son_numero(self):
        self.poste("DEC1")
        self.app.process_scan("CC2")
        self.assertEqual(self.app.commande_affichee, "CC2")
        self.assertEqual(self.bandeau()[0], "Commande CC2")

    def test_4_consigne_sur_la_carte_du_poste(self):
        depot = self.app.depot
        depot.corriger_of("OF1-01", "CC1", "VITR", ["CC1-1000", "CC1-2000"],
                          [("DEC", "DEC1", "Attention au sens du verre"), ("FAC", "FAC1", ""), ("TRE", "TRE1", "")],
                          "Double Vitrage", "", 7, 1200, 800, "4/16/4", None, 0)
        self.poste("DEC1")
        self.app.recharger_etat()
        self.app._afficher_commande("CC1")
        carte = self.app.cartes["OF1-01"]
        self.assertIn("Attention au sens du verre", carte.lbl_consigne.cget("text"))
        self.assertTrue(carte._consigne_visible)
        self.poste("FAC1")
        self.app._afficher_commande("CC1")
        self.assertFalse(self.app.cartes["OF1-01"]._consigne_visible, "consigne réservée au poste de l'étape")

    def test_5_fenetre_d_impression(self):
        from admiral.ui.impression import ImpressionDialog
        dlg = ImpressionDialog(self.root, self.app, "Impression", cde="CC1", ids_of=["OF1-01"], postes=["DEC1", "FAC1"],
                               etape="FAC", coches=("commande", "suiveuses", "etape", "etiquettes", "liste"))
        dlg.menu_poste.set("Tous les postes")
        dlg.mode_etiquettes.set("Une par pièce")
        types = [type(d).__name__ for d in dlg.documents()]
        self.assertEqual(types, ["FicheCommande", "FicheOF", "FicheEtape", "ListeTravail", "ListeTravail", "Etiquettes"])
        dlg.apercu()
        self.assertEqual(len(self.ouverts), 1)
        self.assertTrue(os.path.basename(self.ouverts[0]).startswith("CC1_"))
        with open(self.ouverts[0], "rb") as fichier:
            self.assertTrue(fichier.read(4) == b"%PDF")
        vide = ImpressionDialog(self.root, self.app, "Impression", postes=["DEC1"])
        vide.apercu()
        self.assertEqual(vide.lbl_message.cget("text"), "Cochez au moins un document.")
        vide.destroy()

    def test_6_douchette_reconnue_dans_la_recherche(self):
        class Touche:
            def __init__(self, widget, temps, char="", keysym=""):
                self.widget, self.time, self.char, self.keysym = widget, temps, char, keysym or char

        self.poste("DEC1")
        recherche = self.app.search_entry._entry
        recherche.delete(0, "end")
        recherche.insert(0, "mir")                            # quelqu'un cherchait une commande…
        avant = self.app.recharger_etat().compter("OF1-01", "DEC")
        for i, char in enumerate("OF1-01"):                   # … quand un scan arrive (4 ms entre les caractères)
            recherche.insert("end", char)                     # ce que fait le champ avec chaque touche
            self.app._touche_globale(Touche(recherche, 1000 + 4 * i, char))
        resultat = self.app._touche_globale(Touche(recherche, 1030, keysym="Return"))
        self.assertEqual(resultat, "break")
        self.assertEqual(recherche.get(), "mir", "le code tapé par la douchette est retiré de la recherche")
        self.assertEqual(self.app.recharger_etat().compter("OF1-01", "DEC"), avant + 1, "et le scan est enregistré")
        # Frappe humaine : rien ne se passe
        for i, char in enumerate("OF1-01"):
            self.app._touche_globale(Touche(recherche, 5000 + 150 * i, char))
        self.assertIsNone(self.app._touche_globale(Touche(recherche, 6000, keysym="Return")))
        self.assertEqual(self.app.recharger_etat().compter("OF1-01", "DEC"), avant + 1)
        recherche.delete(0, "end")

    def test_7_double_lecture_ignoree(self):
        self.poste("DEC1")
        avant = self.app.recharger_etat().compter("OF2-01", "DEC")
        self.app.scan_douchette("OF2-01")
        self.app.scan_douchette("OF2-01")                     # la douchette a lu deux fois la même étiquette
        self.assertEqual(self.app.recharger_etat().compter("OF2-01", "DEC"), avant + 1)

    def test_8_port_com(self):
        class DouchetteSimulee:
            connectee, etat = True, "connectée (COM9)"

            def __init__(self):
                self.file = ["OF2-01"]

            def codes(self):
                lus, self.file = self.file, []
                return lus

        self.poste("DEC1")
        self.app._anti_doublon.precedent = (None, -1e9)
        avant = self.app.recharger_etat().compter("OF2-01", "DEC")
        self.app.douchette_com = DouchetteSimulee()
        try:
            self.app._lire_douchette_com()
            self.assertEqual(self.app.recharger_etat().compter("OF2-01", "DEC"), avant + 1)
            self.assertEqual(self.app.lbl_focus_scan.cget("text"), "Douchette COM connectée")
        finally:
            self.app.douchette_com = None

    def test_9_commande_scannee_et_terminee_au_poste(self):
        self.poste("USI1")
        self.app.process_scan("CC2")
        self.assertEqual(self.bandeau()[0], "Pas pour ce poste")
        self.assertIn("Aucun OF de la commande CC2", self.bandeau()[1])
        self.app.process_scan("CC4")
        self.assertEqual(self.bandeau()[0], "Commande sans OF")
        self.poste("FAC1")
        self.app.process_scan("CC2")
        self.assertEqual(self.bandeau()[0], "Commande CC2")
        self.assertEqual(self.app.btn_terminer_commande.cget("state"), "normal")
        self.app.terminer_commande_poste()                    # confirmation acceptée (messagebox simulée)
        etat = self.app.recharger_etat()
        self.assertEqual((etat.compter("OF2-01", "DEC"), etat.compter("OF2-01", "FAC")), (4, 4),
                         "découpe complétée, façonnage terminé")
        self.assertEqual(self.app.btn_terminer_commande.cget("state"), "disabled")

    def test_z_remise_a_zero(self):
        self.app.depot.enregistrer_chef("Karim", "4321")
        self.app._maj_mise_en_service()
        self.assertIn("OF", self.app.lbl_contenu_atelier.cget("text"))
        self.app.champ_vider.insert(0, "non")
        self.app.remettre_atelier_a_zero()
        self.assertIn("Tapez VIDER", self.app.lbl_remise_info.cget("text"))
        self.assertTrue(self.app.depot.contenu_atelier()["OF"], "rien n'est effacé sans confirmation")
        self.app.champ_vider.delete(0, "end")
        self.app.champ_vider.insert(0, "vider")
        self.app.remettre_atelier_a_zero()
        contenu = self.app.depot.contenu_atelier()
        self.assertEqual((contenu["OF"], contenu["scans"], contenu["validations"]), (0, 0, 0))
        self.assertEqual(contenu["commandes"], 4, "les commandes en cours sont relues du classeur Sage")
        self.assertEqual(self.app.etat.ofs, {})
        self.assertEqual(self.app.depot.chef_par_code("4321"), "Karim")
        sauvegardes = os.listdir(os.path.join(self.tmp.name, "sauvegardes"))
        self.assertTrue(any("avant_remise_a_zero" in nom for nom in sauvegardes), "copie de la base avant le vidage")


if __name__ == "__main__":
    unittest.main()
