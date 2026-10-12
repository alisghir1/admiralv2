# Recette PyInstaller : un seul fichier Admiral.exe (Windows), sans console.
# Construction : pyinstaller --noconfirm --clean admiral.spec   (voir build_exe.bat)
from PyInstaller.utils.hooks import collect_data_files

# Thèmes et polices de CustomTkinter + icônes de l'application, extraits au lancement (sys._MEIPASS)
fichiers = collect_data_files("customtkinter") + [("assets/icons", "assets/icons")]

a = Analysis(
    ["suivi_atelier.py"],
    pathex=["."],
    datas=fichiers,
    hiddenimports=["PIL._tkinter_finder"],
    excludes=["openpyxl.tests"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="Admiral",
    console=False,      # application fenêtrée : pas de fenêtre noire
    upx=False,          # la compression UPX déclenche souvent les antivirus
)
