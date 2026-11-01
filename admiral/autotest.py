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
    from .domain import lecture_sage
    from .ui.dialogs import AddOfDialog, ConfigDialog, HistoriqueDialog, ModifierOfDialog
    from .ui.widgets import get_icon

    def etapes():
        log = journal()
        try:
            manquantes = [nom for nom in ("refresh", "settings", "barcode", "plus") if get_icon(nom) is None]
            if manquantes:
                raise RuntimeError(f"icônes introuvables : {', '.join(manquantes)}")
            log.info("Autotest : icônes OK")
            from .config import POSTE_BUREAU_ETUDE
            poste_initial = app.poste_actuel

            def passer_en(poste):
                app.poste_actuel = poste
                app._maj_entete_poste()
                app._appliquer_mode()
                app.refresh_dashboard()
                root.update()

            # Mode poste machine : l'écran Atelier seul, barre d'onglets masquée
            if app.est_bureau_etude:
                passer_en(app.libelles_postes()[0])
            if app.notebook.winfo_manager() or not app.tab_atelier.winfo_manager():
                raise RuntimeError("un poste machine doit afficher l'écran Atelier seul")
            commandes = app.tree_cmd.get_children()
            if commandes:
                app.tree_cmd.selection_set(commandes[0])
                app.on_order_select()
            app.process_scan("AUTOTEST-CODE-INCONNU")   # chemin d'erreur, n'écrit rien
            root.update()
            log.info("Autotest : poste %s, atelier OK (%d commandes, %d cartes)", app.get_codpost(), len(commandes), len(app.cartes))

            # Mode Bureau d'étude : tous les onglets sauf Atelier
            passer_en(POSTE_BUREAU_ETUDE)
            onglets = list(app.notebook._segmented_button.cget("values"))
            if app.tab_atelier.winfo_manager() or app.NOM_ONGLET_ATELIER in onglets:
                raise RuntimeError("l'écran Atelier est visible au Bureau d'étude")
            for onglet in onglets:
                app.notebook.set(onglet)
                app.on_main_tab_changed()
                root.update()
                log.info("Autotest : Bureau d'étude, onglet %s OK", onglet)
            for section in ("Produits et gammes", "Opérations", "Postes", "Import Excel"):
                app._afficher_section_admin(section)
                root.update()

            # Retour au poste de départ avant d'ouvrir les fenêtres (aucune configuration n'est écrite)
            passer_en(poste_initial)

            # Relecture automatique de Sage : fichiers lus dans un fil, recopie et écrans dans le fil de l'interface
            app._lecture_sage.oublier()
            app._lecture_sage.lancer(app.dossier_sage)
            app._lecture_sage.attendre(120)
            lecture = app._lecture_sage.resultat()
            if isinstance(lecture, Exception) or lecture is lecture_sage.EN_COURS:
                raise RuntimeError(f"relecture de Sage en arrière-plan : {lecture!r}")
            app.appliquer_lecture_sage(lecture)
            app._rafraichir_ecrans_sage("auto-vérification")
            root.update()
            log.info("Autotest : relecture automatique de Sage OK (%d commandes)", len(app.sage.entetes))

            # Fenêtres en dernier : rien n'est rafraîchi après leur fermeture (sous Windows, traiter les
            # événements d'une fenêtre fermée aussitôt ouverte peut faire planter Tk)
            of = next(iter(app.etat.ofs.values()), None)
            fenetres = [ConfigDialog(root, app.libelles_postes(), is_cancellable=True, actuel=app.poste_actuel),
                        AddOfDialog(root, app.depot, of.cde if of else "CC000000")]
            if of:
                fenetres += [ModifierOfDialog(root, app.depot, of), HistoriqueDialog(root, of, app.depot.historique_scans(of.id))]
            for fenetre in fenetres:
                fenetre.destroy()
            log.info("Autotest : %d fenêtres OK", len(fenetres))
            log.info("AUTOTEST RÉUSSI")
            resultat["code"] = 0
        except Exception:
            log.error("AUTOTEST ÉCHOUÉ\n%s", traceback.format_exc())
            resultat["code"] = 1
        root.after(200, root.destroy)

    root.after(DELAI_DEMARRAGE_MS, etapes)
