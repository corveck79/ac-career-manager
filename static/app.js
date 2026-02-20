/* AC Career Manager - Frontend JS */
'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let career     = null;
let config     = null;
let standings  = [];
let calendar   = [];
let pendingRace = null;

// ── Track name map ──────────────────────────────────────────────────────────
const TRACK_NAMES = {
    // MX5 Cup
    'ks_silverstone/national':         'Silverstone National',
    'ks_brands_hatch/indy':            'Brands Hatch Indy',
    'magione':                         'Magione',
    'ks_vallelunga/club_circuit':      'Vallelunga Club',
    'ks_black_cat_county/layout_long': 'Black Cat County',
    // GT4
    'ks_silverstone/gp':               'Silverstone GP',
    'ks_brands_hatch/gp':              'Brands Hatch GP',
    'ks_red_bull_ring/layout_national':'Red Bull Ring',
    // GT3 / WEC
    'spa':                             'Spa-Francorchamps',
    'monza':                           'Monza',
    'ks_laguna_seca':                  'Laguna Seca',
    'mugello':                         'Mugello',
    'imola':                           'Imola',
};

function fmtTrack(id) {
    return TRACK_NAMES[id] || id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
function fmtCar(id) {
    if (!id) return '–';
    return id.replace(/^ks_/, '').replace(/_/g, ' ')
             .replace(/\b\w/g, c => c.toUpperCase());
}
function fmtPos(n) {
    return n === 1 ? 'P1 🥇' : n === 2 ? 'P2 🥈' : n === 3 ? 'P3 🥉' : 'P' + n;
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

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await checkSetup();
    await Promise.all([loadCareer(), loadConfig()]);
    await Promise.all([loadStandings(), loadCalendar()]);
    refresh();
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
async function loadStandings() {
    try {
        const r   = await fetch('/api/standings');
        const d   = await r.json();
        standings = d.standings || [];
    } catch (e) { console.error('loadStandings', e); }
}
async function loadCalendar() {
    try {
        const r  = await fetch('/api/season-calendar');
        calendar = await r.json();
    } catch (e) { console.error('loadCalendar', e); }
}

// ── Full refresh ───────────────────────────────────────────────────────────
function refresh() {
    updateDriverCard();
    renderCalendar();
    renderStandings();
}

// ── Driver card ────────────────────────────────────────────────────────────
function updateDriverCard() {
    if (!career || !config) return;

    const name   = career.driver_name || 'No Driver';
    const total  = (config.seasons && config.seasons.races_per_tier) || 10;
    const done   = career.races_completed || 0;

    // Top bar
    document.getElementById('tier-badge').textContent    = tierName(career.tier || 0);
    document.getElementById('season-badge').textContent  = 'Season ' + (career.season || 1);
    document.getElementById('topbar-driver-name').textContent = (name !== 'No Driver') ? name : '';

    // Sidebar driver card
    document.getElementById('driver-initials').textContent = initials(name);
    document.getElementById('driver-name').textContent     = name;
    document.getElementById('driver-team').textContent     = career.team  || '–';
    document.getElementById('driver-car').textContent      = fmtCar(career.car);
    document.getElementById('driver-points').textContent   = career.points || 0;
    document.getElementById('races-done').textContent      = done + '/' + total;

    // Position from standings
    const me = standings.find(s => s.is_player);
    document.getElementById('driver-pos').textContent = me ? 'P' + me.position : '–';
}

// ── Season Calendar ────────────────────────────────────────────────────────
function renderCalendar() {
    const row     = document.getElementById('rounds-row');
    const progEl  = document.getElementById('calendar-progress');
    const nrbBar  = document.getElementById('next-race-bar');
    const doneBanner = document.getElementById('season-done-bar');
    if (!row) return;

    row.innerHTML = '';

    if (!calendar || !calendar.length) {
        if (progEl) progEl.textContent = '0 / 10 races';
        return;
    }

    const total = calendar.length;
    const done  = calendar.filter(r => r.status === 'completed').length;
    if (progEl) progEl.textContent = done + ' / ' + total + ' races';

    let nextRound = null;

    calendar.forEach(r => {
        const pill = document.createElement('div');
        pill.className = 'round-pill ' + r.status;

        // Shorten track name to first word (max 8 chars)
        const shortTrack = fmtTrack(r.track).split(' ')[0].slice(0, 8);
        const icon = r.status === 'completed' ? '✓' : r.status === 'next' ? '►' : '○';
        const resultHtml = (r.status === 'completed' && r.result)
            ? '<div class="rp-result">P' + r.result.position + '</div>'
            : '';

        pill.innerHTML =
            '<div class="rp-num">R' + r.round + '</div>' +
            '<div class="rp-track">' + shortTrack + '</div>' +
            '<div class="rp-status">' + icon + '</div>' +
            resultHtml;

        row.appendChild(pill);
        if (r.status === 'next') nextRound = r;
    });

    // Season done?
    if (done >= total) {
        nrbBar.style.display = 'none';
        doneBanner.classList.remove('hidden');
        return;
    }

    // Show next race bar
    doneBanner.classList.add('hidden');
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
    }
}

// ── Standings ──────────────────────────────────────────────────────────────
function renderStandings() {
    const tbody = document.getElementById('standings-body');
    const empty = document.getElementById('standings-empty');
    const table = document.getElementById('standings-table');
    if (!tbody) return;

    const hasCareer = career && career.team;

    if (!hasCareer || !standings.length) {
        if (empty) empty.style.display = '';
        if (table) table.style.display = 'none';
        return;
    }
    if (empty) empty.style.display = 'none';
    if (table) table.style.display = '';

    tbody.innerHTML = standings.map(s => {
        const posClass = s.position === 1 ? 'pos-1' :
                         s.position === 2 ? 'pos-2' :
                         s.position === 3 ? 'pos-3' : '';
        const rowClass = s.is_player ? 'player-row' : '';
        const gap      = s.gap === 0 ? '–' : '–' + s.gap;
        return (
            '<tr class="' + rowClass + '">' +
            '<td class="col-pos ' + posClass + '">' + s.position + '</td>' +
            '<td class="col-team">' + (s.is_player ? '★ ' : '') + s.team + '</td>' +
            '<td class="col-car">'  + fmtCar(s.car)   + '</td>' +
            '<td class="col-pts">'  + s.points         + '</td>' +
            '<td class="col-gap">'  + gap              + '</td>' +
            '</tr>'
        );
    }).join('');
}

// ── Setup ──────────────────────────────────────────────────────────────────
async function checkSetup() {
    try {
        const r = await fetch('/api/setup-status');
        const d = await r.json();
        if (!d.valid) {
            const input = document.getElementById('setup-ac-path');
            if (input && d.path) input.value = d.path;
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
    if (!path) { hint.textContent = 'Vul een map in.'; return; }
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
            await Promise.all([loadStandings(), loadCalendar()]);
            refresh();
            showToast('Assetto Corsa gevonden!');
        } else {
            hint.textContent = d.message || 'Map niet gevonden.';
        }
    } catch (e) { hint.textContent = 'Fout: ' + e.message; }
}

// Native folder picker — calls Qt main thread via Flask endpoint
async function browseFolder() {
    try {
        const r = await fetch('/api/browse-folder', { method: 'POST' });
        const d = await r.json();
        return d.folder || null;
    } catch {
        return null;
    }
}

// ── View management ────────────────────────────────────────────────────────
const ALL_VIEWS = ['standings', 'result', 'contracts', 'config'];

function showView(name) {
    ALL_VIEWS.forEach(v => {
        const el = document.getElementById('view-' + v);
        if (!el) return;
        if (v === name) {
            el.style.display = '';
            el.classList.add('active');
            el.classList.remove('hidden');
        } else {
            el.style.display = 'none';
            el.classList.remove('active');
            el.classList.add('hidden');
        }
    });
}

function openConfig() {
    if (!config) return;
    const diff  = config.difficulty || {};
    const seas  = config.seasons    || {};
    const paths = config.paths      || {};

    const aiEl    = document.getElementById('s-ai-level');
    const varEl   = document.getElementById('s-ai-var');
    const racesEl = document.getElementById('s-races');
    const pathEl  = document.getElementById('s-ac-path');
    const hint    = document.getElementById('s-ac-hint');

    aiEl.value    = diff.base_ai_level || 85;
    document.getElementById('s-ai-level-val').textContent = aiEl.value;

    varEl.value   = diff.ai_variance || 1.5;
    document.getElementById('s-ai-var-val').textContent = '\u00b1' + varEl.value;

    racesEl.value = seas.races_per_tier || 10;
    document.getElementById('s-races-val').textContent = racesEl.value;

    pathEl.value  = paths.ac_install || '';
    if (hint) hint.textContent = '';

    showView('config');
}

// ── Modal helpers ──────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

// ── New Career ─────────────────────────────────────────────────────────────
function openNewCareer() {
    const input = document.getElementById('new-driver-name');
    if (input) input.value = (career && career.driver_name) || '';
    openModal('modal-new-career');
    setTimeout(() => { if (input) input.focus(); }, 100);
}

async function confirmNewCareer() {
    const name = (document.getElementById('new-driver-name').value || '').trim();
    if (!name) {
        showToast('Please enter a driver name', 'error');
        return;
    }
    try {
        const r = await fetch('/api/new-career', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ driver_name: name }),
        });
        const d = await r.json();
        if (d.status === 'success') {
            closeModal('modal-new-career');
            await Promise.all([loadCareer(), loadConfig()]);
            await Promise.all([loadStandings(), loadCalendar()]);
            refresh();
            showView('standings');
            showToast('Career started! Good luck, ' + name + '! 🏁');
        } else {
            showToast('Error starting career', 'error');
        }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

// ── Start Race ─────────────────────────────────────────────────────────────
async function startRace() {
    if (!career || !career.team) {
        showToast('Start a new career first!', 'error');
        return;
    }
    const total = (config && config.seasons && config.seasons.races_per_tier) || 10;
    if ((career.races_completed || 0) >= total) {
        showToast('Season complete — check your contract offers!', 'warning');
        showView('contracts');
        return;
    }
    try {
        const r = await fetch('/api/next-race');
        pendingRace = await r.json();

        // Populate modal
        const details = document.getElementById('race-details');
        details.innerHTML = [
            rdItem('Track',    fmtTrack(pendingRace.track)),
            rdItem('Car',      fmtCar(pendingRace.car)),
            rdItem('Team',     pendingRace.team || '–'),
            rdItem('Round',    'Race ' + pendingRace.race_num + ' / ' + total),
            rdItem('Laps',     pendingRace.laps),
            rdItem('AI Level', Math.round(pendingRace.ai_difficulty) + '%'),
        ].join('');

        // Update AI level in calendar bar
        document.getElementById('nrb-ai').textContent =
            Math.round(pendingRace.ai_difficulty);

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

async function confirmStartRace() {
    try {
        const r = await fetch('/api/start-race', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const d = await r.json();
        closeModal('modal-race');

        if (d.status === 'success') {
            showToast('AC launched! Go race! 🏁');
            // Pre-fill result label and switch view after a moment
            const lbl = document.getElementById('result-race-label');
            if (lbl && pendingRace) {
                lbl.textContent =
                    'Race ' + pendingRace.race_num +
                    ' · ' + fmtTrack(pendingRace.track);
            }
            document.getElementById('finish-position').value = 1;
            document.getElementById('best-lap').value        = '';
            document.getElementById('fastest-lap').checked   = false;
            setTimeout(() => showView('result'), 1200);
        } else {
            showToast(d.message || 'Failed to launch AC', 'error');
        }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

// ── Submit Race Result ─────────────────────────────────────────────────────
async function submitResult(e) {
    e.preventDefault();
    const pos     = parseInt(document.getElementById('finish-position').value);
    const lapTime = document.getElementById('best-lap').value;
    const fl      = document.getElementById('fastest-lap').checked;

    try {
        const r = await fetch('/api/finish-race', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ position: pos, lap_time: lapTime, fastest_lap: fl }),
        });
        const d = await r.json();

        if (d.status === 'season_complete') {
            await handleSeasonComplete(d);
        } else if (d.status === 'success') {
            const pts = d.result ? d.result.points : 0;
            showToast(fmtPos(pos) + ' — +' + pts + ' pts' + (fl ? ' (+FL)' : '') + '!');
            await Promise.all([loadCareer(), loadStandings(), loadCalendar()]);
            refresh();
            showView('standings');
        } else {
            showToast('Error submitting result', 'error');
        }
    } catch (err) { showToast('Error: ' + err.message, 'error'); }
}

// ── Season Complete ────────────────────────────────────────────────────────
async function handleSeasonComplete(data) {
    await Promise.all([loadCareer(), loadStandings(), loadCalendar()]);
    refresh();

    const posEl = document.getElementById('final-pos-text');
    if (posEl) {
        posEl.textContent =
            'You finished P' + data.position +
            ' with ' + data.total_points + ' points.';
    }
    renderContracts(data.contracts || []);
    showView('contracts');
    showToast('Season over! Choose your next contract.');
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
    el.innerHTML = contracts.map(c =>
        '<div class="contract-card">' +
        '<div class="contract-team">'     + c.team_name   + '</div>' +
        '<div class="contract-tier-lbl">' + (c.tier_level || '') + ' · ' + (c.tier_name || '') + '</div>' +
        '<div class="contract-car-lbl">'  + fmtCar(c.car) + '</div>' +
        '<button class="btn btn-race" onclick="acceptContract(\'' + c.id + '\')">Sign Contract</button>' +
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
            showToast('Welcome to ' + d.new_team + '! 🏎');
            await Promise.all([loadCareer(), loadConfig()]);
            await Promise.all([loadStandings(), loadCalendar()]);
            refresh();
            showView('standings');
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
    const aiLevel = parseFloat(document.getElementById('s-ai-level').value);
    const aiVar   = parseFloat(document.getElementById('s-ai-var').value);
    const races   = parseInt(document.getElementById('s-races').value);
    const acPath  = (document.getElementById('s-ac-path').value || '').trim();
    const hint    = document.getElementById('s-ac-hint');

    // Deep-clone and patch
    const updated = JSON.parse(JSON.stringify(config));
    updated.difficulty.base_ai_level = aiLevel;
    updated.difficulty.ai_variance   = aiVar;
    updated.seasons.races_per_tier   = races;
    if (acPath) updated.paths.ac_install = acPath;

    try {
        const r = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated),
        });
        const d = await r.json();
        if (d.status === 'success') {
            config = updated;
            showToast('Instellingen opgeslagen!');
            showView('standings');
        } else {
            showToast('Opslaan mislukt', 'error');
        }
    } catch (e) { showToast('Fout: ' + e.message, 'error'); }
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
