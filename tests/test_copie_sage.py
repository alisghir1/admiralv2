import os
import tempfile
import unittest

from admiral.db import schema
from admiral.db.depot import Depot
from admiral.domain import sage


def lecture(date_source, commandes):
    """Lecture Sage simulée : commandes = {DO_Piece: {DL_Ligne: quantité}}."""
    donnees = sage.DonneesSage(source="BASE SAGE ADM.xlsx", date_source=date_source)
    for piece, lignes in commandes.items():
        donnees.entetes[piece] = {"DO_Piece": piece, "DO_Tiers": f"CLIENT {piece}"}
        for numero, qte in lignes.items():
            cle = f"{piece}-{numero}"
            ligne = {"DO_Piece": piece, "DL_Ligne": str(numero), "AR_Ref": "ART-1", "DL_Qte": str(qte), "LONG": ""}
            donnees.lignes[cle] = ligne
            donnees.lignes_par_piece.setdefault(piece, []).append((cle, ligne))
    return donnees


class CopieSage(unittest.TestCase):
    def setUp(self):
        self.depot = Depot(schema.ouvrir(":memory:"))
        bilan = self.depot.synchroniser_sage(lecture("2026-07-28T14:00:00", {
            "CC1": {1000: 5, 2000: 2}, "CC2": {1000: 3}}))
        self.assertEqual((bilan.commandes_nouvelles, len(bilan.lignes_nouvelles)), (["CC1", "CC2"], 3))

    def test_copie_identique_a_la_lecture(self):
        donnees = self.depot.charger_sage()
        self.assertEqual(list(donnees.entetes), ["CC1", "CC2"])
        self.assertEqual(donnees.client("CC2"), "CLIENT CC2")
        self.assertEqual([c for c, _ in donnees.lignes_commande("CC1")], ["CC1-1000", "CC1-2000"])
        self.assertEqual(donnees.lignes["CC1-1000"].get("LONG", ""), "", "valeur vide non stockée, lue comme vide")
        self.assertEqual(donnees.date_source, "2026-07-28T14:00:00")

    def test_relecture_sans_changement(self):
        bilan = self.depot.synchroniser_sage(lecture("2026-07-28T14:00:00", {"CC1": {1000: 5, 2000: 2}, "CC2": {1000: 3}}))
        self.assertEqual(bilan.resume(), "aucun changement")

    def test_commande_livree_garde_ses_lignes_pour_ses_of(self):
        bilan = self.depot.synchroniser_sage(lecture("2026-07-29T09:00:00", {"CC1": {1000: 5, 2000: 2}}))
        self.assertEqual((bilan.commandes_sorties, bilan.lignes_sorties), (["CC2"], ["CC2-1000"]))
        donnees = self.depot.charger_sage()
        self.assertNotIn("CC2", donnees.entetes, "plus listée : elle n'est plus dans Sage")
        self.assertEqual(donnees.lignes_commande("CC2"), [])
        enfants = sage.lignes_enfants(donnees, "CC2", "CC2-1000")
        self.assertEqual([(c, q) for c, q, _ in enfants], [("CC2-1000", 3)], "l'OF garde le détail de sa ligne")

    def test_ligne_modifiee_ajoutee_retiree(self):
        bilan = self.depot.synchroniser_sage(lecture("2026-07-29T09:00:00", {
            "CC1": {1000: 4, 3000: 1}, "CC2": {1000: 3}}))  # livraison partielle de 1000, 2000 supprimée
        self.assertEqual((bilan.lignes_modifiees, bilan.lignes_nouvelles, bilan.lignes_sorties),
                         (["CC1-1000"], ["CC1-3000"], ["CC1-2000"]))
        self.assertEqual(bilan.resume(), "1 ligne ajoutée · 1 ligne modifiée · 1 ligne retirée")
        donnees = self.depot.charger_sage()
        self.assertEqual([c for c, _ in donnees.lignes_commande("CC1")], ["CC1-1000", "CC1-3000"])
        self.assertEqual(donnees.lignes["CC1-1000"]["DL_Qte"], "4")
        self.assertIn("CC1-2000", donnees.lignes, "la ligne retirée reste lisible par son OF")

    def test_commande_revenue_dans_sage(self):
        self.depot.synchroniser_sage(lecture("2026-07-29T09:00:00", {"CC1": {1000: 5, 2000: 2}}))
        bilan = self.depot.synchroniser_sage(lecture("2026-07-30T09:00:00", {
            "CC1": {1000: 5, 2000: 2}, "CC2": {1000: 3}}))
        self.assertEqual(bilan.commandes_nouvelles, ["CC2"])
        self.assertIn("CC2", self.depot.charger_sage().entetes)

    def test_lecture_plus_ancienne_ignoree(self):
        # Fichier périmé sur un autre poste : il ne doit pas effacer la copie plus récente
        bilan = self.depot.synchroniser_sage(lecture("2026-07-01T08:00:00", {"CC9": {1000: 1}}))
        self.assertTrue(bilan.ignoree)
        self.assertEqual(list(self.depot.charger_sage().entetes), ["CC1", "CC2"])

    def test_lecture_vide_ignoree(self):
        bilan = self.depot.synchroniser_sage(lecture("2026-07-29T09:00:00", {}))
        self.assertTrue(bilan.ignoree)
        self.assertEqual(list(self.depot.charger_sage().entetes), ["CC1", "CC2"])

    def test_ligne_csv_avec_valeurs_en_trop(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "F-DOCLIGNE.csv"), "w", encoding="utf-8") as f:
                f.write("DO_Piece,DL_Ligne,DL_Qte\nCC3,1000,2,en trop,encore\n")
            lu = sage.charger(d)
        lu.date_source = "2026-07-29T09:00:00"
        self.assertEqual(self.depot.synchroniser_sage(lu).lignes_nouvelles, ["CC3-1000"])
        self.assertEqual(self.depot.charger_sage().lignes["CC3-1000"], {"DO_Piece": "CC3", "DL_Ligne": "1000", "DL_Qte": "2"})

    def test_migration_cree_les_tables(self):
        tables = {nom for (nom,) in self.depot.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"SageCommandes", "SageLignes", "SageLecture"} <= tables)


if __name__ == "__main__":
    unittest.main()
