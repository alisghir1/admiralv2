#!/bin/bash
export TK_SILENCE_DEPRECATION=1
cd "$(dirname "$0")"
echo "Lancement d'Admiral v2..."
/usr/bin/python3 suivi_atelier.py
