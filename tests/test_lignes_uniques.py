"""Une ligne de commande Sage ne peut appartenir qu'à un seul OF actif (migration 5, table OF_LignesSage)."""
import os
import sqlite3
import tempfile
import unittest

from admiral.db import schema
from admiral.db.depot import Depot, LigneDejaAffectee

GAMME = [("DEC", None)]


def compter_of(depot):
    return depot.conn.execute("SELECT COUNT(*) FROM CdeDetail").fetchone()[0]


class LignesUniques(unittest.TestCase):
    def setUp(self):
        self.depot = Depot(schema.ouvrir(":memory:"))

    def test_une_ligne_dans_un_seul_of(self):
        premier = self.depot.creer_of("CC1", "P", "A", "", 2, "CC1-1000,CC1-2000", GAMME)
        with self.assertRaises(LigneDejaAffectee) as erreur:
            self.depot.creer_of("CC1", "P", "B", "", 1, "CC1-2000,CC1-3000", GAMME)
        self.assertEqual(erreur.exception.deja, {"CC1-2000": premier})
        self.assertIn("ligne 2000", str(erreur.exception))
        self.assertEqual(compter_of(self.depot), 1, "rien n'est créé : ni l'OF, ni sa gamme, ni ses lignes")
        self.assertEqual(self.depot.conn.execute("SELECT COUNT(*) FROM OF_Gammes").fetchone()[0], 1)
        self.assertNotIn("CC1-3000", self.depot.lignes_affectees("CC1"))

    def test_cle_courte_et_cle_complete_designent_la_meme_ligne(self):
        self.depot.creer_of("CC1", "P", "A", "", 1, "1000", GAMME)   # ancien format de stockage
        with self.assertRaises(LigneDejaAffectee):
            self.depot.creer_of("CC1", "P", "B", "", 1, "CC1-1000", GAMME)

    def test_la_base_refuse_le_doublon_meme_sans_l_application(self):
        id_of = self.depot.creer_of("CC1", "P", "A", "", 1, "CC1-1000", GAMME)
        with self.assertRaises(sqlite3.IntegrityError):
            self.depot.conn.execute("INSERT INTO OF_LignesSage (CleLigne, ID_OF) VALUES ('CC1-1000', 'OF-9999')")
        self.assertEqual(self.depot.lignes_affectees("CC1"), {"CC1-1000": id_of})

    def test_lignes_affectees_par_commande(self):
        a = self.depot.creer_of("CC1", "P", "A", "", 1, "CC1-1000", GAMME)
        b = self.depot.creer_of("CC10", "P", "B", "", 1, "CC10-1000", GAMME)
        self.assertEqual(self.depot.lignes_affectees("CC1"), {"CC1-1000": a}, "CC10 n'est pas confondue avec CC1")
        self.assertEqual(self.depot.lignes_affectees("CC10"), {"CC10-1000": b})

    def test_of_sans_ligne(self):
        self.depot.creer_of("CC1", "P", "A", "", 1, "", GAMME)
        self.depot.creer_of("CC1", "P", "B", "", 1, "", GAMME)
        self.assertEqual(compter_of(self.depot), 2)

    def test_annuler_libere_reactiver_reprend(self):
        ancien = self.depot.creer_of("CC1", "P", "A", "", 1, "CC1-1000", GAMME)
        self.depot.changer_statut_of(ancien, "annule")
        self.assertEqual(self.depot.lignes_affectees("CC1"), {}, "l'OF annulé libère sa ligne")
        self.depot.changer_statut_of(ancien, "actif")
        self.assertEqual(self.depot.lignes_affectees("CC1"), {"CC1-1000": ancien}, "réactivé : il la reprend")

        self.depot.changer_statut_of(ancien, "annule")
        nouveau = self.depot.creer_of("CC1", "P", "B", "", 1, "CC1-1000", GAMME)
        with self.assertRaises(LigneDejaAffectee):
            self.depot.changer_statut_of(ancien, "actif")
        statut = self.depot.conn.execute("SELECT Statut FROM CdeDetail WHERE ID_OF = ?", (ancien,)).fetchone()[0]
        self.assertEqual(statut, "annule", "réactivation refusée : l'OF reste annulé")
        self.assertEqual(self.depot.lignes_affectees("CC1"), {"CC1-1000": nouveau})

    def test_supprimer_libere(self):
        id_of = self.depot.creer_of("CC1", "P", "A", "", 1, "CC1-1000", GAMME)
        self.depot.supprimer_of(id_of)
        self.assertEqual(self.depot.lignes_affectees("CC1"), {})
        self.depot.creer_of("CC1", "P", "B", "", 1, "CC1-1000", GAMME)


class MigrationCinq(unittest.TestCase):
    def test_reprise_des_of_existants_et_sauvegarde(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, "suivi_atelier.db")
            conn = sqlite3.connect(chemin)
            for migration in schema.MIGRATIONS[:4]:   # base telle que la laissait la version précédente
                migration(conn)
            conn.execute("PRAGMA user_version = 4")
            conn.executemany(
                "INSERT INTO CdeDetail (ID_OF, CDE, PROD, Qte, LignesSage, Statut) VALUES (?, ?, 'P', 1, ?, ?)",
                [("OF-1000", "CC1", "CC1-1000,CC1-2000", "actif"),
                 ("OF-1001", "CC1", "CC1-2000,3000", "actif"),       # doublon hérité + clé au format court
                 ("OF-1002", "CC1", "CC1-4000", "annule"),
                 ("OF-1003", "CC2", None, "actif")])
            conn.commit()
            conn.close()

            conn = schema.ouvrir(chemin)
            self.assertEqual(schema.version(conn), schema.VERSION_SCHEMA)
            self.assertEqual(Depot(conn).lignes_affectees("CC1"),
                             {"CC1-1000": "OF-1000", "CC1-2000": "OF-1000", "CC1-3000": "OF-1001"},
                             "doublon : le plus ancien OF garde la ligne ; l'OF annulé n'en garde aucune")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM CdeDetail").fetchone()[0], 4, "aucun OF perdu")
            self.assertEqual(conn.execute("SELECT LignesSage FROM CdeDetail WHERE ID_OF = 'OF-1001'").fetchone()[0],
                             "CC1-2000,3000", "colonne d'origine conservée")
            conn.close()

            copies = os.listdir(os.path.join(dossier, "sauvegardes"))
            self.assertEqual(len(copies), 1)
            self.assertIn("_v4_avant_v5_", copies[0])
            copie = sqlite3.connect(os.path.join(dossier, "sauvegardes", copies[0]))
            self.assertEqual(schema.version(copie), 4, "la copie est la base d'avant la mise à niveau")
            copie.close()

            schema.ouvrir(chemin).close()   # base déjà à jour : pas de nouvelle copie
            self.assertEqual(len(os.listdir(os.path.join(dossier, "sauvegardes"))), 1)


if __name__ == "__main__":
    unittest.main()
