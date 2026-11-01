import os
import tempfile
import unittest
from types import SimpleNamespace

from admiral.db import schema
from admiral.db.depot import Depot
from admiral.domain import lecture_sage, sage
from admiral.ui.app import SotraglaceApp


def ecrire_lignes(dossier, contenu, date=None):
    chemin = os.path.join(dossier, "F-DOCLIGNE.csv")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("DO_Piece,DL_Ligne,AR_Ref,DL_Qte\n" + contenu)
    if date:
        os.utime(chemin, (date, date))


def lire(lecture, dossier):
    lecture.lancer(dossier)
    lecture.attendre(10)
    return lecture.resultat()


class LectureEnArrierePlan(unittest.TestCase):
    def test_signature(self):
        with tempfile.TemporaryDirectory() as d:
            ecrire_lignes(d, "CC1,1000,REF,1\n", date=1_800_000_000)
            avant = lecture_sage.signature(d)
            with open(os.path.join(d, "~$BASE SAGE ADM.xlsx"), "wb") as f:
                f.write(b"verrou")   # fichier d'Excel ouvert : ignoré
            with open(os.path.join(d, "notes.txt"), "w") as f:
                f.write("autre")
            self.assertEqual(lecture_sage.signature(d), avant)
            os.utime(os.path.join(d, "F-DOCLIGNE.csv"), (1_800_000_060, 1_800_000_060))  # réenregistré
            self.assertNotEqual(lecture_sage.signature(d), avant)
        self.assertIsNone(lecture_sage.signature("/dossier/inexistant"))

    def test_relit_seulement_les_fichiers_modifies(self):
        lecture = lecture_sage.LectureEnFond()
        with tempfile.TemporaryDirectory() as d:
            ecrire_lignes(d, "CC1,1000,REF,1\n", date=1_800_000_000)
            donnees = lire(lecture, d)
            self.assertEqual(list(donnees.lignes), ["CC1-1000"])
            self.assertIsNone(lire(lecture, d), "fichier inchangé : pas de relecture")
            ecrire_lignes(d, "CC1,1000,REF,1\nCC2,1000,REF,4\n", date=1_800_000_060)
            self.assertEqual(list(lire(lecture, d).lignes), ["CC1-1000", "CC2-1000"])
            self.assertIsNone(lecture.resultat(), "le résultat n'est rendu qu'une fois")
            lecture.noter(lecture_sage.signature(d))
            self.assertIsNone(lire(lecture, d))
            lecture.oublier()
            self.assertIsNotNone(lire(lecture, d))

    def test_erreur_rendue_et_relue_ensuite(self):
        lecture = lecture_sage.LectureEnFond()
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "BASE SAGE ADM.xlsx"), "wb") as f:
                f.write(b"enregistrement en cours")
            self.assertIsInstance(lire(lecture, d), sage.SageIllisible)
            self.assertIsInstance(lire(lecture, d), sage.SageIllisible, "un échec n'est pas noté comme lu")


def lecture_simulee(date_source, pieces):
    donnees = sage.DonneesSage(source="BASE SAGE ADM.xlsx", date_source=date_source)
    for piece in pieces:
        donnees.entetes[piece] = {"DO_Piece": piece}
        ligne = {"DO_Piece": piece, "DL_Ligne": "1000", "DL_Qte": "1"}
        donnees.lignes[f"{piece}-1000"] = ligne
        donnees.lignes_par_piece[piece] = [(f"{piece}-1000", ligne)]
    return donnees


class AppliquerLecture(unittest.TestCase):
    """SotraglaceApp.appliquer_lecture_sage sur un écran simulé (sans fenêtre)."""

    def setUp(self):
        depot = Depot(schema.ouvrir(":memory:"))
        depot.synchroniser_sage(lecture_simulee("2026-07-28T14:00:00", ["CC1"]))
        self.rafraichissements = []
        self.app = SimpleNamespace(depot=depot, sage=depot.charger_sage(), _maj_libelle_sage=lambda: None,
                                   _rafraichir_ecrans_sage=self.rafraichissements.append)

    def appliquer(self, resultat):
        SotraglaceApp.appliquer_lecture_sage(self.app, resultat)

    def test_nouvelle_commande(self):
        self.appliquer(lecture_simulee("2026-07-28T15:00:00", ["CC1", "CC2"]))
        self.assertEqual(list(self.app.sage.entetes), ["CC1", "CC2"])
        self.assertEqual(self.rafraichissements, ["1 nouvelle commande · 1 ligne ajoutée"])

    def test_fichier_reenregistre_sans_changement(self):
        self.appliquer(lecture_simulee("2026-07-28T15:00:00", ["CC1"]))
        self.assertEqual(self.app.sage.date_source, "2026-07-28T15:00:00")
        self.assertEqual(self.rafraichissements, [], "rien de nouveau : les écrans ne bougent pas")

    def test_rien_a_lire_ni_erreur(self):
        self.appliquer(None)
        self.appliquer(sage.SageIllisible("enregistrement en cours"))
        self.assertEqual(list(self.app.sage.entetes), ["CC1"])
        self.assertEqual(self.rafraichissements, [])

    def test_copie_mise_a_jour_par_un_autre_poste(self):
        self.app.depot.synchroniser_sage(lecture_simulee("2026-07-28T16:00:00", ["CC1", "CC3"]))
        self.appliquer(None)  # les fichiers de ce poste n'ont pas changé
        self.assertIn("CC3", self.app.sage.entetes)
        self.assertEqual(self.rafraichissements, ["copie mise à jour par un autre poste"])


if __name__ == "__main__":
    unittest.main()
