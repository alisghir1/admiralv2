# Recette PyInstaller : un seul fichier Admiral.exe (Windows), sans console.
# Construction : pyinstaller --noconfirm --clean admiral.spec   (voir build_exe.bat)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Thèmes et polices de CustomTkinter + icônes de l'application, extraits au lancement (sys._MEIPASS)
# + fichiers de reportlab (impression PDF : polices, configuration)
fichiers = collect_data_files("customtkinter") + collect_data_files("reportlab") + [("assets/icons", "assets/icons")]

a = Analysis(
    ["suivi_atelier.py"],
    pathex=["."],
    datas=fichiers,
    # reportlab charge certains modules (polices standard, codes-barres) à la demande : on les embarque tous
    # pyserial : douchette en port COM (port choisi à la demande, listes des ports chargées à l'exécution)
    hiddenimports=["PIL._tkinter_finder", "serial.tools.list_ports"] + collect_submodules("reportlab.pdfbase")
                  + collect_submodules("reportlab.graphics.barcode"),
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
