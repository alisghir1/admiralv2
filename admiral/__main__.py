"""Point d'entrée : python -m admiral"""
import os
import sys

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

from tkinter import messagebox  # noqa: E402

import customtkinter as ctk  # noqa: E402

from . import __version__  # noqa: E402
from .config import LOG_DIR  # noqa: E402
from .journal import configurer  # noqa: E402

MESSAGE_ERREUR = "Une erreur inattendue est survenue :\n{}\n\nLe détail est enregistré dans logs/admiral.log."


def main():
    log = configurer(LOG_DIR)
    log.info("Admiral %s", __version__)
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()

    autotest = "--autotest" in sys.argv
    resultat = {"code": 0}

    def erreur_interface(type_exc, valeur, trace):
        # Erreur dans un clic ou un événement : on la journalise et on prévient, l'application continue.
        # En auto-vérification, pas de fenêtre bloquante : l'erreur fait échouer la vérification.
        log.error("Erreur non gérée", exc_info=(type_exc, valeur, trace))
        if autotest:
            resultat["code"] = 1
        else:
            messagebox.showerror("Erreur", MESSAGE_ERREUR.format(valeur), parent=root)

    root.report_callback_exception = erreur_interface

    from .ui.app import SotraglaceApp
    try:
        if autotest:
            from . import autotest as verification
            from .db import schema
            from .db.depot import Depot
            from .config import chemin_base, lire_config
            premier_poste = Depot(schema.ouvrir(chemin_base(lire_config()))).lister_postes(trier=True)[0]
            app = SotraglaceApp(root, poste=lire_config().get("poste") or f"{premier_poste[0]} - {premier_poste[1]}")
            verification.lancer(root, app, resultat)
        else:
            SotraglaceApp(root)
    except Exception as exc:
        log.exception("Échec du démarrage")
        if not autotest:
            messagebox.showerror("Démarrage impossible", MESSAGE_ERREUR.format(exc), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return resultat["code"]


if __name__ == "__main__":
    sys.exit(main())
