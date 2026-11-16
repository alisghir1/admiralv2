"""Douchette sans interface : reconnaissance d'un scan à la vitesse de frappe, double lecture, port COM simulé."""
import time
import unittest

from admiral import douchette


def taper(detecteur, texte, debut=1000, ecart=5, widget=None):
    """Simule la frappe : un caractère toutes les `ecart` ms. Retourne l'heure de la dernière touche."""
    temps = debut
    for i, char in enumerate(texte):
        temps = debut + i * ecart
        detecteur.caractere(char, temps, widget)
    return temps


class Detection(unittest.TestCase):
    def test_un_scan_de_douchette_est_reconnu(self):
        d = douchette.DetecteurScan()
        fin = taper(d, "OF261234-01", widget="recherche")
        code, widgets = d.entree(fin + 8)
        self.assertEqual(code, "OF261234-01")
        self.assertEqual(widgets, ["recherche"] * 11, "pour retirer le code du champ où il a été tapé")

    def test_la_frappe_humaine_n_est_pas_un_scan(self):
        d = douchette.DetecteurScan()
        fin = taper(d, "CC261234", ecart=120)
        self.assertEqual(d.entree(fin + 150), (None, []))

    def test_code_trop_court_ou_entree_tardive(self):
        d = douchette.DetecteurScan()
        fin = taper(d, "CC1")
        self.assertIsNone(d.entree(fin + 5)[0], "trop court pour un code d'Admiral")
        fin = taper(d, "OF261234-01", debut=5000)
        self.assertIsNone(d.entree(fin + 400)[0], "Entrée tapée à la main bien après")

    def test_une_pause_recommence_le_code(self):
        d = douchette.DetecteurScan()
        taper(d, "abc", ecart=200)                   # quelqu'un tapait dans la recherche
        fin = taper(d, "OF261234-01", debut=2000)    # puis un scan
        self.assertEqual(d.entree(fin + 5)[0], "OF261234-01")


class Doublon(unittest.TestCase):
    def test_double_lecture_ignoree(self):
        a = douchette.AntiDoublon(delai=1.0)
        self.assertFalse(a.doublon("OF1-01", 10.0))
        self.assertTrue(a.doublon("OF1-01", 10.4), "relu dans la seconde")
        self.assertFalse(a.doublon("OF1-01", 12.0), "pièce suivante, scannée plus tard")
        self.assertFalse(a.doublon("OF1-02", 12.1), "autre code")


class PortSimule:
    """Port COM simulé : rend les morceaux reçus, puis rien (lecture sans données)."""

    def __init__(self, morceaux):
        self.morceaux = list(morceaux)
        self.port = "COM9"
        self.ferme = False

    def read(self, _taille):
        time.sleep(0.01)
        return self.morceaux.pop(0) if self.morceaux else b""

    def close(self):
        self.ferme = True


class PortCOM(unittest.TestCase):
    def attendre_codes(self, lecteur, nombre, delai=2.0):
        codes, limite = [], time.monotonic() + delai
        while len(codes) < nombre and time.monotonic() < limite:
            codes += lecteur.codes()
            time.sleep(0.02)
        return codes

    def test_codes_lus_avec_ou_sans_fin_de_ligne(self):
        port = PortSimule([b"OF2612", b"34-01\r\nCC261234-1000\r", b"\n", b"CC261234"])   # le dernier sans fin de ligne
        lecteur = douchette.DouchetteSerie("COM9", ouvrir=lambda: port).demarrer()
        try:
            self.assertEqual(self.attendre_codes(lecteur, 3), ["OF261234-01", "CC261234-1000", "CC261234"])
            self.assertTrue(lecteur.connectee)
            self.assertIn("COM9", lecteur.etat)
        finally:
            lecteur.arreter()

    def test_douchette_absente(self):
        def absente():
            raise OSError("port COM9 introuvable")
        lecteur = douchette.DouchetteSerie("COM9", ouvrir=absente).demarrer()
        try:
            limite = time.monotonic() + 2
            while lecteur.etat.startswith("recherche") and time.monotonic() < limite:
                time.sleep(0.02)
            self.assertFalse(lecteur.connectee)
            self.assertIn("introuvable", lecteur.etat)
        finally:
            lecteur.arreter()


if __name__ == "__main__":
    unittest.main()
