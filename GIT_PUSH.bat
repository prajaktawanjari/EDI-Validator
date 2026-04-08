@echo off
echo.
echo ===================================
echo   Git Push Helper
echo ===================================
echo.

cd /d "%~dp0"

git status
echo.

set /p message="Enter commit message: "

git add .
git commit -m "%message%"
git push

echo.
echo ===================================
echo   Push Complete!
echo ===================================
echo.
pause
