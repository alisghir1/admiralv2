"""Lance les tests sur le serveur Windows de GitHub et signale chaque échec par une annotation.

Les annotations s'affichent sur la page de l'exécution et se lisent par l'API publique sans connexion ;
le journal complet, lui, demande d'être connecté. Si le processus s'arrête net (plantage de Tk sous
Windows, sans « FAIL » ni « ERROR »), l'annotation donne les dernières lignes : le test en cours.
"""
import os
import re
import subprocess
import sys

SEPARATEUR = "=" * 70
FIN_DES_ERREURS = "\n" + "-" * 70 + "\nRan "


def annotations(sortie, code):
    """[(titre, message)] des échecs trouvés dans la sortie de unittest (vide si code vaut 0)."""
    if code == 0:
        return []
    resultat = []
    for bloc in sortie.split(SEPARATEUR + "\n")[1:]:
        bloc = bloc.split(FIN_DES_ERREURS)[0]
        entete = re.match(r"(FAIL|ERROR): (\S+) \((.+?)\)", bloc)
        if entete:
            lignes = [ligne for ligne in bloc.splitlines() if ligne.strip() and not set(ligne) <= {"-"}]
            resultat.append((f"{entete.group(1)} {entete.group(3)}", "\n".join(lignes[-6:])))
    if not resultat:
        lignes = [ligne for ligne in sortie.splitlines() if ligne.strip()]
        resultat.append((f"Tests interrompus (code {code})", "\n".join(lignes[-8:])))
    return resultat


def annoter(titre, message):
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title={titre}::{message}", flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    environnement = dict(os.environ, PYTHONIOENCODING="utf-8")
    execution = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environnement)
    sortie = execution.stdout.decode("utf-8", errors="replace")
    print(sortie, flush=True)
    for titre, message in annotations(sortie, execution.returncode):
        annoter(titre, message)
    return execution.returncode


if __name__ == "__main__":
    sys.exit(main())
