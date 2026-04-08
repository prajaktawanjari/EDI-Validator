@echo off
echo ========================================
echo   EDI Validator - Network Server
echo ========================================
echo.
echo Starting server accessible on network...
echo.
echo Your colleagues can access:
echo   HTML: file:///C:/Users/Prajakta/GitHub/EDI Validator/index.html
echo   API:  http://192.168.1.4:8000
echo.
echo Press CTRL+C to stop the server
echo ========================================
echo.

cd /d "%~dp0"
C:\Users\Prajakta\AppData\Local\Programs\Python\Python313\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8000
pause
