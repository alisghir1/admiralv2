import sqlite3

def reset_atelier():
    conn = sqlite3.connect('suivi_atelier.db')
    cursor = conn.cursor()

    # Supprimer uniquement les OFs et les Scans (l'onglet Atelier)
    cursor.execute("DELETE FROM Scans")
    cursor.execute("DELETE FROM OF_Gammes")
    cursor.execute("DELETE FROM CdeDetail")

    conn.commit()
    conn.close()
    print("Base Atelier réinitialisée avec succès sans toucher aux Produits/Postes.")

if __name__ == '__main__':
    reset_atelier()
