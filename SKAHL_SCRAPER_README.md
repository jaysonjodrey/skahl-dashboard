# SKAHL Historical Data Scraper - Windows Edition

Local Python script to incrementally fetch SKAHL hockey league data from snokinghockeyleague.com without sandbox restrictions.

## Setup (One-Time)

### 1. Install Python (if you don't have it)
- Download from: https://www.python.org/downloads/
- Make sure to check "Add Python to PATH" during installation

### 2. Install Required Package
Open PowerShell or Command Prompt and run:
```
pip install requests
```

### 3. Place Scripts
Copy these files to a folder (e.g., `C:\Users\jayso\Documents\SKAHL Scraper\`):
- `skahl_scraper_windows.py`
- `scrape_skahl.bat` (optional, for easy clicking)

## Usage

### Option A: Double-click the batch file (Easiest)
```
scrape_skahl.bat
```
This fetches all missing seasons and saves to your SKAHL Dashboard folder.

### Option B: Command Line
```
python skahl_scraper_windows.py
```

### Option C: Fetch Specific Seasons
```
python skahl_scraper_windows.py --seasons 1090 1091 1092
```

## What It Does

1. **Connects to snokinghockeyleague.com** and fetches all season metadata
2. **Identifies missing seasons** - seasons not yet in your database
3. **Fetches player data** for each missing season (with 1-second delays between requests)
4. **Saves to SQLite database** in your SKAHL Dashboard folder
5. **Respects the server** with throttling and error handling

## Database Location

```
C:\Users\jayso\Documents\Claude\Projects\SKAHL Dashboard\skahl_historical.db
```

The script creates/updates this automatically.

## Features

- ✅ **Incremental** - Only fetches seasons not yet in database
- ✅ **Resumable** - Can stop and restart anytime
- ✅ **Respectful** - 1-second delays between API calls
- ✅ **Robust** - Handles timeouts and errors gracefully
- ✅ **Transparent** - Shows progress and data counts

## Sample Output

```
================================================================================
SKAHL HISTORICAL DATA SCRAPER - Windows Version
================================================================================

📡 Fetching player data for 44 season(s)...
   Database: C:\Users\jayso\Documents\Claude\Projects\SKAHL Dashboard\skahl_historical.db

[ 1/44] 2023-2024 SKAHL Fall-Winter                   ✓ 14 divs | 287 players | 354 stats
[ 2/44] 2023 SKAHL Summer Playoffs                    ✓ 10 divs | 156 players | 187 stats
...

================================================================================
✓ SCRAPE COMPLETE
================================================================================
Seasons in DB:       45
Seasons with data:   45
Unique players:      1024
Total stat records:  12847
Database size:       3.45 MB
================================================================================
```

## Troubleshooting

### "python: command not found"
- Make sure Python is installed and added to PATH
- Restart Command Prompt/PowerShell after installing Python

### "ModuleNotFoundError: No module named 'requests'"
```
pip install requests
```

### Script stalls/times out
- The API might be slow - wait a bit and try again
- Check your internet connection
- The script will skip problematic seasons and continue

### Database locked error
- Make sure you're not running the scraper twice simultaneously
- Close DB Browser if you have it open on the database

## Next Steps

Once you have the data:
1. Open database in **DB Browser for SQLite** to explore
2. Run SQL queries to analyze player performance
3. Export data to CSV for further analysis
4. Build visualizations with your favorite tool

## Script Details

- **Language**: Python 3.6+
- **Dependencies**: `requests` library
- **Database**: SQLite 3
- **API**: snokinghockeyleague.com (public)
- **Rate Limiting**: 1 second between requests (respectful)

---

**Questions?** Run with `--help` for command-line options.
