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
- **Web-Based Dashboard:** Modern, responsive UI for career management
- **One-Click Race Launching:** Automatic AC integration

---

## QUICK START

**Requirements:**
- Python 3.10 or higher
- Windows (paths configured for Windows)
- Assetto Corsa installed via Steam

**Installation:**
```bash
# 1. Clone the project
git clone https://github.com/corveck79/ac-career-manager.git

# 2. Open command prompt in the app folder
# 3. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Set your AC path in config.json (see CONFIGURATION below)

# 6. Start the app
start.bat        # recommended: handles venv + opens browser automatically
# OR
python app.py    # then open http://localhost:5000 manually
```

---

## FILE STRUCTURE

```
ac-career-manager/
├── app.py                    # Flask backend (main server)
├── career_manager.py         # Career logic & game rules
├── config.json              # All configuration (tunable!)
├── requirements.txt         # Python dependencies
├── start.bat               # Quick start script
│
├── templates/
│   └── dashboard.html      # Web UI (HTML)
│
└── static/
    ├── style.css          # CSS styling
    └── app.js             # Frontend JavaScript
```

---

## CONFIGURATION

Edit `config.json` while the app is **stopped**.

### Set your AC install path:
```json
"paths": {
  "ac_install": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa"
}
```

### Change races per tier:
```json
"seasons": {
  "races_per_tier": 10
}
```

### Adjust AI difficulty:
```json
"difficulty": {
  "base_ai_level": 85,
  "tier_multipliers": {
    "mx5_cup": -4,
    "gt4":     -2,
    "gt3":      0,
    "wec":      1.5
  }
}
```

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
4. Assetto Corsa opens with the race configured
5. **Drive the race** in AC
6. Return to app and enter your **finishing position**
7. Points calculated automatically

### End of Season
After 10 races:
1. Season completes automatically
2. You receive contract offers based on your championship position
3. Choose which team/car you want next season
4. Progress to next tier

### Championship Points (F1 standard)
P1: 25 · P2: 18 · P3: 15 · P4: 12 · P5: 10 · P6: 8 · P7: 6 · P8: 4 · P9: 2 · P10: 1
**Fastest Lap:** +1 point (if you finish top 10)

---

## CAREER PROGRESSION

### Tier 1: MX5 Cup (Junior)
- Car: Mazda MX5 Cup (one-make)
- Teams: 14
- AI Difficulty: base 85 − 4 = **81** ± 1.5
- Tracks: Silverstone National, Brands Hatch Indy, Magione, Vallelunga, Black Cat County

### Tier 2: GT4 SuperCup
- Cars: Porsche Cayman GT4, Maserati GT MC GT4, Lotus 2-Eleven GT4
- Teams: 16
- AI Difficulty: base 85 − 2 = **83** ± 1.5
- Tracks: Silverstone GP, Spa, Brands Hatch GP, Monza, Red Bull Ring

### Tier 3: British GT GT3
- Cars: Ferrari 488 GT3, Porsche 911 GT3, McLaren 650 GT3, BMW Z4 GT3, Lamborghini Huracán GT3, Mercedes AMG GT3, Nissan GTR GT3, and more
- Teams: 20 (Factory / Semi-Factory / Customer)
- AI Difficulty: base 85 + 0 = **85** ± 1.5
- Tracks: Silverstone GP, Spa, Monza, Laguna Seca, Mugello, Imola

### Tier 4: WEC / Elite Endurance
- Cars: Same GT3 lineup, endurance setup
- Teams: 10 elite teams
- AI Difficulty: base 85 + 1.5 = **86.5** ± 1.5
- Tracks: Silverstone GP, Spa, Monza, Mugello

---

## TROUBLESHOOTING

### "AC not found"
- Check AC install path in `config.json`
- Steam default: `C:\Program Files (x86)\Steam\steamapps\common\assettocorsa`
- Note: folder name is all lowercase, no spaces

### "Port 5000 already in use"
- `start.bat` kills existing processes on port 5000 automatically
- Or edit `app.py`: `app.run(port=5001)`

### "Race launches but wrong track/car"
- Make sure you launch AC via the app, not manually
- The app writes to `Documents\Assetto Corsa\cfg\race.ini`

### "Career data lost"
- Backup `career_data.json` before editing config
- Delete `career_data.json` to start fresh

---

## SYSTEM REQUIREMENTS

- Windows 10/11
- Python 3.10+
- Assetto Corsa (Steam)
- All required base game DLC cars

---

## LICENSE

Open source — feel free to modify and distribute.
