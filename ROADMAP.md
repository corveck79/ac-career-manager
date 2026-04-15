# AC Career GT Edition — Roadmap

## Shipped

| Version | Highlights |
|---------|-----------|
| **v1.0–v1.6** | Core career loop: 4-tier ladder, AC race launch, points, standings |
| **v1.7.0** | Driver profiles (120 drivers, 5 skills, nicknames), driver history |
| **v1.8.0** | Career wizard, post-race debrief, real promotion/relegation contracts |
| **v1.16.0** | Linux / Steam Proton support via `platform_paths.py` |
| **v1.17.0** | Auto-polling race result (no button press needed) |
| **v1.18.0** | Player career card, team modal with liveries, driver card 5-bar stats |
| **v1.19.x** | Qualifying simulation, correct grid order for Race Only mode |
| **v1.20.0** | **Big wave:** cross-tier AI race simulation (all 4 tiers race every round), driver progress system (skill drift / wet evolution / form scores / retirements / rivalries / mid-season swaps), tier progress UI, Paddock News feed |

---

## In Progress / Planned

> v1.20.0 shipped everything from the v1.21 plan. Roadmap is currently open.

---

## Ideas — v1.21.0 and beyond

These are unranked ideas to discuss. Each tagged with rough complexity.

### 🎯 High value, low complexity

**A. Paddock News — player rivalry callout**
Show a special news item when the player and an AI driver are within 10 pts in standings:
> "⚔️ Rivalry: You vs. Fabio Romano — only 8 points separate you."
Currently rivalries only track AI vs AI. Easy addition to `update_rivalries()`.

**B. Season recap screen**
Before contracts are shown, display a season summary card:
- Your stats (wins, podiums, DNFs, best result)
- Championship story (who led, who fell)
- Driver of the season (most improved / most wins)
Feeds from existing `race_results` + `driver_progress`. Mostly frontend.

**C. Paddock News filter**
Add tier/type filter buttons to the Paddock view:
`[All] [GT3] [GT4] [MX5] [Retirements] [Rivalries]`
Pure frontend, ~20 lines of JS.

---

### 🏎️ Medium complexity — gameplay depth

**D. Career achievements**
Unlock badges for milestones:
- "Rain King" — win in wet conditions
- "Triple Champion" — win 3 championships
- "Old Timer" — complete a full career (all 4 tiers)
- "Underdog" — win from P15+ on grid
Store as `career_data['achievements']`. Show on player card. ~60 lines backend + frontend.

**E. Team development (dynamic car performance)**
Teams with strong seasons get a small AI level bonus next season (+1 to +2).
Teams with poor seasons decline. Makes constructors feel alive over multiple seasons.
Already in the original plan as a system, never implemented.

**F. Retirement announcements in UI**
Currently retirements are logged to `paddock_news` but there's no splash/modal.
Add a seasonal retirement summary to the season-end screen:
> "This season, 2 drivers retired: James Hunt (40) and Marco Rossi (38)."
Frontend only — data is already in `last_retirements`.

**G. Driver of the Season award**
At season end, calculate and announce:
- Most wins per tier
- Most improved driver (biggest positive skill delta)
- Wet race specialist (best average in wet conditions)
Show in season-end view + add to paddock news. Entirely derived from existing data.

---

### 🔧 Medium complexity — polish / UX

**H. Career statistics dashboard**
Dedicated "Stats" view with:
- Points per season graph (sparkline)
- Win/podium rate over career
- Tier progression timeline
- Head-to-head vs. specific rival
All data exists in `race_results` + `driver_history`. Mostly frontend charting.

**I. Paddock News "big events" popup**
After finishing a race, if notable events happened (new rivalry, retirement, swap), show a
toast/banner: "📋 News from the paddock — 2 new events." Clicking opens Paddock view.
Frontend only, triggered from `finish_race` response.

**J. Driver profile — career arc visualization**
In the driver modal, show a mini sparkline of skill trend over the career (using `career_start` → `season_start` → `current`). Currently shows only current bars + trend arrow. Already have the data.

---

### 🚀 High complexity — bigger features

**K. AI contract market (visible)**
At season start, show in Paddock News which drivers moved to which teams:
"Connor MacLeod joins BMW Customer Racing for next season."
Requires defining AI contract logic (currently implicit from shuffle). Non-trivial.

**L. Player rival — choose your nemesis**
After finishing a race where a specific AI driver beat you 3+ times, offer:
"Make [Name] your rival?" → tracked separately, shown on dashboard, extra narrative.
Medium backend + frontend.

**M. Custom difficulty per tier**
Different AI offsets for each tier, not just one global setting.
Lets you tune MX5 easy but WEC hard. Config UI change + career_settings refactor.

**N. Endurance mode races**
For WEC tier: multi-stint races (2–3 hours), driver swaps, tyre strategy visible in debrief.
Mostly a career_manager + race.ini change. High complexity due to AC session config.

---

## Notes

- Features A–C are small wins that make the existing paddock system feel more complete
- Features D + G add narrative depth without touching the race loop
- Feature E (team development) was always meant to be in the system — lowest-hanging medium feature
- Stats dashboard (H) would make the career feel more "alive" to look back on
- Nothing above requires breaking changes to existing save files (all additive)
