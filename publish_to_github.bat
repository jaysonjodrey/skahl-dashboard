@echo off
echo =============================================
echo  SKAHL Dashboard - Push to GitHub + Pages
echo =============================================
cd /d "%~dp0"

echo.
echo [1] Pushing to GitHub...
git push origin main
if %errorlevel% neq 0 (
    echo ERROR: Push failed. Check your credentials.
    pause
    exit /b 1
)

echo.
echo [2] Done! Enabling GitHub Pages:
echo   1. Go to: https://github.com/jaysonjodrey/skahl-dashboard/settings/pages
echo   2. Under "Source", select: Deploy from a branch
echo   3. Branch: main  /  Folder: / (root)
echo   4. Click Save
echo.
echo Your dashboard will be live at:
echo   https://jaysonjodrey.github.io/skahl-dashboard/skahl_dashboard.html
echo.
pause
