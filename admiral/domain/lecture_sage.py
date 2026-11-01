"""Lecture du dossier Sage dans un fil d'arrière-plan.

Lire le classeur prend plusieurs secondes (80 000 lignes, parfois sur un partage réseau) :
dans le fil de l'interface, l'écran du poste serait figé pendant ce temps. Le fil ne fait que
lire les fichiers ; la base et l'interface restent dans le fil principal.
Les fichiers ne sont relus que s'ils ont changé depuis la dernière lecture réussie.
"""
import os
import threading

from . import sage

EN_COURS = object()  # resultat() pendant la lecture
EXTENSIONS = (".xlsx", ".csv")


def signature(dossier):
    """Empreinte des fichiers Sage du dossier (nom, date, taille), ou None si le dossier est inaccessible.
    Elle change dès qu'un fichier est enregistré, même avec le même contenu (actualisation dans Excel)."""
    try:
        noms = sorted(os.listdir(dossier))
    except OSError:
        return None
    empreinte = []
    for nom in noms:
        if nom.lower().endswith(EXTENSIONS) and not nom.startswith("~$"):
            try:
                etat = os.stat(os.path.join(dossier, nom))
            except OSError:
                continue  # supprimé entre-temps
            empreinte.append((nom, etat.st_mtime_ns, etat.st_size))
    return tuple(empreinte)


class LectureEnFond:
    """lancer(dossier), puis resultat() jusqu'à obtenir autre chose que EN_COURS :
    None (fichiers inchangés, rien à faire), DonneesSage (ou None si le dossier n'existe pas),
    ou l'exception levée par la lecture (SageIllisible, erreur d'accès…)."""

    def __init__(self):
        self._fil = None
        self._resultat = None
        self._signature = False  # fichiers de la dernière lecture réussie (False : aucune)

    def noter(self, empreinte):
        """Lecture faite hors du fil (démarrage, bouton « Actualiser Sage ») : inutile de relire ces fichiers."""
        self._signature = empreinte

    def oublier(self):
        """La prochaine lecture relit les fichiers, même inchangés."""
        self._signature = False

    def lancer(self, dossier):
        """Démarre une lecture si les fichiers ont changé ; sans effet si une lecture est déjà en cours."""
        if self._fil and self._fil.is_alive():
            return
        self._resultat = None
        empreinte = signature(dossier)
        if empreinte == self._signature:
            return
        self._fil = threading.Thread(target=self._lire, args=(dossier, empreinte), name="lecture-sage", daemon=True)
        self._fil.start()

    def _lire(self, dossier, empreinte):
        try:
            self._resultat = sage.charger(dossier)
            self._signature = empreinte  # empreinte prise avant la lecture : un enregistrement pendant la lecture sera relu
        except Exception as exc:
            self._resultat = exc

    def attendre(self, delai=None):
        if self._fil:
            self._fil.join(delai)

    def resultat(self):
        """Résultat de la dernière lecture lancée, rendu une seule fois (ensuite None)."""
        if self._fil and self._fil.is_alive():
            return EN_COURS
        resultat, self._resultat = self._resultat, None
        return resultat
