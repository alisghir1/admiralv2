import os
import tempfile
import unittest
from datetime import datetime

from admiral.domain import sage


class LectureSage(unittest.TestCase):
    def ecrire(self, dossier, nom, contenu, encodage="utf-8"):
        with open(os.path.join(dossier, nom), "w", encoding=encodage, newline="") as f:
            f.write(contenu)

    def test_virgule_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, "F-DOCENTETE.csv", "DO_Piece,DO_Date,DO_Tiers\nCC1,01/10/2026,CLIENT A\nFA9,01/10/2026,FACTURE\n")
            self.ecrire(d, "F-DOCLIGNE.csv", "DO_Piece,DL_Ligne,AR_Ref,DL_Qte,LONG,LARG\nCC1,1000,REF,5,1200,800\nCC1,2000,REF2,\"2,000\",,\n")
            donnees = sage.charger(d)
        self.assertEqual(list(donnees.entetes), ["CC1"])  # FA9 n'est pas une commande
        self.assertEqual(donnees.client("CC1"), "CLIENT A")
        self.assertEqual([c for c, _ in donnees.lignes_commande("CC1")], ["CC1-1000", "CC1-2000"])

    def test_point_virgule_cp1252(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, "F-DOCENTETE.csv", "DO_Piece;DO_Date;DO_Tiers\nCC2;01/10/2026;FAÇADES & VERRES\n", "cp1252")
            donnees = sage.charger(d)
        self.assertEqual(donnees.client("CC2"), "FAÇADES & VERRES")

    def test_dossier_absent(self):
        self.assertIsNone(sage.charger("/dossier/inexistant"))

    def test_lignes_enfants_et_quantites(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire(d, "F-DOCLIGNE.csv", "DO_Piece,DL_Ligne,DL_Qte,LONG,LARG\nCC1,1000,5.000,1200,800\nCC1,2000,\"2,000\",,\n")
            donnees = sage.charger(d)
        enfants = sage.lignes_enfants(donnees, "CC1", "CC1-1000, 2000, CC1-9999")
        self.assertEqual([(c, q) for c, q, _ in enfants], [("CC1-1000", 5), ("2000", 2)])
        self.assertEqual(sage.dimensions(enfants[0][2]), "1200x800")
        self.assertEqual(sage.dimensions(enfants[1][2]), "")

    def test_lire_qte(self):
        self.assertEqual(sage.lire_qte("3,000"), 3)
        self.assertEqual(sage.lire_qte("abc", 1), 1)
        self.assertEqual(sage.lire_qte(None, 0), 0)


try:
    import openpyxl
except ImportError:
    openpyxl = None

# Feuilles du classeur relié à Sage, avec les colonnes renommées par Excel
ENTETES_CLASSEUR = [
    ("TYPE", "CDE", "DATE", "CODECLI", "REFCLI", "DELAI", "CLIDIV", "OBSERV", "NUM"),
    (1, "CC1", datetime(2026, 7, 28), "CLI-A", "Chantier A", datetime(1753, 1, 1), None, "BLOQUEE", 29),
    (6, "FC9", datetime(2026, 7, 28), "CLI-B", "", datetime(1753, 1, 1), None, None, 30),
]
LIGNES_CLASSEUR = [
    ("TYPE", "NUMCLI", "CDE", "ART", "DESIGN", "UNIT", "QTE", "LIGNE", "NUM", "LONG", "LARG"),
    (1, "CLI-A", "CC1", "ART-1", "Caisson Colonne", "U", 3, 1000, 41, 2000.0, 600),
    (1, "CLI-A", "CC1", "ART-2", "Profil", "ML", 7.6, 2000, 42, None, None),
    (7, "CLI-B", "FC9", "ART-3", "Caisson Bas", "U", 2, 1000, 43, 700, 900),
]


@unittest.skipIf(openpyxl is None, "openpyxl absent")
class LectureClasseurSage(unittest.TestCase):
    def ecrire_classeur(self, chemin, feuilles):
        classeur = openpyxl.Workbook()
        classeur.remove(classeur.active)
        for nom, lignes in feuilles.items():
            feuille = classeur.create_sheet(nom)
            for ligne in lignes:
                feuille.append(ligne)
        classeur.save(chemin)

    def ecrire_classeur_sage(self, dossier, nom="BASE SAGE ADM.xlsx"):
        self.ecrire_classeur(os.path.join(dossier, nom), {"F-DOCENTETE": ENTETES_CLASSEUR, "F-DOCLIGNE": LIGNES_CLASSEUR})

    def test_colonnes_renommees_et_commandes_seules(self):
        with tempfile.TemporaryDirectory() as d:
            self.ecrire_classeur_sage(d)
            donnees = sage.charger(d)
        self.assertEqual(list(donnees.entetes), ["CC1"])  # FC9 est une facture
        self.assertEqual(donnees.client("CC1"), "CLI-A")
        entete = donnees.entetes["CC1"]
        self.assertEqual((entete["DO_Coord01"], entete["DO_Date"], entete["DO_DateLivr"], entete["OBSERV"]),
                         ("Chantier A", "2026-07-28", "", "BLOQUEE"))  # 01/01/1753 : date vide de Sage
        self.assertEqual([c for c, _ in donnees.lignes_commande("CC1")], ["CC1-1000", "CC1-2000"])
        ligne = donnees.lignes["CC1-1000"]
        self.assertEqual((ligne["AR_Ref"], ligne["DL_Qte"], ligne["DL_Ligne"]), ("ART-1", "3", "1000"))
        self.assertEqual(sage.dimensions(ligne), "2000x600")  # 2000.0 lu comme 2000
        self.assertEqual(sage.dimensions(donnees.lignes["CC1-2000"]), "")
        self.assertEqual(donnees.lignes["CC1-2000"]["DL_Qte"], "7.6")
        self.assertTrue(sage.fabricable(ligne))

    def test_classeur_prioritaire_sur_les_csv(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "F-DOCLIGNE.csv"), "w", encoding="utf-8") as f:
                f.write("DO_Piece,DL_Ligne,AR_Ref,DL_Qte\nCC5,1000,REF,1\n")
            self.ecrire_classeur_sage(d)
            donnees = sage.charger(d)
        self.assertEqual(list(donnees.lignes_par_piece), ["CC1"])
        self.assertTrue(donnees.source.endswith("BASE SAGE ADM.xlsx"))

    def test_autres_classeurs_ignores(self):
        # Le référentiel (PRODUIT, GAMPROD…) n'est pas un classeur de commandes ; « ~$ » est le verrou d'Excel
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "F-DOCLIGNE.csv"), "w", encoding="utf-8") as f:
                f.write("DO_Piece,DL_Ligne,AR_Ref,DL_Qte\nCC5,1000,REF,1\n")
            self.ecrire_classeur(os.path.join(d, "BASE SAGE ADMIRAL.xlsx"), {"PRODUIT": [("RefProd", "DesProd")]})
            with open(os.path.join(d, "~$BASE SAGE ADM.xlsx"), "wb") as f:
                f.write(b"verrou")
            donnees = sage.charger(d)
        self.assertEqual(list(donnees.lignes_par_piece), ["CC5"])

    def test_classeur_illisible(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "BASE SAGE ADM.xlsx"), "wb") as f:
                f.write(b"enregistrement en cours")
            with self.assertRaises(sage.SageIllisible):
                sage.charger(d)


if __name__ == "__main__":
    unittest.main()
