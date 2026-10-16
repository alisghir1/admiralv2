"""Corrections de l'audit « suivi d'atelier » (16/10/2026) : référentiel, Charge, Synthèse, dates, lignes Sage."""
import unittest
from datetime import date

from admiral.db import schema
from admiral.db.depot import Depot
from admiral.domain import progression, sage, synthese
from admiral.domain.referentiel import Referentiel
from admiral.ui.dialogs import lire_date


def depot_neuf():
    return Depot(schema.ouvrir(":memory:"))   # postes par défaut : DEC1, USI1, FAC1, TRE1, EXP1


class Referentiel_(unittest.TestCase):
    def setUp(self):
        self.depot = depot_neuf()

    def test_nouveau_ne_remplace_pas_l_existant(self):
        with self.assertRaises(ValueError):
            self.depot.enregistrer_poste("DEC1", "Autre", "FAC", creation=True)
        with self.assertRaises(ValueError):
            self.depot.enregistrer_operation("DEC", "Autre", creation=True)
        self.depot.enregistrer_produit("P", "Produit", ["DEC"], creation=True)
        with self.assertRaises(ValueError):
            self.depot.enregistrer_produit("P", "Autre", ["FAC"], creation=True)
        self.assertEqual(self.depot.operation_du_poste("DEC1"), "DEC")

    def test_operation_d_un_poste_utilise_figee(self):
        self.depot.enregistrer_poste("DEC1", "Découpe", "FAC")      # pas encore utilisé : autorisé
        self.depot.enregistrer_poste("DEC1", "Découpe", "DEC")
        id_of = self.depot.creer_of("CC1", "P", "A", "", 2, "", [("DEC", None)])
        self.depot.ajouter_scans(id_of, [("DEC1", 1)])
        with self.assertRaises(ValueError) as erreur:
            self.depot.enregistrer_poste("DEC1", "Découpe", "FAC")
        self.assertIn("historique", str(erreur.exception))
        self.depot.enregistrer_poste("DEC1", "Découpe numérique", "DEC")   # renommer reste possible
        self.assertEqual(self.depot.charger_etat().compter(id_of, "DEC"), 1)

    def test_operation_en_double_dans_une_gamme(self):
        with self.assertRaises(ValueError):
            self.depot.enregistrer_produit("P", "Produit", ["DEC", "USI", "DEC"])

    def test_dernier_poste_d_une_operation_utilisee(self):
        self.depot.creer_of("CC1", "P", "A", "", 2, "", [("DEC", None), ("TRE", None)])
        with self.assertRaises(ValueError):
            self.depot.supprimer_poste("TRE1")
        self.depot.enregistrer_poste("TRE2", "Four 2", "TRE")
        self.depot.supprimer_poste("TRE1")                          # un autre poste fait la trempe

    def test_import_ne_reecrit_pas_l_historique(self):
        id_of = self.depot.creer_of("CC1", "P", "A", "", 2, "", [("DEC", None)])
        self.depot.ajouter_scans(id_of, [("DEC1", 2)])
        compte = self.depot.importer_referentiel(Referentiel(
            operations=[("DEC", "Découpe")], postes=[("DEC1", "Découpe", "FAC")], produits=[("P", "Produit")],
            gammes={"P": ["DEC", "FAC", "DEC"]}))
        self.assertEqual(self.depot.operation_du_poste("DEC1"), "DEC")
        self.assertEqual([op for _, op, _ in self.depot.gamme_produit("P")], ["DEC", "FAC"])
        self.assertEqual(len(compte["avertissements"]), 2)


class AnnulationParPoste(unittest.TestCase):
    def test_moins_un_ne_touche_que_les_pieces_du_poste(self):
        depot = depot_neuf()
        depot.enregistrer_poste("DEC2", "Découpe 2", "DEC")
        id_of = depot.creer_of("CC1", "P", "A", "", 5, "", [("DEC", None)])
        depot.ajouter_scans(id_of, [("DEC1", 2), ("DEC2", 3)])
        self.assertEqual(len(depot.ids_scans(id_of, "DEC")), 5)
        self.assertEqual(len(depot.ids_scans(id_of, "DEC", poste="DEC1")), 2)


class ChargeEtSynthese(unittest.TestCase):
    def test_etape_libre_faite_par_un_autre_poste(self):
        depot = depot_neuf()
        depot.enregistrer_poste("DEC2", "Découpe 2", "DEC")
        id_of = depot.creer_of("CC1", "P", "A", "", 5, "", [("DEC", None)])
        annule = depot.creer_of("CC1", "P", "B", "", 3, "", [("DEC", None)])
        depot.changer_statut_of(annule, "annule")
        depot.ajouter_scans(id_of, [("DEC1", 5)])
        s = synthese.calculer(depot.charger_etat(), depot.lister_postes_complets(), depot.libelles_operations(), {}, date.today())
        dec2 = next(l for l in s.postes if l.code == "DEC2")
        self.assertEqual((dec2.a_faire, dec2.en_cours, dec2.termines, dec2.reste_operation), (0, 0, 1, 0),
                         "l'étape est finie (par DEC1) et l'OF annulé n'est pas compté")


class DatesEtLignesSage(unittest.TestCase):
    def test_date_sans_annee(self):
        self.assertEqual(lire_date("05/01", date(2026, 12, 16)), "2027-01-05", "janvier suivant")
        self.assertEqual(lire_date("10/12", date(2026, 12, 16)), "2026-12-10", "date récente : en retard, même année")
        self.assertEqual(lire_date("20/12", date(2026, 12, 16)), "2026-12-20")
        self.assertEqual(lire_date("05/01/2027"), "2027-01-05")

    def test_tri_numerique_des_lignes(self):
        lignes = [{"DL_Ligne": n} for n in ("10000", "2000", "1000", "11000")]
        self.assertEqual([l["DL_Ligne"] for l in sorted(lignes, key=sage.numero_ligne)], ["1000", "2000", "10000", "11000"])

    def test_lignes_de_texte_non_fabricables(self):
        self.assertTrue(sage.fabricable({"AR_Ref": "P013036", "DL_Qte": "2"}))
        self.assertFalse(sage.fabricable({"AR_Ref": "", "DL_Qte": "2875,5"}), "sous-total")
        self.assertFalse(sage.fabricable({"AR_Ref": "P013036", "DL_Qte": "0"}), "commentaire")
        self.assertEqual(progression.statut_ligne(0, 0), ("Sans objet", "terminee"))


if __name__ == "__main__":
    unittest.main()
