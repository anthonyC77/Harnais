@echo off
title Qwen web (reseau maison)
cd /d "%~dp0"
echo Lancement de Qwen web pour toute la maison... (ferme cette fenetre pour arreter)
C:\Python311\python.exe qwen_web.py --reseau
pause
