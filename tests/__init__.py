"""Sur le serveur GitHub (variable GITHUB_ACTIONS), chaque test en échec est aussi publié comme
annotation de l'exécution : le détail de l'erreur reste lisible sans ouvrir le journal complet."""
import os
import sys
import unittest

if os.environ.get("GITHUB_ACTIONS"):
    # Sous Windows, la sortie est en cp1252 : un caractère hors de cet encodage (« ◐ », « ✓ »…)
    # dans un message d'échec ferait planter l'affichage du rapport lui-même.
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(errors="backslashreplace")

    def _annoter(test, err, nature):
        trace = unittest.TestResult()._exc_info_to_string(err, test)
        message = trace.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title={nature} : {test.id()}::{message}", flush=True)

    _ajouter_echec = unittest.TextTestResult.addFailure
    _ajouter_erreur = unittest.TextTestResult.addError

    def addFailure(self, test, err):
        _annoter(test, err, "Échec")
        _ajouter_echec(self, test, err)

    def addError(self, test, err):
        _annoter(test, err, "Erreur")
        _ajouter_erreur(self, test, err)

    unittest.TextTestResult.addFailure = addFailure
    unittest.TextTestResult.addError = addError
