"""Jeu de démonstration pour faire valider l'application (version envoyée au client).

Usage : python -m admiral.demo <dossier>
Crée dans le dossier : data/F-DOCENTETE.csv, data/F-DOCLIGNE.csv et suivi_atelier.db.
Le poste n'est pas configuré : l'application le demande au premier lancement.
"""
import os
import sys
from datetime import date, timedelta

from .db import schema
from .db.depot import Depot

COMMANDES = [
    ("CC240001", "MIROITERIE DU NORD"),
    ("CC240002", "MENUISERIE DU CENTRE"),
    ("CC240003", "FACADES & VERRES DE L'OUEST"),
    ("CC240004", "VERANDAS DU SUD"),
    ("CC240005", "HOTEL LE GRAND"),
    ("CC240006", "AGENCEMENT BOUTIQUE LUMIERE"),
    ("CC240007", "CLINIQUE SAINT-PAUL"),
]

LIGNES = [
    # pièce, ligne, référence, désignation, qté, longueur, largeur
    ("CC240001", 1000, "VITR-4-16-4", "Double Vitrage 4/16/4 Clair", 5, 1200, 800),
    ("CC240001", 2000, "FEUILLE-CLAIR-6", "Verre Trempé 6mm Clair JPP", 2, 2100, 950),
    ("CC240002", 1000, "MIROIR-ARGENT-4", "Miroir Argent 4mm JPP", 4, 1500, 600),
    ("CC240003", 1000, "VITR-4-16-4", "Double Vitrage 4/16/4 Gaz Argon", 8, 1800, 1100),
    ("CC240003", 2000, "FEUILLE-CLAIR-6", "Porte en Verre Trempé 6mm Securit", 3, 2040, 830),
    ("CC240004", 1000, "VITR-4-16-4", "Double Vitrage Véranda", 12, 1600, 900),
    ("CC240005", 1000, "MIROIR-ARGENT-4", "Miroir Salle de Bain", 6, 900, 700),
    ("CC240006", 1000, "FEUILLE-CLAIR-10", "Étagère Verre Trempé 10mm", 10, 800, 300),
    ("CC240006", 2000, "MIROIR-ARGENT-4", "Miroir Cabine Essayage", 4, 1800, 600),
    ("CC240007", 1000, "VITR-4-16-4", "Double Vitrage Feuilleté Sécurité", 6, 1400, 1000),
]

PRODUITS = [
    ("VITR-4-16-4", "Double Vitrage Isolant 4/16/4", ["DEC", "FAC", "TRE"]),
    ("FEUILLE-CLAIR-6", "Verre Simple 6mm Clair", ["DEC", "USI", "TRE"]),
    ("FEUILLE-CLAIR-10", "Verre Simple 10mm Clair", ["DEC", "FAC", "TRE", "EXP"]),
    ("MIROIR-ARGENT-4", "Miroir Décoratif Argent 4mm", ["DEC", "FAC"]),
]


def creer(dossier, ecraser=False):
    os.makedirs(os.path.join(dossier, "data"), exist_ok=True)
    chemin_base = os.path.join(dossier, "suivi_atelier.db")
    if os.path.exists(chemin_base):
        if not ecraser:
            raise FileExistsError(f"{chemin_base} existe déjà")
        os.remove(chemin_base)

    jour = date.today().strftime("%d/%m/%Y")
    with open(os.path.join(dossier, "data", "F-DOCENTETE.csv"), "w", encoding="utf-8", newline="") as f:
        f.write("DO_Piece,DO_Date,DO_Tiers\n")
        for piece, client in COMMANDES:
            f.write(f'{piece},{jour},"{client}"\n')
    with open(os.path.join(dossier, "data", "F-DOCLIGNE.csv"), "w", encoding="utf-8", newline="") as f:
        f.write("DO_Piece,DL_Ligne,AR_Ref,DL_Design,DL_Qte,LONG,LARG\n")
        for ligne in LIGNES:
            f.write(",".join(str(v) for v in ligne) + "\n")

    conn = schema.ouvrir(chemin_base)  # crée aussi les opérations et postes par défaut
    depot = Depot(conn)
    for ref, designation, gamme in PRODUITS:
        depot.enregistrer_produit(ref, designation, gamme)

    dans = lambda jours: (date.today() + timedelta(days=jours)).isoformat()
    vitr = [("DEC", None), ("FAC", "FAC1"), ("TRE", None)]
    feuille = [("DEC", None), ("USI", None), ("TRE", None)]
    miroir = [("DEC", None), ("FAC", None)]

    # CC240001 : un OF en cours au façonnage, un OF bloqué (rien découpé)
    a = depot.creer_of("CC240001", "VITR-4-16-4", "Double Vitrage 4/16/4 Clair", "Intercalaire noir", 5,
                       "CC240001-1000", vitr, 1200, 800, "4/16/4", dans(3))
    depot.creer_of("CC240001", "FEUILLE-CLAIR-6", "Verre Trempé 6mm Clair JPP", "", 2,
                       "CC240001-2000", feuille, 2100, 950, "6", dans(3))
    # CC240002 : terminé (découpe et façonnage complets)
    c = depot.creer_of("CC240002", "MIROIR-ARGENT-4", "Miroir Argent 4mm JPP", "Bords polis", 4,
                       "CC240002-1000", miroir, 1500, 600, "4", dans(1))
    # CC240003 : urgent, découpe commencée ; porte en verre pas démarrée
    e = depot.creer_of("CC240003", "VITR-4-16-4", "Double Vitrage 4/16/4 Gaz Argon", "", 8,
                       "CC240003-1000", vitr, 1800, 1100, "4/16/4", dans(2), priorite=1)
    depot.creer_of("CC240003", "FEUILLE-CLAIR-6", "Porte en Verre Trempé 6mm Securit", "Perçage poignée", 3,
                   "CC240003-2000", feuille, 2040, 830, "6", dans(5))
    # CC240004 : en retard, trempe en cours
    f = depot.creer_of("CC240004", "VITR-4-16-4", "Double Vitrage Véranda", "", 12,
                       "CC240004-1000", vitr, 1600, 900, "4/16/4", dans(-2))
    # CC240005 : commande sans OF (à créer au Bureau d'Étude)
    # CC240006 : une étagère à 4 opérations, un OF annulé
    g = depot.creer_of("CC240006", "FEUILLE-CLAIR-10", "Étagère Verre Trempé 10mm", "Joints plats", 10,
                       "CC240006-1000", [("DEC", None), ("FAC", None), ("TRE", None), ("EXP", None)], 800, 300, "10", dans(7))
    h = depot.creer_of("CC240006", "MIROIR-ARGENT-4", "Miroir Cabine Essayage", "Remplacé par une autre référence", 4,
                       "CC240006-2000", miroir, 1800, 600, "4")
    depot.changer_statut_of(h, "annule")
    # CC240007 : livrée et clôturée
    i = depot.creer_of("CC240007", "VITR-4-16-4", "Double Vitrage Feuilleté Sécurité", "", 6,
                       "CC240007-1000", vitr, 1400, 1000, "44.2/16/4")

    depot.ajouter_scans(a, [("DEC1", 5), ("FAC1", 2)])
    depot.ajouter_scans(c, [("DEC1", 4), ("FAC1", 4)])
    depot.ajouter_scans(e, [("DEC1", 3)])
    depot.ajouter_scans(f, [("DEC1", 12), ("FAC1", 12), ("TRE1", 5)])
    depot.ajouter_scans(g, [("DEC1", 10), ("FAC1", 4)])
    depot.ajouter_scans(i, [("DEC1", 6), ("FAC1", 6), ("TRE1", 6)])
    depot.annuler_scans(depot.ids_scans(a, "FAC")[:1])   # une annulation, visible dans l'historique
    depot.ajouter_scans(a, [("FAC1", 1)])
    depot.cloturer_commande("CC240007")
    conn.close()
    return chemin_base


if __name__ == "__main__":
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(arguments) != 1:
        print(__doc__)
        sys.exit(1)
    print("Démonstration créée :", creer(arguments[0], ecraser="--ecraser" in sys.argv))
