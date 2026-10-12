"""Chemins de l'application et configuration du poste (config_poste.json).

Clés reconnues dans config_poste.json :
- "poste"           : poste de ce PC, ex. "DEC1 - Découpe Numérique SEKTOR"
- "base_de_donnees" : chemin de la base SQLite (facultatif ; défaut : suivi_atelier.db à côté de l'application)
- "dossier_sage"    : dossier des exports CSV Sage (facultatif ; défaut : data/ à côté de l'application)
- "code_bureau_etude" : code demandé pour passer ce PC en « Bureau d'étude » (facultatif ; défaut : 0000)
Un chemin relatif est résolu par rapport au dossier de l'application.
"""
import json
import os
import sys

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Fichiers embarqués (icônes) : dans l'exécutable Windows, PyInstaller les extrait dans sys._MEIPASS
RESSOURCES_DIR = getattr(sys, '_MEIPASS', APP_DIR)

CONFIG_FILE = os.path.join(APP_DIR, "config_poste.json")
LOG_DIR = os.path.join(APP_DIR, "logs")
ICON_DIR = os.path.join(RESSOURCES_DIR, "assets", "icons")

# Le Bureau d'étude n'est pas une machine : c'est un mode du PC (pilotage, sans l'écran Atelier)
POSTE_BUREAU_ETUDE = "Bureau d'étude"
CODE_BUREAU_ETUDE_DEFAUT = "0000"

DB_FILE_DEFAUT = os.path.join(APP_DIR, "suivi_atelier.db")
DATA_DIR_DEFAUT = os.path.join(APP_DIR, "data")


def lire_config(chemin=None):
    """Contenu de config_poste.json, ou {} s'il est absent ou illisible."""
    chemin = chemin or CONFIG_FILE
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config if isinstance(config, dict) else {}
    except (OSError, ValueError):
        return {}


def ecrire_config(modifications, chemin=None):
    """Met à jour config_poste.json en conservant les autres clés."""
    chemin = chemin or CONFIG_FILE
    config = lire_config(chemin)
    config.update(modifications)
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _resoudre(chemin, defaut):
    if not chemin:
        return defaut
    chemin = os.path.expanduser(chemin)
    return chemin if os.path.isabs(chemin) else os.path.join(APP_DIR, chemin)


def chemin_base(config):
    return _resoudre(config.get("base_de_donnees"), DB_FILE_DEFAUT)


def dossier_sage(config):
    return _resoudre(config.get("dossier_sage"), DATA_DIR_DEFAUT)


def code_bureau_etude(config):
    return str(config.get("code_bureau_etude") or CODE_BUREAU_ETUDE_DEFAUT)
