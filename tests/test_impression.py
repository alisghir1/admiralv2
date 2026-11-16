"""Impression (contenu des documents et PDF), codes-barres, remise à zéro de l'atelier et consignes par étape.

Sans interface : tourne aussi sur le serveur Windows de GitHub."""
import os
import re
import tempfile
import unittest
from datetime import date

from admiral import pdf
from admiral.db import schema
from admiral.db.depot import Depot
from admiral.domain import codes, documents, sage

AUJOURD_HUI = date(2026, 11, 16)


def lecture(date_source, commandes):
    """Lecture Sage simulée. commandes = {pièce: (date de commande, client, {ligne: (qté, long, larg, chants L, chants H)})}."""
    donnees = sage.DonneesSage(source="BASE SAGE Admiral.xlsx", date_source=date_source)
    for piece, (jour, client, lignes) in commandes.items():
        donnees.entetes[piece] = {"DO_Piece": piece, "DO_Date": jour, "DO_Tiers": f"C{piece[-1]}", "CT_Intitule": client,
                                  "DO_DateLivr": "2026-11-20", "DO_Coord01": "Villa des Pins"}
        for numero, (qte, longueur, largeur, chant_l, chant_h) in lignes.items():
            cle = f"{piece}-{numero}"
            ligne = {"DO_Piece": piece, "DL_Ligne": str(numero), "AR_Ref": "VT8", "DL_Design": f"Crédence {numero}",
                     "DL_Qte": str(qte), "LONG": str(longueur), "LARG": str(largeur), "EU_Enumere": "U",
                     "Chant-L": str(chant_l), "Chant-H": str(chant_h), "SURF": "0.5", "CHANT": "2"}
            donnees.lignes[cle] = ligne
            donnees.lignes_par_piece.setdefault(piece, []).append((cle, ligne))
    return donnees


COMMANDES = {
    "CC261234": ("2026-11-16", "AGENCEMENTS DU LITTORAL", {1000: (4, 1200, 800, 2, 1), 2000: (8, 600, 450, 2, 2),
                                                           3000: (2, 900, 400, 0, 0)}),
    "CC261235": ("2026-11-16", "MENUISERIE & FILS", {1000: (5, 700, 300, 0, 0)}),
    "CC251234": ("2025-09-12", "ANCIEN CLIENT", {1000: (3, 500, 500, 0, 0)}),
}


class Base(unittest.TestCase):
    def setUp(self):
        self.depot = Depot(schema.ouvrir(":memory:"))
        conn = self.depot.conn
        conn.executemany("INSERT INTO Produits VALUES (?, ?)", [("VT8", "Verre trempé 8 mm clair")])
        conn.executemany("INSERT OR REPLACE INTO Operations VALUES (?, ?)", [("DEC", "Découpe"), ("FAC", "Façonnage"), ("TRE", "Trempe")])
        conn.commit()
        self.depot.synchroniser_sage(lecture("2026-11-16T08:00:00", COMMANDES))
        self.urgent = self.depot.creer_of("CC261234", "VT8", "Crédences", "", 12, "CC261234-1000,CC261234-2000",
                                          [("DEC", "DEC1", ""), ("FAC", None, "Joint plat poli, angles cassés"), ("TRE", None)],
                                          date_besoin="2026-11-15", priorite=1)
        self.normal = self.depot.creer_of("CC261235", "VT8", "Étagères", "", 5, "CC261235-1000",
                                          [("DEC", None), ("TRE", None)], date_besoin="2026-11-25")
        self.ancien = self.depot.creer_of("CC251234", "VT8", "Ancien", "", 3, "CC251234-1000", [("DEC", None)])
        self.depot.ajouter_scans(self.urgent, [("DEC1", 7)])
        self.depot.ajouter_scans(self.urgent, [("FAC1", 2)])
        self.depot.ajouter_scans(self.ancien, [("DEC1", 1)])

    def charger(self):
        return self.depot.charger_etat(), self.depot.charger_sage()

    def referentiel(self):
        return self.depot.libelles_operations(), dict(self.depot.lister_postes()), dict(self.depot.lister_produits())


class Codes(unittest.TestCase):
    def test_lecture_normale(self):
        self.assertEqual(codes.lire_scan("  of261234-01 "), ("OF261234-01", False))

    def test_douchette_en_clavier_americain(self):
        # Touches tapées par une douchette réglée en américain sur un PC AZERTY
        self.assertEqual(codes.lire_scan("OFé-&é\"')à&"), ("OF261234-01", True))
        self.assertEqual(codes.lire_scan("CCé-&é\"')&ààà"), ("CC261234-1000", True))
        self.assertEqual(codes.lire_scan("TEST)à&é\"'(-è_ç)QWAZ?"), (codes.CODE_ESSAI, True))

    def test_formes_des_codes(self):
        self.assertEqual(codes.code_article("CC1", "1000"), "CC1-1000")
        self.assertEqual(codes.code_article("CC1", "CC1-1000"), "CC1-1000")
        self.assertEqual(codes.commande_du_code("CMD-CC1"), "CC1")
        self.assertEqual(codes.commande_de_l_article("CC261234-1000"), "CC261234")
        self.assertIsNone(codes.commande_de_l_article("CC261234"))


class Consignes(Base):
    def test_consigne_par_etape(self):
        etat, _ = self.charger()
        self.assertEqual(etat.consigne(self.urgent, "FAC"), "Joint plat poli, angles cassés")
        self.assertEqual(etat.consigne(self.urgent, "DEC"), "")
        self.assertEqual(etat.gamme(self.urgent), [("DEC", "DEC1"), ("FAC", None), ("TRE", None)], "gamme inchangée")
        self.assertEqual(self.depot.etapes_of(self.urgent)[1], (2, "FAC", None, "Joint plat poli, angles cassés"))

    def test_correction_garde_ou_change_la_consigne(self):
        self.depot.corriger_of(self.urgent, "CC261234", "VT8", ["CC261234-1000", "CC261234-2000"],
                               [("DEC", "DEC1", "Attention au sens"), ("FAC", None, ""), ("TRE", None, "")],
                               "Crédences", "", 12, None, None, "", "2026-11-15", 1)
        etat, _ = self.charger()
        self.assertEqual(etat.consigne(self.urgent, "DEC"), "Attention au sens")
        self.assertEqual(etat.consigne(self.urgent, "FAC"), "")


class RemiseAZero(Base):
    def test_vide_l_atelier_et_garde_le_referentiel(self):
        self.depot.valider([self.ancien], None, "Chef", "Test")
        self.depot.cloturer_commande("CC251234")
        self.depot.enregistrer_chef("Karim", "4321")
        self.assertEqual(self.depot.contenu_atelier(), {"OF": 3, "scans": 10, "validations": 1, "commandes": 3})
        self.depot.remettre_a_zero()
        self.assertEqual(self.depot.contenu_atelier(), {"OF": 0, "scans": 0, "validations": 0, "commandes": 0})
        etat, donnees = self.charger()
        self.assertEqual((etat.ofs, etat.cloturees, donnees.entetes, donnees.date_source), ({}, set(), {}, ""))
        self.assertEqual(self.depot.lignes_affectees("CC261234"), {}, "les lignes de commande sont libres")
        self.assertEqual(self.depot.lister_produits(), [("VT8", "Verre trempé 8 mm clair")], "référentiel gardé")
        self.assertTrue(self.depot.lister_postes())
        self.assertEqual(self.depot.chef_par_code("4321"), "Karim", "chefs d'atelier gardés")

    def test_les_commandes_en_cours_reviennent_du_classeur(self):
        self.depot.remettre_a_zero()
        bilan = self.depot.synchroniser_sage(lecture("2026-11-16T08:00:00", COMMANDES))
        self.assertFalse(bilan.ignoree, "la lecture n'est plus comparée à l'ancienne copie")
        etat, donnees = self.charger()
        self.assertEqual(sorted(donnees.entetes), ["CC251234", "CC261234", "CC261235"])
        self.assertEqual(etat.ofs, {})
        # Les numéros d'OF repartent de 01 dans chaque commande
        self.assertEqual(self.depot.creer_of("CC261234", "VT8", "Crédences", "", 4, "CC261234-1000", [("DEC", None)]),
                         "OF261234-01")
        self.assertEqual(self.depot.ajouter_scans("OF261234-01", [("DEC1", 1)]) or self.depot.ids_scans("OF261234-01", "DEC"), [1])


class Documents(Base):
    def test_fiche_suiveuse(self):
        etat, donnees = self.charger()
        fiche = documents.fiche_of(etat, donnees, etat.ofs[self.urgent], *self.referentiel(), aujourd_hui=AUJOURD_HUI)
        self.assertEqual([a.code for a in fiche.articles], ["CC261234-1000", "CC261234-2000"])
        self.assertEqual(fiche.articles[0].dimensions, "1200 × 800")
        self.assertEqual(fiche.articles[0].chants, "1H+2L")
        self.assertEqual([(e.code_op, e.faites) for e in fiche.etapes], [("DEC", 7), ("FAC", 2), ("TRE", 0)])
        self.assertEqual(fiche.etapes[0].poste, "DEC1 · Découpe Numérique SEKTOR")
        self.assertEqual(fiche.etapes[1].consigne, "Joint plat poli, angles cassés")
        self.assertTrue(fiche.urgent and fiche.retard)
        self.assertEqual(fiche.commande.client, "AGENCEMENTS DU LITTORAL (C4)")
        self.assertEqual(fiche.resume, "12 pièces · 6 m² · 24 ml de chant")

    def test_fiches_d_etape(self):
        etat, donnees = self.charger()
        fiches = documents.fiches_etape(etat, donnees, etat.ofs[self.urgent], *self.referentiel())
        self.assertEqual([f.etape.code_op for f in fiches], ["DEC", "FAC", "TRE"])
        facon = fiches[1]
        self.assertEqual((facon.precedente.code_op, facon.suivante.code_op, facon.pretes), ("DEC", "TRE", 5))
        seule = documents.fiches_etape(etat, donnees, etat.ofs[self.urgent], *self.referentiel(), code_op="TRE")
        self.assertEqual(len(seule), 1)

    def test_fiche_commande(self):
        etat, donnees = self.charger()
        fiche = documents.fiche_commande(etat, donnees, "CC261234", self.depot.libelles_operations())
        self.assertEqual([o.id for o in fiche.ofs], [self.urgent])
        self.assertEqual(fiche.ofs[0].faites, {"DEC": 7, "FAC": 2, "TRE": 0})
        self.assertEqual([a.code for a in fiche.lignes_libres], ["CC261234-3000"], "ligne pas encore dans un OF")
        self.assertEqual(fiche.gabarit, "portrait")
        self.assertIn("1 OF ·", fiche.resume)

    def test_liste_de_travail(self):
        etat, donnees = self.charger()
        liste = documents.liste_travail(etat, donnees, "DEC1", *self.referentiel(), aujourd_hui=AUJOURD_HUI)
        travaux = [t for _, ts in liste.groupes for t in ts]
        self.assertEqual([t.id for t in travaux], [self.urgent, self.normal, self.ancien], "urgent en tête")
        self.assertEqual((travaux[0].reste, travaux[0].pretes), (5, 5))
        trempe = documents.liste_travail(etat, donnees, "TRE1", *self.referentiel(), aujourd_hui=AUJOURD_HUI)
        attente = {t.id: t.attente for _, ts in trempe.groupes for t in ts}
        self.assertEqual(attente, {self.urgent: "", self.normal: "attend Découpe"})
        facon = documents.liste_travail(etat, donnees, "FAC1", *self.referentiel(), aujourd_hui=AUJOURD_HUI)
        self.assertEqual([t.consigne for _, ts in facon.groupes for t in ts], ["Joint plat poli, angles cassés"])

    def test_etiquettes(self):
        etat, donnees = self.charger()
        par_ligne = documents.etiquettes(donnees, [etat.ofs[self.urgent]])
        self.assertEqual([e.code for e in par_ligne.etiquettes], ["CC261234-1000", "CC261234-2000"])
        par_piece = documents.etiquettes(donnees, [etat.ofs[self.urgent]], par_piece=True, debut=4)
        self.assertEqual(len(par_piece.etiquettes), 12)
        self.assertEqual((par_piece.etiquettes[0].piece, par_piece.debut), ("1/4", 4))

    def test_assemblage(self):
        etat, donnees = self.charger()
        choix = documents.Choix(cde="CC261234", ids_of=(self.urgent, self.normal), fiche_commande=True,
                                fiches_suiveuses=True, fiches_etape=True, etiquettes=True, postes=("DEC1",))
        docs = documents.assembler(choix, etat, donnees, *self.referentiel())
        types = [type(d).__name__ for d in docs]
        self.assertEqual(types, ["FicheCommande", "FicheOF", "FicheOF"] + ["FicheEtape"] * 5 + ["ListeTravail", "Etiquettes"])
        etapes = [d.etape.code_op for d in docs if isinstance(d, documents.FicheEtape)]
        self.assertEqual(etapes, ["DEC", "DEC", "FAC", "TRE", "TRE"], "fiches d'un même poste à la suite")
        self.assertTrue(documents.Choix(ids_of=(self.urgent,)).vide)
        self.assertFalse(documents.Choix(postes=("DEC1",)).vide)


class PDF(Base):
    def test_un_pdf_avec_tous_les_documents(self):
        etat, donnees = self.charger()
        choix = documents.Choix(cde="CC261234", ids_of=(self.urgent, self.normal), fiche_commande=True,
                                fiches_suiveuses=True, fiches_etape=True, etiquettes=True, par_piece=True, postes=("DEC1",))
        docs = documents.assembler(choix, etat, donnees, *self.referentiel()) + [documents.page_essai(etat, donnees)]
        with tempfile.TemporaryDirectory() as dossier:
            chemin = pdf.generer(os.path.join(dossier, "essai.pdf"), docs, compresser=False)
            with open(chemin, "rb") as fichier:
                contenu = fichier.read()
        self.assertTrue(contenu.startswith(b"%PDF"))
        pages = re.findall(rb"/Type /Page\b(?!s)", contenu)
        # fiche commande, 2 fiches suiveuses, 5 fiches d'étape en demi-pages (3 pages), liste, étiquettes, essai
        self.assertEqual(len(pages), 9)
        self.assertIn(b"841.8898 595.2756", contenu, "liste de travail en paysage")
        for texte in (b"OF261234-01", b"CC261234-1000", b"Joint plat poli", b"MENUISERIE & FILS", b"URGENT"):
            self.assertIn(texte, contenu)

    def test_rien_a_imprimer(self):
        with self.assertRaises(ValueError):
            pdf.generer(os.path.join(tempfile.gettempdir(), "vide.pdf"), [])


if __name__ == "__main__":
    unittest.main()
