# AC CAREER MANAGER
## Professional Racing Career Simulator for Assetto Corsa

**Version:** 1.0.0  
**Platform:** Windows  
**Python:** 3.10+  

---

## OVERVIEW

AC Career Manager is a complete professional career mode system for Assetto Corsa. It provides:

- **4-Tier Career Progression:** MX5 Cup → GT4 → GT3 → WEC
- **10 Races Per Tier** with dynamic team assignments
- **Contract System:** End-of-season team/car selection based on performance
- **Intelligent AI Scaling:** Difficulty increases as you progress
- **Team Management:** 14-20 teams per tier with realistic competition
- **Web-Based Dashboard:** Modern, responsive UI for career management
- **One-Click Race Launching:** Automatic AC integration

---

## QUICK START

### Option A: Standalone EXE (Easiest)
1. Download `AC_Career_Manager.exe` from releases
2. Double-click to run
3. Opens browser at http://localhost:5000
4. Done!

### Option B: Run from Source (Developers)

**Requirements:**
- Python 3.10 or higher
- Windows (paths configured for Windows)

**Installation:**
```bash
# 1. Download/clone the project
# 2. Open command prompt in the app folder
# 3. Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the app
python app.py

# 6. Open browser
# Navigate to http://localhost:5000
```

### Option C: Using start.bat (Easiest Source Method)
1. Right-click on `start.bat`
2. Select "Run as Administrator"
3. Automatically opens browser
4. Ready to race!

---

## FILE STRUCTURE

```
ac-career-app/
├── app.py                    # Flask backend (main server)
├── career_manager.py         # Career logic & game rules
├── config.json              # All configuration (tunable!)
├── requirements.txt         # Python dependencies
├── build.bat               # Build standalone EXE
├── start.bat               # Quick start script
│
├── templates/
│   └── dashboard.html      # Web UI (HTML)
│
├── static/
│   ├── style.css          # Professional CSS styling
│   └── app.js             # Frontend JavaScript
│
└── career_data.json        # Your career save (auto-created)
```

---

## CONFIGURATION

**Everything is configurable in `config.json`:**

### Change races per tier:
```json
"seasons": {
  "races_per_tier": 12    // Change from 10 to 12
}
```

### Add/remove tracks:
```json
"mx5_cup": {
  "tracks": [
    "silverstone",
    "donington",
    "your_track_name"     // Add new track
  ]
}
```

### Adjust AI difficulty:
```json
"difficulty": {
  "base_ai_level": 85,     // Higher = faster
  "tier_multipliers": {
    "mx5_cup": -4,         // Easy (you win easily)
    "gt3": 0,              // Equal difficulty
    "wec": 1.5             // Hard (challenging)
  }
}
```

### Modify race format:
```json
"mx5_cup": {
  "race_format": {
    "laps": 20,            // Change lap count
    "time_limit_minutes": 45
  }
}
```

**⚠️ Edit config.json only when app is stopped!**

---

## HOW TO PLAY

### Starting a Career
1. Click **"New Career"** in the app
2. You start in **MX5 Cup** with **Mazda Academy**
3. Dashboard shows your team, points, and next race

### Race Workflow
1. Click **"START RACE"** button
2. Review race details in modal
3. Click **"LAUNCH AC"**
4. Assetto Corsa opens with race configured
5. **Drive the race** in AC
6. Return to app and enter your **finishing position**
7. Points calculated automatically

### End of Season
After 10 races:
1. Season completes automatically
2. You receive **4 contract offers** (if champion)
3. Choose which team/car you want next season
4. Progress to next tier (GT4, GT3, WEC)

### Championship Points
- **P1:** 25 points
- **P2:** 18 points
- **P3:** 15 points
- **P4:** 12 points
- **P5:** 10 points
- **P6:** 8 points
- **P7:** 6 points
- **P8:** 4 points
- **P9:** 2 points
- **P10:** 1 point
- **Fastest Lap:** +1 point (if you finish top 10)

---

## CAREER PROGRESSION

### Tier 1: MX5 Cup (Junior)
- Car: Mazda MX5 Cup (one-make)
- Teams: 14 teams
- AI Difficulty: -4% (you dominate)
- Races: 10
- Tracks: Silverstone, Donington, Brands Hatch, Snetterton, Oulton Park

### Tier 2: GT4 SuperCup
- Car: Various GT4 models (Ferrari, Porsche, BMW, Mercedes, Lotus, Aston)
- Teams: 16 teams
- AI Difficulty: -2% (competitive but favored)
- Races: 10
- Tracks: Silverstone, Donington, Spa, Brands Hatch, Snetterton

### Tier 3: British GT GT3 (Elite)
- Cars: 20 different GT3 cars
- Teams: 20 teams (Factory, Semi-Factory, Customer)
- AI Difficulty: 0% (equal - real racing)
- Races: 10
- Tracks: Silverstone, Donington, Spa, Monza, Paul Ricard, Laguna Seca

### Tier 4: WEC / Elite Endurance
- Cars: Same GT3s, endurance setup
- Teams: 10 elite teams
- AI Difficulty: +1.5% (very challenging)
- Races: 10 (longer)
- Tracks: Silverstone, Spa, Monza, Paul Ricard

---

## AI & DIFFICULTY

### How AI Works
- **Base level:** 85 (on AC's 0-100 scale)
- **Tier adjustments:** -4 to +1.5 per tier
- **Random variance:** ±1.5% per race (realistic inconsistency)
- **Factory teams:** Slightly better performance

### Examples
- MX5: 85 - 4 = **81%** ± 1.5 (you win 90% of races)
- GT3: 85 + 0 = **85%** ± 1.5 (tight, competitive racing)
- WEC: 85 + 1.5 = **86.5%** ± 1.5 (very challenging)

---

## TROUBLESHOOTING

### "AC not found"
- Check AC install path in config.json
- Default: `C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa`
- Verify AC is actually installed there

### "Port 5000 already in use"
- Close other apps using port 5000
- Or edit `app.py` line: `app.run(port=5001)`

### "Browser won't open"
- Manually navigate to `http://localhost:5000`
- Make sure Python backend is running

### "Race doesn't launch"
- Verify AC path in config.json
- Make sure AC is closed before launching
- Check Windows firewall allows Python

### "Career data lost"
- Backup `career_data.json` before editing config
- Delete `career_data.json` to start fresh
- App will auto-create new save

---

## BUILDING STANDALONE EXE

If you have Python installed:

```bash
# 1. Install PyInstaller
pip install pyinstaller

# 2. Run build script
build.bat

# 3. EXE created in dist\ folder
# Distribute: dist/AC_Career_Manager.exe
```

The resulting EXE is self-contained (~150MB) with no Python installation required on target machine.

---

## API ENDPOINTS

For advanced users:

- `GET /api/career-status` - Current career data
- `GET /api/standings` - Championship standings
- `GET /api/next-race` - Next race details
- `POST /api/start-race` - Launch AC race
- `POST /api/finish-race` - Submit race result
- `POST /api/end-season` - End season
- `POST /api/accept-contract` - Accept contract offer
- `POST /api/new-career` - Start new career
- `GET /api/config` - Current config
- `POST /api/config` - Update config

---

## TIPS & TRICKS

### Optimize Your Setup
- Edit `config.json` for custom difficulty
- Adjust `races_per_tier` for faster/longer career
- Add custom tracks if you have mods

### Save Backups
```bash
# Backup your career
copy career_data.json career_data_backup.json

# Backup config
copy config.json config_backup.json
```

### Performance
- Close unnecessary background apps
- Use `start.bat` for automatic venv setup
- Disable browser extensions for better UI performance

### Custom Teams
Edit `config.json` to add your own fictional teams with custom names.

---

## SYSTEM REQUIREMENTS

### Minimum
- Windows 7 or later
- 500MB disk space
- 4GB RAM

### Recommended
- Windows 10/11
- 1GB disk space (standalone EXE)
- 8GB RAM
- SSD (faster response)

### Assetto Corsa
- Latest AC version
- Content Manager recommended (for car skins)
- All required DLC cars owned

---

## SUPPORT & FEEDBACK

This is a community project. For issues:
1. Check config.json is valid JSON
2. Verify AC paths are correct
3. Ensure Python 3.10+ installed (for source mode)
4. Check firewall/antivirus doesn't block Python

---

## LICENSE

Open source - Feel free to modify and distribute.

---

**Enjoy your career! 🏁**
