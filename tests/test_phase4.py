"""Suivi des OF : annulations tracées, historique, clôture, administration, import Excel, synthèse."""
import unittest
from datetime import date

from admiral.db import schema
from admiral.db.depot import Depot
from admiral.domain import progression, referentiel, synthese


def depot_avec_of():
    depot = Depot(schema.ouvrir(":memory:"))
    id_of = depot.creer_of("CC1", "P", "Vitrage", "", 4, "", [("DEC", None), ("FAC", "FAC1")], date_besoin="2026-10-10", priorite=1)
    return depot, id_of


class AnnulationsEtHistorique(unittest.TestCase):
    def test_annulation_tracee(self):
        depot, id_of = depot_avec_of()
        depot.ajouter_scans(id_of, [("DEC1", 3)])
        depot.annuler_scans(depot.ids_scans(id_of, "DEC")[:1])
        self.assertEqual(depot.charger_etat().compter(id_of, "DEC"), 2, "le scan annulé ne compte plus")
        self.assertEqual(len(depot.ids_scans(id_of, "DEC")), 2, "il n'est plus proposé à l'annulation")
        historique = depot.historique_scans(id_of)
        self.assertEqual(len(historique), 3, "mais il reste dans l'historique")
        self.assertEqual([h[5] for h in historique], [1, 0, 0])
        self.assertIsNotNone(historique[0][6], "avec sa date d'annulation")
        self.assertEqual(historique[0][3], "Découpe")

    def test_suppression_refusee_si_scans(self):
        depot, id_of = depot_avec_of()
        depot.ajouter_scans(id_of, [("DEC1", 1)])
        depot.annuler_scans(depot.ids_scans(id_of, "DEC"))
        with self.assertRaises(ValueError):
            depot.supprimer_of(id_of)          # même un scan annulé protège l'OF
        vierge = depot.creer_of("CC1", "P", "D", "", 1, "", [("DEC", None)])
        depot.supprimer_of(vierge)
        self.assertNotIn(vierge, depot.charger_etat().ofs)
        self.assertEqual(depot.gamme_of(vierge), [])

    def test_modification(self):
        depot, id_of = depot_avec_of()
        depot.modifier_of(id_of, "Vitrage modifié", "obs", 6, 1000, 500, "6", None, 0, {2: None})
        of = depot.charger_etat().ofs[id_of]
        self.assertEqual((of.design, of.qte, of.longueur, of.date_besoin, of.priorite), ("Vitrage modifié", 6, 1000, None, 0))
        self.assertEqual(depot.gamme_of(id_of), [(1, "DEC", None), (2, "FAC", None)])

    def test_of_annule_et_commande_cloturee_refusent_le_scan(self):
        depot, id_of = depot_avec_of()
        depot.changer_statut_of(id_of, "annule")
        etat = depot.charger_etat()
        self.assertEqual(progression.verifier_scan(etat, etat.ofs[id_of], "DEC", "DEC1")[1], f"{id_of} a été annulé")
        self.assertEqual(etat.ofs_par_cde["CC1"], [], "un OF annulé sort de l'atelier")
        self.assertEqual(len(etat.tous_ofs_par_cde["CC1"]), 1, "mais reste visible au Bureau d'Étude")
        depot.changer_statut_of(id_of, "actif")
        depot.cloturer_commande("CC1")
        etat = depot.charger_etat()
        self.assertIn("clôturée", progression.verifier_scan(etat, etat.ofs[id_of], "DEC", "DEC1")[1])
        self.assertEqual(etat.commandes(), [])
        depot.rouvrir_commande("CC1")
        self.assertEqual(depot.charger_etat().commandes(), ["CC1"])

    def test_retard(self):
        depot, id_of = depot_avec_of()
        etat = depot.charger_etat()
        self.assertTrue(etat.en_retard(etat.ofs[id_of], date(2026, 10, 12)))
        self.assertFalse(etat.en_retard(etat.ofs[id_of], date(2026, 10, 9)))
        depot.ajouter_scans(id_of, [("DEC1", 4), ("FAC1", 4)])
        etat = depot.charger_etat()
        self.assertFalse(etat.en_retard(etat.ofs[id_of], date(2026, 10, 12)), "un OF terminé n'est plus en retard")


class AvancementGlobal(unittest.TestCase):
    def test_commande(self):
        depot, id_of = depot_avec_of()                       # DEC > FAC, 4 pièces
        etat = depot.charger_etat()
        self.assertEqual(progression.avancement_global_commande(etat, "CC1"), (0, 4, "pas_demarre"))
        depot.ajouter_scans(id_of, [("DEC1", 4), ("FAC1", 1)])
        self.assertEqual(progression.avancement_global_commande(depot.charger_etat(), "CC1"), (1, 4, "encours"))
        depot.ajouter_scans(id_of, [("FAC1", 3)])
        self.assertEqual(progression.avancement_global_commande(depot.charger_etat(), "CC1"), (4, 4, "terminee"))
        self.assertEqual(progression.avancement_global_commande(depot.charger_etat(), "CC9"), (0, 0, "pas_demarre"))


class Administration(unittest.TestCase):
    def setUp(self):
        self.depot, self.id_of = depot_avec_of()

    def test_operation_utilisee(self):
        with self.assertRaises(ValueError) as erreur:
            self.depot.supprimer_operation("DEC")
        self.assertIn("poste", str(erreur.exception))
        self.depot.enregistrer_operation("LAV", "Lavage")
        self.depot.enregistrer_operation("LAV", "Lavage final")
        self.assertEqual(self.depot.libelles_operations()["LAV"], "Lavage final")
        self.depot.supprimer_operation("LAV")
        self.assertNotIn("LAV", self.depot.libelles_operations())

    def test_poste_utilise(self):
        with self.assertRaises(ValueError):
            self.depot.supprimer_poste("FAC1")     # assigné dans la gamme de l'OF
        self.depot.enregistrer_poste("DEC2", "Découpe 2", "DEC")
        self.assertIn(("DEC2", "Découpe 2", "DEC"), self.depot.lister_postes_complets())
        self.depot.supprimer_poste("DEC2")

    def test_produit_et_gamme(self):
        self.depot.enregistrer_produit("MIR", "Miroir", ["DEC", "FAC"])
        self.assertEqual([op for _, op, _ in self.depot.gamme_produit("MIR")], ["DEC", "FAC"])
        self.depot.enregistrer_produit("MIR", "Miroir argent")       # gamme conservée
        self.assertEqual(len(self.depot.gamme_produit("MIR")), 2)
        self.depot.supprimer_produit("MIR")
        self.assertEqual(self.depot.gamme_produit("MIR"), [])
        with self.assertRaises(ValueError):
            self.depot.supprimer_produit("P")      # utilisé par un OF


class ImportExcel(unittest.TestCase):
    FEUILLES = {
        "PRODUIT": [("REF", "DES"), ("VITR", "Double vitrage"), (None, "ligne vide"), ("MIR", None)],
        "OPERATION": [("REF", "LIB"), ("DEC", "Découpe"), ("LAV", "Lavage")],
        "POSTE": [("COD", "DES"), ("DEC1", "Découpe 1"), ("LAV12", "Laveuse")],
        "GAMPROD": [("REF", "", "OP"), ("VITR", "", None), (None, "", "DEC"), (None, "", "LAV"), ("MIR", "", None), (None, "", "DEC")],
    }

    def test_analyse(self):
        ref = referentiel.analyser(self.FEUILLES)
        self.assertEqual(ref.produits, [("VITR", "Double vitrage"), ("MIR", "")])
        self.assertEqual(ref.postes[1], ("LAV12", "Laveuse", "LAV"))
        self.assertEqual(ref.gammes, {"VITR": ["DEC", "LAV"], "MIR": ["DEC"]})
        self.assertTrue(referentiel.analyser({}).vide)

    def test_import_sans_toucher_aux_of(self):
        depot, id_of = depot_avec_of()
        depot.ajouter_scans(id_of, [("DEC1", 2)])
        compte = depot.importer_referentiel(referentiel.analyser(self.FEUILLES))
        self.assertEqual(compte, {"opérations": 2, "postes": 2, "produits": 2, "gammes": 2})
        etat = depot.charger_etat()
        self.assertIn(id_of, etat.ofs)
        self.assertEqual(etat.compter(id_of, "DEC"), 2)
        self.assertEqual([op for _, op, _ in depot.gamme_produit("VITR")], ["DEC", "LAV"])
        depot.importer_referentiel(referentiel.analyser(self.FEUILLES))   # réimport : pas de doublon
        self.assertEqual(len(depot.gamme_produit("VITR")), 2)


class Synthese(unittest.TestCase):
    def test_indicateurs(self):
        depot, urgent = depot_avec_of()                                     # 4 pièces, besoin le 10/10, urgent
        fini = depot.creer_of("CC1", "P", "Fini", "", 2, "", [("DEC", None)])
        depot.creer_of("CC2", "P", "Vierge", "", 3, "", [("DEC", None), ("FAC", None)])
        depot.ajouter_scans(urgent, [("DEC1", 2)])
        depot.ajouter_scans(fini, [("DEC1", 2)])
        etat = depot.charger_etat()
        s = synthese.calculer(etat, depot.lister_postes_complets(), depot.libelles_operations(),
                              {"DEC1": 4}, date(2026, 10, 12))
        self.assertEqual((s.pieces_jour, s.of_a_faire, s.of_en_cours, s.of_termines, s.of_retard), (4, 1, 1, 1, 1))
        self.assertAlmostEqual(s.avancement, 2 / 9)
        self.assertEqual(len(s.a_surveiller), 1)
        self.assertEqual(s.a_surveiller[0].etape, "Découpe 2/4")
        self.assertTrue(s.a_surveiller[0].motif.startswith("En retard"))
        dec1 = next(l for l in s.postes if l.code == "DEC1")
        self.assertEqual((dec1.a_faire, dec1.en_cours, dec1.termines, dec1.reste_operation), (1, 1, 1, 5))


class MigrationQuatre(unittest.TestCase):
    def test_colonnes(self):
        conn = schema.ouvrir(":memory:")
        self.assertTrue({"Statut", "DateBesoin", "Priorite"} <= schema._colonnes(conn, "CdeDetail"))
        self.assertTrue({"Annule", "DateAnnulation"} <= schema._colonnes(conn, "Scans"))
        self.assertEqual(schema.version(conn), 4)


if __name__ == "__main__":
    unittest.main()
