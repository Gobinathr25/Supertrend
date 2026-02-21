@echo off
echo Stopping Trading Bot...
taskkill /f /fi "WINDOWTITLE eq Backend API*" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq Frontend UI*" >nul 2>&1
echo Done.
pause
