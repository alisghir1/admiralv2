"""Journal applicatif : logs/admiral.log (rotation 3 x 1 Mo)."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

NOM = "admiral"


def configurer(dossier):
    logger = logging.getLogger(NOM)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        os.makedirs(dossier, exist_ok=True)
        fichier = RotatingFileHandler(os.path.join(dossier, "admiral.log"), maxBytes=1_000_000,
                                      backupCount=3, encoding="utf-8")
        fichier.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fichier)
    except OSError:
        pass  # dossier non inscriptible : on journalise seulement sur la console
    if sys.stderr is not None:  # absent dans l'exécutable Windows sans console
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        logger.addHandler(console)
    return logger


def journal():
    return logging.getLogger(NOM)
