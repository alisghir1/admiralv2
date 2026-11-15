"""Tri des listes de commandes et d'OF.

Par défaut, tri par numéro décroissant (les plus récents en haut), dans l'ordre naturel : les nombres
contenus dans le nom sont comparés comme des nombres (OF-1000 après OF-999, CC10 après CC9), le reste comme du texte.
"""
import re

NUMERO = "N° croissant"
NUMERO_DESC = "N° décroissant"
CLIENT = "Client (A → Z)"
ETAT = "État d'avancement"
BESOIN = "Date de besoin"
URGENCE = "Urgents d'abord"

DEFAUT = NUMERO_DESC
TRIS_COMMANDES = (NUMERO_DESC, NUMERO, CLIENT, ETAT)        # le premier est le tri proposé par défaut
TRIS_OF = (NUMERO_DESC, NUMERO, BESOIN, URGENCE, ETAT)

SANS_DATE = "9999-99-99"   # les OF sans date de besoin passent après les autres


def cle_naturelle(texte):
    """Clé de tri « humaine » : 'OF-1000' -> ((1, 0, 'of-'), (0, 1000, ''))."""
    return tuple((0, int(morceau), "") if morceau.isdigit() else (1, 0, morceau.lower())
                 for morceau in re.split(r"(\d+)", str(texte or "")) if morceau)


def trier(elements, mode, numero, client=None, etat=None, besoin=None, urgent=None):
    """Trie selon le mode choisi ; à critère égal, le numéro départage (décroissant, comme le tri par défaut).

    numero, client, etat, besoin, urgent : fonctions qui lisent la donnée sur un élément.
    etat renvoie un rang (0 = à traiter en premier). Un mode sans fonction associée trie par numéro décroissant.
    """
    croissant = sorted(elements, key=lambda e: cle_naturelle(numero(e)))
    if mode == NUMERO:
        return croissant
    par_numero = croissant[::-1]
    if mode == CLIENT and client:
        # Clients vides à la fin
        return sorted(par_numero, key=lambda e: (not client(e), cle_naturelle(client(e))))
    if mode == ETAT and etat:
        return sorted(par_numero, key=etat)
    if mode == BESOIN and besoin:
        return sorted(par_numero, key=lambda e: besoin(e) or SANS_DATE)
    if mode == URGENCE and urgent:
        return sorted(par_numero, key=lambda e: (not urgent(e), (besoin(e) if besoin else None) or SANS_DATE))
    return par_numero   # NUMERO_DESC (défaut)
