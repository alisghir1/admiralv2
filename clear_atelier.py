"""Remet l'atelier à zéro (même effet que Administration > Mise en service > « Remettre à zéro ») :
OF, scans, validations, clôtures et copie des commandes Sage effacés ; référentiel et chefs d'atelier gardés.
Une copie de la base est faite dans sauvegardes/ avant le vidage."""
from admiral import config
from admiral.db import schema
from admiral.db.depot import Depot

DB_FILE = config.chemin_base(config.lire_config())


def reset_atelier():
    conn = schema.ouvrir(DB_FILE)   # base mise à niveau : toutes les tables existent
    copie = schema.sauvegarder(conn, DB_FILE, "avant_remise_a_zero")
    Depot(conn).remettre_a_zero()
    conn.close()
    print(f"Atelier remis à zéro (référentiel et chefs gardés). Copie de la base : {copie}")


if __name__ == '__main__':
    reset_atelier()
