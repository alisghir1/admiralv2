import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(BASE_DIR, "suivi_atelier.db")

def clean():
    print("Nettoyage du jeu de données de test...")

    # 1. Nettoyage des CSV dans data/
    if os.path.exists(DATA_DIR):
        for fname in ["F-DOCENTETE.csv", "F-DOCLIGNE.csv", "docentete.csv", "docligne.csv"]:
            p = os.path.join(DATA_DIR, fname)
            if os.path.exists(p):
                os.remove(p)
                print(f"-> Fichier {fname} supprimé.")

    # 2. Nettoyage de la base de données
    if os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Scans")
        cursor.execute("DELETE FROM OF_Gammes")
        cursor.execute("DELETE FROM CdeDetail")
        cursor.execute("DELETE FROM Gammes")
        cursor.execute("DELETE FROM Produits")
        conn.commit()
        conn.close()
        print("-> Tables Scans, OF_Gammes, CdeDetail, Gammes et Produits vidées.")

    print("\n✅ Nettoyage terminé ! Les données de test ont été entièrement supprimées.")

if __name__ == "__main__":
    clean()
