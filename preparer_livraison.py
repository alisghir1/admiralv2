"""Prépare le dossier à envoyer au client avec ses vraies données.

Usage : python preparer_livraison.py [--base suivi_atelier.db] [--classeur "data/BASE SAGE ADM.xlsx"]
                                     [--sortie livraison_client/Admiral] [--ecraser]

Le dossier reçoit :
- suivi_atelier.db : une base neuve avec le référentiel de --base (produits, opérations, postes, gammes),
  sans OF, sans scans et sans copie Sage (refaite au premier lancement) ;
- data/ : le classeur Sage ;
- LISEZMOI.txt : le mode d'installation (LISEZMOI_INSTALLATION.txt).
Il reste à y glisser Admiral.exe, téléchargé depuis GitHub Actions (artefact « Admiral_exe »).

Les vraies données ne vont jamais dans le dépôt (il est public) : livraison_client/ est ignoré par git.
"""
import argparse
import os
import pathlib
import shutil
import sqlite3
import sys

from admiral.db import schema

DOSSIER = os.path.dirname(os.path.abspath(__file__))

# Tables du référentiel recopiées dans la base livrée (Gammes sans son identifiant, renuméroté)
REFERENTIEL = [
    ("Produits", "RefProd, DesProd", "RefProd"),
    ("Operations", "RefOp, LibelOp", "RefOp"),
    ("Postes", "CodPost, DesPost, RefOp", "CodPost"),
    ("Gammes", "RefProd, CodeOp, Ordre", "RefProd, Ordre"),
]


def creer_base_livraison(source, destination):
    """Base neuve (schéma à jour) avec le référentiel de la base source. Retourne {table: nombre de lignes}."""
    origine = sqlite3.connect(pathlib.Path(source).resolve().as_uri() + "?mode=ro", uri=True)
    conn = sqlite3.connect(destination)
    try:
        schema.initialiser(conn, postes_par_defaut=False)
        comptes = {}
        with conn:
            for table, colonnes, tri in REFERENTIEL:
                lignes = origine.execute(f"SELECT {colonnes} FROM {table} ORDER BY {tri}").fetchall()
                marques = ", ".join("?" * len(colonnes.split(",")))
                conn.executemany(f"INSERT INTO {table} ({colonnes}) VALUES ({marques})", lignes)
                comptes[table] = len(lignes)
        return comptes
    finally:
        origine.close()
        conn.close()


def anomalies_referentiel(chemin):
    """Points du référentiel qui empêcheront des OF d'avancer (à régler avec le client dans l'Administration)."""
    conn = sqlite3.connect(pathlib.Path(chemin).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        inconnues = conn.execute(
            "SELECT CodeOp, GROUP_CONCAT(RefProd, ', ') FROM Gammes "
            "WHERE CodeOp NOT IN (SELECT RefOp FROM Operations) GROUP BY CodeOp ORDER BY CodeOp").fetchall()
        sans_poste = conn.execute(
            "SELECT RefOp, LibelOp FROM Operations WHERE RefOp NOT IN (SELECT RefOp FROM Postes WHERE RefOp IS NOT NULL) "
            "ORDER BY RefOp").fetchall()
    finally:
        conn.close()
    return ([f"gamme de {produits} : « {code} » n'est pas une opération" for code, produits in inconnues]
            + [f"opération {ref} ({libelle}) : aucun poste, elle ne pourra pas être scannée" for ref, libelle in sans_poste])


def preparer(base, classeur, sortie, ecraser=False):
    if os.path.exists(sortie):
        if not ecraser:
            raise FileExistsError(f"{sortie} existe déjà (--ecraser pour le refaire)")
        shutil.rmtree(sortie)
    os.makedirs(os.path.join(sortie, "data"))
    comptes = creer_base_livraison(base, os.path.join(sortie, "suivi_atelier.db"))
    shutil.copy2(classeur, os.path.join(sortie, "data", os.path.basename(classeur)))
    shutil.copy2(os.path.join(DOSSIER, "LISEZMOI_INSTALLATION.txt"), os.path.join(sortie, "LISEZMOI.txt"))
    return comptes


def main():
    parser = argparse.ArgumentParser(description="Prépare le dossier client avec les vraies données.")
    parser.add_argument("--base", default=os.path.join(DOSSIER, "suivi_atelier.db"),
                        help="base dont on reprend le référentiel (défaut : suivi_atelier.db)")
    parser.add_argument("--classeur", default=os.path.join(DOSSIER, "data", "BASE SAGE ADM.xlsx"),
                        help="classeur Sage à livrer (défaut : data/BASE SAGE ADM.xlsx)")
    parser.add_argument("--sortie", default=os.path.join(DOSSIER, "livraison_client", "Admiral"),
                        help="dossier à créer (défaut : livraison_client/Admiral)")
    parser.add_argument("--ecraser", action="store_true", help="refait le dossier s'il existe")
    args = parser.parse_args()

    for chemin in (args.base, args.classeur):
        if not os.path.isfile(chemin):
            sys.exit(f"Introuvable : {chemin}")
    try:
        comptes = preparer(args.base, args.classeur, args.sortie, args.ecraser)
    except FileExistsError as exc:
        sys.exit(str(exc))

    print(f"Dossier prêt : {args.sortie}")
    print("  Base neuve : " + ", ".join(f"{n} {table.lower()}" for table, n in comptes.items()) + ", aucun OF ni scan")
    print(f"  Classeur Sage : data/{os.path.basename(args.classeur)}")
    anomalies = anomalies_referentiel(os.path.join(args.sortie, "suivi_atelier.db"))
    if anomalies:
        print("  À régler avec le client (onglet Administration) :")
        for anomalie in anomalies:
            print(f"    - {anomalie}")
    print("Il reste à y glisser Admiral.exe (GitHub Actions, artefact « Admiral_exe »), puis à compresser le dossier.")


if __name__ == "__main__":
    main()
