@echo off
echo Starting EDI Validator API Server...
echo.
cd /d "%~dp0"
C:\Users\Prajakta\AppData\Local\Programs\Python\Python313\python.exe -m uvicorn api:app --reload --port 8000
pause
