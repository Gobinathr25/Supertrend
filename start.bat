@echo off
title NIFTY Options Trading Bot

echo =======================================
echo   NIFTY Options Trading Bot
echo =======================================
echo.

:: Use full Python path to avoid version conflicts
set PYTHON=C:\Users\GD281\AppData\Local\Programs\Python\Python310\python.exe

:: Verify Python exists
if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    echo Please update the PYTHON path in this file.
    pause
    exit /b
)

echo [INFO] Using Python: %PYTHON%
echo.

:: Install backend deps
echo [1/2] Installing backend dependencies...
cd backend
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b
)

:: Copy .env if missing
if not exist ".env" (
    copy .env.example .env >nul
    echo [INFO] Created .env file
)

:: Start backend in new window
echo [2/2] Starting backend API on http://localhost:8000 ...
start "Backend API" cmd /k "%PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

cd ..

echo.
echo =======================================
echo   Backend is starting...
echo   API:      http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo =======================================
echo.
echo   Open frontend\index.html in your browser for the dashboard.
echo.
pause
