/* AC Career GT Edition - Frontend JS */
'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let career        = null;
let config        = null;
let standings     = [];
let allStandings  = {};       // { mx5_cup: [...], gt4: [...], ... }
let tierProgress  = {};       // { mx5_cup: {done:5, total:12}, ... }
let standingsTier = 0;        // currently displayed tier index
let champMode     = 'drivers'; // 'drivers' | 'teams'
let calendar      = [];
let pendingRace   = null;
let nextRacePreview = null;   // cached /api/next-race result for weather preview
const THEME_PALETTE_KEY = 'ac-theme-palette';

// ── Track name map ──────────────────────────────────────────────────────────
const TRACK_NAMES = {
    // MX5 Cup
    'ks_silverstone/national':         'Silverstone',
    'ks_brands_hatch/indy':            'Brands Hatch',
    'magione':                         'Magione',
    'ks_vallelunga/club_circuit':      'Vallelunga',
    'ks_black_cat_county/layout_long': 'Black Cat County',
    // GT4
    'ks_silverstone/gp':               'Silverstone',
    'ks_brands_hatch/gp':              'Brands Hatch',
    'ks_red_bull_ring/layout_national':'Red Bull Ring',
    // GT3 / WEC
    'spa':                             'Spa',
    'monza':                           'Monza',
    'ks_laguna_seca':                  'Laguna Seca',
    'mugello':                         'Mugello',
    'imola':                           'Imola',
    'zandvoort':                       'Zandvoort',
    'ks_nurburgring/layout_gp':        'Nürburgring',
    'ks_nurburgring/layout_sprint_c':  'Nürburgring',
    'ks_paul_ricard':                  'Paul Ricard',
    'ks_barcelona':                    'Barcelona',
    'ks_barcelona/layout_gp':          'Barcelona',
    'ks_hungaroring':                  'Hungaroring',
    'ks_austria':                      'Red Bull Ring',
    'ks_interlagos':                   'Interlagos',
    'ks_melbourne':                    'Melbourne',
    'ks_monaco':                       'Monaco',
    'ks_silverstone':                  'Silverstone',
};

function fmtTrack(id) {
    return TRACK_NAMES[id] || id.replace(/^ks_/, '').replace(/\//g, ' ').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function fmtCar(id) {
    if (!id) return '–';
    return id.replace(/^ks_/, '').replace(/_/g, ' ')
             .replace(/\b\w/g, c => c.toUpperCase());
}
function fmtWeather(preset) {
    const map = {
        '3_clear':        '☀ Clear',
        '4_mid_clear':    '⛅ Partly Cloudy',
        '6_light_clouds': '🌤 Light Cloud',
        '7_heavy_clouds': '☁ Overcast',
        'wet':            '🌧 Wet',
    };
    return map[preset] || preset || '☀ Clear';
}
function fmtPos(n) {
    return n === 1 ? 'P1 🥇' : n === 2 ? 'P2 🥈' : n === 3 ? 'P3 🥉' : 'P' + n;
}
function fmtMs(ms) {
    if (!ms || ms <= 0) return '–';
    const mins = Math.floor(ms / 60000);
    const secs = (ms % 60000) / 1000;
    return mins + ':' + secs.toFixed(3).padStart(6, '0');
}
function initials(name) {
    if (!name || name === 'No Driver') return '?';
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}
function tierKey(index) {
    return ['mx5_cup', 'gt4', 'gt3', 'wec'][index] || 'mx5_cup';
}
function tierName(index) {
    if (!config || !config.tiers) return 'MX5 Cup';
    const t = config.tiers[tierKey(index)];
    return t ? t.name : 'MX5 Cup';
}
function escHtml(v) {
    return String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}


// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    // Restore saved theme before anything renders
    const savedTheme = localStorage.getItem('ac-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const savedPalette = localStorage.getItem(THEME_PALETTE_KEY) || 'current';
    document.documentElement.setAttribute('data-theme-palette', savedPalette);
    const ttLbl = document.getElementById('tt-label');
    if (ttLbl) ttLbl.textContent = savedTheme === 'light' ? 'Light' : 'Dark';
    const ttThumb = document.querySelector('.tt-thumb');
    if (ttThumb) ttThumb.textContent = savedTheme === 'light' ? '☀️' : '🌙';

    await checkSetup();
    await Promise.all([loadCareer(), loadConfig()]);
    await Promise.all([loadAllStandings(), loadCalendar()]);
    loadNextRacePreview().then(() => renderCalendar());
    refresh();
    loadNewsTicker();
    showView('main');
    if (career) switchStandingsTier(career.tier || 0);

    // Auto-open New Career wizard if no active career exists
    if (!career || !career.driver_name) {
        const setupOverlay = document.getElementById('setup-overlay');
        if (!setupOverlay || setupOverlay.classList.contains('hidden')) {
            setTimeout(() => openNewCareer(), 300);
        }
    }
});

// ── Data loaders ───────────────────────────────────────────────────────────
async function loadCareer() {
    try {
        const r = await fetch('/api/career-status');
        career  = await r.json();
    } catch (e) { console.error('loadCareer', e); }
}
async function loadConfig() {
    try {
        const r = await fetch('/api/config');
        config  = await r.json();
    } catch (e) { console.error('loadConfig', e); }
}
async function loadAllStandings() {
    try {
        const r       = await fetch('/api/all-standings');
        const d       = await r.json();
        // allStandings[tier_key] = { drivers: [...], teams: [...] }
        allStandings  = d.all_standings || {};
        tierProgress  = d.tier_progress || {};
        standingsTier = career ? (career.tier || 0) : 0;
        standings     = (allStandings[tierKey(standingsTier)] || {}).drivers || [];
    } catch (e) { console.error('loadAllStandings', e); }
}
async function loadCalendar() {
    try {
        const r  = await fetch('/api/season-calendar');
        calendar = await r.json();
    } catch (e) { console.error('loadCalendar', e); }
}
async function loadNextRacePreview() {
    try {
        if (!career || career.contracts || career.final_position != null) return;
        const r = await fetch('/api/next-race');
        nextRacePreview = await r.json();
    } catch (e) { nextRacePreview = null; }
}

// ── Full refresh ───────────────────────────────────────────────────────────
function refresh() {
    updateBranding();
    updateDriverCard();
    renderCalendar();
    updateTierTabLabels();
    renderStandings();
    renderMiniStandings();
}

function renderMiniStandings() {
    const body = document.getElementById('mini-standings-body');
    if (!body) return;
    const tier = career ? (career.tier || 0) : 0;
    const tk = tierKey(tier);
    const drivers = (allStandings[tk] || {}).drivers || [];

    // Update subtitle with race progress
    const sub = document.getElementById('mini-standings-subtitle');
    if (sub) {
        const tp = tierProgress[tk];
        sub.textContent = tp ? `Race ${tp.done} / ${tp.total}` : '';
    }

    if (!drivers.length) { body.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">No data yet</td></tr>'; return; }

    // Sort by points descending
    const sorted = [...drivers].sort((a, b) => (b.points || 0) - (a.points || 0));

    // Show top 10 + player if outside top 10
    const top = sorted.slice(0, 10);
    const playerIdx = sorted.findIndex(d => d.is_player);
    const showPlayerSep = playerIdx >= 10;

    let html = '';
    for (let i = 0; i < top.length; i++) {
        const d = top[i];
        const cls = d.is_player ? ' class="ms-player"' : '';
        html += `<tr${cls}><td class="col-pos">${i + 1}</td><td>${d.driver}</td><td class="col-pts">${d.points}</td></tr>`;
    }
    if (showPlayerSep && playerIdx < sorted.length) {
        const p = sorted[playerIdx];
        html += `<tr class="ms-sep"><td colspan="3">...</td></tr>`;
        html += `<tr class="ms-player"><td class="col-pos">${playerIdx + 1}</td><td>${p.driver}</td><td class="col-pts">${p.points}</td></tr>`;
    }
    body.innerHTML = html;
}

function updateBranding() {
    if (!config || !config.app) return;

    const appName = (config.app.name || 'AC Career GT Edition').trim();
    const edition = (config.app.edition || 'GT').trim();

    const topbarTitle = document.getElementById('topbar-title');
    if (topbarTitle) {
        const normalized = appName
            .replace(new RegExp('\\s+' + edition + '\\s+edition$', 'i'), '')
            .replace(/\s+edition$/i, '')
            .trim()
            .toUpperCase();
        topbarTitle.textContent = normalized;
    }

    const editionBadge = document.getElementById('edition-badge');
    if (editionBadge) {
        editionBadge.textContent = edition.toUpperCase() + ' Edition';
    }
}

// ── Driver card ────────────────────────────────────────────────────────────
function updateDriverCard() {
    if (!career || !config) return;

    const name   = career.driver_name || 'No Driver';
    const total  = career.total_races || (config.seasons && config.seasons.races_per_tier) || 10;
    const done   = career.races_completed || 0;

    // Top bar
    document.getElementById('tier-badge').textContent    = tierName(career.tier || 0);
    document.getElementById('season-badge').textContent  = 'Season ' + (career.season || 1);
    const team = career.team || '';
    const topCenter = (name !== 'No Driver')
        ? (team ? name + '  ·  ' + team : name)
        : '';
    document.getElementById('topbar-driver-name').textContent = topCenter;

    // Sidebar driver card
    document.getElementById('driver-initials').textContent = initials(name);
    document.getElementById('driver-name').textContent     = name;
    document.getElementById('driver-team').textContent     = career.team  || '–';
    document.getElementById('driver-car').textContent      = fmtCar(career.car);
    document.getElementById('driver-points').textContent   = career.points || 0;
    document.getElementById('races-done').textContent      = done;

    // Position from player's own tier driver standings (independent of currently viewed tab)
    const playerTierK       = tierKey(career.tier || 0);
    const playerTierDrivers = (allStandings[playerTierK] || {}).drivers || standings;
    const me = playerTierDrivers.find(s => s.is_player);
    document.getElementById('driver-pos').textContent = me ? 'P' + me.position : '–';

    // Rival sidebar indicator
    const rivalStatEl = document.getElementById('rival-stat');
    if (rivalStatEl) {
        const rv = career.rival_name && playerTierDrivers.find(d => d.driver === career.rival_name);
        if (rv) {
            document.getElementById('rival-stat-name').textContent = career.rival_name;
            const gapTxt = rv.gap === 0 ? 'Leader' : 'P' + rv.position + ' ·  –' + rv.gap;
            document.getElementById('rival-stat-pos').textContent = gapTxt;
            rivalStatEl.classList.remove('hidden');
        } else {
            rivalStatEl.classList.add('hidden');
        }
    }

    // Swap Start Race ↔ End Season based on season completion
    const raceBtn = document.getElementById('btn-start-race');
    if (raceBtn) {
        const seasonDone = done >= total && career.team;
        if (seasonDone) {
            raceBtn.innerHTML  = '&#127942; End Season';
            raceBtn.onclick    = goToContracts;
        } else {
            raceBtn.innerHTML  = '&#127937; Start Race';
            raceBtn.onclick    = startRace;
        }
    }
}

// ── Season Calendar ────────────────────────────────────────────────────────
function renderCalendar() {
    const row     = document.getElementById('rounds-row');
    const progEl  = document.getElementById('calendar-progress');
    const nrbBar  = document.getElementById('next-race-bar');

    if (!row) return;

    row.innerHTML = '';

    if (!calendar || !calendar.length) {
        if (progEl) progEl.textContent = '0 / 10 races';
        return;
    }

    const total = calendar.length;
    const done  = calendar.filter(r => r.status === 'completed').length;
    if (progEl) progEl.textContent = done + ' / ' + total + ' races';
    const fillEl = document.getElementById('cal-progress-fill');
    if (fillEl) fillEl.style.width = (total > 0 ? Math.round(done / total * 100) : 0) + '%';

    let nextRound = null;

    calendar.forEach(r => {
        const pill = document.createElement('div');
        pill.className = 'round-pill ' + r.status;

        // Circle icon: ✓ done | ► next | round number upcoming
        const icon = r.status === 'completed' ? '✓' : r.status === 'next' ? '▶' : r.round;
        const shortTrack = fmtTrack(r.track);
        const resultHtml = (r.status === 'completed' && r.result)
            ? '<div class="rp-result">P' + r.result.position + '</div>'
            : '';

        pill.innerHTML =
            '<div class="rp-icon">' + icon + '</div>' +
            '<div class="rp-track">' + shortTrack + '</div>' +
            resultHtml;

        row.appendChild(pill);
        if (r.status === 'next') nextRound = r;
    });

    // Season done?
    if (done >= total) {
        nrbBar.style.display = 'none';
        return;
    }

    // Show next race bar
    nrbBar.style.display = '';

    if (nextRound && config) {
        const tk      = tierKey(career ? career.tier : 0);
        const tierCfg = config.tiers ? config.tiers[tk] : null;
        const laps    = tierCfg ? tierCfg.race_format.laps : '–';

        document.getElementById('nrb-track').textContent =
            fmtTrack(nextRound.track);
        document.getElementById('nrb-meta').textContent  =
            'Race ' + nextRound.round + ' / ' + total + '  ·  ' + laps + ' laps';
        // AI level filled when race modal opens; show placeholder here
        const baseAi = config && config.difficulty ? (config.difficulty.base_ai_level || 85) : 85;
        document.getElementById('nrb-ai').textContent = '~' + (baseAi + (tierCfg ? tierCfg.ai_difficulty : 0));
        // Weather preview (from cached next-race call)
        const weatherEl = document.getElementById('nrb-weather');
        if (weatherEl) {
            weatherEl.textContent = nextRacePreview ? fmtWeather(nextRacePreview.weather) : '–';
        }
    }
}

// ── Standings tier / mode switching ────────────────────────────────────────
function updateTierTabLabels() {
    const names = ['MX5 Cup', 'GT4', 'GT3', 'WEC'];
    document.querySelectorAll('.tier-tab').forEach(t => {
        const ti = parseInt(t.dataset.tier);
        const tk = tierKey(ti);
        const tp = tierProgress[tk];
        const label = names[ti] || tk;
        t.textContent = tp ? `${label} ${tp.done}/${tp.total}` : label;
    });
}

function switchStandingsTier(idx) {
    standingsTier = idx;
    standings     = (allStandings[tierKey(idx)] || {}).drivers || [];
    const playerTier = career ? (career.tier || 0) : 0;
    updateTierTabLabels();
    document.querySelectorAll('.tier-tab').forEach(t => {
        const ti = parseInt(t.dataset.tier);
        t.classList.toggle('active',       ti === idx);
        t.classList.toggle('player-tier',  ti === playerTier);
    });
    renderStandings();
}

function switchChampMode(mode) {
    champMode = mode;
    document.getElementById('champ-tab-drivers').classList.toggle('active', mode === 'drivers');
    document.getElementById('champ-tab-teams').classList.toggle('active',   mode === 'teams');
    const lbl = document.getElementById('standings-col-label');
    if (lbl) lbl.textContent = mode === 'drivers' ? 'Driver' : 'Team';
    renderStandings();
}

// ── Standings ──────────────────────────────────────────────────────────────
function renderStandings() {
    const tbody = document.getElementById('standings-body');
    const empty = document.getElementById('standings-empty');
    const table = document.getElementById('standings-table');
    if (!tbody) return;

    const hasCareer = career && career.team;
    const tierK     = tierKey(standingsTier);
    const tierData  = allStandings[tierK] || { drivers: [], teams: [] };
    const data      = champMode === 'drivers' ? (tierData.drivers || []) : (tierData.teams || []);

    if (!hasCareer || !data.length) {
        if (empty) empty.style.display = '';
        if (table) table.style.display = 'none';
        return;
    }
    if (empty) empty.style.display = 'none';
    if (table) table.style.display = '';

    tbody.innerHTML = data.map(s => {
        const posClass   = s.position === 1 ? 'pos-1' :
                           s.position === 2 ? 'pos-2' :
                           s.position === 3 ? 'pos-3' : '';
        const isRival    = !s.is_player && champMode === 'drivers' &&
                           career && career.rival_name && s.driver === career.rival_name;
        const rowClass   = s.is_player ? 'player-row' : (isRival ? 'rival-row' : '');
        const gap        = s.position === 1
            ? '<span class="gap-leader">LEADER</span>'
            : (s.gap === 0 ? '–' : '–' + s.gap);
        const isDriverMode = champMode === 'drivers';
        const main  = isDriverMode ? (s.driver || s.team) : s.team;
        // Teams mode: show both drivers as sub ("Driver1 / Driver2")
        const sub   = isDriverMode
            ? s.team
            : (s.driver2 ? s.driver + ' / ' + s.driver2 : (s.driver || ''));
        const mainSafe = escHtml(main);
        const subSafe  = escHtml(sub);
        const star       = s.is_player ? '★ ' : '';
        const rivalBadge = isRival ? '⚔ ' : '';
        const formBadge  = !s.is_player && isDriverMode && s.form_score != null
            ? (s.form_score >= 0.35 ? '<span class="form-badge form-hot" title="Hot streak">🔥</span>'
             : s.form_score <= -0.35 ? '<span class="form-badge form-cold" title="Poor form">❄️</span>'
             : '')
            : '';
        const driverName = (s.driver || '').replace(/'/g, "\\'");
        const teamName   = (s.team  || '').replace(/'/g, "\\'");
        // For teams mode: look up primary driver's skin_index from driver standings
        let skinIdxForRow = s.skin_index || 0;
        if (!isDriverMode && s.car) {
            const primDr = (tierData.drivers || []).find(d => d.team === s.team && d.is_primary !== false);
            if (primDr) skinIdxForRow = primDr.skin_index || 0;
        }
        const clickable = isDriverMode
            ? (s.is_player
                ? ' onclick="showPlayerProfile()"'
                : ' onclick="showDriverProfile(\'' + driverName + '\',\'' + (s.car || '') + '\',' + (s.skin_index || 0) + ')"')
            : ' onclick="showTeamProfile(\'' + teamName + '\',\'' + (s.car || '') + '\')"';
        const liveryImg = s.car != null
            ? '<img class="livery-swatch" src="/api/livery-preview?car=' +
              encodeURIComponent(s.car) + '&index=' + skinIdxForRow +
              '" onerror="this.style.display=\'none\'" alt="">'
            : '';
        return (
            '<tr class="' + rowClass + '"' + clickable + '>' +
            '<td class="col-pos ' + posClass + '">' + liveryImg + s.position + '</td>' +
            '<td class="col-name">' + star + rivalBadge + mainSafe + formBadge +
              (sub ? '<div class="sub-name">' + subSafe + '</div>' : '') +
            '</td>' +
            '<td class="col-pts">' + s.points + '</td>' +
            '<td class="col-gap">' + gap + '</td>' +
            '</tr>'
        );
    }).join('');
}

// ── Setup ──────────────────────────────────────────────────────────────────
async function checkSetup() {
    try {
        const r = await fetch('/api/setup-status');
        const d = await r.json();
        if (d.auto_detected) {
            showToast('Assetto Corsa installatie automatisch gevonden.');
        }
        if (!d.valid) {
            const input = document.getElementById('setup-ac-path');
            if (input) input.value = d.path || d.default_hint || '';
            document.getElementById('setup-overlay').classList.remove('hidden');
        }
    } catch (e) { /* server not ready yet, ignore */ }
}

async function browseSetupFolder() {
    const path = await browseFolder();
    if (path) document.getElementById('setup-ac-path').value = path;
}

async function confirmSetup() {
    const path = (document.getElementById('setup-ac-path').value || '').trim();
    const hint = document.getElementById('setup-hint');
    if (!path) { hint.textContent = 'Please enter a folder path.'; return; }
    try {
        const r = await fetch('/api/save-ac-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        const d = await r.json();
        if (d.status === 'success') {
            document.getElementById('setup-overlay').classList.add('hidden');
            await Promise.all([loadCareer(), loadConfig()]);
            await Promise.all([loadAllStandings(), loadCalendar()]);
            loadNextRacePreview().then(() => renderCalendar());
            refresh();
            showToast('Assetto Corsa found!');
        } else {
            hint.textContent = d.message || 'Folder not found.';
        }
    } catch (e) { hint.textContent = 'Error: ' + e.message; }
}

// Native folder picker via pywebview JS API
async function browseFolder() {
    if (window.pywebview && window.pywebview.api) {
        return await window.pywebview.api.browse_folder();
    }
    return null;
}

// ── View management ────────────────────────────────────────────────────────
const ALL_VIEWS = ['standings', 'stats', 'result', 'contracts', 'recap', 'config', 'paddock', 'achievements'];
// 'main' is the default home state: no view-card active, calendar + dashboard grid visible

function showView(name) {
    // Stop auto-polling when navigating away from the result view
    if (name !== 'result' && _resultPollTimer) {
        clearInterval(_resultPollTimer);
        _resultPollTimer = null;
    }
    const isHome = (name === 'main');
    ALL_VIEWS.forEach(v => {
        const el = document.getElementById('view-' + v);
        if (!el) return;
        if (!isHome && v === name) {
            el.style.display = '';
            el.classList.add('active');
            el.classList.remove('hidden');
        } else {
            el.style.display = 'none';
            el.classList.remove('active');
            el.classList.add('hidden');
        }
    });
    // Calendar + dashboard grid visible only on home ('main')
    const cal = document.querySelector('.calendar-card');
    if (cal) cal.classList.toggle('hidden', !isHome);
    const grid = document.querySelector('.dashboard-grid');
    if (grid) grid.classList.toggle('hidden', !isHome);

    // Auto-render contracts from career data when navigating to contracts view
    if (name === 'contracts' && career && career.contracts && career.contracts.length) {
        renderContracts(career.contracts);
    }
}

function openConfig() {
    if (!config) return;
    const diff  = config.difficulty || {};
    const seas  = config.seasons    || {};
    const paths = config.paths      || {};

    const aiEl    = document.getElementById('s-ai-level');
    const varEl   = document.getElementById('s-ai-var');
    const pathEl  = document.getElementById('s-ac-path');
    const hint    = document.getElementById('s-ac-hint');

    aiEl.value    = diff.base_ai_level || 85;
    document.getElementById('s-ai-level-val').textContent = aiEl.value;

    varEl.value   = diff.ai_variance || 1.5;
    document.getElementById('s-ai-var-val').textContent = '\u00b1' + varEl.value;

    pathEl.value  = paths.ac_install || '';
    if (hint) hint.textContent = '';

    // Race conditions toggles (stored in career_settings, default ON)
    const cs = (career && career.career_settings) || {};
    document.getElementById('s-dynamic-weather').checked = cs.dynamic_weather !== false;
    document.getElementById('s-night-cycle').checked      = cs.night_cycle      !== false;

    // CSP / Pure badges and night-cycle hint
    const cspStatus = (career && career.csp_status) || {};
    const bCsp  = document.getElementById('badge-csp');
    const bPure = document.getElementById('badge-pure');
    if (bCsp)  bCsp.classList.toggle('csp-found',  !!cspStatus.csp);
    if (bPure) bPure.classList.toggle('csp-found', !!cspStatus.pure);
    const ncHint = document.getElementById('night-cycle-csp-hint');
    if (ncHint) ncHint.classList.toggle('hidden', !!cspStatus.csp);
    syncThemePaletteButtons();

    showView('config');
}

// ── Theme Toggle ───────────────────────────────────────────────────────────
function toggleTheme() {
    const cur  = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('ac-theme', next);
    const lbl   = document.getElementById('tt-label');
    const thumb = document.querySelector('.tt-thumb');
    if (lbl)   lbl.textContent   = next === 'light' ? 'Light' : 'Dark';
    if (thumb) thumb.textContent = next === 'light' ? '☀️' : '🌙';
}

function setThemePalette(palette) {
    const next = (palette === 'motorsport') ? 'motorsport' : 'current';
    document.documentElement.setAttribute('data-theme-palette', next);
    localStorage.setItem(THEME_PALETTE_KEY, next);
    syncThemePaletteButtons();
}

function syncThemePaletteButtons() {
    const current = document.documentElement.getAttribute('data-theme-palette') || 'current';
    const bCurrent = document.getElementById('s-palette-current');
    const bMoto = document.getElementById('s-palette-motorsport');
    if (bCurrent) bCurrent.classList.toggle('active', current === 'current');
    if (bMoto) bMoto.classList.toggle('active', current === 'motorsport');
}

// ── Stats page ──────────────────────────────────────────────────────────────
function openStats() {
    renderStats();
    showView('stats');
}

const _TICKER_ICONS = {
    flag: '🏁', trophy: '🏆', chart_up: '📈', chart_down: '📉',
    clipboard: '📋', swords: '⚔️', form_hot: '🔥', form_cold: '❄️',
    new_season: '🏎️', standings: '📊', rain: '🌧️', star: '⭐',
    race_result: '🏁'
};

async function loadNewsTicker() {
    const card  = document.getElementById('news-ticker-card');
    const items = document.getElementById('news-ticker-items');
    if (!card || !items) return;
    try {
        const news = await fetch('/api/paddock-news').then(r => r.json());
        if (!news || news.length === 0) { card.style.display = 'none'; return; }
        // Show only the 4 most recent, skip standings_update (they're boring on main page)
        const filtered = news.filter(n => n.type !== 'standings_update').slice(0, 4);
        if (filtered.length === 0) { card.style.display = 'none'; return; }
        items.innerHTML = filtered.map(n => {
            const icon = _TICKER_ICONS[n.icon] || '📌';
            return `<div class="news-item"><span class="news-icon">${icon}</span><span class="news-text">${n.text}</span></div>`;
        }).join('');
        card.style.display = '';
    } catch (e) { card.style.display = 'none'; }
}

async function loadPaddockNews() {
    const feed = document.getElementById('paddock-feed');
    if (!feed) return;
    try {
        const news = await fetch('/api/paddock-news').then(r => r.json());
        let html = '';
        let lastHeader = '';
        for (const item of news) {
            const header = item.race > 0
                ? `Season ${item.season}, Race ${item.race}`
                : `Season ${item.season}, Pre-Season`;
            if (header !== lastHeader) {
                html += `<div class="news-header">${header}</div>`;
                lastHeader = header;
            }
            const icon = _TICKER_ICONS[item.icon] || '📌';
            html += `<div class="news-item">
                <span class="news-icon">${icon}</span>
                <span class="news-text">${item.text}</span>
            </div>`;
        }
        feed.innerHTML = html || '<p class="muted">No news yet. Complete some races first.</p>';
    } catch (e) {
        feed.innerHTML = '<p class="muted">Could not load paddock news.</p>';
    }
}

async function loadAchievements() {
    const grid = document.getElementById('achievements-grid');
    if (!grid) return;
    try {
        const data = await fetch('/api/achievements').then(r => r.json());
        const all = data.all || {};
        const order = data.order || [];
        const unlocked = data.unlocked || [];
        const unlockedMap = {};
        for (const u of unlocked) unlockedMap[u.id] = u;
        let html = '';
        for (const aid of order) {
            const ach = all[aid];
            if (!ach) continue;
            const u = unlockedMap[aid];
            const cls = u ? 'ach-card unlocked' : 'ach-card locked';
            const seasonTag = u ? `<div class="ach-season">Season ${u.season}</div>` : '';
            html += `<div class="${cls}">
                <div class="ach-icon">${ach.icon}</div>
                <div class="ach-name">${ach.name}</div>
                <div class="ach-desc">${ach.desc}</div>
                ${seasonTag}
            </div>`;
        }
        grid.innerHTML = html || '<p class="muted">No achievements defined.</p>';
    } catch (e) {
        grid.innerHTML = '<p class="muted">Could not load achievements.</p>';
    }
}

function renderStats() {
    const el = document.getElementById('stats-content');
    if (!el || !career) {
        if (el) el.innerHTML = '<div class="empty-state">Start a career to see statistics.</div>';
        return;
    }

    const results = career.race_results || [];
    const history = career.player_history || [];
    const wins    = results.filter(r => r.position === 1).length;
    const podiums = results.filter(r => r.position <= 3).length;
    const best    = results.length ? Math.min(...results.map(r => r.position)) : '–';
    const avg     = results.length
        ? (results.reduce((s, r) => s + r.position, 0) / results.length).toFixed(1) : '–';

    // Current championship position
    const tierK   = tierKey(career.tier);
    const drivers = (allStandings[tierK] || {}).drivers || [];
    const me      = drivers.find(d => d.is_player);
    const champPos = me ? 'P' + me.position : '–';
    const champGap = me && me.gap > 0 ? '–' + me.gap + ' pts' : (me ? 'Leader' : '–');

    // Rival status
    const rv       = career.rival_name && drivers.find(d => d.driver === career.rival_name);
    const rivalHtml = rv
        ? '<div class="rival-debrief" style="margin-bottom:.8rem">⚔ Rival <strong>' +
          career.rival_name + '</strong> is P' + rv.position +
          (rv.gap > 0 ? ' (–' + rv.gap + ' pts)' : ' (leader)') + '</div>'
        : '';

    el.innerHTML =
        '<div class="stats-grid">' +
        '<div class="stat-tile"><div class="stat-val">' + results.length + '</div><div class="stat-lbl">Races</div></div>' +
        '<div class="stat-tile"><div class="stat-val">' + wins    + '</div><div class="stat-lbl">Wins</div></div>' +
        '<div class="stat-tile"><div class="stat-val">' + podiums + '</div><div class="stat-lbl">Podiums</div></div>' +
        '<div class="stat-tile"><div class="stat-val">' + (career.points || 0) + '</div><div class="stat-lbl">Points</div></div>' +
        '<div class="stat-tile"><div class="stat-val">' + best + '</div><div class="stat-lbl">Best Finish</div></div>' +
        '<div class="stat-tile"><div class="stat-val">' + avg  + '</div><div class="stat-lbl">Avg Finish</div></div>' +
        '</div>' +
        '<div class="stats-champ">' +
        '<span class="stats-champ-pos">' + champPos + '</span>' +
        '<span class="stats-champ-gap">' + champGap + '</span>' +
        '<span class="stats-champ-lbl">in the championship</span>' +
        '</div>' +
        rivalHtml +
        (history.length
            ? '<div class="stats-section-label">Season history</div>' +
              '<table class="standings-table"><thead><tr>' +
              '<th>Season</th><th>Tier</th><th>Pos</th><th>Points</th><th>Races</th><th>Wins</th>' +
              '</tr></thead><tbody>' +
              history.slice().reverse().map(h =>
                  '<tr><td>' + h.season + '</td>' +
                  '<td>' + (TIER_LABELS[h.tier] || h.tier) + '</td>' +
                  '<td>' + (h.pos === 1 ? '🏆 1' : h.pos) + '</td>' +
                  '<td>' + h.pts + '</td><td>' + h.races + '</td><td>' + h.wins + '</td></tr>'
              ).join('') +
              '</tbody></table>'
            : '<div class="empty-state">No completed seasons yet.</div>');
}

// ── Modal helpers ──────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

// ── Driver profile card ─────────────────────────────────────────────────────
const NATIONALITY_FLAGS = {
    ITA:'🇮🇹', GBR:'🇬🇧', FRA:'🇫🇷', GER:'🇩🇪', ESP:'🇪🇸', NLD:'🇳🇱',
    BRA:'🇧🇷', USA:'🇺🇸', JPN:'🇯🇵', CHN:'🇨🇳', RUS:'🇷🇺', IND:'🇮🇳',
    SWE:'🇸🇪', MAR:'🇲🇦', KEN:'🇰🇪', CRO:'🇭🇷', IRL:'🇮🇪', TUR:'🇹🇷',
    GHA:'🇬🇭', AUS:'🇦🇺', POL:'🇵🇱', CZE:'🇨🇿', ROU:'🇷🇴',
};
function nationalityFlag(code) { return NATIONALITY_FLAGS[code] || '🏁'; }

const TIER_LABELS = {mx5_cup:'MX5 Cup', gt4:'GT4', gt3:'GT3', wec:'WEC'};
let _driverProfileData = null;

function _setDeltaBadge(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    const n = Number(value || 0);
    el.classList.remove('up', 'down', 'flat');
    if (n > 0.05)       { el.textContent = '↑' + n.toFixed(1); el.classList.add('up'); }
    else if (n < -0.05) { el.textContent = '↓' + Math.abs(n).toFixed(1); el.classList.add('down'); }
    else                { el.textContent = ''; el.classList.add('flat'); }
}

function renderDriverDeltas() {
    const p = (_driverProfileData && _driverProfileData.profile) ? _driverProfileData.profile : {};
    const season = (p.skill_deltas || {}).season || {};
    _setDeltaBadge('dp-skill-delta',  season.skill);
    _setDeltaBadge('dp-aggr-delta',   season.aggression);
    _setDeltaBadge('dp-wet-delta',    season.wet_skill);
    _setDeltaBadge('dp-quali-delta',  season.quali_pace);
    _setDeltaBadge('dp-cons-delta',   season.consistency);
}

async function showDriverProfile(name, car, skinIndex) {
    try {
        const liveryEl = document.getElementById('dp-livery');
        if (liveryEl) {
            if (car) {
                liveryEl.src = '/api/livery-preview?car=' + encodeURIComponent(car) + '&index=' + (skinIndex || 0);
                liveryEl.classList.remove('hidden');
                liveryEl.onerror = () => liveryEl.classList.add('hidden');
            } else {
                liveryEl.classList.add('hidden');
            }
        }
        const r    = await fetch('/api/driver-profile?name=' + encodeURIComponent(name));
        const data = await r.json();
        const p    = data.profile  || {};
        const cur  = data.current  || null;
        const hist = (data.history && data.history.seasons) ? data.history.seasons : [];
        _driverProfileData = data;

        document.getElementById('dp-nationality').textContent =
            nationalityFlag(p.nationality) + '  ' + (p.nationality || '');
        document.getElementById('dp-name').textContent  = data.name || name;
        document.getElementById('dp-team').textContent  =
            cur ? (cur.team || '') + (cur.car ? '  ·  ' + fmtCar(cur.car) : '') : '';
        // Nickname — show only when present
        const metaEl = document.getElementById('dp-meta');
        if (metaEl) {
            const ageTxt = (p.age !== undefined && p.age !== null) ? ('Age ' + p.age) : 'Age ?';
            const potTxt = (p.potential !== undefined && p.potential !== null) ? ('Potential ' + p.potential) : 'Potential ?';
            metaEl.textContent = ageTxt + ' | ' + potTxt;
        }
        const trendEl = document.getElementById('dp-trend');
        if (trendEl) {
            const t = (p.trend_label || 'Stable');
            trendEl.textContent = t.toUpperCase();
            trendEl.className = 'dp-trend ' + t.toLowerCase();
        }
        const nickEl = document.getElementById('dp-nickname');
        if (nickEl) {
            if (p.nickname) {
                nickEl.textContent = '"' + p.nickname + '"';
                nickEl.classList.remove('hidden');
            } else {
                nickEl.classList.add('hidden');
            }
        }

        // Stat bars — reset width to 0 first so CSS transition plays
        function setDpBar(barId, valId, value) {
            const bar = document.getElementById(barId);
            const val = document.getElementById(valId);
            if (bar) { bar.style.width = '0'; requestAnimationFrame(() => { bar.style.width = (value || 0) + '%'; }); }
            if (val) val.textContent = value ?? '–';
        }
        setDpBar('dp-skill-bar',  'dp-skill-val',  p.skill);
        setDpBar('dp-aggr-bar',   'dp-aggr-val',   p.aggression);
        setDpBar('dp-wet-bar',    'dp-wet-val',    p.wet_skill);
        setDpBar('dp-quali-bar',  'dp-quali-val',  p.quali_pace);
        setDpBar('dp-cons-bar',   'dp-cons-val',   p.consistency);
        renderDriverDeltas();

        // Current season
        document.getElementById('dp-current').innerHTML = cur
            ? 'P' + cur.position + ' &nbsp;·&nbsp; ' + cur.points + ' pts' +
              (cur.gap === 0 ? ' &nbsp;·&nbsp; <span style="color:var(--accent)">LEADER</span>'
                             : ' &nbsp;·&nbsp; –' + cur.gap)
            : '–';

        // Career history
        const histEl    = document.getElementById('dp-history');
        const histLabel = document.getElementById('dp-history-label');
        if (hist.length) {
            histLabel.style.display = '';
            histEl.innerHTML = hist.slice().reverse().map(s =>
                '<div class="dp-history-row">' +
                '<span>S' + s.season + ' ' + (TIER_LABELS[s.tier] || s.tier) + '</span>' +
                '<span>P' + s.pos + ' · ' + s.pts + ' pts' + (s.pos === 1 ? ' 🏆' : '') + '</span>' +
                '</div>'
            ).join('');
        } else {
            histLabel.style.display = 'none';
            histEl.innerHTML = '<span style="color:var(--text-faint);font-size:.75rem">No previous seasons</span>';
        }

        openModal('modal-driver');
    } catch (e) {
        showToast('Could not load driver profile', 'error');
    }
}

function showTeamProfile(teamName, car) {
    const tierK      = tierKey(standingsTier);
    const drivers    = (allStandings[tierK] || {}).drivers || [];
    const teamDrivers = drivers.filter(d => d.team === teamName);

    document.getElementById('tm-name').textContent = teamName;
    document.getElementById('tm-car').textContent  = fmtCar(car);

    // Team class badge (factory/semi/customer)
    const badge = document.getElementById('tm-class-badge');
    if (badge) {
        const entry = drivers.find(d => d.team === teamName);
        const cls   = entry && entry.tier_level ? entry.tier_level : '';
        if (cls) {
            badge.textContent = cls.toUpperCase();
            badge.className   = 'team-class-badge badge-' + cls;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    const tmEl = document.getElementById('tm-drivers');
    if (teamDrivers.length) {
        tmEl.innerHTML = teamDrivers.map(d =>
            '<div class="tm-driver-card">' +
            '<img class="tm-livery" src="/api/livery-preview?car=' + encodeURIComponent(car) +
            '&index=' + (d.skin_index || 0) + '" onerror="this.style.display=\'none\'" alt="">' +
            '<div class="tm-driver-name">' + (d.driver || '') + (d.is_player ? ' ★' : '') + '</div>' +
            '<div class="tm-driver-pts">P' + d.position + ' &nbsp;·&nbsp; ' + d.points + ' pts</div>' +
            '</div>'
        ).join('');
    } else {
        tmEl.innerHTML = '<span style="color:var(--text-faint);font-size:.8rem">No driver data</span>';
    }
    openModal('modal-team');

    // Fetch and render team history + champion banner
    const histSection  = document.getElementById('tm-history-section');
    const histEl       = document.getElementById('tm-history');
    const champBanner  = document.getElementById('tm-champion-banner');
    if (histSection)  histSection.classList.add('hidden');
    if (champBanner)  champBanner.classList.add('hidden');
    fetch('/api/team-profile?name=' + encodeURIComponent(teamName))
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (!data) return;
            const seasons = (data.history && data.history.seasons) || [];
            const titles  = data.titles || 0;
            // Champion banner
            if (champBanner && titles > 0) {
                champBanner.textContent = '🏆 ' + titles + 'x Championship Winner';
                champBanner.classList.remove('hidden');
            }
            if (!seasons.length) return;
            histSection.classList.remove('hidden');
            histEl.innerHTML = seasons.slice().reverse().map(s =>
                '<div class="dp-history-row' + (s.pos === 1 ? ' hist-champion' : '') + '">' +
                '<span>S' + s.season + ' ' + (s.tier_name || s.tier) + '</span>' +
                '<span>P' + s.pos + ' · ' + s.pts + ' pts' + (s.pos === 1 ? ' 🏆' : '') + '</span>' +
                '</div>'
            ).join('');
        })
        .catch(() => {});
}

async function showPlayerProfile() {
    try {
        const r    = await fetch('/api/player-profile');
        const data = await r.json();

        const livEl = document.getElementById('pp-livery');
        if (livEl) {
            if (data.car) {
                livEl.src = '/api/livery-preview?car=' + encodeURIComponent(data.car) + '&index=0';
                livEl.classList.remove('hidden');
                livEl.onerror = () => livEl.classList.add('hidden');
            } else {
                livEl.classList.add('hidden');
            }
        }

        const ppNat = document.getElementById('pp-nationality');
        if (ppNat) ppNat.textContent = data.nationality ? nationalityFlag(data.nationality) : '';
        document.getElementById('pp-name').textContent = data.driver_name || 'Player';
        document.getElementById('pp-team').textContent =
            (data.team || '') + (data.car ? '  ·  ' + fmtCar(data.car) : '');
        document.getElementById('pp-races').textContent = data.races ?? '–';
        document.getElementById('pp-wins').textContent  = data.wins  ?? '–';
        document.getElementById('pp-pods').textContent  = data.podiums ?? '–';
        document.getElementById('pp-avg').textContent   = data.avg_finish ?? '–';

        const hist      = data.history || [];
        const histEl    = document.getElementById('pp-history');
        const histLabel = document.getElementById('pp-history-label');
        if (hist.length) {
            histLabel.style.display = '';
            histEl.innerHTML = hist.slice().reverse().map(s =>
                '<div class="dp-history-row">' +
                '<span>S' + s.season + ' ' + (TIER_LABELS[s.tier] || s.tier) + '</span>' +
                '<span>P' + s.pos + ' · ' + s.pts + ' pts' + (s.pos === 1 ? ' 🏆' : '') + '</span>' +
                '</div>'
            ).join('');
        } else {
            histLabel.style.display = 'none';
            histEl.innerHTML = '<span style="color:var(--text-faint);font-size:.75rem">No previous seasons yet</span>';
        }

        openModal('modal-player');
    } catch (e) {
        showToast('Could not load player profile', 'error');
    }
}

// ── Career Wizard ───────────────────────────────────────────────────────────
let wizardState = {
    page:          1,
    difficulty:    'pro',
    weatherMode:   'realistic',
    customTracks:  null,   // null = use config defaults
    scannedTracks: [],
    selectedIds:   new Set(),
};

function openNewCareer() {
    // Reset state
    wizardState = {
        page: 1, difficulty: 'pro', weatherMode: 'realistic',
        customTracks: null, scannedTracks: [], selectedIds: new Set(),
    };
    showWizardPage(1);
    // Reset preset selections
    document.querySelectorAll('#diff-grid .wizard-preset').forEach(el =>
        el.classList.toggle('active', el.dataset.val === 'pro'));
    document.querySelectorAll('#weather-grid .wizard-preset').forEach(el =>
        el.classList.toggle('active', el.dataset.val === 'realistic'));
    // Reset scan UI
    document.getElementById('scan-loading').classList.add('hidden');
    document.getElementById('scan-results').classList.add('hidden');
    document.getElementById('btn-start-wizard').style.display = 'none';
    const nameInput = document.getElementById('new-driver-name');
    if (nameInput) nameInput.value = (career && career.driver_name) || '';
    // Show warning if overwriting existing career
    const warningEl = document.getElementById('wizard-career-warning');
    if (warningEl) warningEl.classList.toggle('hidden', !(career && career.driver_name && career.team));
    openModal('modal-new-career');
    setTimeout(() => { if (nameInput) nameInput.focus(); }, 100);
}

function showWizardPage(n) {
    wizardState.page = n;
    for (let i = 1; i <= 4; i++) {
        const page = document.getElementById('wizard-page-' + i);
        const dot  = document.getElementById('wdot-' + i);
        if (page) page.classList.toggle('hidden', i !== n);
        if (dot) {
            dot.classList.toggle('active', i === n);
            dot.classList.toggle('done',   i < n);
        }
    }
}

function wizardNext() {
    if (wizardState.page === 1) {
        const name = (document.getElementById('new-driver-name').value || '').trim();
        if (!name) { showToast('Enter a driver name', 'error'); return; }
    }
    if (wizardState.page < 4) showWizardPage(wizardState.page + 1);
}

function wizardPrev() {
    if (wizardState.page > 1) showWizardPage(wizardState.page - 1);
}

function selectPreset(type, val, el) {
    const grid = (type === 'diff') ? 'diff-grid' : 'weather-grid';
    document.querySelectorAll('#' + grid + ' .wizard-preset').forEach(e => e.classList.remove('active'));
    el.classList.add('active');
    if (type === 'diff') wizardState.difficulty  = val;
    else                 wizardState.weatherMode = val;
}

async function scanLibrary() {
    const btn = document.getElementById('btn-scan-lib');
    btn.disabled = true;
    document.getElementById('scan-loading').classList.remove('hidden');
    document.getElementById('scan-results').classList.add('hidden');
    document.getElementById('btn-start-wizard').style.display = 'none';
    try {
        const r    = await fetch('/api/scan-content');
        const data = await r.json();
        if (data.error) { showToast(data.error, 'error'); return; }

        wizardState.scannedTracks = data.tracks || [];

        // Pre-select tracks that match the current config defaults
        const defaults = new Set();
        if (config && config.tiers) {
            Object.values(config.tiers).forEach(t => (t.tracks || []).forEach(id => defaults.add(id)));
        }
        wizardState.selectedIds = new Set(
            wizardState.scannedTracks.map(t => t.id).filter(id => defaults.has(id))
        );

        renderTrackChecklist('all');
        document.getElementById('scan-results').classList.remove('hidden');
        document.getElementById('btn-start-wizard').style.display = '';
        _updateTrackCount();
    } catch (e) {
        showToast('Scan failed: ' + e.message, 'error');
    } finally {
        document.getElementById('scan-loading').classList.add('hidden');
        btn.disabled = false;
    }
}

function filterTracks(filter, btn) {
    document.querySelectorAll('.scan-filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderTrackChecklist(filter);
}

function renderTrackChecklist(filter) {
    const tracks = wizardState.scannedTracks.filter(t => {
        if (filter === 'short')  return t.length > 0 && t.length <= 3000;
        if (filter === 'medium') return t.length > 3000 && t.length <= 7000;
        if (filter === 'long')   return t.length > 7000;
        return true;
    });
    const list = document.getElementById('track-checklist');
    if (!tracks.length) {
        list.innerHTML = '<div class="form-hint" style="padding:.4rem 0">No tracks found for this filter.</div>';
        return;
    }
    list.innerHTML = tracks.map(t => {
        const checked = wizardState.selectedIds.has(t.id) ? 'checked' : '';
        const lenStr  = t.length ? (t.length / 1000).toFixed(2) + ' km' : '–';
        const safeId  = t.id.replace(/[^a-z0-9_\-\/]/gi, '_');
        return '<label class="track-check-item">' +
            '<input type="checkbox" value="' + t.id + '" ' + checked +
            ' onchange="toggleTrack(\'' + t.id + '\',this.checked)">' +
            '<span class="track-check-name">' + t.name + '</span>' +
            '<span class="track-check-len">' + lenStr + '</span>' +
            '</label>';
    }).join('');
}

function toggleTrack(id, checked) {
    if (checked) wizardState.selectedIds.add(id);
    else         wizardState.selectedIds.delete(id);
    _updateTrackCount();
}

function _updateTrackCount() {
    const el = document.getElementById('scan-track-count');
    if (el) el.textContent = wizardState.selectedIds.size + ' track(s) selected for GT4 / GT3 / WEC';
}

function useDefaultTracks() {
    wizardState.customTracks = null;
    startCareerFromWizard();
}

async function startCareerFromWizard() {
    const name = (document.getElementById('new-driver-name').value || '').trim();
    if (!name) { showWizardPage(1); showToast('Enter a driver name', 'error'); return; }

    // Build custom_tracks from wizard selection (if user scanned)
    let customTracks = null;
    if (wizardState.selectedIds.size > 0) {
        const selected = Array.from(wizardState.selectedIds);
        // All selected tracks go to GT4 / GT3 / WEC (same pool)
        // MX5 always uses config defaults — no custom track pool needed
        customTracks = { gt4: selected, gt3: selected, wec: selected };
    }

    try {
        const r = await fetch('/api/new-career', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({
                driver_name:   name,
                nationality:   document.getElementById('new-driver-nationality').value || '',
                difficulty:    wizardState.difficulty,
                weather_mode:  wizardState.weatherMode,
                custom_tracks: customTracks,
            }),
        });
        const d = await r.json();
        closeModal('modal-new-career');
        if (d.status === 'success') {
            await Promise.all([loadCareer(), loadConfig()]);
            await Promise.all([loadAllStandings(), loadCalendar()]);
            loadNextRacePreview().then(() => renderCalendar());
            refresh();
            showView('main');
            showToast('Career started! Good luck, ' + name + '! \uD83C\uDFC1');
        } else {
            showToast(d.message || 'Error starting career', 'error');
        }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

// ── End Season / Go to Contracts ───────────────────────────────────────────
async function goToContracts() {
    // If recap data is cached from this session, show it first
    if (_lastRecap) {
        renderRecap(_lastRecap.recap, _lastRecap.position, _lastRecap.total_points);
        showView('recap');
        return;
    }
    // Contracts already generated (e.g. app restarted after season end) — fetch stored recap first
    if (career && career.contracts && career.contracts.length) {
        try {
            const r = await fetch('/api/season-recap');
            if (r.ok) {
                const d = await r.json();
                _lastRecap = { recap: d.recap, position: d.position, total_points: d.total_points };
                renderRecap(d.recap, d.position, d.total_points);
                showView('recap');
                return;
            }
        } catch (_) {}
        showView('contracts');
        return;
    }
    // End-season not yet processed — trigger it now
    try {
        const r = await fetch('/api/end-season', { method: 'POST' });
        const d = await r.json();
        await Promise.all([loadCareer(), loadAllStandings(), loadCalendar()]);
        refresh();
        _pendingContracts = d.contracts || [];
        _lastRecap = d.recap
            ? { recap: d.recap, position: d.position, total_points: d.total_points }
            : null;
        if (d.recap) {
            renderRecap(d.recap, d.position, d.total_points);
            showView('recap');
        } else {
            showView('contracts');
        }
    } catch (e) { showToast('Error loading season end data', 'error'); }
}

// ── Start Race ─────────────────────────────────────────────────────────────
async function startRace() {
    if (!career || !career.team) {
        showToast('Start a new career first!', 'error');
        return;
    }
    const total = (career && career.total_races) || (config && config.seasons && config.seasons.races_per_tier) || 10;
    if ((career.races_completed || 0) >= total) {
        showToast('Season complete! Check your contract offers.', 'warning');
        goToContracts();
        return;
    }
    try {
        const r = await fetch('/api/next-race');
        pendingRace = await r.json();

        // Populate modal
        const details = document.getElementById('race-details');
        const pracMin  = pendingRace.practice_minutes || 10;
        const qualiMin = pendingRace.quali_minutes   || 10;
        details.innerHTML = [
            rdItem('Track',       fmtTrack(pendingRace.track)),
            rdItem('Car',         fmtCar(pendingRace.car)),
            rdItem('Team',        pendingRace.team || '–'),
            rdItem('Round',       'Race ' + pendingRace.race_num + ' / ' + total),
            rdItem('Race',        pendingRace.laps + ' laps'),
            rdItem('AI Level',    Math.round(pendingRace.ai_difficulty) + '%'),
            rdItem('Practice',    pracMin + ' min'),
            rdItem('Qualifying',  qualiMin + ' min'),
            rdItem('Weather',     fmtWeather(pendingRace.weather)),
        ].join('');

        // Update AI level in calendar bar
        document.getElementById('nrb-ai').textContent =
            Math.round(pendingRace.ai_difficulty);

        // Pre-flight check: verify track and car exist in AC
        const pfRes = await fetch(
            '/api/preflight-check?track=' + encodeURIComponent(pendingRace.track) +
            '&car=' + encodeURIComponent(pendingRace.car || '')
        );
        const pf    = await pfRes.json();
        const pfDiv = document.getElementById('preflight-warnings');
        if (pf.issues && pf.issues.length > 0) {
            pfDiv.innerHTML = pf.issues.map(i =>
                '<div class="preflight-issue preflight-' + i.type + '">' +
                (i.type === 'error' ? '&#10060; ' : '&#9888; ') + i.msg +
                '</div>'
            ).join('');
            pfDiv.classList.remove('hidden');
        } else {
            pfDiv.innerHTML = '';
            pfDiv.classList.add('hidden');
        }

        openModal('modal-race');
    } catch (e) { showToast('Error loading race details', 'error'); }
}

function rdItem(label, value) {
    return (
        '<div class="rd-item">' +
        '<div class="rd-label">' + label + '</div>' +
        '<div class="rd-value">' + value + '</div>' +
        '</div>'
    );
}

// ── Auto result polling ────────────────────────────────────────────────────
let _resultPollTimer  = null;
const POLL_INTERVAL_MS  = 5000;   // check every 5 s
const POLL_MAX_ATTEMPTS = 360;    // give up after 30 min
function resumeResultCheckOnReturn() {
    if (document.hidden) return;
    const resultView = document.getElementById('view-result');
    if (!resultView || resultView.style.display === 'none') return;
    if (_resultPollTimer) return;

    const autoEl   = document.getElementById('result-auto');
    const foundEl  = document.getElementById('result-found');
    const manualEl = document.getElementById('result-manual');
    if (!autoEl || !foundEl || !manualEl) return;

    const waitingForAutoResult =
        autoEl.style.display !== 'none' &&
        foundEl.classList.contains('hidden') &&
        manualEl.classList.contains('hidden');

    if (waitingForAutoResult) {
        fetchRaceResult();
        startResultPolling();
    }
}

document.addEventListener('visibilitychange', resumeResultCheckOnReturn);
window.addEventListener('focus', resumeResultCheckOnReturn);

function startResultPolling() {
    if (_resultPollTimer) clearInterval(_resultPollTimer);
    let attempts = 0;
    const statusEl = document.getElementById('result-auto-status');
    if (statusEl) {
        statusEl.textContent = 'Waiting for AC to finish…';
        statusEl.className   = 'result-auto-status loading';
    }
    _resultPollTimer = setInterval(async () => {
        attempts++;
        if (attempts > POLL_MAX_ATTEMPTS) {
            clearInterval(_resultPollTimer);
            _resultPollTimer = null;
            if (statusEl) {
                statusEl.textContent = 'Timed out. Click the button to try again.';
                statusEl.className   = 'result-auto-status warning';
            }
            return;
        }
        try {
            const r = await fetch('/api/read-race-result');
            const d = await r.json();
            if (d.status === 'found' || d.status === 'incomplete') {
                clearInterval(_resultPollTimer);
                _resultPollTimer = null;
                fetchRaceResult();   // reuse existing display logic
            }
        } catch (_) { /* network hiccup — keep polling */ }
    }, POLL_INTERVAL_MS);
}

async function confirmStartRace(mode) {
    mode = mode || 'race_only';
    try {
        const r = await fetch('/api/start-race', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode }),
        });
        const d = await r.json();
        closeModal('modal-race');

        if (d.status === 'success') {
            const modeLabel = mode === 'full_weekend' ? 'Full Weekend gestart! 🏁' : 'AC launched! Go race! 🏁';
            showToast(modeLabel);
            // Set race label
            const lbl = document.getElementById('result-race-label');
            if (lbl && pendingRace) {
                lbl.textContent =
                    'Race ' + pendingRace.race_num +
                    ' · ' + fmtTrack(pendingRace.track);
            }
            // Reset result view to auto-read state
            if (_resultPollTimer) { clearInterval(_resultPollTimer); _resultPollTimer = null; }
            document.getElementById('result-auto').style.display     = '';
            document.getElementById('result-auto-status').textContent = '';
            document.getElementById('result-auto-status').className   = 'result-auto-status';
            document.getElementById('result-found').classList.add('hidden');
            document.getElementById('result-manual').classList.add('hidden');
            document.getElementById('debrief-panel').classList.add('hidden');
            const _sd = document.getElementById('debrief-sectors');
            if (_sd) _sd.classList.add('hidden');
            const _md = document.getElementById('debrief-meta');
            if (_md) _md.classList.add('hidden');
            document.getElementById('finish-position').value = 1;
            document.getElementById('best-lap').value        = '';
            if (pendingRace) pendingRace._autoResult = null;
            setTimeout(() => { showView('result'); startResultPolling(); }, 1200);
        } else {
            showToast(d.message || 'Failed to launch AC', 'error');
        }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

// ── Auto-read AC result ────────────────────────────────────────────────────
async function fetchRaceResult() {
    const statusEl = document.getElementById('result-auto-status');
    statusEl.textContent = 'Searching for result...';
    statusEl.className   = 'result-auto-status loading';

    try {
        const r = await fetch('/api/read-race-result');
        const d = await r.json();

        if (d.status === 'found') {
            document.getElementById('rf-position').textContent = 'P' + d.position;
            document.getElementById('rf-best-lap').textContent = d.best_lap || '–';
            document.getElementById('rf-laps').textContent     = d.laps_completed + ' / ' + d.expected_laps;
            document.getElementById('result-found').classList.remove('hidden');
            document.getElementById('result-auto').style.display = 'none';
            statusEl.textContent = '';
            if (pendingRace) pendingRace._autoResult = d;
            renderDebrief(d.lap_analysis, d.position);

        } else if (d.status === 'incomplete') {
            statusEl.textContent = 'Race not completed (' + d.laps_completed + '/' + d.expected_laps +
                ' laps). Please enter the result manually.';
            statusEl.className = 'result-auto-status warning';
            showManualForm('Race ended early. Please enter result manually.');
            if (d.position) document.getElementById('finish-position').value = d.position;
            if (d.best_lap) document.getElementById('best-lap').value         = d.best_lap;

        } else {
            statusEl.textContent = d.message || 'No result found. Close AC and try again.';
            statusEl.className   = 'result-auto-status warning';
        }
    } catch (e) {
        statusEl.textContent = 'Error: ' + e.message;
        statusEl.className   = 'result-auto-status error';
    }
}

function renderDebrief(analysis, position) {
    const panel = document.getElementById('debrief-panel');
    if (!panel) return;
    if (!analysis || analysis.consistency === undefined) {
        panel.classList.add('hidden');
        return;
    }

    // Consistency score badge
    const score = analysis.consistency;
    const badge = document.getElementById('debrief-consistency');
    badge.textContent = score + '/100';
    badge.className = 'consistency-badge ' + (
        score >= 80 ? 'con-excellent' :
        score >= 60 ? 'con-good' :
        score >= 40 ? 'con-average' : 'con-poor'
    );

    // Engineer feedback text
    const reportEl = document.getElementById('debrief-report');
    if (reportEl) reportEl.textContent = analysis.engineer_report || '';

    // Lap sparkline (mini bar chart)
    const lapsEl = document.getElementById('debrief-laps');
    const laps   = analysis.lap_times || [];
    if (lapsEl && laps.length >= 2) {
        const minLt = Math.min(...laps);
        const maxLt = Math.max(...laps);
        const range = maxLt - minLt || 1;
        const bars  = laps.map((lt, i) => {
            const pct    = 100 - Math.round(((lt - minLt) / range) * 75); // 25–100%
            const isBest = (lt === minLt);
            return '<div class="lap-bar' + (isBest ? ' lap-bar-best' : '') +
                   '" style="height:' + pct + '%" title="Lap ' + (i + 1) + ': ' + fmtMs(lt) + '"></div>';
        }).join('');
        lapsEl.innerHTML =
            '<div class="lap-bars">' + bars + '</div>' +
            '<div class="lap-sparkline-label">' +
            laps.length + ' laps &nbsp;·&nbsp; &#9650; taller = faster &nbsp;·&nbsp; best: ' + fmtMs(minLt) +
            ' &nbsp;·&nbsp; avg: ' + fmtMs(analysis.avg_lap_ms) +
            '</div>';
    } else if (lapsEl) {
        lapsEl.innerHTML = '';
    }

    // Sector breakdown (S1/S2/S3 best + avg, weakest highlighted)
    const secEl = document.getElementById('debrief-sectors');
    const sa    = analysis.sector_analysis;
    if (secEl && sa && sa.length === 3) {
        const labels = ['S1', 'S2', 'S3'];
        secEl.innerHTML = sa.map((s, i) => {
            const isWeak = (analysis.weakest_sector === i + 1);
            return '<div class="sector-card' + (isWeak ? ' sector-weak' : '') + '">' +
                '<div class="sector-label">' + labels[i] + (isWeak ? ' ⚠' : '') + '</div>' +
                '<div class="sector-best">' + fmtMs(s.best_ms) + '</div>' +
                '<div class="sector-avg">avg ' + fmtMs(s.avg_ms) + '</div>' +
                '</div>';
        }).join('');
        secEl.classList.remove('hidden');
    } else if (secEl) {
        secEl.classList.add('hidden');
    }

    // Meta row: gap to leader · tyre compound · track cuts
    const metaEl = document.getElementById('debrief-meta');
    if (metaEl) {
        const parts = [];
        if (analysis.gap_to_leader_ms) {
            parts.push('⏱ +' + fmtMs(analysis.gap_to_leader_ms) + ' to leader');
        }
        if (analysis.tyre) {
            parts.push('🏎 ' + analysis.tyre);
        }
        if (analysis.total_cuts) {
            parts.push('⚠ ' + analysis.total_cuts + ' track limit' +
                       (analysis.total_cuts > 1 ? 's' : ''));
        }
        if (parts.length) {
            metaEl.textContent = parts.join('  ·  ');
            metaEl.classList.remove('hidden');
        } else {
            metaEl.classList.add('hidden');
        }
    }

    panel.classList.remove('hidden');

    // Rival status one-liner
    const existingRivalEl = document.getElementById('debrief-rival');
    if (existingRivalEl) existingRivalEl.remove();
    if (career && career.rival_name) {
        const tierK   = tierKey(career.tier);
        const drivers = (allStandings[tierK] || {}).drivers || [];
        const rv      = drivers.find(d => d.driver === career.rival_name);
        if (rv) {
            const gapTxt = rv.gap === 0 ? 'leader' : rv.gap + ' pts behind';
            const div    = document.createElement('div');
            div.id        = 'debrief-rival';
            div.className = 'rival-debrief';
            div.innerHTML = '⚔ Rival <strong>' + career.rival_name + '</strong> is P' +
                            rv.position + ' (' + gapTxt + ')';
            panel.appendChild(div);
        }
    }
}

function showManualForm(hint) {
    const manualEl = document.getElementById('result-manual');
    const hintEl   = document.getElementById('result-manual-hint');
    if (hintEl) hintEl.textContent = hint || '';
    manualEl.classList.remove('hidden');
}

async function submitAutoResult() {
    if (!pendingRace || !pendingRace._autoResult) return;
    const d       = pendingRace._autoResult;
    const pos     = d.position;
    const lapTime = d.best_lap || '';
    const marginMs = Number.isFinite(d.margin_to_p2_ms) ? d.margin_to_p2_ms : null;
    await _postFinishRace(pos, lapTime, marginMs);
}

// ── Submit Race Result (manual form) ──────────────────────────────────────
async function submitResult(e) {
    e.preventDefault();
    const pos     = parseInt(document.getElementById('finish-position').value);
    const lapTime = document.getElementById('best-lap').value;
    await _postFinishRace(pos, lapTime, null);
}

async function _postFinishRace(pos, lapTime, marginMs) {
    try {
        const r = await fetch('/api/finish-race', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ position: pos, lap_time: lapTime, margin_ms: marginMs }),
        });
        const d = await r.json();

        if (d.status === 'season_complete') {
            await handleSeasonComplete(d);
        } else if (d.status === 'success') {
            const pts = d.result ? d.result.points : 0;
            const aiMsg = d.ai_change ? (' AI ' + (d.ai_change > 0 ? '+' : '') + d.ai_change + ' (offset ' + d.ai_offset + ')') : '';
            showToast(fmtPos(pos) + ' — +' + pts + ' pts!' + aiMsg);
            await Promise.all([loadCareer(), loadAllStandings(), loadCalendar()]);
            loadNextRacePreview().then(() => renderCalendar());
            refresh();
            loadNewsTicker();
            showView('main');
        } else {
            showToast('Error submitting result', 'error');
        }
    } catch (err) { showToast('Error: ' + err.message, 'error'); }
}

// ── Season Complete ────────────────────────────────────────────────────────
let _pendingContracts = [];
let _lastRecap = null;  // cached for End Season button re-entry

async function handleSeasonComplete(data) {
    await Promise.all([loadCareer(), loadAllStandings(), loadCalendar()]);
    refresh();
    loadNewsTicker();

    _pendingContracts = data.contracts || [];
    _lastRecap = data.recap
        ? { recap: data.recap, position: data.position, total_points: data.total_points }
        : null;

    if (data.recap) {
        renderRecap(data.recap, data.position, data.total_points);
        showView('recap');
        showToast('Season over! Review your recap, then choose a contract.');
    } else {
        // Fallback for old responses without recap
        renderContracts(_pendingContracts);
        showView('contracts');
        showToast('Season over! Choose your next contract.');
    }
}

function showRecapContracts() {
    renderContracts(_pendingContracts);
    showView('contracts');
}

const _TIER_LABELS = {mx5_cup: 'MX5 Cup', gt4: 'GT4', gt3: 'GT3', wec: 'WEC'};

function renderRecap(recap, position, totalPoints) {
    const posEl = document.getElementById('recap-pos-text');
    if (posEl) posEl.textContent = 'You finished P' + position + ' with ' + totalPoints + ' points.';

    const p = recap.player || {};
    const champions = recap.tier_champions || {};
    const improved = recap.most_improved;

    // Team boss quote
    if (recap.boss_message) {
        const bossEl = document.getElementById('recap-boss-quote');
        if (bossEl) {
            bossEl.innerHTML =
                `<span class="recap-quote-text">"${recap.boss_message}"</span>` +
                `<span class="recap-quote-attr">Team Principal</span>`;
            bossEl.classList.remove('hidden');
        }
    }

    let html = '<div class="recap-grid">';

    // Player stats block
    html += '<div class="recap-block">';
    html += '<div class="recap-block-title">Your Season</div>';
    html += '<div class="recap-stats">';
    html += `<div class="recap-stat"><span class="recap-stat-val">${p.wins ?? 0}</span><span class="recap-stat-lbl">Wins</span></div>`;
    html += `<div class="recap-stat"><span class="recap-stat-val">${p.podiums ?? 0}</span><span class="recap-stat-lbl">Podiums</span></div>`;
    html += `<div class="recap-stat"><span class="recap-stat-val">${p.best_result ? 'P' + p.best_result : '—'}</span><span class="recap-stat-lbl">Best Result</span></div>`;
    html += `<div class="recap-stat"><span class="recap-stat-val">${p.races ?? 0}</span><span class="recap-stat-lbl">Races</span></div>`;
    html += '</div></div>';

    // Tier champions block
    const tierKeys = ['mx5_cup', 'gt4', 'gt3', 'wec'];
    const champEntries = tierKeys.filter(tk => champions[tk]);
    if (champEntries.length) {
        html += '<div class="recap-block">';
        html += '<div class="recap-block-title">&#127942; Champions</div>';
        html += '<table class="recap-table">';
        for (const tk of champEntries) {
            html += `<tr><td class="recap-tier-lbl">${_TIER_LABELS[tk] || tk}</td><td>${champions[tk]}</td></tr>`;
        }
        html += '</table></div>';
    }

    // Most improved
    if (improved) {
        html += '<div class="recap-block">';
        html += '<div class="recap-block-title">&#128200; Most Improved</div>';
        html += `<p class="recap-improved">${improved}</p>`;
        html += '</div>';
    }

    html += '</div>';
    document.getElementById('recap-body').innerHTML = html;
}

// ── Contracts ──────────────────────────────────────────────────────────────
function renderContracts(contracts) {
    const el = document.getElementById('contracts-list');
    if (!el) return;

    if (!contracts || contracts.length === 0) {
        el.innerHTML = '<p style="color:var(--text-dim)">No contracts available.</p>';
        return;
    }
    if (contracts[0] && contracts[0].complete) {
        el.innerHTML =
            '<p style="color:var(--accent);font-size:1.1rem;font-weight:700">' +
            'Congratulations! You have completed the full career! 🏆</p>';
        return;
    }
    const hasDegRisk = contracts.some(c => c.degradation_risk);
    const banner = hasDegRisk
        ? '<div class="deg-risk-banner">⚠ Poor season results. Your seat is at risk. Limited offers available.</div>'
        : '';

    el.innerHTML = banner + contracts.map(c =>
        '<div class="contract-card' + (c.degradation_risk ? ' contract-deg' : '') + '">' +
        '<div class="contract-team">'     + escHtml(c.team_name) + '</div>' +
        '<div class="contract-tier-lbl">' + escHtml(c.tier_level || '') + ' · ' + escHtml(c.tier_name || '') + '</div>' +
        '<div class="contract-car-lbl">'  + escHtml(fmtCar(c.car)) + '</div>' +
        '<p class="contract-desc">'       + escHtml(c.description || '') + '</p>' +
        '<button class="btn btn-race" onclick=\'acceptContract(' + JSON.stringify(String(c.id || '')) + ')\'>Sign Contract</button>' +
        '</div>'
    ).join('');
}

async function acceptContract(contractId) {
    try {
        const r = await fetch('/api/accept-contract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contract_id: contractId }),
        });
        const d = await r.json();
        if (d.status === 'success') {
            _lastRecap = null;
            _pendingContracts = [];
            showToast('Welcome to ' + d.new_team + '! 🏎');
            await Promise.all([loadCareer(), loadConfig()]);
            await Promise.all([loadAllStandings(), loadCalendar()]);
            loadNextRacePreview().then(() => renderCalendar());
            refresh();
            loadNewsTicker();
            showView('main');
        } else {
            showToast(d.message || 'Error accepting contract', 'error');
        }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

// ── Settings ───────────────────────────────────────────────────────────────
async function browseAcFolder() {
    const path = await browseFolder();
    if (path) {
        document.getElementById('s-ac-path').value = path;
        const hint = document.getElementById('s-ac-hint');
        if (hint) hint.textContent = '';
    }
}

async function saveSettings() {
    const aiLevel        = parseFloat(document.getElementById('s-ai-level').value);
    const aiVar          = parseFloat(document.getElementById('s-ai-var').value);
    const acPath         = (document.getElementById('s-ac-path').value || '').trim();
    const hint           = document.getElementById('s-ac-hint');
    const dynamicWeather = document.getElementById('s-dynamic-weather').checked;
    const nightCycle     = document.getElementById('s-night-cycle').checked;

    // Deep-clone and patch
    const updated = JSON.parse(JSON.stringify(config));
    updated.difficulty.base_ai_level = aiLevel;
    updated.difficulty.ai_variance   = aiVar;
    // races_per_tier is now auto-derived from track list length — not saved here
    if (acPath) updated.paths.ac_install = acPath;

    try {
        const [r1, r2] = await Promise.all([
            fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updated),
            }),
            fetch('/api/career-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dynamic_weather: dynamicWeather, night_cycle: nightCycle }),
            }),
        ]);
        const d = await r1.json();
        if (d.status === 'success') {
            config = updated;
            if (career) {
                if (!career.career_settings) career.career_settings = {};
                career.career_settings.dynamic_weather = dynamicWeather;
                career.career_settings.night_cycle     = nightCycle;
            }
            renderCalendar();  // refresh next-race bar with new AI level
            showToast('Settings saved!');
            showView('main');
        } else {
            showToast('Save failed', 'error');
        }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className   = 'toast' +
        (type === 'error'   ? ' error'   : '') +
        (type === 'warning' ? ' warning' : '');
    t.classList.remove('hidden');
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.add('hidden'), 3500);
}
