"""Auto-vérification de l'exécutable : « Admiral.exe --autotest ».

Ouvre chaque onglet et chaque fenêtre sur les données présentes, sans rien enregistrer
(aucun scan, aucune configuration), puis ferme l'application. Code de sortie 0 si tout
s'est affiché sans erreur, 1 sinon ; le détail est écrit dans logs/admiral.log.
"""
import traceback

from .journal import journal

DELAI_DEMARRAGE_MS = 1500


def lancer(root, app, resultat):
    """Programme la vérification après l'affichage ; resultat["code"] reçoit 0 ou 1."""
    from .ui.dialogs import AddOfDialog, ConfigDialog, HistoriqueDialog, ModifierOfDialog
    from .ui.widgets import get_icon

    def etapes():
        log = journal()
        try:
            manquantes = [nom for nom in ("refresh", "settings", "barcode", "plus") if get_icon(nom) is None]
            if manquantes:
                raise RuntimeError(f"icônes introuvables : {', '.join(manquantes)}")
            log.info("Autotest : icônes OK")
            for onglet in (app.NOM_ONGLET_ATELIER, app.NOM_ONGLET_SYNTHESE, app.NOM_ONGLET_GENERATION,
                           app.NOM_ONGLET_MATRICE, app.NOM_ONGLET_CHARGE, app.NOM_ONGLET_ADMIN):
                app.notebook.set(onglet)
                app.on_main_tab_changed()
                root.update()
                log.info("Autotest : onglet %s OK", onglet)

            app.notebook.set(app.NOM_ONGLET_ATELIER)
            commandes = app.tree_cmd.get_children()
            if commandes:
                app.tree_cmd.selection_set(commandes[0])
                app.on_order_select()
            app.process_scan("AUTOTEST-CODE-INCONNU")   # chemin d'erreur, n'écrit rien
            root.update()
            log.info("Autotest : atelier OK (%d commandes, %d cartes)", len(commandes), len(app.cartes))

            for section in ("Produits et gammes", "Opérations", "Postes", "Import Excel"):
                app._afficher_section_admin(section)
                root.update()

            of = next(iter(app.etat.ofs.values()), None)
            fenetres = [ConfigDialog(root, app.libelles_postes(), is_cancellable=True, actuel=app.poste_actuel),
                        AddOfDialog(root, app.depot, of.cde if of else "CC000000")]
            if of:
                fenetres += [ModifierOfDialog(root, app.depot, of), HistoriqueDialog(root, of, app.depot.historique_scans(of.id))]
            for fenetre in fenetres:
                fenetre.update()
                fenetre.destroy()
            log.info("Autotest : %d fenêtres OK", len(fenetres))
            log.info("AUTOTEST RÉUSSI")
            resultat["code"] = 0
        except Exception:
            log.error("AUTOTEST ÉCHOUÉ\n%s", traceback.format_exc())
            resultat["code"] = 1
        root.after(200, root.destroy)

    root.after(DELAI_DEMARRAGE_MS, etapes)
