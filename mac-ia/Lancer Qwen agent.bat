@echo off
title Claude Code pilote par Qwen (Mac)
cd /d "%~dp0"
set "PROJET=%~1"
if "%PROJET%"=="" set "PROJET=D:\HorusCoachIA"
echo Session Claude Code pilotee par Qwen, projet : %PROJET%
C:\Python311\python.exe agent_qwen.py --projet "%PROJET%"
pause
