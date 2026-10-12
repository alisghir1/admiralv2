#!/bin/bash
export TK_SILENCE_DEPRECATION=1
cd "$(dirname "$0")"
echo "Lancement d'Admiral v2 (via environnement local Python 3.12)..."
./.venv/bin/python suivi_atelier.py
