import sqlite3
import unittest

from admiral.db import schema
from admiral.db.depot import Depot


class Schema(unittest.TestCase):
    def test_base_neuve(self):
        conn = schema.ouvrir(":memory:")
        self.assertEqual(schema.version(conn), schema.VERSION_SCHEMA)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM Postes").fetchone()[0], 5)

    def test_mise_a_niveau_ancienne_base(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript('''
            CREATE TABLE CdeDetail (ID_OF TEXT PRIMARY KEY, CDE TEXT, PROD TEXT, DESIGN TEXT, OBSERV TEXT, Qte INTEGER);
            CREATE TABLE Scans (ID_Scan INTEGER PRIMARY KEY AUTOINCREMENT, ID_OF TEXT, Poste TEXT, Timestamp DATETIME);
            INSERT INTO CdeDetail VALUES ('OF-1000', 'CC1', 'P', 'D', '', 3);
            INSERT INTO Scans (ID_OF, Poste) VALUES ('OF-1000', 'DEC1');
        ''')
        schema.initialiser(conn)
        self.assertIn("LignesSage", schema._colonnes(conn, "CdeDetail"))
        self.assertIn("Child_Key", schema._colonnes(conn, "Scans"))
        self.assertTrue({"Longueur", "Largeur", "Epaisseur"} <= schema._colonnes(conn, "CdeDetail"))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM Scans").fetchone()[0], 1)  # données conservées
        schema.initialiser(conn)  # idempotent
        self.assertEqual(schema.version(conn), schema.VERSION_SCHEMA)

    def test_base_plus_recente_refusee(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(f"PRAGMA user_version = {schema.VERSION_SCHEMA + 1}")
        with self.assertRaises(RuntimeError):
            schema.initialiser(conn)


class DepotTests(unittest.TestCase):
    def setUp(self):
        self.depot = Depot(schema.ouvrir(":memory:"))

    def test_numerotation_des_of(self):
        self.assertEqual(self.depot.creer_of("CC1", "P", "D", "", 2, "", [("DEC", None)]), "OF-1000")
        self.depot.conn.execute("INSERT INTO CdeDetail (ID_OF, CDE, Qte) VALUES ('OF-9999', 'X', 1)")
        self.assertEqual(self.depot.creer_of("CC1", "P", "D", "", 2, "", [("DEC", None)]), "OF-10000")

    def test_creation_scans_et_etat(self):
        id_of = self.depot.creer_of("CC1", "P", "D", "obs", 4, "CC1-1000", [("DEC", None), ("FAC", "FAC1")])
        self.depot.ajouter_scans(id_of, [("DEC1", 2)])
        self.depot.ajouter_scans(id_of, [("DEC1", 1)], child_key="CC1-1000")
        etat = self.depot.charger_etat()
        self.assertEqual(etat.gamme(id_of), [("DEC", None), ("FAC", "FAC1")])
        self.assertEqual(etat.compter(id_of, "DEC"), 3)
        self.assertEqual(etat.compter(id_of, "DEC", None), 2)
        self.assertEqual(etat.ofs_par_cde["CC1"][0].lignes_sage, "CC1-1000")

    def test_dimensions_de_l_of(self):
        id_of = self.depot.creer_of("CC1", "P", "D", "", 2, "", [("DEC", None)], longueur=1200, largeur=800, epaisseur="6")
        of = self.depot.charger_etat().ofs[id_of]
        self.assertEqual((of.longueur, of.largeur, of.epaisseur), (1200, 800, "6"))
        sans = self.depot.creer_of("CC1", "P", "D", "", 2, "", [("DEC", None)])
        self.assertEqual(self.depot.charger_etat().ofs[sans].epaisseur, "")

    def test_suppression_du_plus_recent(self):
        id_of = self.depot.creer_of("CC1", "P", "D", "", 4, "", [("DEC", None)])
        self.depot.ajouter_scans(id_of, [("DEC1", 3)])
        ids = self.depot.ids_scans(id_of, "DEC")
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.depot.annuler_scans(ids[:1])
        self.assertEqual(self.depot.charger_etat().compter(id_of, "DEC"), 2)


if __name__ == "__main__":
    unittest.main()
