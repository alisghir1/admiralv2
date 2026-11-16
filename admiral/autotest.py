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
            from .config import POSTE_BUREAU_ETUDE, POSTE_CHEF_ATELIER
            poste_initial = app.poste_actuel

            def passer_en(poste):
                app.poste_actuel = poste
                app._maj_entete_poste()
                app._appliquer_mode()
                app.refresh_dashboard()
                root.update()

            # Mode poste machine : l'écran Atelier seul, barre d'onglets masquée
            if app.est_pilotage:   # PC du Bureau d'étude ou d'un chef d'atelier
                passer_en(app.libelles_postes()[0])
            if app.notebook.winfo_manager() or not app.tab_atelier.winfo_manager():
                raise RuntimeError("un poste machine doit afficher l'écran Atelier seul")
            commandes = app.tree_cmd.get_children()
            if commandes:
                app.tree_cmd.selection_set(commandes[0])
                app.on_order_select()
            app.process_scan("AUTOTEST-CODE-INCONNU")   # chemin d'erreur, n'écrit rien
            from .domain import codes
            app.process_scan(codes.CODE_ESSAI)          # page d'essai de la douchette, n'écrit rien
            app.process_scan("TEST)à&é\"'(-è_ç)QWAZ?")  # même code tapé en clavier américain : corrigé
            if app.lbl_scan_status.cget("text") != "Douchette en clavier anglais":
                raise RuntimeError("le code d'essai tapé en clavier américain n'est pas reconnu")

            # Douchette reconnue à sa vitesse de frappe, curseur dans la recherche : le code d'essai est traité
            class Touche:
                def __init__(self, temps, char="", keysym=""):
                    self.widget, self.time, self.char, self.keysym = app.search_entry._entry, temps, char, keysym or char
            for i, char in enumerate(codes.CODE_ESSAI):
                app._touche_globale(Touche(1000 + 3 * i, char))
            app._touche_globale(Touche(1100, keysym="Return"))
            if app.lbl_scan_status.cget("text") != "Douchette bien réglée":
                raise RuntimeError("scan de douchette non reconnu hors du champ de scan")
            from serial.tools import list_ports   # douchette en port COM : pyserial embarqué dans l'exe
            log.info("Autotest : douchette OK (%d ports COM)", len(list_ports.comports()))
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
            from .ui.administration import SECTIONS
            for section in SECTIONS:
                app._afficher_section_admin(section)
                root.update()

            # Mode Chef d'atelier : Pilotage, Synthèse, Charge, Validations ; ni Création d'OF ni Administration
            passer_en(POSTE_CHEF_ATELIER)
            barre = app.notebook._segmented_button
            visibles = [nom for nom in barre.cget("values") if barre._buttons_dict[nom].winfo_manager()]
            if any(nom in visibles for nom in app.ONGLETS_BUREAU_ETUDE) or app.NOM_ONGLET_PILOTAGE not in visibles:
                raise RuntimeError(f"onglets du Chef d'atelier incorrects : {visibles}")
            for onglet in visibles:
                app.notebook.set(onglet)
                app.on_main_tab_changed()
                root.update()
                log.info("Autotest : Chef d'atelier, onglet %s OK", onglet)
            commandes = app.tree_pil_cmd.get_children()
            if commandes:
                app.tree_pil_cmd.selection_set(commandes[0])
                app._afficher_commande_pilotage()
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

            # Impression : un PDF de chaque document (reportlab et Code 128 embarqués dans l'exe), sans l'ouvrir
            import os
            import tempfile
            from . import pdf
            from .domain import documents
            from .ui.impression import referentiel
            etat = app.recharger_etat()
            en_service = etat.ofs_en_service()
            postes = [code for code, _ in app.depot.lister_postes(trier=True)]
            choix = documents.Choix(cde=en_service[0].cde if en_service else None,
                                    ids_of=tuple(of.id for of in en_service[:3]), fiche_commande=True,
                                    fiches_suiveuses=True, fiches_etape=True, etiquettes=True, par_piece=True,
                                    postes=tuple(postes))
            docs = documents.assembler(choix, etat, app.sage, *referentiel(app.depot))
            docs.append(documents.page_essai(etat, app.sage))
            with tempfile.TemporaryDirectory() as dossier:
                chemin = pdf.generer(os.path.join(dossier, "autotest.pdf"), docs)
                taille = os.path.getsize(chemin)
            if taille < 2000:
                raise RuntimeError(f"PDF d'impression trop petit ({taille} octets)")
            log.info("Autotest : impression OK (%d documents, %d octets)", len(docs), taille)

            # Fenêtres en dernier : rien n'est rafraîchi après leur fermeture (sous Windows, traiter les
            # événements d'une fenêtre fermée aussitôt ouverte peut faire planter Tk)
            of = next(iter(app.etat.ofs.values()), None)
            fenetres = [ConfigDialog(root, app.libelles_postes(), is_cancellable=True, actuel=app.poste_actuel),
                        AddOfDialog(root, app.depot, of.cde if of else "CC000000")]
            if of:
                from .ui.pilotage import ValidationDialog
                fenetres.append(ValidationDialog(root, app.depot, app.etat, [of], "auto-vérification", par_etape=True))
                fenetres += [ModifierOfDialog(root, app.depot, of, sage=app.sage, cloturees=app.etat.cloturees), HistoriqueDialog(root, of, app.depot.historique_scans(of.id), app.depot.historique_validations(of.id), app.depot.libelles_operations())]
            from .ui.impression import ImpressionDialog
            fenetres.append(ImpressionDialog(root, app, "Impression", cde=of.cde if of else None,
                                             ids_of=[of.id] if of else [], postes=postes, coches=("liste",)))
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
