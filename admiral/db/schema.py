"""Création et mise à niveau du schéma SQLite.

La version du schéma est stockée dans PRAGMA user_version. Chaque migration fait
passer la base d'une version à la suivante ; elles sont toutes idempotentes, donc
une base créée par une ancienne version de l'application est mise à niveau sans perte.
"""
import os
import sqlite3
from datetime import datetime

OPERATIONS_PAR_DEFAUT = [
    ("DEC", "Découpe"),
    ("USI", "Usinage"),
    ("FAC", "Façonnage"),
    ("TRE", "Trempe"),
    ("EXP", "Expédition"),
]

POSTES_PAR_DEFAUT = [
    ("DEC1", "Découpe Numérique SEKTOR", "DEC"),
    ("USI1", "Centre Usinage 1", "USI"),
    ("FAC1", "Ligne Façonnage 1", "FAC"),
    ("TRE1", "Four Trempe", "TRE"),
    ("EXP1", "Zone Expédition", "EXP"),
]


def _colonnes(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _ajouter_colonne(conn, table, colonne, type_sql):
    if colonne not in _colonnes(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_sql}")


def _migration_1_tables(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS Produits (
            RefProd TEXT PRIMARY KEY,
            DesProd TEXT
        );
        CREATE TABLE IF NOT EXISTS Operations (
            RefOp TEXT PRIMARY KEY,
            LibelOp TEXT
        );
        CREATE TABLE IF NOT EXISTS Postes (
            CodPost TEXT PRIMARY KEY,
            DesPost TEXT,
            RefOp TEXT
        );
        CREATE TABLE IF NOT EXISTS Gammes (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            RefProd TEXT,
            CodeOp TEXT,
            Ordre INTEGER
        );
        CREATE TABLE IF NOT EXISTS CdeDetail (
            ID_OF TEXT PRIMARY KEY,
            CDE TEXT,
            PROD TEXT,
            DESIGN TEXT,
            OBSERV TEXT,
            Qte INTEGER DEFAULT 1,
            LignesSage TEXT
        );
        CREATE TABLE IF NOT EXISTS OF_Gammes (
            ID_OF TEXT,
            Ordre INTEGER,
            CodeOp TEXT,
            Poste_Assigne TEXT,
            PRIMARY KEY (ID_OF, Ordre)
        );
        CREATE TABLE IF NOT EXISTS Scans (
            ID_Scan INTEGER PRIMARY KEY AUTOINCREMENT,
            ID_OF TEXT NOT NULL,
            Poste TEXT NOT NULL,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            Child_Key TEXT
        );
    ''')
    # Bases créées avant l'ajout de ces colonnes
    _ajouter_colonne(conn, "CdeDetail", "LignesSage", "TEXT")
    _ajouter_colonne(conn, "Scans", "Child_Key", "TEXT")


def _migration_2_index(conn):
    conn.executescript('''
        CREATE INDEX IF NOT EXISTS idx_scans_of_poste ON Scans (ID_OF, Poste);
        CREATE INDEX IF NOT EXISTS idx_cdedetail_cde ON CdeDetail (CDE);
        CREATE INDEX IF NOT EXISTS idx_postes_refop ON Postes (RefOp);
    ''')


def _migration_3_dimensions(conn):
    # Dimensions de l'OF en champs dédiés (auparavant saisies dans OBSERV)
    _ajouter_colonne(conn, "CdeDetail", "Longueur", "INTEGER")
    _ajouter_colonne(conn, "CdeDetail", "Largeur", "INTEGER")
    _ajouter_colonne(conn, "CdeDetail", "Epaisseur", "TEXT")


def _migration_4_suivi(conn):
    # OF : statut (actif / annule), date de besoin (AAAA-MM-JJ), priorité (0 normale, 1 urgente)
    _ajouter_colonne(conn, "CdeDetail", "Statut", "TEXT DEFAULT 'actif'")
    _ajouter_colonne(conn, "CdeDetail", "DateBesoin", "TEXT")
    _ajouter_colonne(conn, "CdeDetail", "Priorite", "INTEGER DEFAULT 0")
    # Scans : une annulation est tracée au lieu d'effacer la ligne
    _ajouter_colonne(conn, "Scans", "Annule", "INTEGER DEFAULT 0")
    _ajouter_colonne(conn, "Scans", "DateAnnulation", "DATETIME")
    conn.execute("CREATE TABLE IF NOT EXISTS CommandesCloturees (CDE TEXT PRIMARY KEY, DateCloture DATETIME DEFAULT CURRENT_TIMESTAMP)")


def cle_ligne(cde, cle):
    """Clé complète d'une ligne de commande Sage : « CC240001-1000 » (les anciens OF stockaient parfois « 1000 »)."""
    cle = cle.strip()
    return cle if cle.startswith(f"{cde}-") else f"{cde}-{cle}"


def _migration_5_lignes_uniques(conn):
    """Une ligne de commande Sage ne peut appartenir qu'à un seul OF actif.

    La clé primaire sur CleLigne fait respecter la règle par la base elle-même. La colonne
    CdeDetail.LignesSage est conservée (historique, et lignes à reprendre si un OF annulé est réactivé).
    Un OF annulé libère ses lignes : il n'a pas de liaison."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS OF_LignesSage (
            CleLigne TEXT PRIMARY KEY,
            ID_OF TEXT NOT NULL
        )''')
    conn.execute("CREATE INDEX IF NOT EXISTS idx_of_lignes_of ON OF_LignesSage (ID_OF)")
    # Reprise des OF existants, du plus ancien au plus récent : en cas de doublon, le premier OF garde la ligne
    for id_of, cde, lignes in conn.execute(
            "SELECT ID_OF, CDE, LignesSage FROM CdeDetail WHERE COALESCE(Statut, 'actif') = 'actif' "
            "AND COALESCE(LignesSage, '') <> '' ORDER BY rowid").fetchall():
        conn.executemany("INSERT OR IGNORE INTO OF_LignesSage (CleLigne, ID_OF) VALUES (?, ?)",
                         [(cle_ligne(cde, c), id_of) for c in lignes.split(",") if c.strip()])


MIGRATIONS = [
    _migration_1_tables,
    _migration_2_index,
    _migration_3_dimensions,
    _migration_4_suivi,
    _migration_5_lignes_uniques,
]

VERSION_SCHEMA = len(MIGRATIONS)


def version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def initialiser(conn, postes_par_defaut=True):
    """Applique les migrations manquantes et, si demandé, crée les postes par défaut quand la table est vide."""
    actuelle = version(conn)
    if actuelle > VERSION_SCHEMA:
        raise RuntimeError(
            f"La base est en version {actuelle}, cette application gère au plus la version {VERSION_SCHEMA}. "
            "Mettez l'application à jour.")
    for numero in range(actuelle, VERSION_SCHEMA):
        with conn:
            MIGRATIONS[numero](conn)
            conn.execute(f"PRAGMA user_version = {numero + 1}")

    if postes_par_defaut and conn.execute("SELECT COUNT(*) FROM Postes").fetchone()[0] == 0:
        with conn:
            conn.executemany("INSERT OR IGNORE INTO Operations (RefOp, LibelOp) VALUES (?, ?)", OPERATIONS_PAR_DEFAUT)
            conn.executemany("INSERT OR IGNORE INTO Postes (CodPost, DesPost, RefOp) VALUES (?, ?, ?)", POSTES_PAR_DEFAUT)


def sauvegarder_avant_migration(conn, chemin):
    """Copie de la base dans sauvegardes/ (à côté de la base) avant une mise à niveau du schéma. Retourne le chemin."""
    dossier = os.path.join(os.path.dirname(os.path.abspath(chemin)), "sauvegardes")
    os.makedirs(dossier, exist_ok=True)
    nom = os.path.splitext(os.path.basename(chemin))[0]
    copie = os.path.join(dossier, f"{nom}_v{version(conn)}_avant_v{VERSION_SCHEMA}_{datetime.now():%Y-%m-%d_%H%M%S}.db")
    destination = sqlite3.connect(copie)
    with destination:
        conn.backup(destination)
    destination.close()
    return copie


def ouvrir(chemin):
    """Ouvre la base (créée si besoin) et la met à niveau.

    Une base existante est copiée dans sauvegardes/ avant toute mise à niveau du schéma.
    Pas de mode WAL : il ne fonctionne pas sur un partage réseau. Le délai d'attente
    laisse plusieurs postes écrire sans erreur "database is locked".
    """
    conn = sqlite3.connect(chemin, timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    if chemin != ":memory:" and 0 < version(conn) < VERSION_SCHEMA:
        sauvegarder_avant_migration(conn, chemin)
    initialiser(conn)
    return conn
