"""Règles d'avancement et de scan. Fonctions pures sur EtatAtelier (aucun accès base ni interface)."""

# Ordre d'affichage des commandes : En cours, puis À faire, puis Terminées
ORDRE_ETATS = {'encours': 0, 'pas_demarre': 1, 'terminee': 2}


def index_etape(gamme, mon_op, codpost):
    """Position de l'étape traitée par ce poste dans la gamme [(CodeOp, Poste_Assigne)], ou -1."""
    for i, (code_op, poste_assigne) in enumerate(gamme):
        if code_op == mon_op and (poste_assigne is None or poste_assigne == codpost):
            return i
    return -1


def motif_hors_gamme(id_of, gamme, mon_op, codpost):
    """Message expliquant pourquoi ce poste ne traite pas cet OF, ou None s'il le traite."""
    if not mon_op:
        return f"Le poste {codpost} n'a pas d'opération configurée"
    if index_etape(gamme, mon_op, codpost) >= 0:
        return None
    autres = [p for op, p in gamme if op == mon_op and p]
    if autres:
        return f"{id_of} est assigné au poste {', '.join(autres)}"
    return f"{id_of} ne passe pas par l'opération {mon_op}"


def repartir_scans(etat, id_of, ref_op, enfants):
    """Scans effectifs par ligne Sage : scans propres à la ligne, complétés par les scans
    généraux de l'OF (douchette) dans l'ordre des lignes. enfants : [(clé, qté, ...)]."""
    restants = etat.compter(id_of, ref_op, None)
    resultat = {}
    for cle, qte, *_ in enfants:
        n = etat.compter(id_of, ref_op, cle)
        ajout = min(restants, max(0, qte - n))
        resultat[cle] = n + ajout
        restants -= ajout
    return resultat


def disponibles(etat, of, gamme, index, mon_op):
    """Pièces prêtes pour ce poste : faites à l'étape précédente (tout poste) moins faites ici."""
    scans_prec = etat.compter(of.id, gamme[index - 1][0]) if index > 0 else of.qte
    return scans_prec - etat.compter(of.id, mon_op)


def verifier_scan(etat, of, mon_op, codpost):
    """Contrôle d'un scan douchette. Retourne (ok, message, nb scans actuels à ce poste)."""
    if of.annule:
        return False, f"{of.id} a été annulé", 0
    if of.cde in etat.cloturees:
        return False, f"La commande {of.cde} est clôturée", 0
    gamme = etat.gamme(of.id)
    motif = motif_hors_gamme(of.id, gamme, mon_op, codpost)
    if motif:
        return False, motif, 0

    mes_scans = etat.compter(of.id, mon_op)
    if mes_scans >= of.qte:
        return False, f"Quantité déjà atteinte pour {of.id} ({mes_scans}/{of.qte})", mes_scans

    index = index_etape(gamme, mon_op, codpost)
    if index > 0:
        prev_op = gamme[index - 1][0]
        scans_prec = etat.compter(of.id, prev_op)
        if scans_prec <= mes_scans:
            return False, f"Bloqué : étape précédente ({prev_op}) à {scans_prec}/{of.qte}", mes_scans
    return True, "", mes_scans


def statut_of_au_poste(qte, mes_scans, dispo):
    """(statut, situation, tag) d'un OF vu depuis le poste."""
    if mes_scans >= qte and qte > 0:
        return "Terminé", "Terminé à ce poste", "terminee"
    if mes_scans > 0:
        situation = f"Prêt à produire : {dispo} dispo" if dispo > 0 else "En attente étape précédente"
        return f"En cours ({mes_scans}/{qte})", situation, "encours"
    situation = f"Prêt à produire : {dispo} dispo" if dispo > 0 else "Bloqué (Étape précédente non finie)"
    return "Pas démarré", situation, "pas_demarre"


def etat_au_poste(qte, mes_scans, dispo):
    """pret / encours / attente / bloque / terminee."""
    if qte > 0 and mes_scans >= qte:
        return "terminee"
    if dispo > 0:
        return "encours" if mes_scans > 0 else "pret"
    return "attente" if mes_scans > 0 else "bloque"


def situation_au_poste(etat, dispo, etape_precedente=None, scans_precedents=0, qte=0):
    """Phrase courte expliquant l'état au poste."""
    if etat == "terminee":
        return "Terminé à ce poste"
    if etat in ("pret", "encours"):
        return f"{dispo} pièce{'s' if dispo > 1 else ''} prête{'s' if dispo > 1 else ''} à produire"
    if etape_precedente:
        return f"En attente de {etape_precedente} ({scans_precedents}/{qte})"
    return "En attente de l'étape précédente"


def statut_ligne(scans, qte):
    """(statut, tag) d'une ligne Sage rattachée à un OF."""
    if scans >= qte and qte > 0:
        return "Terminé", "terminee"
    if scans > 0:
        return f"En cours ({scans}/{qte})", "encours"
    return "Pas encore démarré", "pas_demarre"


def tag_etat(total_scans, tout_fini):
    if total_scans == 0:
        return "pas_demarre"
    return "terminee" if tout_fini else "encours"


def tag_avancement(scannes, total):
    if total > 0 and scannes >= total:
        return "terminee"
    if scannes > 0:
        return "encours"
    return "pas_demarre"


def avancement_commande(etat, cde, mon_op, codpost):
    """(pièces faites, pièces prévues, "x.x%") pour ce poste sur une commande.
    Prévues = quantité des OF dont la gamme passe par ce poste ; (0, 0, "N/A") s'il n'y en a aucun."""
    if not mon_op:
        return 0, 0, "N/A"
    total_qte = 0
    total_scanne = 0
    for of in etat.ofs_par_cde.get(cde, []):
        for code_op, poste_assigne in etat.gamme(of.id):
            if code_op == mon_op and (poste_assigne is None or poste_assigne == codpost):
                total_qte += of.qte
                total_scanne += min(etat.compter(of.id, mon_op), of.qte)
    if total_qte == 0:
        return 0, 0, "N/A"
    return total_scanne, total_qte, f"{total_scanne / total_qte * 100:.1f}%"


def avancement_global_commande(etat, cde):
    """(pièces terminées, pièces prévues, tag) d'une commande, tous postes confondus (vue Bureau d'étude).
    Une pièce est terminée quand elle est sortie de la dernière opération de sa gamme."""
    faites = prevues = 0
    commencee = False
    for of in etat.ofs_par_cde.get(cde, []):
        gamme = etat.gamme(of.id)
        if not gamme:
            continue
        prevues += of.qte
        faites += min(etat.compter(of.id, gamme[-1][0]), of.qte)
        commencee = commencee or any(etat.compter(of.id, op) for op, _ in gamme)
    if prevues and faites >= prevues:
        return faites, prevues, "terminee"
    return faites, prevues, "encours" if commencee else "pas_demarre"


def plan_rattrapage(etat, of, mon_op, codpost, nombre, child_key=None, enfants=()):
    """Scans à insérer pour un ajout manuel de `nombre` pièces à ce poste : [(poste, quantité)].

    Les étapes précédentes de la gamme sont complétées uniquement jusqu'au niveau atteint
    ici (jamais au-delà). Pour une ligne Sage (child_key), le niveau tient compte des scans
    généraux répartis sur la ligne."""
    gamme = etat.gamme(of.id)
    index = index_etape(gamme, mon_op, codpost)

    def effectif(ref_op):
        if child_key is None:
            return etat.compter(of.id, ref_op)
        repartis = repartir_scans(etat, of.id, ref_op, enfants)
        return repartis.get(child_key, etat.compter(of.id, ref_op, child_key))

    cible = effectif(mon_op) + nombre
    plan = []
    for prev_op, poste_assigne in gamme[:max(index, 0)]:
        manquants = max(0, cible - effectif(prev_op))
        poste = poste_assigne or etat.premier_poste(prev_op)
        if manquants and poste:
            plan.append((poste, manquants))
    plan.append((codpost, nombre))
    return plan
