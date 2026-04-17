@echo off
title ElderCare Automation System Launcher
echo ===================================================
echo     Starting ElderCare Automation System
echo ===================================================

echo [1/4] Starting Central Backend API...
start "ElderCare: Backend" cmd /c "python backend\app.py"
timeout /t 3 /nobreak > nul

echo [2/4] Starting AI Voice Assistant...
start "ElderCare: AI Voice Assistant" cmd /c "python ai_assistant\main_assistant.py"

echo [3/4] Starting Vision Fall Detector...
start "ElderCare: Vision Sensor" cmd /c "python vision\fall_detector.py"

echo [4/4] Opening Dashboard UI...
start dashboard\index.html

echo ===================================================
echo   System is running! 
echo   Make sure your ESP32 devices are powered on.
echo   Close the command prompt windows to stop the services.
echo ===================================================
pause
