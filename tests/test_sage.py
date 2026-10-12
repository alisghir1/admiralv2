import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
