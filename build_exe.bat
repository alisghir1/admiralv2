@echo off
echo ===================================================
echo COMPILATION SOTRAGLACE - SUIVI ATELIER (PyInstaller)
echo ===================================================
echo.

set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
set PIP_CMD="%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pip.exe"
set PYINSTALLER_CMD="%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pyinstaller.exe"

echo Installation de PyInstaller si manquant...
%PYTHON_CMD% -m pip install pyinstaller

echo.
echo Nettoyage des anciennes compilations...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist suivi_atelier.spec del suivi_atelier.spec

echo.
echo Compilation en cours (cela peut prendre quelques minutes)...
%PYINSTALLER_CMD% --noconsole --onefile --windowed --name "Sotraglace_Suivi_Atelier" --distpath . suivi_atelier.py

echo.
echo Nettoyage final...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist suivi_atelier.spec del suivi_atelier.spec

echo ===================================================
echo TERMINE ! L'executable Sotraglace_Suivi_Atelier.exe a ete cree.
echo ===================================================
