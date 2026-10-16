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
            # Verrou d'écriture dès la lecture du dernier numéro : deux PC ne peuvent pas prendre le même OF-n
            if not self.conn.in_transaction:
                self.conn.execute("BEGIN IMMEDIATE")
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

    def ajouter_lignes_of(self, id_of, lignes, nouvelle_qte):
        """Ajoute des lignes Sage à un OF actif et fixe sa nouvelle quantité.
        Lève LigneDejaAffectee si une ligne est dans un autre OF, ValueError si l'OF est annulé."""
        with self.conn:
            cde, actuelles, statut = self.conn.execute(
                "SELECT CDE, COALESCE(LignesSage, ''), COALESCE(Statut, 'actif') FROM CdeDetail WHERE ID_OF = ?",
                (id_of,)).fetchone()
            if statut == "annule":
                raise ValueError(f"{id_of} est annulé : réactivez-le avant de lui ajouter des lignes.")
            presentes = set(self._cles(cde, actuelles))
            nouvelles = [c for c in self._cles(cde, lignes) if c not in presentes]
            self._verifier_lignes_libres(nouvelles, sauf_of=id_of)
            jetons = [c.strip() for c in actuelles.split(",") if c.strip()] + nouvelles
            self.conn.executemany("INSERT OR IGNORE INTO OF_LignesSage (CleLigne, ID_OF) VALUES (?, ?)",
                                  [(c, id_of) for c in nouvelles])
            self.conn.execute("UPDATE CdeDetail SET LignesSage = ?, Qte = ? WHERE ID_OF = ?",
                              (",".join(jetons), nouvelle_qte, id_of))
        return nouvelles

    def retirer_ligne_of(self, id_of, cle, nouvelle_qte):
        """Retire une ligne Sage d'un OF (elle redevient libre) et fixe sa nouvelle quantité.
        Refusé (ValueError) si des pièces de cette ligne ont été scannées."""
        with self.conn:
            cde, actuelles = self.conn.execute(
                "SELECT CDE, COALESCE(LignesSage, '') FROM CdeDetail WHERE ID_OF = ?", (id_of,)).fetchone()
            complete = cle_ligne(cde, cle)
            jetons = [c.strip() for c in actuelles.split(",") if c.strip()]
            retires = [c for c in jetons if cle_ligne(cde, c) == complete]
            if not retires:
                raise ValueError(f"La ligne {complete.rsplit('-', 1)[-1]} n'est pas dans {id_of}.")
            scans = self.conn.execute(
                f"SELECT COUNT(*) FROM Scans WHERE ID_OF = ? AND COALESCE(Annule, 0) = 0 "
                f"AND Child_Key IN ({','.join('?' * len(retires))})", (id_of, *retires)).fetchone()[0]
            if scans:
                raise ValueError(f"La ligne {complete.rsplit('-', 1)[-1]} a déjà {scans} pièce(s) scannée(s) dans {id_of} : "
                                 "annulez-les d'abord à l'atelier.")
            self.conn.execute("DELETE FROM OF_LignesSage WHERE CleLigne = ? AND ID_OF = ?", (complete, id_of))
            self.conn.execute("UPDATE CdeDetail SET LignesSage = ?, Qte = ? WHERE ID_OF = ?",
                              (",".join(c for c in jetons if c not in retires), nouvelle_qte, id_of))

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

    def ids_scans(self, id_of, ref_op, child_key=TOUS_SCANS, poste=None):
        """ID des scans d'un OF pour une opération (d'un seul poste si `poste`), du plus récent au plus ancien."""
        sql = '''SELECT Scans.ID_Scan FROM Scans JOIN Postes ON Scans.Poste = Postes.CodPost
                 WHERE Scans.ID_OF = ? AND Postes.RefOp = ? AND COALESCE(Scans.Annule, 0) = 0'''
        params = [id_of, ref_op]
        if poste is not None:
            sql += " AND Scans.Poste = ?"
            params.append(poste)
        if child_key is None:
            sql += " AND Scans.Child_Key IS NULL"
        elif child_key is not TOUS_SCANS:
            sql += " AND Scans.Child_Key = ?"
            params.append(child_key)
        sql += " ORDER BY Scans.ID_Scan DESC"
        return [row[0] for row in self.conn.execute(sql, params)]

    def rattacher_scans_generaux(self, id_of, ref_op, repartition):
        """Rattache des scans généraux (douchette, +1 de l'OF) à des lignes Sage, du plus ancien au plus récent.
        repartition : [(clé de ligne, nombre)]. Les compteurs ne changent pas : le scan est seulement attribué."""
        libres = list(reversed(self.ids_scans(id_of, ref_op, None)))
        maj = []
        for cle, nombre in repartition:
            for _ in range(nombre):
                if libres:
                    maj.append((cle, libres.pop(0)))
        with self.conn:
            self.conn.executemany("UPDATE Scans SET Child_Key = ? WHERE ID_Scan = ?", maj)

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

    def _existe(self, table, colonne, valeur):
        return self._compter(f"SELECT COUNT(*) FROM {table} WHERE {colonne} = ?", valeur) > 0

    def enregistrer_operation(self, ref_op, libelle, creation=False):
        """creation : « Nouveau » dans l'Administration, refusé si le code existe déjà (pas d'écrasement)."""
        if creation and self._existe("Operations", "RefOp", ref_op):
            raise ValueError(f"L'opération {ref_op} existe déjà : sélectionnez-la dans la liste pour la modifier.")
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

    def motif_operation_figee(self, codpost, ref_op):
        """Pourquoi l'opération du poste ne peut pas passer à ref_op (None si c'est possible).
        Les scans ne mémorisent que le poste : changer son opération réécrirait tout l'historique
        (des pièces de découpe compteraient en usinage) et bloquerait les étapes qui lui sont assignées."""
        row = self.conn.execute("SELECT RefOp FROM Postes WHERE CodPost = ?", (codpost,)).fetchone()
        if not row or row[0] == ref_op:
            return None
        usages = [(self._compter("SELECT COUNT(*) FROM Scans WHERE Poste = ?", codpost), "scan(s)"),
                  (self._compter("SELECT COUNT(*) FROM OF_Gammes WHERE Poste_Assigne = ?", codpost), "étape(s) d'OF assignée(s)")]
        utilise = [f"{n} {quoi}" for n, quoi in usages if n]
        if not utilise:
            return None
        return (f"Le poste {codpost} a déjà {', '.join(utilise)} pour l'opération {row[0]} : changer son opération "
                "fausserait l'historique. Créez plutôt un nouveau poste.")

    def enregistrer_poste(self, codpost, designation, ref_op, creation=False):
        if creation and self._existe("Postes", "CodPost", codpost):
            raise ValueError(f"Le poste {codpost} existe déjà : sélectionnez-le dans la liste pour le modifier.")
        motif = self.motif_operation_figee(codpost, ref_op)
        if motif:
            raise ValueError(motif)
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
        # Dernier poste d'une opération encore à faire dans des OF actifs : plus personne ne pourrait la scanner
        ref_op = self.operation_du_poste(codpost)
        if ref_op and self._compter("SELECT COUNT(*) FROM Postes WHERE RefOp = ?", ref_op) == 1:
            n = self._compter("SELECT COUNT(DISTINCT g.ID_OF) FROM OF_Gammes g JOIN CdeDetail c ON c.ID_OF = g.ID_OF "
                              "WHERE g.CodeOp = ? AND COALESCE(c.Statut, 'actif') = 'actif'", ref_op)
            if n:
                raise ValueError(f"{codpost} est le seul poste de l'opération {ref_op}, utilisée par {n} OF actif(s) : "
                                 "créez d'abord un autre poste pour cette opération.")
        with self.conn:
            self.conn.execute("DELETE FROM Postes WHERE CodPost = ?", (codpost,))

    def enregistrer_produit(self, ref_prod, designation, operations=None, creation=False):
        """Crée ou modifie un produit ; operations (liste de RefOp dans l'ordre) remplace sa gamme si fournie.
        Une opération ne peut figurer qu'une fois dans une gamme (les pièces sont comptées par opération)."""
        if creation and self._existe("Produits", "RefProd", ref_prod):
            raise ValueError(f"Le produit {ref_prod} existe déjà : sélectionnez-le dans la liste pour le modifier.")
        if operations is not None and len(set(operations)) != len(operations):
            doublons = sorted({op for op in operations if operations.count(op) > 1})
            raise ValueError(f"L'opération {', '.join(doublons)} figure deux fois dans la gamme : "
                             "une opération ne peut être faite qu'une fois par pièce.")
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
        Retourne le nombre d'éléments importés par catégorie, et sous « avertissements » ce qui n'a pas
        été appliqué : opération d'un poste déjà utilisé (gardée), opération en double dans une gamme (retirée)."""
        avertissements = []
        postes = []
        for codpost, designation, ref_op in referentiel.postes:
            if self.motif_operation_figee(codpost, ref_op):
                actuelle = self.operation_du_poste(codpost)
                avertissements.append(f"poste {codpost} : opération {actuelle} conservée (déjà utilisé), {ref_op} ignorée")
                ref_op = actuelle
            postes.append((codpost, designation, ref_op))
        gammes = {}
        for ref_prod, operations in referentiel.gammes.items():
            uniques = list(dict.fromkeys(operations))
            if len(uniques) != len(operations):
                avertissements.append(f"gamme {ref_prod} : opération en double retirée")
            gammes[ref_prod] = uniques
        with self.conn:
            self.conn.executemany("INSERT INTO Operations (RefOp, LibelOp) VALUES (?, ?) "
                                  "ON CONFLICT(RefOp) DO UPDATE SET LibelOp = excluded.LibelOp", referentiel.operations)
            self.conn.executemany("INSERT INTO Postes (CodPost, DesPost, RefOp) VALUES (?, ?, ?) "
                                  "ON CONFLICT(CodPost) DO UPDATE SET DesPost = excluded.DesPost, RefOp = excluded.RefOp",
                                  postes)
            self.conn.executemany("INSERT INTO Produits (RefProd, DesProd) VALUES (?, ?) "
                                  "ON CONFLICT(RefProd) DO UPDATE SET DesProd = excluded.DesProd", referentiel.produits)
            for ref_prod, operations in gammes.items():
                self._remplacer_gamme(ref_prod, operations)
        compte = {"opérations": len(referentiel.operations), "postes": len(referentiel.postes),
                  "produits": len(referentiel.produits), "gammes": len(referentiel.gammes)}
        if avertissements:
            compte["avertissements"] = avertissements
        return compte
