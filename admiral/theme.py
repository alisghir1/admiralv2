"""Jetons de design : couleurs, typographie et espacements (thème industriel sombre).

Règles : chaque état est signalé par un mot ET une couleur (jamais la couleur seule) ;
tout texte atteint un contraste d'au moins 4,5:1 sur son fond ; les zones cliquables
de l'atelier font au moins 44 px de haut.
"""
import sys

# --- Fonds et surfaces (du plus sombre au plus clair) ---
FOND = "#0B1120"            # fond de fenêtre
CARTE = "#0F172A"           # cartes et panneaux
SURFACE = "#1E293B"         # tableaux, champs, éléments posés sur une carte
SURFACE_SURVOL = "#273449"
SURFACE_ACTIVE = "#162032"  # élément sélectionné
BORDURE = "#334155"
BORDURE_SURVOL = "#475569"

# --- Texte ---
TEXTE = "#F8FAFC"           # 18:1 sur FOND
TEXTE_ATTENUE = "#94A3B8"   # 5,7:1 sur SURFACE
TEXTE_DESACTIVE = "#64748B"
TEXTE_ENFANT = "#94A3B8"
BLANC = "#FFFFFF"
TITRE = "#38BDF8"           # 8,3:1 sur CARTE

# --- Actions (texte du bouton entre parenthèses, contraste ≥ 4,5:1) ---
PRIMAIRE = "#2563EB"            # (blanc) 5,2:1
PRIMAIRE_SURVOL = "#1D4ED8"
SECONDAIRE = "#334155"          # (texte clair) 9,9:1
SECONDAIRE_SURVOL = "#475569"
SUCCES = "#047857"              # (blanc) 5,5:1 — l'ancien #059669 n'atteignait que 3,8:1
SUCCES_SURVOL = "#065F46"
ALERTE = "#D97706"              # (texte sombre FOND) 5,9:1 — le blanc n'atteignait que 3,2:1
ALERTE_SURVOL = "#B45309"
ERREUR = "#DC2626"              # (blanc) 4,8:1
ERREUR_SURVOL = "#B91C1C"

# --- États (fond de pastille / texte de pastille, contraste ≥ 6,9:1) ---
SUCCES_FOND = "#064E3B"
SUCCES_TEXTE = "#A7F3D0"
SUCCES_VIF = "#34D399"
ALERTE_FOND = "#78350F"
ALERTE_TEXTE = "#FDE68A"
ERREUR_FOND = "#7F1D1D"
ERREUR_TEXTE = "#FECACA"
INFO_FOND = "#1E3A8A"
INFO_TEXTE = "#BFDBFE"
NEUTRE_FOND = "#334155"
NEUTRE_TEXTE = "#E2E8F0"

# État -> (libellé, fond, texte). Même vocabulaire dans tous les écrans.
ETATS = {
    "pret":        ("Prêt",       INFO_FOND,    INFO_TEXTE),
    "encours":     ("En cours",   ALERTE_FOND,  ALERTE_TEXTE),
    "attente":     ("En attente", NEUTRE_FOND,  NEUTRE_TEXTE),
    "bloque":      ("Bloqué",     ERREUR_FOND,  ERREUR_TEXTE),
    "terminee":    ("Terminé",    SUCCES_FOND,  SUCCES_TEXTE),
    "pas_demarre": ("À faire",    NEUTRE_FOND,  NEUTRE_TEXTE),
    "urgent":      ("Urgent",     ERREUR_FOND,  ERREUR_TEXTE),
    "retard":      ("En retard",  ERREUR_FOND,  ERREUR_TEXTE),
    "annule":      ("Annulé",     SURFACE,      TEXTE_ATTENUE),
    "cloturee":    ("Clôturée",   SURFACE,      TEXTE_ATTENUE),
}

# --- Typographie : police système de chaque plateforme ---
if sys.platform == "win32":
    FAMILLE, FAMILLE_CHIFFRES = "Segoe UI", "Consolas"
elif sys.platform == "darwin":
    FAMILLE, FAMILLE_CHIFFRES = "Helvetica Neue", "Menlo"
else:
    FAMILLE, FAMILLE_CHIFFRES = "DejaVu Sans", "DejaVu Sans Mono"

# Échelle (px) : légende, corps, sous-titre, titre, chiffre de carte, chiffre de scan
TAILLE_LEGENDE = 12
TAILLE_CORPS = 14
TAILLE_SOUS_TITRE = 16
TAILLE_TITRE = 20
TAILLE_CHIFFRE = 28
TAILLE_CHIFFRE_SCAN = 40


def police(taille=TAILLE_CORPS, gras=False):
    return (FAMILLE, taille, "bold") if gras else (FAMILLE, taille)


def police_chiffres(taille=TAILLE_CORPS, gras=True):
    """Chiffres et codes (OF-1001, 3 / 7) : chasse fixe, les colonnes ne bougent pas."""
    return (FAMILLE_CHIFFRES, taille, "bold") if gras else (FAMILLE_CHIFFRES, taille)


# --- Espacements et formes ---
ESPACE_XS, ESPACE_S, ESPACE_M, ESPACE_L, ESPACE_XL = 4, 8, 12, 16, 24
RAYON_CONTROLE = 8
RAYON_CARTE = 12
RAYON_ONGLET = 18            # onglets principaux en pilule
HAUTEUR_BOUTON = 40          # bureau d'étude, souris
HAUTEUR_BOUTON_ATELIER = 48  # atelier : doigts, gants
HAUTEUR_LIGNE_TABLEAU = 40

# --- Durées d'affichage des messages (ms) ---
DUREE_MESSAGE_SUCCES = 5000
DUREE_MESSAGE_ERREUR = 8000
DUREE_SURBRILLANCE = 1500
