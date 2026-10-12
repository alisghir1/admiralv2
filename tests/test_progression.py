import unittest

from admiral.domain.etat import OF, EtatAtelier
from admiral.domain import progression as p

POSTES = [("DEC1", "DEC"), ("DEC2", "DEC"), ("FAC1", "FAC"), ("TRE1", "TRE"), ("USI1", "USI")]


def etat(scans=(), gammes=None, qte=7, lignes=""):
    of = OF("OF-1", "CC1", "P", "Double vitrage", "", qte, lignes)
    gammes = gammes or [("OF-1", "DEC", None), ("OF-1", "FAC", "FAC1"), ("OF-1", "TRE", None)]
    return of, EtatAtelier([of], gammes, POSTES, list(scans))


class Comptage(unittest.TestCase):
    def test_scans_agreges_par_operation(self):
        _, e = etat([("OF-1", "DEC1", None, 2), ("OF-1", "DEC2", None, 1), ("OF-1", "DEC1", "L1", 3)])
        self.assertEqual(e.compter("OF-1", "DEC"), 6)
        self.assertEqual(e.compter("OF-1", "DEC", None), 3)
        self.assertEqual(e.compter("OF-1", "DEC", "L1"), 3)
        self.assertEqual(e.compter_poste("OF-1", "DEC1"), 5)

    def test_scan_d_un_poste_inconnu_ignore_par_operation(self):
        _, e = etat([("OF-1", "XXX", None, 4)])
        self.assertEqual(e.compter("OF-1", "DEC"), 0)
        self.assertEqual(e.compter_poste("OF-1", "XXX"), 4)

    def test_premier_poste_par_ordre_alphabetique(self):
        _, e = etat()
        self.assertEqual(e.premier_poste("DEC"), "DEC1")
        self.assertIsNone(e.premier_poste("ZZZ"))


class VerifierScan(unittest.TestCase):
    def test_premiere_etape_acceptee(self):
        of, e = etat()
        self.assertEqual(p.verifier_scan(e, of, "DEC", "DEC1"), (True, "", 0))

    def test_operation_hors_gamme(self):
        of, e = etat()
        ok, motif, _ = p.verifier_scan(e, of, "USI", "USI1")
        self.assertFalse(ok)
        self.assertIn("ne passe pas par l'opération USI", motif)

    def test_poste_non_assigne(self):
        of, e = etat(gammes=[("OF-1", "DEC", "DEC2")])
        ok, motif, _ = p.verifier_scan(e, of, "DEC", "DEC1")
        self.assertFalse(ok)
        self.assertIn("assigné au poste DEC2", motif)

    def test_poste_sans_operation(self):
        of, e = etat()
        self.assertFalse(p.verifier_scan(e, of, None, "ZZZ")[0])

    def test_bloque_si_etape_precedente_insuffisante(self):
        of, e = etat([("OF-1", "DEC1", None, 1), ("OF-1", "FAC1", None, 1)])
        ok, motif, mes = p.verifier_scan(e, of, "FAC", "FAC1")
        self.assertFalse(ok)
        self.assertIn("étape précédente (DEC) à 1/7", motif)
        self.assertEqual(mes, 1)

    def test_quantite_atteinte(self):
        of, e = etat([("OF-1", "DEC1", None, 7)])
        ok, motif, _ = p.verifier_scan(e, of, "DEC", "DEC1")
        self.assertFalse(ok)
        self.assertIn("7/7", motif)


class Repartition(unittest.TestCase):
    def test_scans_generaux_repartis_dans_l_ordre(self):
        _, e = etat([("OF-1", "DEC1", None, 6), ("OF-1", "DEC1", "L2", 1)])
        enfants = [("L1", 5), ("L2", 2)]
        self.assertEqual(p.repartir_scans(e, "OF-1", "DEC", enfants), {"L1": 5, "L2": 2})

    def test_repartition_partielle(self):
        _, e = etat([("OF-1", "DEC1", None, 2)])
        self.assertEqual(p.repartir_scans(e, "OF-1", "DEC", [("L1", 4)]), {"L1": 2})


class Rattrapage(unittest.TestCase):
    def test_complete_les_etapes_sans_les_depasser(self):
        # DEC à 1, FAC à 1 : TOUT scanner en TRE (7) doit compléter DEC et FAC à 7, pas à 8
        of, e = etat([("OF-1", "DEC1", None, 1), ("OF-1", "FAC1", None, 1)])
        plan = p.plan_rattrapage(e, of, "TRE", "TRE1", 7)
        self.assertEqual(plan, [("DEC1", 6), ("FAC1", 6), ("TRE1", 7)])

    def test_etapes_deja_completes_non_touchees(self):
        of, e = etat([("OF-1", "DEC1", None, 7), ("OF-1", "FAC1", None, 7)])
        self.assertEqual(p.plan_rattrapage(e, of, "TRE", "TRE1", 1), [("TRE1", 1)])

    def test_ligne_sage_tient_compte_des_scans_generaux(self):
        # DEC a 5 scans généraux, qui couvrent entièrement la ligne L1 (qté 5)
        of, e = etat([("OF-1", "DEC1", None, 5)])
        plan = p.plan_rattrapage(e, of, "FAC", "FAC1", 5, child_key="L1", enfants=[("L1", 5)])
        self.assertEqual(plan, [("FAC1", 5)])


class Avancement(unittest.TestCase):
    def test_avancement_commande(self):
        _, e = etat([("OF-1", "DEC1", None, 3)])
        self.assertEqual(p.avancement_commande(e, "CC1", "DEC", "DEC1"), (3, 7, "42.9%"))

    def test_commande_hors_poste(self):
        _, e = etat()
        self.assertEqual(p.avancement_commande(e, "CC1", "USI", "USI1"), (0, 0, "N/A"))

    def test_statuts(self):
        self.assertEqual(p.statut_of_au_poste(7, 7, 0)[2], "terminee")
        self.assertEqual(p.statut_of_au_poste(7, 2, 3), ("En cours (2/7)", "Prêt à produire : 3 dispo", "encours"))
        self.assertEqual(p.statut_of_au_poste(7, 0, 0)[1], "Bloqué (Étape précédente non finie)")
        self.assertEqual(p.tag_avancement(0, 0), "pas_demarre")
        self.assertEqual(p.tag_avancement(5, 5), "terminee")


class EtatAuPoste(unittest.TestCase):
    def test_etats(self):
        self.assertEqual(p.etat_au_poste(7, 7, 0), "terminee")
        self.assertEqual(p.etat_au_poste(7, 0, 3), "pret")
        self.assertEqual(p.etat_au_poste(7, 2, 3), "encours")
        self.assertEqual(p.etat_au_poste(7, 2, 0), "attente")
        self.assertEqual(p.etat_au_poste(7, 0, 0), "bloque")

    def test_situations(self):
        self.assertEqual(p.situation_au_poste("pret", 1), "1 pièce prête à produire")
        self.assertEqual(p.situation_au_poste("encours", 3), "3 pièces prêtes à produire")
        self.assertEqual(p.situation_au_poste("bloque", 0, "Découpe", 0, 7), "En attente de Découpe (0/7)")
        self.assertEqual(p.situation_au_poste("terminee", 0), "Terminé à ce poste")


class Dimensions(unittest.TestCase):
    def test_champs_dedies(self):
        of = OF("OF-1", "CC1", "P", "D", "Intercalaire noir", 1, "", 1200, 800, "4/16/4")
        self.assertEqual(of.dimensions, "1200 × 800 mm · ép. 4/16/4")
        self.assertEqual(of.observations, "Intercalaire noir")

    def test_ancien_of_dimensions_dans_observations(self):
        of = OF("OF-1", "CC1", "P", "D", "1200 x 800 mm", 1, "")
        self.assertEqual(of.dimensions, "1200 x 800 mm")
        self.assertEqual(of.observations, "")
        self.assertEqual(OF("OF-2", "CC1", "P", "D", "", 1, "").dimensions, "—")


if __name__ == "__main__":
    unittest.main()
