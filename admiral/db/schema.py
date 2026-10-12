"""Création et mise à niveau du schéma SQLite.

La version du schéma est stockée dans PRAGMA user_version. Chaque migration fait
passer la base d'une version à la suivante ; elles sont toutes idempotentes, donc
une base créée par une ancienne version de l'application est mise à niveau sans perte.
"""
import sqlite3

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


MIGRATIONS = [
    _migration_1_tables,
    _migration_2_index,
    _migration_3_dimensions,
    _migration_4_suivi,
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


def ouvrir(chemin):
    """Ouvre la base (créée si besoin) et la met à niveau.

    Pas de mode WAL : il ne fonctionne pas sur un partage réseau. Le délai d'attente
    laisse plusieurs postes écrire sans erreur "database is locked".
    """
    conn = sqlite3.connect(chemin, timeout=10)
    conn.execute("PRAGMA busy_timeout = 10000")
    initialiser(conn)
    return conn
