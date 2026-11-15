from admiral import config
from admiral.db import schema

DB_FILE = config.chemin_base(config.lire_config())

def reset_atelier():
    conn = schema.ouvrir(DB_FILE)   # base mise à niveau : toutes les tables existent
    cursor = conn.cursor()

    # Supprimer uniquement les OF, leurs scans, lignes et validations (l'onglet Atelier)
    cursor.execute("DELETE FROM Scans")
    cursor.execute("DELETE FROM OF_Gammes")
    cursor.execute("DELETE FROM OF_LignesSage")
    cursor.execute("DELETE FROM ValidationsChef")
    cursor.execute("DELETE FROM CdeDetail")

    conn.commit()
    conn.close()
    print("Base Atelier réinitialisée avec succès sans toucher aux Produits/Postes.")

if __name__ == '__main__':
    reset_atelier()
