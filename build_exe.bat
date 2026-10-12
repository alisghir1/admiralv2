@echo off
rem ===================================================================
rem  Fabrique la version Windows d'Admiral a envoyer au client :
rem    dist\Admiral_validation_client\      (Admiral.exe + demo + LISEZMOI)
rem    dist\Admiral_validation_client.zip
rem  A lancer sur un PC Windows avec Python 3.12 installe (python.org).
rem ===================================================================
setlocal
cd /d "%~dp0"
set SORTIE=dist\Admiral_validation_client

echo [1/6] Environnement de construction...
if not exist .venv-build\Scripts\python.exe (
    python -m venv .venv-build || goto erreur
)
.venv-build\Scripts\python -m pip install --quiet --upgrade pip
.venv-build\Scripts\python -m pip install --quiet -r requirements.txt "pyinstaller>=6.10,<7" || goto erreur

echo [2/6] Tests automatiques...
.venv-build\Scripts\python -m unittest discover -s tests -t . || goto erreur

echo [3/6] Fabrication de Admiral.exe...
.venv-build\Scripts\python -m PyInstaller --noconfirm --clean admiral.spec || goto erreur

echo [4/6] Dossier client avec les donnees de demonstration...
if exist %SORTIE% rmdir /s /q %SORTIE%
mkdir %SORTIE%
copy /y dist\Admiral.exe %SORTIE%\ >nul || goto erreur
.venv-build\Scripts\python -m admiral.demo %SORTIE% || goto erreur
copy /y LISEZMOI_CLIENT.txt %SORTIE%\LISEZMOI.txt >nul

echo [5/6] Auto-verification de l'exe (une fenetre s'ouvre quelques secondes)...
start "" /wait %SORTIE%\Admiral.exe --autotest
if errorlevel 1 (
    type %SORTIE%\logs\admiral.log
    goto erreur
)
rmdir /s /q %SORTIE%\logs

echo [6/6] Archive zip...
powershell -NoProfile -Command "Compress-Archive -Path '%SORTIE%\*' -DestinationPath 'dist\Admiral_validation_client.zip' -Force" || goto erreur

echo.
echo ===================================================================
echo  TERMINE : dist\Admiral_validation_client.zip est pret a envoyer.
echo ===================================================================
exit /b 0

:erreur
echo.
echo *** ECHEC : voir les messages ci-dessus. ***
exit /b 1
