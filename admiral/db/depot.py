"""Accès aux données : toutes les requêtes SQL de l'application sont ici.

L'interface ne manipule jamais la connexion directement. Pour passer plus tard à une
base centrale (serveur), seule cette classe sera à remplacer.
"""
from ..domain.etat import OF, EtatAtelier, TOUS_SCANS
from .schema import cle_ligne


class LigneDejaAffectee(ValueError):
    """Une ligne de commande Sage est déjà dans un autre OF actif."""

    def __init__(self, deja):
        self.deja = deja   # {clé de ligne: OF qui la détient}
        detail = ", ".join(f"ligne {cle.rsplit('-', 1)[-1]} → {id_of}" for cle, id_of in sorted(deja.items()))
        super().__init__(f"Ligne(s) déjà dans un OF : {detail}.")


class Depot:
    def __init__(self, conn):
        self.conn = conn

    # --- Référentiel ---

    def lister_postes(self, trier=False):
        """[(CodPost, DesPost)]"""
        sql = "SELECT CodPost, DesPost FROM Postes" + (" ORDER BY CodPost" if trier else "")
        return self.conn.execute(sql).fetchall()

    def operation_du_poste(self, codpost):
        row = self.conn.execute("SELECT RefOp FROM Postes WHERE CodPost = ?", (codpost,)).fetchone()
        return row[0] if row else None

    def lister_operations(self):
        """[(RefOp, LibelOp)] triés par RefOp"""
        return self.conn.execute("SELECT RefOp, LibelOp FROM Operations ORDER BY RefOp").fetchall()

    def libelles_operations(self):
        return dict(self.lister_operations())

    def lister_produits(self):
        """[(RefProd, DesProd)]"""
        return self.conn.execute("SELECT RefProd, DesProd FROM Produits").fetchall()

    def gamme_produit(self, ref_prod):
        """Gamme standard d'un produit : [(Ordre, CodeOp, LibelOp)]"""
        return self.conn.execute('''
            SELECT Gammes.Ordre, Gammes.CodeOp, Operations.LibelOp
            FROM Gammes LEFT JOIN Operations ON Gammes.CodeOp = Operations.RefOp
            WHERE RefProd = ? ORDER BY Ordre
        ''', (ref_prod,)).fetchall()

    def postes_pour_operation(self, ref_op):
        """[(CodPost, DesPost)]"""
        return self.conn.execute("SELECT CodPost, DesPost FROM Postes WHERE RefOp = ?", (ref_op,)).fetchall()

    # --- OF ---

    def charger_etat(self):
        """Photo complète de l'atelier en quatre requêtes."""
        ofs = [OF(*row[:7], row[7], row[8], row[9] or "", row[10] or "actif", row[11] or None, row[12] or 0)
               for row in self.conn.execute(
                   "SELECT ID_OF, CDE, PROD, DESIGN, OBSERV, Qte, LignesSage, Longueur, Largeur, Epaisseur, "
                   "Statut, DateBesoin, Priorite FROM CdeDetail ORDER BY rowid")]
        gammes = self.conn.execute(
            "SELECT ID_OF, CodeOp, Poste_Assigne FROM OF_Gammes ORDER BY ID_OF, Ordre").fetchall()
        postes = self.conn.execute("SELECT CodPost, RefOp FROM Postes").fetchall()
        scans = self.conn.execute(
            "SELECT ID_OF, Poste, Child_Key, COUNT(*) FROM Scans WHERE COALESCE(Annule, 0) = 0 "
            "GROUP BY ID_OF, Poste, Child_Key").fetchall()
        cloturees = [row[0] for row in self.conn.execute("SELECT CDE FROM CommandesCloturees")]
        return EtatAtelier(ofs, gammes, postes, scans, cloturees)

    def creer_of(self, cde, ref_prod, design, observ, qte, lignes_sage, etapes, longueur=None, largeur=None, epaisseur="",
                 date_besoin=None, priorite=0):
        """Crée un OF et sa gamme. etapes : [(CodeOp, Poste_Assigne ou None)]. Retourne l'ID créé.
        Lève LigneDejaAffectee si une des lignes Sage appartient déjà à un OF actif (rien n'est créé)."""
        cles = self._cles(cde, lignes_sage)
        with self.conn:
            self._verifier_lignes_libres(cles)
            # Tri numérique : OF-10000 doit passer après OF-9999
            dernier = self.conn.execute(
                "SELECT MAX(CAST(SUBSTR(ID_OF, 4) AS INTEGER)) FROM CdeDetail WHERE ID_OF LIKE 'OF-%'").fetchone()[0]
            id_of = f"OF-{dernier + 1}" if dernier is not None else "OF-1000"
            self.conn.execute(
                "INSERT INTO CdeDetail (ID_OF, CDE, PROD, DESIGN, OBSERV, Qte, LignesSage, Longueur, Largeur, Epaisseur, "
                "Statut, DateBesoin, Priorite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'actif', ?, ?)",
                (id_of, cde, ref_prod, design, observ, qte, lignes_sage, longueur, largeur, epaisseur, date_besoin, priorite))
            self.conn.executemany(
                "INSERT INTO OF_Gammes (ID_OF, Ordre, CodeOp, Poste_Assigne) VALUES (?, ?, ?, ?)",
                [(id_of, ordre, code_op, poste) for ordre, (code_op, poste) in enumerate(etapes, start=1)])
            self.conn.executemany("INSERT INTO OF_LignesSage (CleLigne, ID_OF) VALUES (?, ?)", [(c, id_of) for c in cles])
        return id_of

    # --- Lignes Sage des OF (une ligne = un seul OF actif) ---

    @staticmethod
    def _cles(cde, lignes_sage):
        return list(dict.fromkeys(cle_ligne(cde, c) for c in (lignes_sage or "").split(",") if c.strip()))

    def _verifier_lignes_libres(self, cles, sauf_of=None):
        deja = {}
        for cle in cles:
            row = self.conn.execute("SELECT ID_OF FROM OF_LignesSage WHERE CleLigne = ?", (cle,)).fetchone()
            if row and row[0] != sauf_of:
                deja[cle] = row[0]
        if deja:
            raise LigneDejaAffectee(deja)

    def lignes_affectees(self, cde):
        """{clé de ligne « CDE-DL_Ligne »: OF actif qui la contient} pour une commande."""
        prefixe = f"{cde}-"
        return dict(self.conn.execute(
            "SELECT CleLigne, ID_OF FROM OF_LignesSage WHERE substr(CleLigne, 1, ?) = ?",
            (len(prefixe), prefixe)).fetchall())

    # --- Scans ---

    def ajouter_scans(self, id_of, plan, child_key=None):
        """plan : [(poste, quantité)]"""
        with self.conn:
            self.conn.executemany(
                "INSERT INTO Scans (ID_OF, Poste, Child_Key) VALUES (?, ?, ?)",
                [(id_of, poste, child_key) for poste, quantite in plan for _ in range(quantite)])

    def ids_scans(self, id_of, ref_op, child_key=TOUS_SCANS):
        """ID des scans d'un OF pour une opération, du plus récent au plus ancien."""
        sql = '''SELECT Scans.ID_Scan FROM Scans JOIN Postes ON Scans.Poste = Postes.CodPost
                 WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND COALESCE(Scans.Annule, 0) = 0'''
        params = [id_of, ref_op]
        if child_key is None:
            sql += " AND Scans.Child_Key IS NULL"
        elif child_key is not TOUS_SCANS:
            sql += " AND Scans.Child_Key = ?"
            params.append(child_key)
        sql += " ORDER BY Scans.ID_Scan DESC"
        return [row[0] for row in self.conn.execute(sql, params)]

    def annuler_scans(self, ids):
        """Annulation tracée : le scan reste dans l'historique, marqué annulé avec sa date."""
        with self.conn:
            self.conn.executemany("UPDATE Scans SET Annule = 1, DateAnnulation = CURRENT_TIMESTAMP WHERE ID_Scan = ?",
                                  [(i,) for i in ids])

    def historique_scans(self, id_of):
        """[(ID_Scan, date locale, poste, opération, ligne Sage, annulé, date d'annulation locale)], du plus récent au plus ancien."""
        return self.conn.execute('''
            SELECT Scans.ID_Scan, datetime(Scans.Timestamp, 'localtime'), Scans.Poste,
                   COALESCE(Operations.LibelOp, Postes.RefOp, '?'), Scans.Child_Key, COALESCE(Scans.Annule, 0),
                   datetime(Scans.DateAnnulation, 'localtime')
            FROM Scans LEFT JOIN Postes ON Scans.Poste = Postes.CodPost
                       LEFT JOIN Operations ON Postes.RefOp = Operations.RefOp
            WHERE Scans.ID_OF = ? ORDER BY Scans.ID_Scan DESC
        ''', (id_of,)).fetchall()

    def scans_du_jour_par_poste(self):
        """{poste: nombre de scans valides aujourd'hui (heure locale)}"""
        return dict(self.conn.execute('''
            SELECT Poste, COUNT(*) FROM Scans
            WHERE COALESCE(Annule, 0) = 0 AND date(Timestamp, 'localtime') = date('now', 'localtime')
            GROUP BY Poste
        ''').fetchall())

    # --- Modification des OF ---

    def gamme_of(self, id_of):
        """[(Ordre, CodeOp, Poste_Assigne)]"""
        return self.conn.execute(
            "SELECT Ordre, CodeOp, Poste_Assigne FROM OF_Gammes WHERE ID_OF = ? ORDER BY Ordre", (id_of,)).fetchall()

    def nombre_scans(self, id_of):
        """Scans de l'OF, annulés compris (un OF scanné ne se supprime pas, il s'annule)."""
        return self.conn.execute("SELECT COUNT(*) FROM Scans WHERE ID_OF = ?", (id_of,)).fetchone()[0]

    def modifier_of(self, id_of, design, observ, qte, longueur, largeur, epaisseur, date_besoin, priorite, postes_par_ordre):
        """postes_par_ordre : {Ordre: poste assigné ou None}"""
        with self.conn:
            self.conn.execute(
                "UPDATE CdeDetail SET DESIGN = ?, OBSERV = ?, Qte = ?, Longueur = ?, Largeur = ?, Epaisseur = ?, "
                "DateBesoin = ?, Priorite = ? WHERE ID_OF = ?",
                (design, observ, qte, longueur, largeur, epaisseur, date_besoin, priorite, id_of))
            self.conn.executemany("UPDATE OF_Gammes SET Poste_Assigne = ? WHERE ID_OF = ? AND Ordre = ?",
                                  [(poste, id_of, ordre) for ordre, poste in postes_par_ordre.items()])

    def changer_statut_of(self, id_of, statut):
        """Annuler libère les lignes Sage de l'OF ; réactiver les reprend, et échoue (LigneDejaAffectee)
        si un autre OF les a prises entre-temps."""
        with self.conn:
            if statut == "annule":
                self.conn.execute("DELETE FROM OF_LignesSage WHERE ID_OF = ?", (id_of,))
            else:
                cde, lignes = self.conn.execute("SELECT CDE, LignesSage FROM CdeDetail WHERE ID_OF = ?", (id_of,)).fetchone()
                cles = self._cles(cde, lignes)
                self._verifier_lignes_libres(cles, sauf_of=id_of)
                self.conn.executemany("INSERT OR IGNORE INTO OF_LignesSage (CleLigne, ID_OF) VALUES (?, ?)",
                                      [(c, id_of) for c in cles])
            self.conn.execute("UPDATE CdeDetail SET Statut = ? WHERE ID_OF = ?", (statut, id_of))

    def supprimer_of(self, id_of):
        """Suppression définitive, refusée si l'OF a déjà été scanné."""
        if self.nombre_scans(id_of):
            raise ValueError(f"{id_of} a déjà des scans : annulez-le plutôt que de le supprimer.")
        with self.conn:
            self.conn.execute("DELETE FROM OF_Gammes WHERE ID_OF = ?", (id_of,))
            self.conn.execute("DELETE FROM OF_LignesSage WHERE ID_OF = ?", (id_of,))
            self.conn.execute("DELETE FROM CdeDetail WHERE ID_OF = ?", (id_of,))

    # --- Commandes ---

    def cloturer_commande(self, cde):
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO CommandesCloturees (CDE) VALUES (?)", (cde,))

    def rouvrir_commande(self, cde):
        with self.conn:
            self.conn.execute("DELETE FROM CommandesCloturees WHERE CDE = ?", (cde,))

    # --- Référentiel (administration) ---

    def _compter(self, sql, *params):
        return self.conn.execute(sql, params).fetchone()[0]

    def lister_postes_complets(self):
        """[(CodPost, DesPost, RefOp)] triés par code"""
        return self.conn.execute("SELECT CodPost, DesPost, RefOp FROM Postes ORDER BY CodPost").fetchall()

    def enregistrer_operation(self, ref_op, libelle):
        with self.conn:
            self.conn.execute("INSERT INTO Operations (RefOp, LibelOp) VALUES (?, ?) "
                              "ON CONFLICT(RefOp) DO UPDATE SET LibelOp = excluded.LibelOp", (ref_op, libelle))

    def supprimer_operation(self, ref_op):
        usages = [(self._compter("SELECT COUNT(*) FROM Postes WHERE RefOp = ?", ref_op), "poste(s)"),
                  (self._compter("SELECT COUNT(*) FROM Gammes WHERE CodeOp = ?", ref_op), "gamme(s) produit"),
                  (self._compter("SELECT COUNT(*) FROM OF_Gammes WHERE CodeOp = ?", ref_op), "étape(s) d'OF")]
        utilise = [f"{n} {quoi}" for n, quoi in usages if n]
        if utilise:
            raise ValueError(f"L'opération {ref_op} est utilisée par " + ", ".join(utilise) + ".")
        with self.conn:
            self.conn.execute("DELETE FROM Operations WHERE RefOp = ?", (ref_op,))

    def enregistrer_poste(self, codpost, designation, ref_op):
        with self.conn:
            self.conn.execute("INSERT INTO Postes (CodPost, DesPost, RefOp) VALUES (?, ?, ?) "
                              "ON CONFLICT(CodPost) DO UPDATE SET DesPost = excluded.DesPost, RefOp = excluded.RefOp",
                              (codpost, designation, ref_op))

    def supprimer_poste(self, codpost):
        usages = [(self._compter("SELECT COUNT(*) FROM Scans WHERE Poste = ?", codpost), "scan(s)"),
                  (self._compter("SELECT COUNT(*) FROM OF_Gammes WHERE Poste_Assigne = ?", codpost), "étape(s) d'OF assignée(s)")]
        utilise = [f"{n} {quoi}" for n, quoi in usages if n]
        if utilise:
            raise ValueError(f"Le poste {codpost} est utilisé par " + ", ".join(utilise) + ".")
        with self.conn:
            self.conn.execute("DELETE FROM Postes WHERE CodPost = ?", (codpost,))

    def enregistrer_produit(self, ref_prod, designation, operations=None):
        """Crée ou modifie un produit ; operations (liste de RefOp dans l'ordre) remplace sa gamme si fournie."""
        with self.conn:
            self.conn.execute("INSERT INTO Produits (RefProd, DesProd) VALUES (?, ?) "
                              "ON CONFLICT(RefProd) DO UPDATE SET DesProd = excluded.DesProd", (ref_prod, designation))
            if operations is not None:
                self._remplacer_gamme(ref_prod, operations)

    def _remplacer_gamme(self, ref_prod, operations):
        self.conn.execute("DELETE FROM Gammes WHERE RefProd = ?", (ref_prod,))
        self.conn.executemany("INSERT INTO Gammes (RefProd, CodeOp, Ordre) VALUES (?, ?, ?)",
                              [(ref_prod, op, ordre) for ordre, op in enumerate(operations, start=1)])

    def supprimer_produit(self, ref_prod):
        n = self._compter("SELECT COUNT(*) FROM CdeDetail WHERE PROD = ?", ref_prod)
        if n:
            raise ValueError(f"Le produit {ref_prod} est utilisé par {n} OF.")
        with self.conn:
            self.conn.execute("DELETE FROM Gammes WHERE RefProd = ?", (ref_prod,))
            self.conn.execute("DELETE FROM Produits WHERE RefProd = ?", (ref_prod,))

    def importer_referentiel(self, referentiel):
        """Ajoute ou met à jour opérations, postes, produits et gammes, sans toucher aux OF ni aux scans.
        Retourne le nombre d'éléments importés par catégorie."""
        with self.conn:
            self.conn.executemany("INSERT INTO Operations (RefOp, LibelOp) VALUES (?, ?) "
                                  "ON CONFLICT(RefOp) DO UPDATE SET LibelOp = excluded.LibelOp", referentiel.operations)
            self.conn.executemany("INSERT INTO Postes (CodPost, DesPost, RefOp) VALUES (?, ?, ?) "
                                  "ON CONFLICT(CodPost) DO UPDATE SET DesPost = excluded.DesPost, RefOp = excluded.RefOp",
                                  referentiel.postes)
            self.conn.executemany("INSERT INTO Produits (RefProd, DesProd) VALUES (?, ?) "
                                  "ON CONFLICT(RefProd) DO UPDATE SET DesProd = excluded.DesProd", referentiel.produits)
            for ref_prod, operations in referentiel.gammes.items():
                self._remplacer_gamme(ref_prod, operations)
        return {"opérations": len(referentiel.operations), "postes": len(referentiel.postes),
                "produits": len(referentiel.produits), "gammes": len(referentiel.gammes)}
