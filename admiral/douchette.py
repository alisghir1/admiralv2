"""Lecture de la douchette, sans interface (testable seule).

Deux façons de brancher une douchette :
- en clavier (réglage d'usine) : elle « tape » le code puis Entrée dans la fenêtre au premier plan.
  DetecteurScan la reconnaît à sa vitesse : aucun humain ne tape six caractères en quelques millisecondes.
  Le scan est ainsi traité où que soit le curseur dans Admiral (champ de recherche, fenêtre ouverte) ;
- en port COM (réglée avec un code-barres de sa notice) : DouchetteSerie lit le port dans un fil
  d'arrière-plan. Le scan arrive même quand Admiral n'est pas au premier plan.
"""
import queue
import re
import threading

ECART_MAX_MS = 50        # entre deux caractères d'un scan (une douchette : quelques ms ; un humain : 80 ms et plus)
LONGUEUR_MIN = 6         # le plus court des codes d'Admiral : « OF-1000 » (7 caractères)
DOUBLON_SECONDES = 1.0   # le même code relu dans ce délai est un double scan de la douchette


class DetecteurScan:
    """Reconnaît une douchette en mode clavier à sa vitesse de frappe."""

    def __init__(self):
        self.caracteres = []
        self.widgets = []     # widget qui a reçu chaque caractère (pour retirer le code d'un champ de saisie)
        self.dernier = None   # heure du dernier caractère (ms, horloge des événements clavier)

    def oublier(self):
        self.caracteres, self.widgets, self.dernier = [], [], None

    def caractere(self, char, temps_ms, widget=None):
        if self.dernier is not None and abs(temps_ms - self.dernier) > ECART_MAX_MS:
            self.oublier()   # frappe humaine, ou début d'un nouveau scan
        self.caracteres.append(char)
        self.widgets.append(widget)
        self.dernier = temps_ms

    def entree(self, temps_ms):
        """Touche Entrée : (code, widgets) si les caractères qui précèdent viennent d'une douchette, sinon (None, [])."""
        rapide = self.dernier is not None and abs(temps_ms - self.dernier) <= 2 * ECART_MAX_MS
        code = "".join(self.caracteres) if rapide and len(self.caracteres) >= LONGUEUR_MIN else None
        widgets = self.widgets if code else []
        self.oublier()
        return code, widgets


class AntiDoublon:
    """Ignore le même code relu par la douchette dans la seconde (double lecture d'une étiquette)."""

    def __init__(self, delai=DOUBLON_SECONDES):
        self.delai = delai
        self.precedent = (None, -1e9)

    def doublon(self, code, maintenant):
        code_prec, temps_prec = self.precedent
        self.precedent = (code, maintenant)
        return code == code_prec and maintenant - temps_prec < self.delai


def choisir_port():
    """Port COM de la douchette quand la configuration dit "auto" : le seul port USB branché."""
    from serial.tools import list_ports
    ports = [p.device for p in list_ports.comports() if "USB" in (p.hwid or "").upper()]
    if len(ports) == 1:
        return ports[0]
    if not ports:
        raise OSError("aucun port USB : la douchette est-elle branchée et réglée en port COM ?")
    raise OSError(f"plusieurs ports USB ({', '.join(ports)}) : indiquez celui de la douchette dans config_poste.json")


class DouchetteSerie:
    """Douchette en port COM, lue dans un fil d'arrière-plan. Les codes lus attendent dans une file que
    l'interface vide (codes()) : le fil ne touche jamais à Tk. Débranchée, elle est recherchée toutes les 5 s.
    Un code se termine par un retour à la ligne ou, à défaut, par un silence de 0,2 s."""

    ATTENTE_RECONNEXION = 5

    def __init__(self, port, vitesse=9600, ouvrir=None):
        self.port = port
        self.vitesse = vitesse
        self.etat = "recherche…"
        self.connectee = False
        self._file = queue.Queue()
        self._arret = threading.Event()
        self._ouvrir = ouvrir or self._ouvrir_port

    def _ouvrir_port(self):
        import serial
        port = choisir_port() if str(self.port).lower() == "auto" else self.port
        return serial.Serial(port, self.vitesse, timeout=0.2)

    def demarrer(self):
        threading.Thread(target=self._boucle, name="douchette", daemon=True).start()
        return self

    def arreter(self):
        self._arret.set()

    def codes(self):
        """Codes lus depuis le dernier appel (fil de l'interface)."""
        lus = []
        while True:
            try:
                lus.append(self._file.get_nowait())
            except queue.Empty:
                return lus

    def _publier(self, brut):
        texte = brut.decode("latin-1", errors="replace").strip()
        if texte:
            self._file.put(texte)

    def _boucle(self):
        while not self._arret.is_set():
            try:
                liaison = self._ouvrir()
            except Exception as exc:   # port absent, occupé, pilote manquant…
                self.connectee, self.etat = False, f"absente ({exc})"
                self._arret.wait(self.ATTENTE_RECONNEXION)
                continue
            self.connectee, self.etat = True, f"connectée ({getattr(liaison, 'port', self.port)})"
            tampon = b""
            try:
                while not self._arret.is_set():
                    donnees = liaison.read(64)
                    if not donnees:
                        if tampon:   # pas de fin de ligne envoyée : le silence termine le code
                            self._publier(tampon)
                            tampon = b""
                        continue
                    tampon += donnees
                    *complets, tampon = re.split(rb"[\r\n]+", tampon)
                    for brut in complets:
                        self._publier(brut)
            except Exception as exc:   # douchette débranchée pendant la lecture
                self.connectee, self.etat = False, f"débranchée ({exc})"
            finally:
                try:
                    liaison.close()
                except Exception:
                    pass
            self._arret.wait(self.ATTENTE_RECONNEXION)
