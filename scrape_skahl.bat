@echo off
REM SKAHL Historical Data Scraper - Windows Batch Wrapper
REM Run this to fetch all missing seasons into your database

cd /d "%~dp0"
python skahl_scraper_windows.py %*
pause
