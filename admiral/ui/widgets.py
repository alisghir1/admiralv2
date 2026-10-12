"""Utilitaires d'interface : icônes, centrage, focus des fenêtres, surlignage des sélections."""
import os
import tkinter as tk

import customtkinter as ctk

from ..config import ICON_DIR

_ICONS_CACHE = {}


def get_icon(name, size=(16, 16)):
    key = (name, size)
    if key in _ICONS_CACHE:
        return _ICONS_CACHE[key]
    icon_path = os.path.join(ICON_DIR, f"{name}.png")
    if not os.path.exists(icon_path):
        return None
    try:
        from PIL import Image
        img = Image.open(icon_path)
    except (ImportError, OSError):
        return None
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
    _ICONS_CACHE[key] = ctk_img
    return ctk_img


def centrer_fenetre(win, largeur, hauteur):
    # winfo_width() vaut 1 tant que la fenêtre n'est pas dessinée : on centre avec la taille voulue,
    # réduite si l'écran est plus petit (portable 1366×768 : barre des tâches et titre compris).
    # Sous Windows avec mise à l'échelle (125 %, 150 %), CustomTkinter multiplie les tailles par ce facteur.
    win.update_idletasks()
    try:
        echelle = ctk.ScalingTracker.get_window_scaling(win)
    except (AttributeError, KeyError):
        echelle = 1.0
    largeur = min(largeur, int((win.winfo_screenwidth() - 40) / echelle))
    hauteur = min(hauteur, int((win.winfo_screenheight() - 90) / echelle))
    x = int((win.winfo_screenwidth() - largeur * echelle) // 2)
    y = int((win.winfo_screenheight() - hauteur * echelle) // 2)
    win.geometry(f"{largeur}x{hauteur}+{x}+{y}")


def capturer_focus(win, essais=20):
    # grab_set échoue ("window not viewable") si la fenêtre n'est pas encore affichée : on réessaie.
    try:
        win.grab_set()
    except tk.TclError:
        if essais > 0 and win.winfo_exists():
            win.after(50, lambda: capturer_focus(win, essais - 1))


def maj_tags_selection(tree):
    """Passe les lignes sélectionnées sur la variante "_sel" de leur tag (couleur de sélection par état)."""
    selected_items = tree.selection()

    # Lignes de premier niveau et leurs enfants directs
    all_items = []
    for item in tree.get_children():
        all_items.append(item)
        all_items.extend(tree.get_children(item))

    for item in all_items:
        tags = tree.item(item, "tags")
        if not tags:
            if item in selected_items:
                tree.item(item, tags=("default_sel",))
            continue

        base_tag = tags[0].replace("_sel", "")
        new_tag = f"{base_tag}_sel" if item in selected_items else base_tag
        if tags[0] != new_tag:
            tree.item(item, tags=(new_tag,))


class FenetreDialogue(ctk.CTkToplevel):
    """Fenêtre secondaire sûre sous Windows.

    Sous Windows, CTkToplevel programme des tâches différées (icône à 200 ms, couleur de la barre de
    titre, tailles min/max à 1 s). Si la fenêtre est fermée avant, ces tâches agissent sur une fenêtre
    détruite et font planter Tk (violation d'accès). On les ignore quand la fenêtre n'existe plus."""

    def _existe(self):
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _windows_set_titlebar_icon(self):
        if self._existe():
            super()._windows_set_titlebar_icon()

    def _set_scaled_min_max(self):
        if self._existe():
            super()._set_scaled_min_max()

    def _windows_set_titlebar_color(self, color_mode):
        if self._existe():
            super()._windows_set_titlebar_color(color_mode)

    def _revert_withdraw_after_windows_set_titlebar_color(self):
        if self._existe():
            super()._revert_withdraw_after_windows_set_titlebar_color()
