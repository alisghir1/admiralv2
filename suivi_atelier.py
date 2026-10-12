"""Lanceur d'Admiral v2 (conservé pour Lancer_Admiral.command et build_exe.bat).

Le code de l'application est dans le paquet admiral/.
"""
import sys

from admiral.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
