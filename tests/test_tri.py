import unittest

from admiral.domain import tri


class TestTri(unittest.TestCase):
    def test_ordre_naturel(self):
        noms = ["OF-1000", "OF-999", "OF-10000", "OF-1002"]
        self.assertEqual(sorted(noms, key=tri.cle_naturelle), ["OF-999", "OF-1000", "OF-1002", "OF-10000"])
        self.assertEqual(sorted(["CC10", "cc9", "CC251523"], key=tri.cle_naturelle), ["cc9", "CC10", "CC251523"])

    def test_modes(self):
        ofs = [{"id": "OF-12", "besoin": None, "urgent": False},
               {"id": "OF-3", "besoin": "2026-12-01", "urgent": False},
               {"id": "OF-20", "besoin": "2026-11-01", "urgent": True}]
        ids = lambda mode: [o["id"] for o in tri.trier(ofs, mode, numero=lambda o: o["id"], besoin=lambda o: o["besoin"],
                                                         urgent=lambda o: o["urgent"])]
        self.assertEqual(ids(tri.NUMERO), ["OF-3", "OF-12", "OF-20"])
        self.assertEqual(ids(tri.NUMERO_DESC), ["OF-20", "OF-12", "OF-3"])
        self.assertEqual(ids(tri.BESOIN), ["OF-20", "OF-3", "OF-12"], "sans date à la fin")
        self.assertEqual(ids(tri.URGENCE), ["OF-20", "OF-3", "OF-12"])

    def test_client_et_etat_departages_par_numero(self):
        cdes = [("CC10", "B", 1), ("CC9", "B", 0), ("CC2", "", 0), ("CC1", "A", 2)]
        trier = lambda mode: [c[0] for c in tri.trier(cdes, mode, numero=lambda c: c[0], client=lambda c: c[1],
                                                      etat=lambda c: c[2])]
        self.assertEqual(trier(tri.CLIENT), ["CC1", "CC10", "CC9", "CC2"], "à client égal : numéro décroissant")
        self.assertEqual(trier(tri.ETAT), ["CC9", "CC2", "CC10", "CC1"])
        self.assertEqual(trier(tri.DEFAUT), ["CC10", "CC9", "CC2", "CC1"])
        self.assertEqual(tri.TRIS_COMMANDES[0], tri.NUMERO_DESC, "proposé par défaut dans les menus")


if __name__ == "__main__":
    unittest.main()
