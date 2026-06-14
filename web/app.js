/* VagoScore v3 — app.js */
const $ = id => document.getElementById(id);
const fmtNum = (n, cur='') => new Intl.NumberFormat('es-CO').format(Math.round(n)) + (cur ? ' ' + cur : '');

let isNational = true, lastPred = null, leaguesData = [];
const LOAD_MSGS = ['Conectando con Sofascore…','Leyendo forma reciente…','Consultando Transfermarkt…','Calculando ELO…','Analizando H2H…','Midiendo química…','Fusionando señales…','Calculando probabilidades…'];

/* ═══ NAV ═══ */
document.querySelectorAll('.nl').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nl').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    $('view-' + btn.dataset.view).classList.add('active');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});
function goView(name) {
  document.querySelectorAll('.nl').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  $('view-' + name).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
$('hero-cta').addEventListener('click', () => goView('fixtures'));

/* ═══ STATUS + INIT ═══ */
async function init() {
  $('hero-date').textContent = new Date().toLocaleDateString('es-CO', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
  try {
    const s = await fetch('/api/status').then(r => r.json());
    if (s.apifootball_connected) {
      $('sdot').className = 'sdot on'; $('stext').textContent = 'API conectada';
      await loadLeagues();
      loadLive();
    } else {
      $('sdot').className = 'sdot off'; $('stext').textContent = 'sin API-Football';
      $('hs-leagues').textContent = '—';
      $('fixtures-home').innerHTML = '<div style="padding:2rem;color:#666;font-family:var(--ff-mono);font-size:0.8rem">Configura APIFOOTBALL_KEY en Render para ver partidos en tiempo real.</div>';
    }
  } catch { $('sdot').className = 'sdot off'; $('stext').textContent = 'sin conexión'; }
}
init();

/* ═══ LEAGUES + FIXTURES ═══ */
let leaguesGrouped = null;

async function loadLeagues() {
  // Carga agrupada jerárquica: mundiales → continentes → países
  const g = await fetch('/api/leagues/grouped').then(r => r.json());
  leaguesGrouped = g;
  // Aplanar para índice rápido por id
  leaguesData = [];
  const buildOptions = () => {
    let html = '<option value="">Elige competición…</option>';
    // 1. Mundiales y continentales primero
    if (g.world && g.world.length) {
      html += '<optgroup label="🌍 MUNDIALES Y CONTINENTALES">';
      g.world.forEach(l => { const i = leaguesData.push(l) - 1; html += `<option value="${i}">${l.name}</option>`; });
      html += '</optgroup>';
    }
    // 2. Por continente → país
    if (g.continents) {
      for (const [cont, countries] of Object.entries(g.continents)) {
        html += `<optgroup label="── ${cont.toUpperCase()} ──">`;
        for (const [country, ls] of Object.entries(countries)) {
          ls.forEach(l => { const i = leaguesData.push(l) - 1; html += `<option value="${i}">${country} · ${l.name}</option>`; });
        }
        html += '</optgroup>';
      }
    }
    return html;
  };
  const opts = buildOptions();
  $('hs-leagues').textContent = leaguesData.length;
  $('league-sel').innerHTML = opts;
  $('fixture-league-sel').innerHTML = opts;
  if (leaguesData.length) loadFixtures(0, 'home');
}

async function loadFixtures(idx, target) {
  const l = leaguesData[idx];
  if (!l) return;
  const data = await fetch(`/api/fixtures?league=${l.id}&season=${l.season}&days=30`).then(r => r.json());
  const fx = (data.fixtures || []).map(f => ({ ...f, _season: l.season, _league: l.id }));
  if (target === 'home') renderFixturesHome(fx);
  else renderFixturesList(fx);
}

$('league-sel').addEventListener('change', e => { if (e.target.value !== '') loadFixtures(+e.target.value, 'home'); });
$('fixture-league-sel').addEventListener('change', e => { if (e.target.value !== '') loadFixtures(+e.target.value, 'list'); });

function renderFixturesHome(fx) {
  const el = $('fixtures-home');
  if (!fx.length) { el.innerHTML = '<div style="padding:2rem;color:#666;font-family:var(--ff-mono);font-size:0.8rem">Sin partidos próximos.</div>'; return; }
  el.innerHTML = fx.slice(0, 12).map(f => {
    const d = new Date(f.date);
    const ds = d.toLocaleDateString('es-CO', { weekday:'short', day:'numeric', month:'short' });
    const ts = d.toLocaleTimeString('es-CO', { hour:'2-digit', minute:'2-digit' });
    return `<div class="fx-card" onclick="openMatch(${f.fixture_id||0}, '${esc(f.home.name)}', '${esc(f.away.name)}', ${f.home.id||0}, ${f.away.id||0}, ${f._season||2024})">
      <div class="fx-round">${f.round || '—'}</div>
      <div class="fx-matchup">
        <div class="fx-team">${f.home.logo ? `<img src="${f.home.logo}" alt="">` : ''}<span class="fx-team-name">${f.home.name}</span></div>
        <div class="fx-team">${f.away.logo ? `<img src="${f.away.logo}" alt="">` : ''}<span class="fx-team-name">${f.away.name}</span></div>
      </div>
      <div class="fx-foot"><span>${ds} · ${ts}</span><span class="fx-cta">Ver partido →</span></div>
    </div>`;
  }).join('');
}

function renderFixturesList(fx) {
  const el = $('fixtures-list');
  if (!fx.length) { el.innerHTML = '<div style="padding:2rem;color:#666;font-family:var(--ff-mono);font-size:0.8rem">Sin partidos próximos en esta competición.</div>'; return; }
  el.innerHTML = fx.map(f => {
    const d = new Date(f.date);
    const ds = d.toLocaleDateString('es-CO', { day:'numeric', month:'short' });
    const ts = d.toLocaleTimeString('es-CO', { hour:'2-digit', minute:'2-digit' });
    return `<div class="fxl-item" onclick="openMatch(${f.fixture_id||0}, '${esc(f.home.name)}', '${esc(f.away.name)}', ${f.home.id||0}, ${f.away.id||0}, ${f._season||2024})">
      <div class="fxl-home">${f.home.logo ? `<img class="fxl-img" src="${f.home.logo}" alt="">` : ''}<span class="fxl-name">${f.home.name}</span></div>
      <div class="fxl-center"><div class="fxl-date">${ds}</div><div class="fxl-time">${ts}</div></div>
      <div class="fxl-away"><span class="fxl-name">${f.away.name}</span>${f.away.logo ? `<img class="fxl-img" src="${f.away.logo}" alt="">` : ''}</div>
      <div class="fxl-action">Ver partido →</div>
    </div>`;
  }).join('');
}

function selectMatch(home, away) {
  $('ta').value = home; $('tb').value = away;
  goView('analyze');
}
function esc(s) { return (s||'').replace(/'/g, "\\'"); }

/* ═══ LIVE ═══ */
async function loadLive() {
  try {
    const d = await fetch('/api/live').then(r => r.json());
    const live = d.live || [];
    $('hs-live').textContent = live.length;
    if (live.length) {
      $('live-badge').hidden = false;
      $('live-strip').hidden = false;
      $('ls-scroll').innerHTML = live.map(m => `<div class="ls-match" onclick="openLiveMatch(${m.fixture_id||0})" style="cursor:pointer"><span>${m.home}</span><span class="ls-score">${m.score}</span><span>${m.away}</span><span class="ls-min">${m.elapsed}'</span></div>`).join('');
    }
  } catch {}
}

/* ═══ ANALYZE ═══ */
$('seg').addEventListener('click', e => {
  const btn = e.target.closest('.seg-opt');
  if (!btn) return;
  document.querySelectorAll('.seg-opt').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  isNational = btn.dataset.nat === 'true';
});

let ldTimer = null;
$('run-btn').addEventListener('click', runAnalysis);

async function runAnalysis() {
  const a = $('ta').value.trim(), b = $('tb').value.trim();
  if (!a || !b) { alert('Escribe ambos equipos.'); return; }
  $('results-zone').hidden = true;
  $('loading').hidden = false;
  let i = 0; $('ld-msg').textContent = LOAD_MSGS[0];
  ldTimer = setInterval(() => { i=(i+1)%LOAD_MSGS.length; $('ld-msg').textContent = LOAD_MSGS[i]; }, 2000);
  try {
    const data = await fetch('/api/predict', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ team_a:a, team_b:b, is_national:isNational })
    }).then(r => r.json());
    clearInterval(ldTimer);
    $('loading').hidden = true;
    if (data.error) throw new Error(data.error);
    lastPred = data;
    renderResults(data);
    $('results-zone').hidden = false;
    // Cargar alineación probable dentro del análisis
    loadAnalysisLineup(data);
  } catch(err) {
    clearInterval(ldTimer);
    $('loading').hidden = true;
    alert('Error: ' + err.message);
  }
}

function renderResults(data) {
  const pred = data.prediction, p = pred.prediction, s = pred.scores;
  const a = data.team_a, b = data.team_b;

  // Radar SVG
  const factors = [
    [s[a].sofascore, s[b].sofascore, 'FORMA'],
    [s[a].elo,       s[b].elo,       'ELO'],
    [s[a].chemistry, s[b].chemistry, 'QUÍMICA'],
    [s[a].h2h,       s[b].h2h,       'H2H'],
    [s[a].market,    s[b].market,    'VALOR'],
  ];
  const radarHTML = buildRadar(factors, a, b);

  // Factores
  const fNames = { sofascore:'Forma reciente', elo:'Ranking ELO', chemistry:'Química', h2h:'Head-to-Head', market:'Valor mercado' };
  const fwKey = { sofascore:'sofascore_form', elo:'elo_rating', chemistry:'chemistry', h2h:'h2h', market:'market_value' };
  const fWeights = pred.weights_used;
  const factorsHTML = ['sofascore','elo','chemistry','h2h','market'].map(k => {
    const va = s[a][k], vb = s[b][k];
    const w = Math.round((fWeights[fwKey[k]] || 0) * 100);
    return `<div class="factor"><div class="factor-head"><span class="factor-name">${fNames[k]}</span><span class="factor-w">peso ${w}%</span></div>
      <div class="factor-bars"><div class="fbar l"><div class="fbar-fill" style="width:${va}%"></div><span class="fbar-n">${va.toFixed(0)}</span></div>
      <div class="fbar r"><div class="fbar-fill" style="width:${vb}%"></div><span class="fbar-n">${vb.toFixed(0)}</span></div></div></div>`;
  }).join('');

  const raw = pred.raw || {};
  const kpA = raw.key_player_a, kpB = raw.key_player_b;
  const kpHTML = (kpA || kpB) ? `
    <div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">04</span><h2 class="sh-title">JUGADORES CLAVE</h2><div class="sh-line"></div></div>
    <div class="kp-strip">
      ${kpA ? `<div class="kp-card"><div class="kp-team">${a}</div><div class="kp-name">${kpA.name||'—'}</div><div class="kp-rat">${(kpA.avg_rating||0).toFixed(2)} ★ · ${kpA.position||'?'}</div></div>` : '<div class="kp-card"></div>'}
      ${kpB ? `<div class="kp-card"><div class="kp-team">${b}</div><div class="kp-name">${kpB.name||'—'}</div><div class="kp-rat">${(kpB.avg_rating||0).toFixed(2)} ★ · ${kpB.position||'?'}</div></div>` : '<div class="kp-card"></div>'}
    </div>` : '';

  $('results-zone').innerHTML = `
    <div class="res-hero">
      <div class="res-team"><div class="res-team-name">${a}</div><div class="res-score a">${s[a].total.toFixed(1)}</div><div class="res-tag">vagoscore</div></div>
      <div class="res-center"><span class="res-vs-label">marcador probable</span><span class="res-predicted">${p.most_likely_score}</span><span class="res-conf">confianza ${p.confidence}%</span></div>
      <div class="res-team"><div class="res-team-name">${b}</div><div class="res-score b">${s[b].total.toFixed(1)}</div><div class="res-tag">vagoscore</div></div>
    </div>
    <div class="prob-bar">
      <div class="pb-seg pb-a" style="flex-basis:${p.p_win_a}%">${p.p_win_a}%</div>
      <div class="pb-seg pb-d" style="flex-basis:${p.p_draw}%">${p.p_draw}%</div>
      <div class="pb-seg pb-b" style="flex-basis:${p.p_win_b}%">${p.p_win_b}%</div>
    </div>
    <div class="prob-legend">
      <span><i style="background:var(--lime)"></i>Gana ${a} ${p.p_win_a}%</span>
      <span><i style="background:#444"></i>Empate ${p.p_draw}%</span>
      <span><i style="background:var(--white);opacity:0.3"></i>Gana ${b} ${p.p_win_b}%</span>
    </div>
    <div class="xg-strip">
      <div class="xg-block"><div class="xg-num">${p.xg_a}</div><div class="xg-lbl">xG ${a}</div></div>
      <div class="xg-block"><div class="xg-num">${p.xg_b}</div><div class="xg-lbl">xG ${b}</div></div>
    </div>
    <div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">02</span><h2 class="sh-title">DATOS DEL PARTIDO</h2><div class="sh-line"></div></div>
    ${buildDetailPanels(pred, a, b)}
    <div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">03</span><h2 class="sh-title">ALINEACIÓN PROBABLE</h2><div class="sh-line"></div></div>
    <div id="analysis-lineup-zone"><div class="ai-loading">Cargando alineaciones probables…</div></div>
    <div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">04</span><h2 class="sh-title">RADAR DE SEÑALES</h2><div class="sh-line"></div></div>
    <div class="radar-wrap">${radarHTML}</div>
    <div class="section-header" style="padding:1rem 2rem"><span class="sh-num">05</span><h2 class="sh-title">DESGLOSE</h2><div class="sh-line"></div></div>
    <div class="factors-grid" style="margin:0 2rem 2rem">${factorsHTML}</div>
    ${kpHTML}
    <div id="ai-zone"><div class="ai-panel" style="text-align:center"><div class="ai-head" style="justify-content:center"><span class="ai-badge">⬡ IA</span><span class="ai-title">Análisis experto con IA</span></div><p style="color:var(--muted);font-size:0.9rem;margin-bottom:1rem">Deja que la IA interprete todo el análisis: lectura táctica, factores clave y dónde está el valor.</p><button class="ai-cta-btn" id="ai-trigger" onclick="requestAIAnalysis()">Generar análisis IA ⬡</button></div></div>
    <div class="cta-banca">
      <p>¿Hay valor en este partido? Lleva estas probabilidades al módulo de Banca y deja que Kelly calcule cuánto apostar.</p>
      <button onclick="sendToKelly(${p.p_win_a},${p.p_draw},${p.p_win_b},'${esc(a)}','${esc(b)}')">IR A BANCA →</button>
    </div>`;
}

/* ═══ PANELES DE DATOS CRUDOS (desplegables) ═══ */
function buildDetailPanels(pred, a, b) {
  const raw = pred.raw || {};
  const s = pred.scores;
  let html = '';

  // Panel 1: ELO numérico
  const eloA = raw.elo_a, eloB = raw.elo_b;
  const eloEst = raw.elo_is_estimate;
  if (eloA != null || eloB != null) {
    const diff = (eloA && eloB) ? Math.abs(eloA - eloB) : null;
    const fav = (eloA && eloB) ? (eloA > eloB ? a : b) : '—';
    html += `<div class="detail-panel open"><div class="dp-header" onclick="togglePanel(this)">
      <span class="dp-title"><span class="dp-icon">▦</span>Ranking ELO${eloEst ? ' <span style="color:#666;font-size:0.9em">(derivado)</span>' : ''}</span><span class="dp-chevron">▾</span></div>
      <div class="dp-body"><div class="dp-inner"><div class="elo-compare">
        <div class="elo-side"><div class="elo-num a">${eloA ?? '—'}</div><div class="elo-team">${a}</div></div>
        <div class="elo-diff"><strong>${diff ?? '—'}</strong>de diferencia<br><span style="color:var(--lime)">${fav} favorito</span></div>
        <div class="elo-side"><div class="elo-num b">${eloB ?? '—'}</div><div class="elo-team">${b}</div></div>
      </div><div class="elo-src">${eloEst ? 'Derivado de forma reciente real (API-Football)' : 'Fuente: eloratings.net / clubelo.com'}</div></div></div></div>`;
  }

  // Panel 2: Últimos partidos (forma) — AMBOS equipos con detalle
  const formA = raw.form_a, formB = raw.form_b;
  const matchesA = raw.matches_a, matchesB = raw.matches_b;
  if (formA || formB || matchesA || matchesB) {
    const dots = (form) => (form || []).slice(0,10).map(r => `<span class="fdot ${r}">${r}</span>`).join('');
    const matchList = (matches) => !matches || !matches.length ? '<p style="color:#555;font-family:var(--ff-mono);font-size:0.65rem;padding:0.5rem 0">Sin datos detallados</p>' :
      matches.slice(0,10).map(m => `
        <div class="rm-item">
          <span class="rm-result ${m.result}">${m.result}</span>
          <span class="rm-loc">${m.is_home ? 'L' : 'V'}</span>
          <span class="rm-opp">${m.opponent_logo ? `<img src="${m.opponent_logo}" class="rm-logo">` : ''}${m.opponent}</span>
          <span class="rm-score">${m.score}</span>
          <span class="rm-date">${m.date ? new Date(m.date).toLocaleDateString('es-CO',{day:'numeric',month:'short'}) : ''}</span>
        </div>`).join('');

    html += `<div class="detail-panel open"><div class="dp-header" onclick="togglePanel(this)">
      <span class="dp-title"><span class="dp-icon">◷</span>Últimos partidos · ambos equipos</span><span class="dp-chevron">▾</span></div>
      <div class="dp-body"><div class="dp-inner">
        <div class="form-row"><span class="form-team-lbl">${a}</span><div class="form-dots">${dots(formA)}</div></div>
        <div class="form-row"><span class="form-team-lbl">${b}</span><div class="form-dots">${dots(formB)}</div></div>
        <div class="rm-grid">
          <div class="rm-col"><div class="rm-col-head">${a}</div>${matchList(matchesA)}</div>
          <div class="rm-col"><div class="rm-col-head">${b}</div>${matchList(matchesB)}</div>
        </div>
        <p style="font-family:var(--ff-mono);font-size:0.6rem;color:#555;margin-top:0.8rem">L = local · V = visitante · del más reciente al más antiguo</p>
      </div></div></div>`;
  }

  // Panel 3: Valor de mercado de la plantilla
  const mvA = raw.market_value_a, mvB = raw.market_value_b;
  const mvEst = raw.market_is_estimate;
  if (mvA != null || mvB != null) {
    html += `<div class="detail-panel open"><div class="dp-header" onclick="togglePanel(this)">
      <span class="dp-title"><span class="dp-icon">$</span>Valor de plantilla${mvEst ? ' <span style="color:#666;font-size:0.9em">(estimado)</span>' : ''}</span><span class="dp-chevron">▾</span></div>
      <div class="dp-body"><div class="dp-inner"><div class="elo-compare">
        <div class="elo-side"><div class="elo-num a" style="font-size:2rem">${fmtMV(mvA)}</div><div class="elo-team">${a}</div></div>
        <div class="elo-diff"><span style="color:var(--lime)">${mvEst ? 'rating + ELO' : 'Transfermarkt'}</span></div>
        <div class="elo-side"><div class="elo-num b" style="font-size:2rem">${fmtMV(mvB)}</div><div class="elo-team">${b}</div></div>
      </div>${mvEst ? '<div class="elo-src">Estimación derivada de la calidad medible del plantel (API-Football no expone el valor exacto en €)</div>' : ''}</div></div></div>`;
  }

  // Panel 4: Head to head
  const h2h = raw.h2h_summary;
  if (h2h) {
    html += `<div class="detail-panel open"><div class="dp-header" onclick="togglePanel(this)">
      <span class="dp-title"><span class="dp-icon">⚔</span>Head to Head</span><span class="dp-chevron">▾</span></div>
      <div class="dp-body"><div class="dp-inner"><p style="font-family:var(--ff-mono);font-size:0.8rem;color:var(--muted);line-height:1.7">${typeof h2h === 'string' ? h2h : JSON.stringify(h2h)}</p></div></div></div>`;
  }

  if (!html) html = '<p style="padding:0 2rem 2rem;color:#555;font-family:var(--ff-mono);font-size:0.75rem">Los datos crudos detallados se muestran cuando el análisis los provee.</p>';
  return html;
}

function fmtMV(v) {
  if (v == null) return '—';
  if (v >= 1e9) return '€' + (v/1e9).toFixed(2) + 'B';
  if (v >= 1e6) return '€' + (v/1e6).toFixed(0) + 'M';
  if (v >= 1e3) return '€' + (v/1e3).toFixed(0) + 'K';
  return '€' + v;
}

/* ═══ RADAR SVG ═══ */
function buildRadar(factors, nameA, nameB) {
  const N = factors.length, cx = 200, cy = 200, R = 150;
  const angles = factors.map((_, i) => (i / N) * Math.PI * 2 - Math.PI / 2);
  function pt(val, r = R) { return angles.map((a, i) => [cx + r * Math.cos(angles[i]) * (val[i]/100), cy + r * Math.sin(angles[i]) * (val[i]/100)]); }
  const valsA = factors.map(f => f[0]), valsB = factors.map(f => f[1]);
  const ptsA = pt(valsA), ptsB = pt(valsB);
  const polyA = ptsA.map(p => p.join(',')).join(' ');
  const polyB = ptsB.map(p => p.join(',')).join(' ');
  // Grid circles
  let gridLines = '';
  [0.25,0.5,0.75,1].forEach(r => {
    const pts = angles.map(a => [cx + R*r*Math.cos(a), cy + R*r*Math.sin(a)]);
    gridLines += `<polygon points="${pts.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#2a2a2a" stroke-width="1"/>`;
  });
  // Axis lines
  let axisLines = angles.map(a => `<line x1="${cx}" y1="${cy}" x2="${cx+R*Math.cos(a)}" y2="${cy+R*Math.sin(a)}" stroke="#2a2a2a" stroke-width="1"/>`).join('');
  // Labels
  let labels = factors.map((f, i) => {
    const lx = cx + (R + 22) * Math.cos(angles[i]), ly = cy + (R + 22) * Math.sin(angles[i]);
    return `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" fill="#666" font-family="Space Mono, monospace" font-size="9" letter-spacing="1">${f[2]}</text>`;
  }).join('');
  return `<svg class="radar-svg" viewBox="0 0 400 400" width="340" height="340">
    ${gridLines}${axisLines}
    <polygon points="${polyA}" fill="rgba(200,241,53,0.15)" stroke="#c8f135" stroke-width="2"/>
    <polygon points="${polyB}" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.4)" stroke-width="2"/>
    ${ptsA.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="#c8f135"/>`).join('')}
    ${ptsB.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="rgba(255,255,255,0.5)"/>`).join('')}
    ${labels}
    <text x="30" y="390" fill="#c8f135" font-family="Space Mono,monospace" font-size="9">■ ${nameA}</text>
    <text x="200" y="390" fill="#888" font-family="Space Mono,monospace" font-size="9">■ ${nameB}</text>
  </svg>`;
}

/* ═══ KELLY ═══ */
function sendToKelly(ph, pd, pa, ta, tb) {
  $('k-ph').value = ph; $('k-pd').value = pd; $('k-pa').value = pa;
  $('kl-a').textContent = ta; $('kl-b').textContent = tb;
  $('ko-a').textContent = ta; $('ko-b').textContent = tb;
  $('hint-autofill').hidden = false;
  goView('bankroll');
}

$('k-btn').addEventListener('click', async () => {
  const payload = {
    p_home: +$('k-ph').value, p_draw: +$('k-pd').value, p_away: +$('k-pa').value,
    odds_home: +$('k-oh').value, odds_draw: +$('k-od').value, odds_away: +$('k-oa').value,
    bankroll: +$('k-bank').value, kelly_multiplier: +$('k-mult').value,
    team_a: $('kl-a').textContent, team_b: $('kl-b').textContent,
    currency: $('k-cur').value,
  };
  try {
    const d = await fetch('/api/kelly', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) }).then(r => r.json());
    if (d.error) throw new Error(d.error);
    renderKelly(d, payload.currency);
    $('k-results').hidden = false;
  } catch(e) { alert('Error: ' + e.message); }
});

function renderKelly(d, cur) {
  const best = d.best_bet;
  let bestHTML = '';
  if (best) {
    bestHTML = `<div class="best-bet">
      <div class="bb-tag">Apuesta de valor recomendada</div>
      <div class="bb-outcome">${best.outcome_label}</div>
      <div class="bb-nums">
        <div class="bb-num"><div class="bb-val hl">${fmtNum(best.stake)}</div><div class="bb-lbl">apostar (${cur})</div></div>
        <div class="bb-num"><div class="bb-val">+${best.edge_pct}%</div><div class="bb-lbl">edge</div></div>
        <div class="bb-num"><div class="bb-val">${best.decimal_odds}</div><div class="bb-lbl">cuota</div></div>
        <div class="bb-num"><div class="bb-val">${fmtNum(best.potential_profit)}</div><div class="bb-lbl">ganancia potencial</div></div>
      </div></div>`;
  }
  let simHTML = '';
  if (d.simulation) {
    const s = d.simulation;
    simHTML = `<div class="sim-block">
      <div class="sim-tag">Monte Carlo · ${s.n_bets} apuestas repetidas · 400 escenarios</div>
      <div class="sim-nums">
        <div class="sim-n"><div class="sim-nv">${fmtNum(s.median_final)}</div><div class="sim-nl">mediana final</div></div>
        <div class="sim-n"><div class="sim-nv">${fmtNum(s.p10)}</div><div class="sim-nl">malo (p10)</div></div>
        <div class="sim-n"><div class="sim-nv">${fmtNum(s.p90)}</div><div class="sim-nl">bueno (p90)</div></div>
        <div class="sim-n"><div class="sim-nv ${s.ruin_probability_pct>5?'warn':''}">${s.ruin_probability_pct}%</div><div class="sim-nl">prob. ruina</div></div>
      </div></div>`;
  }
  const betsHTML = d.recommendations.map(r =>
    `<div class="abt ${r.edge_pct>0?'has-v':''}">
      <span class="abt-name">${r.outcome_label}</span>
      <span><span class="abt-lbl">edge</span><span class="abt-v ${r.edge_pct>0?'pos':'neg'}">${r.edge_pct>0?'+':''}${r.edge_pct}%</span></span>
      <span><span class="abt-lbl">modelo / casa</span>${Math.round(r.model_prob*100)}% / ${Math.round(r.implied_prob*100)}%</span>
      <span><span class="abt-lbl">apostar</span>${r.stake>0?fmtNum(r.stake):'—'}</span>
    </div>`).join('');
  $('k-results').innerHTML = `
    <div class="k-verdict ${d.has_value?'v-yes':'v-no'}">
      <h3>${d.has_value?'Hay valor':'Sin valor — mejor no apostar'}</h3>
      <p>${d.verdict}</p></div>
    ${bestHTML}${simHTML}
    <div style="padding:1rem 2rem 0.5rem;font-family:var(--ff-mono);font-size:0.62rem;letter-spacing:2px;color:var(--muted)">TODOS LOS RESULTADOS</div>
    <div class="all-bets">${betsHTML}</div>
    ${d.fair_probabilities?.bookmaker_margin_pct?`<p style="text-align:center;color:var(--muted);font-family:var(--ff-mono);font-size:0.7rem;padding:1rem 2rem 2rem">Margen de la casa: ${d.fair_probabilities.bookmaker_margin_pct}% — eso es lo que debes superar.</p>`:''}`;
}

/* ═══ BACKTEST ═══ */
$('bt-btn').addEventListener('click', async () => {
  let preds;
  try { preds = JSON.parse($('bt-in').value); } catch { alert('JSON inválido.'); return; }
  try {
    const d = await fetch('/api/backtest', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({predictions:preds}) }).then(r=>r.json());
    if (d.error) throw new Error(d.error);
    renderBT(d); $('bt-results').hidden = false;
  } catch(e) { alert('Error: ' + e.message); }
});

function renderBT(d) {
  const aC = d.accuracy_pct>=50?'good':'bad', rC = d.roi_pct>0?'good':'bad';
  $('bt-results').innerHTML = `
    <div class="bt-metrics">
      <div class="bt-m"><div class="bt-mv ${aC}">${d.accuracy_pct}%</div><div class="bt-ml">acierto</div></div>
      <div class="bt-m"><div class="bt-mv">${d.brier_score}</div><div class="bt-ml">brier score</div></div>
      <div class="bt-m"><div class="bt-mv ${rC}">${d.roi_pct>0?'+':''}${d.roi_pct}%</div><div class="bt-ml">ROI</div></div>
      <div class="bt-m"><div class="bt-mv">${d.value_bet_hit_rate}%</div><div class="bt-ml">hit rate valor</div></div>
    </div>
    <div class="bt-interp">${d.interpretation}</div>
    <div style="padding:1rem 2rem 0.5rem;font-family:var(--ff-mono);font-size:0.62rem;letter-spacing:2px;color:var(--muted)">DETALLE POR PARTIDO</div>
    <div class="bt-rows">${d.details.map(m=>`
      <div class="bt-row">
        <span>${m.match||''}</span>
        <span><span class="bt-lbl2">predijo</span>${m.predicted}</span>
        <span><span class="bt-lbl2">real</span>${m.actual}</span>
        <span class="${m.correct?'bt-hit':'bt-miss'}">${m.correct?'✓':'✗'}</span>
      </div>`).join('')}
    </div>`;
}

/* ═══════════════ v4: DETALLE DE PARTIDO + CANCHA ═══════════════ */

let currentMatch = null;

$('match-back').addEventListener('click', () => goView('fixtures'));

async function openMatch(fixtureId, home, away, homeId, awayId, season) {
  currentMatch = { fixtureId, home, away, homeId, awayId, season };
  $('match-title').textContent = `${home} vs ${away}`.toUpperCase();
  goView('match');
  const zone = $('match-detail-zone');
  zone.innerHTML = '<div class="loading"><div class="ld-bars"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><p>Cargando alineaciones y datos…</p></div>';

  // Cargar alineaciones: confirmada si existe, probable si no
  let lineups = null;
  try {
    const url = `/api/lineup/detailed/${fixtureId}?season=${season}&home_id=${homeId}&away_id=${awayId}`;
    lineups = await fetch(url).then(r => r.json());
  } catch {}

  let html = '';

  // Botón para analizar este partido
  html += `<div style="padding:1.5rem 2rem;display:flex;gap:1rem;flex-wrap:wrap;align-items:center">
    <button class="btn-run" onclick="selectMatch('${esc(home)}','${esc(away)}')">ANALIZAR ESTE PARTIDO ↗</button>
    <span style="font-family:var(--ff-mono);font-size:0.7rem;color:var(--muted)">Corre el modelo de 5 señales sobre este enfrentamiento</span>
  </div>`;

  // Badge de estado de la alineación
  const isProbable = lineups && lineups.status === 'probable';
  const isConfirmed = lineups && lineups.status === 'confirmed';
  if (isProbable || isConfirmed) {
    html += `<div class="lineup-status ${isConfirmed ? 'confirmed' : 'probable'}">
      ${isConfirmed ? '✓ ALINEACIÓN CONFIRMADA' : '◷ ALINEACIÓN PROBABLE'}
      <span>${isConfirmed ? 'Titulares oficiales del partido' : 'Estimada según los jugadores con más minutos · se actualizará cuando se confirme'}</span>
    </div>`;
  }

  // Cancha con alineaciones
  if (lineups && (lineups.home || lineups.away)) {
    html += renderPitchSection(lineups, home, away);
  } else {
    html += `<div style="margin:0 2rem 2rem;padding:2rem;background:var(--gray-3);border:1px solid var(--border);text-align:center">
      <p style="font-family:var(--ff-mono);font-size:0.8rem;color:var(--muted);line-height:1.7">No hay datos de alineación disponibles para este partido todavía.<br>Puedes analizar el enfrentamiento con el modelo.</p>
    </div>`;
  }

  zone.innerHTML = html;
  // Activar primera pestaña de cancha
  const firstTab = zone.querySelector('.pitch-tab');
  if (firstTab) firstTab.click();
}

function renderPitchSection(lineups, home, away) {
  const hasHome = lineups.home && lineups.home.starters && lineups.home.starters.length;
  const hasAway = lineups.away && lineups.away.starters && lineups.away.starters.length;
  let html = `<div class="pitch-wrap"><div class="pitch-teams-tab">`;
  if (hasHome) html += `<button class="pitch-tab" onclick="showPitch('home')">${home}</button>`;
  if (hasAway) html += `<button class="pitch-tab" onclick="showPitch('away')">${away}</button>`;
  html += `</div><div id="pitch-container"></div></div>`;
  window._lineups = lineups;
  return html;
}

function showPitch(side) {
  const tabs = document.querySelectorAll('.pitch-tab');
  tabs.forEach(t => t.classList.remove('active'));
  const lineup = window._lineups[side];
  if (!lineup) return;
  const idx = side === 'home' ? 0 : (tabs.length > 1 ? 1 : 0);
  if (tabs[idx]) tabs[idx].classList.add('active');

  const cont = $('pitch-container');
  const starters = lineup.starters || [];

  // Agrupar jugadores por fila (row del grid) para centrar cada línea
  const rows = {};
  starters.forEach(p => {
    if (!p.grid) return;
    const row = p.grid.split(':')[0];
    (rows[row] = rows[row] || []).push(p);
  });
  const rowKeys = Object.keys(rows).map(Number).sort((x, y) => x - y);
  const maxRow = Math.max(...rowKeys, 1);

  let dots = '';
  rowKeys.forEach(row => {
    const playersInRow = rows[row];
    const n = playersInRow.length;
    // Ordenar por columna del grid para mantener orden visual
    playersInRow.sort((a, b) => (+a.grid.split(':')[1]) - (+b.grid.split(':')[1]));
    playersInRow.forEach((p, i) => {
      // Y: portero abajo (88%), delanteros arriba (12%)
      const y = 88 - ((row - 1) / Math.max(maxRow - 1, 1)) * 74;
      // X: centrar la línea — n jugadores distribuidos simétricamente
      const x = ((i + 1) / (n + 1)) * 100;
      const rating = p.rating ? parseFloat(p.rating) : null;
      const rClass = rating ? (rating >= 7 ? 'high' : rating >= 6.5 ? 'mid' : 'low') : 'mid';
      const shortName = (p.name || '').split(' ').slice(-1)[0];
      dots += `<div class="player-dot" style="left:${x}%;top:${y}%" onclick="showPlayer(${p.id||0}, '${esc(p.name||'')}', '${p.pos||''}', ${p.number||0}, ${currentMatch.season})">
        <div class="pd-circle">${p.number || '?'}</div>
        <div class="pd-name">${shortName}</div>
        ${rating ? `<div class="pd-rating ${rClass}">${rating.toFixed(1)}</div>` : ''}
      </div>`;
    });
  });

  const probableTag = lineup.is_probable
    ? '<span style="color:#ffb432">◷ probable</span>'
    : '<span style="color:var(--lime)">✓ confirmada</span>';

  cont.innerHTML = `
    <div class="pitch">
      <div class="pitch-box top"></div>
      <div class="pitch-box bot"></div>
      <div class="pitch-spot"></div>
      ${dots}
    </div>
    <div class="pitch-formation">Formación ${lineup.formation || '—'} · ${probableTag}</div>
    ${lineup.coach ? `<div class="pitch-coach">DT: ${lineup.coach}</div>` : ''}`;
}

async function showPlayer(id, name, pos, number, season) {
  if (!id) return;
  // popup
  let pop = $('player-pop');
  if (!pop) {
    pop = document.createElement('div');
    pop.id = 'player-pop'; pop.className = 'player-pop';
    document.body.appendChild(pop);
  }
  pop.className = 'player-pop show';
  pop.innerHTML = `<div class="pp-card"><button class="pp-close" onclick="document.getElementById('player-pop').className='player-pop'">×</button>
    <div class="pp-name">${name}</div><div class="pp-meta">Cargando datos…</div></div>`;

  try {
    const d = await fetch(`/api/player/${id}?season=${season}`).then(r => r.json());
    const rating = d.rating ? parseFloat(d.rating).toFixed(2) : '—';
    pop.querySelector('.pp-card').innerHTML = `
      <button class="pp-close" onclick="document.getElementById('player-pop').className='player-pop'">×</button>
      ${d.photo ? `<img class="pp-photo" src="${d.photo}" alt="">` : ''}
      <div class="pp-name">${d.name || name}</div>
      <div class="pp-meta">${d.position || pos || '—'} · ${d.age || '?'} años · ${d.nationality || ''}</div>
      <div class="pp-stats">
        <div class="pp-stat"><div class="pp-sv">${rating}</div><div class="pp-sl">rating temporada</div></div>
        <div class="pp-stat"><div class="pp-sv">${d.appearances ?? '—'}</div><div class="pp-sl">partidos</div></div>
        <div class="pp-stat"><div class="pp-sv">${d.goals ?? 0}</div><div class="pp-sl">goles</div></div>
        <div class="pp-stat"><div class="pp-sv">${d.assists ?? 0}</div><div class="pp-sl">asistencias</div></div>
      </div>`;
  } catch {
    pop.querySelector('.pp-meta').textContent = 'No se pudieron cargar los datos del jugador.';
  }
}

/* ═══ PANELES DESPLEGABLES (toggle) ═══ */
function togglePanel(el) {
  el.closest('.detail-panel').classList.toggle('open');
}

/* ═══════════════ v5: ESCÁNER DE BANCA + IA ═══════════════ */

// Tabs de modo banca
document.querySelectorAll('.bm-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.bm-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const mode = tab.dataset.mode;
    $('mode-single').hidden = mode !== 'single';
    $('mode-scan').hidden = mode !== 'scan';
    if (mode === 'scan') populateScanLeagues();
  });
});

// Slider de exposición
const scExp = $('sc-exp');
if (scExp) scExp.addEventListener('input', e => { $('sc-exp-val').textContent = e.target.value + '%'; });

// Poblar ligas del escáner (reusa leaguesData)
function populateScanLeagues() {
  const sel = $('sc-league');
  if (!leaguesData.length) { sel.innerHTML = '<option value="">Configura API-Football primero</option>'; return; }
  if (sel.options.length > 1) return; // ya cargado
  sel.innerHTML = '<option value="">Elige competición…</option>' +
    leaguesData.map((l,i) => `<option value="${i}">${l.name}${l.country ? ' · '+l.country : ''}</option>`).join('');
}

// Ejecutar escáner
const scBtn = $('sc-btn');
if (scBtn) scBtn.addEventListener('click', async () => {
  const idx = $('sc-league').value;
  if (idx === '') { alert('Elige una competición.'); return; }
  const league = leaguesData[idx];
  const payload = {
    league_id: league.id, season: league.season,
    bankroll: +$('sc-bank').value,
    kelly_mult: +$('sc-mult').value,
    max_exposure: +$('sc-exp').value / 100,
    currency: $('sc-cur').value,
    days: 7,
  };
  $('sc-results').hidden = true;
  $('sc-loading').hidden = false;
  const msgs = ['Buscando próximos partidos…','Corriendo el modelo en cada uno…','Evaluando todos los mercados…','Detectando apuestas de valor…','Repartiendo el capital…','Optimizando la cartera…'];
  let i = 0; $('sc-load-msg').textContent = msgs[0];
  const t = setInterval(() => { i=(i+1)%msgs.length; $('sc-load-msg').textContent = msgs[i]; }, 2500);

  try {
    const d = await fetch('/api/scan', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) }).then(r=>r.json());
    clearInterval(t); $('sc-loading').hidden = true;
    if (d.error) throw new Error(d.error);
    renderScan(d, payload.currency);
    $('sc-results').hidden = false;
  } catch(e) { clearInterval(t); $('sc-loading').hidden = true; alert('Error: ' + e.message); }
});

function renderScan(d, cur) {
  if (!d.has_value) {
    $('sc-results').innerHTML = `<div class="scan-verdict" style="border-color:var(--red)"><h3>Sin valor esta jornada</h3><p>${d.verdict}</p><p style="margin-top:0.8rem;color:#555">Partidos analizados: ${d.total_fixtures_scanned || 0}</p></div>`;
    return;
  }
  const aiHTML = d.ai_summary ? `<div class="ai-panel"><div class="ai-head"><span class="ai-badge">⬡ IA</span><span class="ai-title">Lectura del estratega</span></div><div class="ai-summary">${d.ai_summary}</div></div>` : '';

  const betsHTML = d.recommended_bets.map((b,i) => `
    <div class="scan-bet ${i===0?'top':''}">
      <div><span class="scan-rank">${i+1}</span><span class="sb-match">${b.match}</span><div class="sb-date">${b.date ? new Date(b.date).toLocaleDateString('es-CO',{day:'numeric',month:'short'}) : ''}</div></div>
      <div><span class="sb-cell-lbl">${b.market_name || 'apuesta'}</span><span class="sb-bet">${b.bet_label}</span>${b.bookmaker ? `<span class="sb-book">⊞ ${b.bookmaker}</span>` : ''}${b.market_fair_prob ? `<span class="sb-fair">modelo ${Math.round(b.model_prob*100)}% vs casa ${Math.round(b.market_fair_prob*100)}%</span>` : ''}</div>
      <div><span class="sb-cell-lbl">edge</span><span class="sb-edge">+${b.edge_pct}%</span></div>
      <div><span class="sb-cell-lbl">cuota</span><span class="sb-odds">${b.decimal_odds}</span></div>
      <div><span class="sb-cell-lbl">apostar</span><span class="sb-stake">${fmtNum(b.stake)}</span></div>
    </div>`).join('');

  const booksHTML = d.bookmakers_used && d.bookmakers_used.length
    ? `<div class="scan-books"><span class="sb-books-lbl">Casas consultadas:</span> ${d.bookmakers_used.join(' · ')}</div>` : '';

  $('sc-results').innerHTML = `
    <div class="scan-verdict"><h3>Cartera de la jornada</h3><p>${d.verdict}</p></div>
    ${aiHTML}
    <div class="scan-summary">
      <div class="ss-cell"><div class="ss-val lime">${d.n_bets}</div><div class="ss-lbl">apuestas</div></div>
      <div class="ss-cell"><div class="ss-val">${fmtNum(d.total_stake)}</div><div class="ss-lbl">capital (${cur})</div></div>
      <div class="ss-cell"><div class="ss-val">${d.total_exposure_pct}%</div><div class="ss-lbl">exposición</div></div>
      <div class="ss-cell"><div class="ss-val lime">+${fmtNum(d.expected_value)}</div><div class="ss-lbl">valor esperado</div></div>
    </div>
    <div style="padding:0 2rem 0.5rem;font-family:var(--ff-mono);font-size:0.62rem;letter-spacing:2px;color:var(--muted)">CARTERA RECOMENDADA · ${d.total_fixtures_scanned} PARTIDOS ANALIZADOS</div>
    <div class="scan-bets">${betsHTML}</div>
    ${booksHTML}
    <p style="padding:0 2rem 2rem;font-family:var(--ff-mono);font-size:0.65rem;color:#555;line-height:1.7">Las cuotas mostradas son las mejores disponibles entre las casas que API-Football lista para tu cuenta (varían según país). Los montos respetan tu tope de exposición del ${d.max_exposure_pct}% por jornada con ${d.kelly_mult === 0.5 ? '½' : d.kelly_mult === 1 ? 'Kelly completo' : '¼'} Kelly. Herramienta de cálculo, no consejo financiero.</p>`;
}

/* ═══ PANEL DE IA EN ANÁLISIS ═══ */
async function loadAnalysisLineup(data) {
  const zone = $('analysis-lineup-zone');
  if (!zone) return;
  const meta = data.api_meta || {};
  const homeId = meta.team_a_id, awayId = meta.team_b_id;
  const season = (data.prediction && data.prediction.raw && data.prediction.raw.season) || 2024;
  const a = data.team_a, b = data.team_b;

  if (!homeId && !awayId) {
    zone.innerHTML = '<div style="margin:0 2rem 2rem;padding:1.5rem;background:var(--gray-3);border:1px solid var(--border);text-align:center;font-family:var(--ff-mono);font-size:0.75rem;color:var(--muted)">Las alineaciones requieren API-Football configurada.</div>';
    return;
  }

  try {
    const url = `/api/lineup/detailed/0?season=${season}&home_id=${homeId}&away_id=${awayId}`;
    const lineups = await fetch(url).then(r => r.json());
    if (!lineups || (!lineups.home && !lineups.away)) {
      zone.innerHTML = '<div style="margin:0 2rem 2rem;padding:1.5rem;background:var(--gray-3);border:1px solid var(--border);text-align:center;font-family:var(--ff-mono);font-size:0.75rem;color:var(--muted)">No hay datos de alineación disponibles.</div>';
      return;
    }
    window._lineups = lineups;
    const isProbable = lineups.status === 'probable';
    let html = `<div class="lineup-status ${isProbable ? 'probable' : 'confirmed'}">
      ${isProbable ? '◷ ALINEACIÓN PROBABLE' : '✓ ALINEACIÓN CONFIRMADA'}
      <span>${isProbable ? 'Estimada según jugadores con más minutos · se actualiza al confirmarse' : 'Titulares oficiales'}</span>
    </div>`;
    html += renderPitchSection(lineups, a, b);
    zone.innerHTML = html;
    const firstTab = zone.querySelector('.pitch-tab');
    if (firstTab) firstTab.click();
  } catch(e) {
    zone.innerHTML = '<div style="margin:0 2rem 2rem;padding:1.5rem;text-align:center;color:var(--muted);font-family:var(--ff-mono);font-size:0.75rem">No se pudieron cargar las alineaciones.</div>';
  }
}

async function requestAIAnalysis() {
  if (!lastPred) return;
  const btn = $('ai-trigger');
  if (btn) btn.outerHTML = '<div class="ai-loading">⬡ La IA está analizando el partido…</div>';
  try {
    const d = await fetch('/api/ai/analyze', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ prediction_data: lastPred }) }).then(r=>r.json());
    const zone = $('ai-zone');
    if (!d.available) {
      if (zone) zone.innerHTML = `<div class="ai-panel"><div class="ai-head"><span class="ai-badge">⬡ IA</span><span class="ai-title">Análisis con IA</span></div><p style="color:var(--muted);font-size:0.9rem">La IA no está configurada. Agrega tu clave DEEPSEEK_API_KEY en Render para desbloquear el análisis experto.</p></div>`;
      return;
    }
    const factorsHTML = (d.key_factors || []).map(f => `<div class="ai-factor">${f}</div>`).join('');
    if (zone) zone.innerHTML = `<div class="ai-panel">
      <div class="ai-head"><span class="ai-badge">⬡ IA · DEEPSEEK</span><span class="ai-title">Lectura experta del partido</span></div>
      <div class="ai-summary">${d.summary || ''}</div>
      ${factorsHTML ? `<div class="ai-factors">${factorsHTML}</div>` : ''}
      ${d.betting_read ? `<div class="ai-betting"><span class="ai-betting-lbl">Lectura de apuesta</span>${d.betting_read}</div>` : ''}
    </div>`;
  } catch(e) {
    const zone = $('ai-zone');
    if (zone) zone.innerHTML = `<div class="ai-panel"><p style="color:var(--red)">No se pudo generar el análisis de IA.</p></div>`;
  }
}

/* ═══════════════ OPTIMIZADOR DE PESOS ═══════════════ */
const optBtn = $('opt-btn');
if (optBtn) optBtn.addEventListener('click', async () => {
  let historical;
  try { historical = JSON.parse($('opt-in').value); }
  catch { alert('El JSON no es válido. Revisa el formato.'); return; }

  optBtn.textContent = 'OPTIMIZANDO…'; optBtn.disabled = true;
  try {
    const d = await fetch('/api/optimize-weights', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ historical, iterations: 3000 }) }).then(r=>r.json());
    renderOptResults(d);
    $('opt-results').hidden = false;
  } catch(e) { alert('Error: ' + e.message); }
  finally { optBtn.textContent = '⚙ OPTIMIZAR PESOS ↗'; optBtn.disabled = false; }
});

function renderOptResults(d) {
  const zone = $('opt-results');
  if (!d.success) {
    zone.innerHTML = `<div class="scan-verdict" style="border-color:var(--red)"><h3>No se pudo optimizar</h3><p>${d.reason}</p></div>`;
    return;
  }
  const names = { sofascore_form:'Forma jugadores', elo_rating:'Ranking ELO', chemistry:'Química', h2h:'Head-to-head', market_value:'Valor mercado' };
  const ow = d.optimized_weights, dw = d.default_weights;

  const bars = Object.keys(ow).map(k => {
    const optV = ow[k]*100, defV = dw[k]*100;
    return `<div class="optw-row">
      <div class="optw-name">${names[k]}</div>
      <div class="optw-bars">
        <div class="optw-bar-track"><div class="optw-bar def" style="width:${defV}%"></div></div>
        <div class="optw-bar-track"><div class="optw-bar opt" style="width:${optV}%"></div></div>
      </div>
      <div class="optw-vals"><span class="optw-def">${defV.toFixed(0)}%</span><span class="optw-arrow">→</span><span class="optw-opt">${optV.toFixed(0)}%</span></div>
    </div>`;
  }).join('');

  zone.innerHTML = `
    <div class="scan-verdict"><h3>Pesos optimizados</h3><p>${d.verdict}</p></div>
    ${d.warning ? `<div class="opt-warning">⚠ ${d.warning}</div>` : ''}
    <div class="scan-summary">
      <div class="ss-cell"><div class="ss-val">${d.n_matches}</div><div class="ss-lbl">partidos</div></div>
      <div class="ss-cell"><div class="ss-val">${d.base_brier}</div><div class="ss-lbl">error inicial</div></div>
      <div class="ss-cell"><div class="ss-val lime">${d.optimized_brier}</div><div class="ss-lbl">error optimizado</div></div>
      <div class="ss-cell"><div class="ss-val lime">${d.improvement_pct}%</div><div class="ss-lbl">mejora</div></div>
    </div>
    <div style="padding:0 2rem 0.5rem;font-family:var(--ff-mono);font-size:0.62rem;letter-spacing:2px;color:var(--muted)">DEFAULT (gris) → OPTIMIZADO (lima)</div>
    <div class="optw-list">${bars}</div>
    <p style="padding:1rem 2rem 2rem;font-family:var(--ff-mono);font-size:0.65rem;color:#555;line-height:1.7">Estos pesos minimizan el error sobre tus datos históricos. Optimizar el pasado no garantiza el futuro: con muestras pequeñas, el riesgo de sobreajuste es real. Úsalos como punto de partida, no como verdad absoluta.</p>`;
}

/* ═══════════════ PARTIDO EN VIVO ═══════════════ */
let liveRefreshTimer = null;

const liveBackBtn = $('live-back');
if (liveBackBtn) liveBackBtn.addEventListener('click', () => {
  if (liveRefreshTimer) clearInterval(liveRefreshTimer);
  goView('home');
});

async function openLiveMatch(fixtureId) {
  if (!fixtureId) return;
  goView('live');
  const zone = $('live-detail-zone');
  zone.innerHTML = '<div class="loading"><div class="ld-bars"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><p>Cargando partido en vivo…</p></div>';

  await renderLiveMatch(fixtureId);
  // Auto-refresco cada 30 segundos
  if (liveRefreshTimer) clearInterval(liveRefreshTimer);
  liveRefreshTimer = setInterval(() => renderLiveMatch(fixtureId, true), 30000);
}

async function renderLiveMatch(fixtureId, isRefresh) {
  const zone = $('live-detail-zone');
  try {
    const d = await fetch(`/api/live/${fixtureId}`).then(r => r.json());
    if (d.error) { zone.innerHTML = `<div class="scan-verdict" style="border-color:var(--red);margin:2rem"><h3>No disponible</h3><p>${d.error}</p></div>`; return; }

    // Marcador grande
    const goalsEvents = (d.goals_events || []).map(g =>
      `<div class="live-goal"><span class="lg-min">${g.minute}'</span><span class="lg-player">⚽ ${g.player || '—'}</span><span class="lg-team">${g.team || ''}</span></div>`
    ).join('') || '<p style="color:var(--muted);font-family:var(--ff-mono);font-size:0.75rem;padding:0.5rem 0">Sin goles todavía</p>';

    // Estadísticas
    const statRows = [];
    const sh = d.stats.home || {}, sa = d.stats.away || {};
    const statKeys = [['Ball Possession','Posesión'],['Total Shots','Tiros'],['Shots on Goal','Tiros al arco'],['Corner Kicks','Córners'],['Fouls','Faltas']];
    statKeys.forEach(([k,label]) => {
      if (sh[k] != null || sa[k] != null) {
        statRows.push(`<div class="live-stat"><span class="lst-h">${sh[k] ?? '—'}</span><span class="lst-lbl">${label}</span><span class="lst-a">${sa[k] ?? '—'}</span></div>`);
      }
    });

    // Sugerencias en vivo
    const sugg = (d.live_suggestions || []).map(s =>
      `<div class="live-sugg"><div class="lsug-market">${s.market}</div><div class="lsug-reason">${s.reason}</div></div>`
    ).join('');

    zone.innerHTML = `
      <div class="live-scoreboard">
        <div class="lsb-team"><div class="lsb-logo">${d.home.logo?`<img src="${d.home.logo}">`:''}</div><div class="lsb-name">${d.home.name}</div></div>
        <div class="lsb-center">
          <div class="lsb-score">${d.home.goals ?? 0} - ${d.away.goals ?? 0}</div>
          <div class="lsb-min">● ${d.elapsed ?? 0}' ${d.status || ''}</div>
        </div>
        <div class="lsb-team"><div class="lsb-logo">${d.away.logo?`<img src="${d.away.logo}">`:''}</div><div class="lsb-name">${d.away.name}</div></div>
      </div>

      <div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">●</span><h2 class="sh-title">GOLES</h2><div class="sh-line"></div></div>
      <div class="live-goals">${goalsEvents}</div>

      ${statRows.length ? `<div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">▦</span><h2 class="sh-title">ESTADÍSTICAS</h2><div class="sh-line"></div></div><div class="live-stats">${statRows.join('')}</div>` : ''}

      ${sugg ? `<div class="section-header" style="padding:2rem 2rem 1rem"><span class="sh-num">⚡</span><h2 class="sh-title">SUGERENCIAS EN VIVO</h2><div class="sh-line"></div></div><div class="live-suggs">${sugg}</div><p style="padding:1rem 2rem 2rem;font-family:var(--ff-mono);font-size:0.62rem;color:#555;line-height:1.6">${d.disclaimer}</p>` : ''}

      <div style="padding:1rem 2rem 3rem;text-align:center;font-family:var(--ff-mono);font-size:0.62rem;color:#555">↻ Se actualiza solo cada 30 segundos</div>`;
  } catch(e) {
    if (!isRefresh) zone.innerHTML = `<div class="scan-verdict" style="border-color:var(--red);margin:2rem"><h3>Error</h3><p>No se pudo cargar el partido en vivo.</p></div>`;
  }
}
