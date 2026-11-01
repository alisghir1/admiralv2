import os
import sqlite3
import tempfile
import unittest

import preparer_livraison
from admiral.db import schema
from admiral.db.depot import Depot


class DossierLivraison(unittest.TestCase):
    def test_referentiel_seul_et_classeur(self):
        with tempfile.TemporaryDirectory() as d:
            source = os.path.join(d, "source.db")
            conn = schema.ouvrir(source)  # opérations et postes par défaut
            depot = Depot(conn)
            depot.enregistrer_produit("VITR", "Double vitrage", ["DEC", "FAC", "COL"])
            id_of = depot.creer_of("CC1", "VITR", "Vitrage", "", 2, "CC1-1000", [("DEC", "DEC1"), ("FAC", None)])
            depot.ajouter_scans(id_of, [("DEC1", 1)])
            conn.close()
            classeur = os.path.join(d, "BASE SAGE ADM.xlsx")
            with open(classeur, "wb") as f:
                f.write(b"classeur")
            sortie = os.path.join(d, "livraison", "Admiral")

            comptes = preparer_livraison.preparer(source, classeur, sortie)

            self.assertEqual(comptes["Produits"], 1)
            self.assertEqual(comptes["Gammes"], 3)
            self.assertTrue(os.path.isfile(os.path.join(sortie, "data", "BASE SAGE ADM.xlsx")))
            self.assertTrue(os.path.isfile(os.path.join(sortie, "LISEZMOI.txt")))
            livree = sqlite3.connect(os.path.join(sortie, "suivi_atelier.db"))
            self.assertEqual(schema.version(livree), schema.VERSION_SCHEMA)
            for table in ("CdeDetail", "OF_Gammes", "OF_LignesSage", "Scans", "SageCommandes"):
                self.assertEqual(livree.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)
            self.assertEqual(livree.execute("SELECT CodeOp FROM Gammes WHERE RefProd = 'VITR' ORDER BY Ordre").fetchall(),
                             [("DEC",), ("FAC",), ("COL",)])
            livree.close()

            anomalies = preparer_livraison.anomalies_referentiel(os.path.join(sortie, "suivi_atelier.db"))
            self.assertEqual(anomalies, ["gamme de VITR : « COL » n'est pas une opération"])

            with self.assertRaises(FileExistsError):
                preparer_livraison.preparer(source, classeur, sortie)


if __name__ == "__main__":
    unittest.main()
