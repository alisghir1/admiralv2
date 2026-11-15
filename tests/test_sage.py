import os
import tempfile
import unittest
from datetime import date, datetime

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

    def test_client_code_et_nom(self):
        donnees = sage.DonneesSage(entetes={
            "CC1": {"DO_Tiers": "C0901", "CT_Intitule": "AGENCEMENTS DU LITTORAL"},
            "CC2": {"DO_Tiers": "C0001", "CT_Intitule": "CLIENT DIVERS", "Client Divers": "Mme Martin"},
            "CC3": {"DO_Tiers": "C0902"},                                   # ancien classeur : pas de nom
            "CC4": {"DO_Tiers": "MIROITERIE", "CT_Intitule": "Miroiterie"},  # nom déjà dans le code : pas de doublon
            "CC5": {"CT_Intitule": "SANS CODE"},
        })
        self.assertEqual(donnees.client("CC5"), "SANS CODE")
        self.assertEqual([donnees.client(c) for c in ("CC1", "CC2", "CC3", "CC4")],
                         ["AGENCEMENTS DU LITTORAL (C0901)", "Mme Martin (C0001)", "C0902", "MIROITERIE"])
        self.assertEqual(donnees.client("CC9"), "Inconnu")
        self.assertEqual([donnees.client_pour_tri(c) for c in ("CC1", "CC2", "CC3")],
                         ["AGENCEMENTS DU LITTORAL", "Mme Martin", "C0902"])

    def test_infos_de_la_commande(self):
        donnees = sage.DonneesSage(entetes={
            "CC1": {"DO_Tiers": "C0901", "DO_Coord01": " Villa des Pins ", "DO_Date": "2025-09-11", "DO_DateLivr": "2026-11-10",
                    "OBSERV": "EN ATTENTE MESURE"},
            "CC2": {"DO_Tiers": "C0001"},
        })
        infos = donnees.infos_commande("CC1")
        self.assertEqual((infos.reference, infos.date, infos.delai, infos.niveau),
                         ("Villa des Pins", "2025-09-11", "2026-11-10", "alerte"))
        self.assertEqual(infos.textes(aujourd_hui=date(2026, 11, 1)),
                         ("Réf. client : Villa des Pins · Commandée le 11/09/2025 · ", "Délai : 10/11", False))
        self.assertEqual(infos.textes(avec_date=False, aujourd_hui=date(2026, 11, 15)),
                         ("Réf. client : Villa des Pins · ", "Délai dépassé : 10/11", True))
        self.assertEqual(donnees.infos_commande("CC2").textes(), ("", "", False))
        self.assertIn("villa des pins", donnees.texte_recherche("CC1"))
        self.assertIn("attente mesure", donnees.texte_recherche("CC1"))

    def test_niveau_des_observations(self):
        niveaux = {texte: sage.InfosCommande(observations=texte).niveau for texte in (
            "ANNULEE", "Chant, BLOQUEE", "EN ATTENTE MESURE", "Repture de stock panneau", "reptue de stock",
            "CAISSONS STD", "chant terminer")}
        self.assertEqual(niveaux, {"ANNULEE": "bloque", "Chant, BLOQUEE": "bloque", "EN ATTENTE MESURE": "alerte",
                                   "Repture de stock panneau": "alerte", "reptue de stock": "alerte",
                                   "CAISSONS STD": "info", "chant terminer": "info"})

    def test_dates_sage(self):
        self.assertEqual(sage.lire_date_sage("2026-11-10"), "2026-11-10")
        self.assertEqual(sage.lire_date_sage("7/29/24 0:00"), "2024-07-29")   # anciens exports CSV
        self.assertEqual(sage.lire_date_sage("29/07/2026"), "2026-07-29")     # démonstration
        for vide in ("1/1/53 0:00", "1753-01-01", "", None, "n'importe quoi"):
            self.assertEqual(sage.lire_date_sage(vide), "", vide)

    def test_quantite_chants_et_resume(self):
        porte = {"DL_Qte": "2", "EU_Enumere": "U", "SURF": "0.42", "CHANT": "2.6", "Chant-L": "2", "Chant-H": "1"}
        profil = {"DL_Qte": "7.6", "EU_Enumere": "ML", "Chant-L": "0", "Chant-H": "0"}
        self.assertEqual([sage.quantite(porte), sage.quantite(profil), sage.quantite({"DL_Qte": "3"})], ["2", "7,6 ML", "3"])
        self.assertEqual([sage.chants(porte), sage.chants(profil), sage.chants({"Chant-L": "1"})], ["1H+2L", "", "1L"])
        self.assertEqual(sage.chants_communs([porte, dict(porte)]), "1H+2L")
        self.assertEqual(sage.chants_communs([porte, profil]), "")
        self.assertEqual(sage.resume_lignes([porte]), "1 ligne · 2 pièces · 0,84 m² · 5,2 ml de chant")
        self.assertEqual(sage.resume_lignes([porte, profil]), "2 lignes · 9 pièces · 0,84 m² · 5,2 ml de chant")
        self.assertEqual(sage.resume_lignes([profil]), "1 ligne · 7 pièces")

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
# Classeur des commandes en cours : en-têtes et lignes, colonnes renommées en clair
ENTETES_VUES = [
    ("Type", "Commande", "Date", "CodeCli", "Client", "Client Divers", "Ref client", "Délai", "Num", "Observations",
     "Etat", None),
    (1, "CC1", datetime(2025, 9, 11), "C0901", "AGENCEMENTS DU LITTORAL", "", "Villa des Pins", datetime(1753, 1, 1), 101,
     "EN ATTENTE MESURE", 1, None),
    (1, "CC2", datetime(2026, 11, 5), "C0001", "CLIENT DIVERS", "M. DUPONT ", "", datetime(2026, 11, 10), 102,
     None, 1, None),
]
LIGNES_VUES = [
    ("Type", "Client", "Commande", "Article", "Désignation", "Quantité", "Unit", "DL_Ligne", "Num", "LONG", "LARG",
     "SURF", "CHANT", "Etat", "Chant-L", "Chant-H"),
    (1, "C0901", "CC1", "P000101", "Porte 72x60", 2, 3, 1000, 201, 700, 600, 0.42, 2.6, 1, 1, 0),
    (1, "C0901", "CC1", "DIV0000", "Profil", 7.6, 1, 2000, 202, None, None, None, None, 1, None, None),
    (1, "C0001", "CC2", "P060000", "Plan de travail", 1, 2, 1000, 203, 2200, 600, 1.32, 5.6, 1, 2, 2),
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

    def test_classeur_des_vues_commandes_en_cours(self):
        # « BASE SAGE Admiral.xlsx » : commandes en cours seulement, colonnes renommées en clair
        with tempfile.TemporaryDirectory() as d:
            self.ecrire_classeur(os.path.join(d, "BASE SAGE Admiral.xlsx"),
                                 {"DOCENTETE": ENTETES_VUES, "DOCLIGNE": LIGNES_VUES})
            donnees = sage.charger(d)
        self.assertEqual(list(donnees.entetes), ["CC1", "CC2"])
        entete = donnees.entetes["CC1"]
        self.assertEqual((entete["DO_Tiers"], entete["CT_Intitule"], entete["DO_Coord01"], entete["DO_DateLivr"],
                          entete["OBSERV"], entete["cbMarq"]),
                         ("C0901", "AGENCEMENTS DU LITTORAL", "Villa des Pins", "", "EN ATTENTE MESURE", "101"))
        # Code et nom du client ; pour un client de passage, le nom saisi dans « Client Divers »
        self.assertEqual(donnees.client("CC1"), "AGENCEMENTS DU LITTORAL (C0901)")
        self.assertEqual(donnees.client("CC2"), "M. DUPONT (C0001)")
        self.assertEqual(donnees.client_pour_tri("CC2"), "M. DUPONT")
        self.assertEqual(donnees.client("CC9", ""), "")
        # Dans les lignes, « Client » est le code du client
        ligne = donnees.lignes["CC1-1000"]
        self.assertEqual((ligne["CT_Num"], ligne["AR_Ref"], ligne["DL_Design"], ligne["DL_Qte"], ligne["EU_Enumere"]),
                         ("C0901", "P000101", "Porte 72x60", "2", "U"))
        self.assertEqual((ligne["SURF"], ligne["CHANT"], ligne["Chant-L"], ligne["Chant-H"]), ("0.42", "2.6", "1", "0"))
        self.assertEqual(sage.dimensions(ligne), "700x600")
        self.assertEqual([donnees.lignes[c]["EU_Enumere"] for c in ("CC1-2000", "CC2-1000")], ["ML", "M2"])
        self.assertEqual(donnees.lignes["CC1-2000"]["DL_Qte"], "7.6")

    def test_classeur_illisible(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "BASE SAGE ADM.xlsx"), "wb") as f:
                f.write(b"enregistrement en cours")
            with self.assertRaises(sage.SageIllisible):
                sage.charger(d)


if __name__ == "__main__":
    unittest.main()
