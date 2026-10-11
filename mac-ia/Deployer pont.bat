@echo off
rem Copie bridge/ sur le Mac puis relance le pont (deux demandes de mot de passe SSH).
cd /d "%~dp0"
scp -r bridge anthonychassier@192.168.1.50:~/mac-ia/
if errorlevel 1 goto echec
ssh anthonychassier@192.168.1.50 "pkill -f bridge/server.py; cd ~/mac-ia && nohup python3 bridge/server.py > bridge.log 2>&1 < /dev/null &"
timeout /t 3 /nobreak > nul
curl -s http://192.168.1.50:1235/health
echo.
pause
exit /b 0
:echec
echo Copie refusee : Mac allume, Session a distance active ?
pause
exit /b 1
