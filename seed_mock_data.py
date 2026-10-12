import os
import csv

from admiral import config
from admiral.db import schema

DATA_DIR = config.dossier_sage(config.lire_config())
DB_FILE = config.chemin_base(config.lire_config())

def seed():
    print("Génération du jeu de données de test...")
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Génération des fichiers CSV Sage
    file_entetes = os.path.join(DATA_DIR, "F-DOCENTETE.csv")
    entetes_rows = [
        {"DO_Piece": "CC240001", "DO_Date": "12/10/2026", "DO_Tiers": "MIROITERIE DU NORD"},
        {"DO_Piece": "CC240002", "DO_Date": "12/10/2026", "DO_Tiers": "MENUISERIE DU CENTRE"},
        {"DO_Piece": "CC240003", "DO_Date": "12/10/2026", "DO_Tiers": "FACADES & VERRES DE L'OUEST"}
    ]
    with open(file_entetes, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["DO_Piece", "DO_Date", "DO_Tiers"])
        writer.writeheader()
        writer.writerows(entetes_rows)
    print(f"-> {file_entetes} généré (3 commandes).")

    file_lignes = os.path.join(DATA_DIR, "F-DOCLIGNE.csv")
    lignes_rows = [
        {"DO_Piece": "CC240001", "DL_Ligne": "1000", "AR_Ref": "VITR-4-16-4", "DL_Design": "Double Vitrage 4/16/4 Clair", "DL_Qte": "5", "LONG": "1200", "LARG": "800"},
        {"DO_Piece": "CC240001", "DL_Ligne": "2000", "AR_Ref": "FEUILLE-CLAIR-6", "DL_Design": "Verre Trempé 6mm Clair JPP", "DL_Qte": "2", "LONG": "2100", "LARG": "950"},
        {"DO_Piece": "CC240002", "DL_Ligne": "1000", "AR_Ref": "MIROIR-ARGENT-4", "DL_Design": "Miroir Argent 4mm JPP", "DL_Qte": "4", "LONG": "1500", "LARG": "600"},
        {"DO_Piece": "CC240003", "DL_Ligne": "1000", "AR_Ref": "VITR-4-16-4", "DL_Design": "Double Vitrage 4/16/4 Gaz Argon", "DL_Qte": "8", "LONG": "1800", "LARG": "1100"},
        {"DO_Piece": "CC240003", "DL_Ligne": "2000", "AR_Ref": "FEUILLE-CLAIR-6", "DL_Design": "Porte en Verre Trempé 6mm Securit", "DL_Qte": "3", "LONG": "2040", "LARG": "830"}
    ]
    with open(file_lignes, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["DO_Piece", "DL_Ligne", "AR_Ref", "DL_Design", "DL_Qte", "LONG", "LARG"])
        writer.writeheader()
        writer.writerows(lignes_rows)
    print(f"-> {file_lignes} généré (5 lignes d'articles).")

    # 2. Remplissage de la base SQLite
    conn = schema.ouvrir(DB_FILE)
    cursor = conn.cursor()

    # Nettoyage préalable des tables concernées
    cursor.execute("DELETE FROM Scans")
    cursor.execute("DELETE FROM OF_Gammes")
    cursor.execute("DELETE FROM CdeDetail")
    cursor.execute("DELETE FROM Gammes")
    cursor.execute("DELETE FROM Produits")

    # Insertion du catalogue produits de base
    produits = [
        ("VITR-4-16-4", "Double Vitrage Isolant 4/16/4"),
        ("FEUILLE-CLAIR-6", "Verre Simple 6mm Clair"),
        ("MIROIR-ARGENT-4", "Miroir Décoratif Argent 4mm")
    ]
    cursor.executemany("INSERT INTO Produits (RefProd, DesProd) VALUES (?, ?)", produits)

    # Insertion des gammes de fabrication standard pour ces produits
    gammes = [
        # Double vitrage : Découpe -> Façonnage -> Trempe
        ("VITR-4-16-4", "DEC", 1),
        ("VITR-4-16-4", "FAC", 2),
        ("VITR-4-16-4", "TRE", 3),
        # Verre simple : Découpe -> Usinage -> Trempe
        ("FEUILLE-CLAIR-6", "DEC", 1),
        ("FEUILLE-CLAIR-6", "USI", 2),
        ("FEUILLE-CLAIR-6", "TRE", 3),
        # Miroir : Découpe -> Façonnage
        ("MIROIR-ARGENT-4", "DEC", 1),
        ("MIROIR-ARGENT-4", "FAC", 2)
    ]
    cursor.executemany("INSERT INTO Gammes (RefProd, CodeOp, Ordre) VALUES (?, ?, ?)", gammes)

    # Création des OFs initiaux pour la Commande CC240001
    cursor.execute("""
        INSERT INTO CdeDetail (ID_OF, CDE, PROD, DESIGN, OBSERV, Qte, LignesSage)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("OF-1001", "CC240001", "VITR-4-16-4", "Double Vitrage 4/16/4 Clair", "1200 x 800 mm", 7, "CC240001-1000,CC240001-2000"))

    cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", ("OF-1001", 1, "DEC", "DEC1"))
    cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", ("OF-1001", 2, "FAC", "FAC1"))
    cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", ("OF-1001", 3, "TRE", "TRE1"))

    # Création d'un OF pour la Commande CC240002 (avec 1 scan pour montrer le statut 'En cours')
    cursor.execute("""
        INSERT INTO CdeDetail (ID_OF, CDE, PROD, DESIGN, OBSERV, Qte, LignesSage)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("OF-1002", "CC240002", "MIROIR-ARGENT-4", "Miroir Argent 4mm JPP", "1500 x 600 mm", 4, "CC240002-1000"))

    cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", ("OF-1002", 1, "DEC", "DEC1"))
    cursor.execute("INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)", ("OF-1002", 2, "FAC", "FAC1"))

    # Ajouter 1 scan sur OF-1002 pour simuler un démarrage
    cursor.execute("INSERT INTO Scans (ID_OF, Poste) VALUES (?, ?)", ("OF-1002", "DEC1"))

    conn.commit()
    conn.close()
    print("-> Base SQLite 'suivi_atelier.db' configurée avec succès !")
    print("\nCommandes prêtes :")
    print(" - CC240001 : 1 OF prêt à scanner (OF-1001, Qté 5) au poste DEC1")
    print(" - CC240002 : 1 OF démarré (OF-1002, 1/4 scanné) au poste DEC1")
    print(" - CC240003 : Commande sans OF (disponible dans le Bureau d'Étude pour tester la création d'OF)")

if __name__ == "__main__":
    seed()
