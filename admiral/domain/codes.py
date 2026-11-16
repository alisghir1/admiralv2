"""Codes-barres d'Admiral : ce que contient chaque code et comment un scan de douchette est relu.

Chaque élément a son propre code, unique (ce sont les clés de la base) et de forme distincte :
- commande : son numéro Sage, « CC261234 » (l'ancien « CMD-CC261234 » est encore reconnu) ;
- OF : son numéro, « OF261234-01 » (ou « OF-1000 » pour les OF d'avant la numérotation par commande) ;
- article (ligne de commande) : « CC261234-1000 », numéro de la commande et numéro de la ligne dans Sage.
Ils sont imprimés en Code 128, que toutes les douchettes lisent.
"""

PREFIXE_ANCIEN_COMMANDE = "CMD-"

# Code de la page d'essai : chiffres, tiret et les lettres que le clavier AZERTY déplace (A, Z, Q, W, M)
CODE_ESSAI = "TEST-0123456789-AZQWM"

# Une douchette réglée en clavier américain sur un PC en AZERTY tape la touche, pas le caractère :
# « 2 » arrive en « é », « - » en « ) », « A » en « Q », « M » en « ? »… On remet les bons caractères.
_CLAVIER_AMERICAIN = str.maketrans({
    "&": "1", "é": "2", "É": "2", '"': "3", "'": "4", "(": "5", "-": "6", "è": "7", "È": "7", "_": "8",
    "ç": "9", "Ç": "9", "à": "0", "À": "0", ")": "-",
    "A": "Q", "Q": "A", "Z": "W", "W": "Z", "a": "q", "q": "a", "z": "w", "w": "z", "?": "M", ",": "M",
})
# Caractères qui n'existent dans aucun code d'Admiral : leur présence trahit le clavier américain
_SIGNES_CLAVIER_AMERICAIN = set("&éÉ\"'(èÈ_çÇàÀ")


def lire_scan(texte):
    """(code, clavier_corrige) : le code lu par la douchette en majuscules, corrigé si la douchette tape
    en clavier américain (clavier_corrige vaut alors True : à signaler pour la régler en français)."""
    brut = (texte or "").strip()
    if any(c in _SIGNES_CLAVIER_AMERICAIN for c in brut):
        return brut.translate(_CLAVIER_AMERICAIN).upper(), True
    return brut.upper(), False


def code_article(cde, cle):
    """« CC261234-1000 » : code-barres d'une ligne de commande (cle : « 1000 » ou « CC261234-1000 »)."""
    cle = cle.strip()
    return cle if cle.startswith(f"{cde}-") else f"{cde}-{cle}"


def commande_du_code(code):
    """Numéro de commande d'un code « CC261234 » ou « CMD-CC261234 »."""
    return code[len(PREFIXE_ANCIEN_COMMANDE):] if code.startswith(PREFIXE_ANCIEN_COMMANDE) else code


def commande_de_l_article(code):
    """« CC261234-1000 » -> « CC261234 », ou None si le code n'a pas la forme d'un code article."""
    cde, tiret, ligne = code.rpartition("-")
    return cde if tiret and cde and ligne.isdigit() else None
