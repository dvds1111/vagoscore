const $ = (id) => document.getElementById(id);
const fmt = (n, cur) => new Intl.NumberFormat('es-CO').format(Math.round(n)) + (cur ? ' ' + cur : '');

let isNational = true;
let lastAnalysis = null;

// ═══════ NAV ENTRE VISTAS ═══════
$('nav-tabs').addEventListener('click', (e) => {
  const tab = e.target.closest('.tab');
  if (!tab) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  tab.classList.add('active');
  $('view-' + tab.dataset.view).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

function goToView(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === name));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  $('view-' + name).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ═══════ ESTADO DEL SISTEMA ═══════
async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    if (s.apifootball_connected) {
      $('status-dot').className = 'status-dot on';
      $('status-text').textContent = 'API conectada';
      loadLeagues();
    } else {
      $('status-dot').className = 'status-dot off';
      $('status-text').textContent = 'sin API-Football';
      $('fixtures-hint').textContent = 'Configura tu clave de API-Football (variable APIFOOTBALL_KEY) para explorar partidos en tiempo real. Mientras tanto, puedes usar Análisis, Banca y Backtest manualmente.';
    }
  } catch {
    $('status-dot').className = 'status-dot off';
    $('status-text').textContent = 'sin conexión';
  }
}
loadStatus();

// ═══════ VISTA 1: LIGAS Y PARTIDOS ═══════
let leaguesData = [];
async function loadLeagues() {
  try {
    const r = await fetch('/api/leagues');
    const data = await r.json();
    leaguesData = data.leagues || [];
    const sel = $('league-select');
    if (!leaguesData.length) { sel.innerHTML = '<option value="">No hay ligas disponibles</option>'; return; }
    sel.innerHTML = '<option value="">Elige una competición…</option>' +
      leaguesData.map((l, i) => `<option value="${i}">${l.name} — ${l.country}</option>`).join('');
  } catch (e) {
    $('league-select').innerHTML = '<option value="">Error al cargar</option>';
  }
}

$('league-select').addEventListener('change', async (e) => {
  const idx = e.target.value;
  if (idx === '') return;
  const league = leaguesData[idx];
  const grid = $('fixtures-grid');
  grid.innerHTML = '<div class="empty-hint">Cargando partidos…</div>';
  try {
    const r = await fetch(`/api/fixtures?league=${league.id}&season=${league.season}&days=21`);
    const data = await r.json();
    renderFixtures(data.fixtures || []);
  } catch {
    grid.innerHTML = '<div class="empty-hint">No se pudieron cargar los partidos.</div>';
  }
});

function renderFixtures(fixtures) {
  const grid = $('fixtures-grid');
  if (!fixtures.length) { grid.innerHTML = '<div class="empty-hint">No hay partidos próximos en esta competición.</div>'; return; }
  grid.innerHTML = '';
  fixtures.slice(0, 24).forEach(fx => {
    const date = new Date(fx.date);
    const dateStr = date.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
    const card = document.createElement('div');
    card.className = 'fixture-card';
    card.innerHTML = `
      <div class="fx-round">${fx.round || 'Próximo partido'}</div>
      <div class="fx-teams">
        <div class="fx-team"><img src="${fx.home.logo}" alt=""><span>${fx.home.name}</span></div>
        <div class="fx-team"><img src="${fx.away.logo}" alt=""><span>${fx.away.name}</span></div>
      </div>
      <div class="fx-meta"><span>${dateStr}</span><span class="fx-cta">Analizar →</span></div>`;
    card.addEventListener('click', () => {
      $('team-a').value = fx.home.name;
      $('team-b').value = fx.away.name;
      goToView('analyze');
    });
    grid.appendChild(card);
  });
}

// ═══════ VISTA 2: ANÁLISIS ═══════
$('type-toggle').addEventListener('click', (e) => {
  const btn = e.target.closest('.toggle-opt');
  if (!btn) return;
  document.querySelectorAll('#type-toggle .toggle-opt').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  isNational = btn.dataset.national === 'true';
});

const loadingMsgs = ['Conectando con Sofascore…','Leyendo forma reciente…','Consultando Transfermarkt…','Calculando ELO…','Analizando head-to-head…','Midiendo química…','Fusionando señales…','Calculando probabilidades…'];
let loadingTimer = null;
$('run-btn').addEventListener('click', runAnalysis);

async function runAnalysis() {
  const teamA = $('team-a').value.trim(), teamB = $('team-b').value.trim();
  if (!teamA || !teamB) { alert('Escribe ambos equipos.'); return; }

  $('analysis-results').hidden = true;
  $('loading-zone').hidden = false;
  let i = 0;
  $('loading-msg').textContent = loadingMsgs[0];
  loadingTimer = setInterval(() => { i = (i+1) % loadingMsgs.length; $('loading-msg').textContent = loadingMsgs[i]; }, 2000);

  try {
    const resp = await fetch('/api/predict', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ team_a: teamA, team_b: teamB, is_national: isNational }),
    });
    const data = await resp.json();
    clearInterval(loadingTimer);
    $('loading-zone').hidden = true;
    if (data.error) throw new Error(data.error);
    lastAnalysis = data;
    renderAnalysis(data);
    $('analysis-results').hidden = false;
  } catch (err) {
    clearInterval(loadingTimer);
    $('loading-zone').hidden = true;
    alert('Error: ' + err.message);
  }
}

function renderAnalysis(data) {
  const pred = data.prediction, p = pred.prediction, s = pred.scores;
  const a = data.team_a, b = data.team_b;

  const factorDefs = [
    ['sofascore','Forma reciente', pred.weights_used.sofascore_form],
    ['elo','Ranking ELO', pred.weights_used.elo_rating],
    ['chemistry','Química de alineación', pred.weights_used.chemistry],
    ['h2h','Head-to-Head', pred.weights_used.h2h],
    ['market','Valor de mercado', pred.weights_used.market_value],
  ];
  let factorsHTML = '';
  factorDefs.forEach(([k,name,w]) => {
    const va = s[a][k], vb = s[b][k];
    factorsHTML += `<div class="factor"><div class="factor-top"><span class="factor-name">${name}</span><span class="factor-weight">peso ${Math.round(w*100)}%</span></div>
      <div class="fbars">
        <div class="fbar l"><div class="fbar-fill" style="width:${va}%"></div><span class="fbar-num">${va.toFixed(0)}</span></div>
        <div class="fbar r"><div class="fbar-fill" style="width:${vb}%"></div><span class="fbar-num">${vb.toFixed(0)}</span></div>
      </div></div>`;
  });

  const raw = pred.raw || {};
  let kpHTML = '';
  [[a, raw.key_player_a],[b, raw.key_player_b]].forEach(([team,kp]) => {
    if (!kp) return;
    kpHTML += `<div class="kp-card"><span class="kp-team">${team}</span><div class="kp-name">${kp.name||'—'}</div><span class="kp-rating">${(kp.avg_rating||0).toFixed(2)} ★</span><div style="font-size:0.74rem;color:var(--txt-dim);margin-top:0.3rem">${kp.position||'n/d'} · ${kp.matches||0} partidos</div></div>`;
  });

  $('analysis-results').innerHTML = `
    <div class="glass verdict-card">
      <div class="verdict-row">
        <div class="vteam"><div class="vteam-name">${a}</div><div class="vteam-score a">${s[a].total.toFixed(1)}</div><div class="vteam-tag">vagoscore</div></div>
        <div class="vcenter"><span class="vcenter-lbl">marcador probable</span><span class="vscore">${p.most_likely_score}</span><span class="vconf">confianza ${p.confidence}%</span></div>
        <div class="vteam"><div class="vteam-name">${b}</div><div class="vteam-score b">${s[b].total.toFixed(1)}</div><div class="vteam-tag">vagoscore</div></div>
      </div>
      <div class="prob-bar">
        <div class="pseg a" style="flex-basis:${p.p_win_a}%">${p.p_win_a}%</div>
        <div class="pseg d" style="flex-basis:${p.p_draw}%">${p.p_draw}%</div>
        <div class="pseg b" style="flex-basis:${p.p_win_b}%">${p.p_win_b}%</div>
      </div>
      <div class="prob-legend"><span><i style="background:var(--lime)"></i>Gana ${a}</span><span><i style="background:var(--amber)"></i>Empate</span><span><i style="background:var(--cyan)"></i>Gana ${b}</span></div>
      <div class="xg-row"><div class="xg-card"><div class="xg-val">${p.xg_a}</div><div class="xg-lbl">xG ${a}</div></div><div class="xg-card"><div class="xg-val">${p.xg_b}</div><div class="xg-lbl">xG ${b}</div></div></div>
    </div>
    <div class="section-title">Desglose por señal</div>
    <div class="factors">${factorsHTML}</div>
    ${kpHTML ? `<div class="section-title">Jugadores clave</div><div class="kp-grid">${kpHTML}</div>` : ''}
    <div class="glass cta-bankroll">
      <p><strong>¿Y cuánto apostar?</strong> Lleva estas probabilidades al módulo de Banca y deja que el criterio de Kelly calcule el tamaño óptimo según tu capital.</p>
      <button class="btn-primary" id="to-bankroll">Gestionar banca <span>→</span></button>
    </div>`;

  $('to-bankroll').addEventListener('click', () => {
    $('kp-home').value = p.p_win_a; $('kp-draw').value = p.p_draw; $('kp-away').value = p.p_win_b;
    $('kp-a-lbl').textContent = a; $('kp-b-lbl').textContent = b;
    $('ko-a-lbl').textContent = a; $('ko-b-lbl').textContent = b;
    $('autofill-hint').hidden = false;
    goToView('bankroll');
  });
}

// ═══════ VISTA 3: KELLY ═══════
$('currency').addEventListener('change', (e) => {
  const syms = {COP:'$',USD:'$',EUR:'€',MXN:'$',ARS:'$'};
  $('currency-sym').textContent = syms[e.target.value] || '$';
});

$('kelly-btn').addEventListener('click', async () => {
  const payload = {
    p_home: +$('kp-home').value, p_draw: +$('kp-draw').value, p_away: +$('kp-away').value,
    odds_home: +$('ko-home').value, odds_draw: +$('ko-draw').value, odds_away: +$('ko-away').value,
    bankroll: +$('bankroll').value, kelly_multiplier: +$('kelly-mult').value,
    team_a: $('kp-a-lbl').textContent, team_b: $('kp-b-lbl').textContent,
    currency: $('currency').value,
  };
  try {
    const r = await fetch('/api/kelly', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    renderKelly(data, payload.currency);
    $('kelly-results').hidden = false;
  } catch (e) { alert('Error: ' + e.message); }
});

function renderKelly(d, cur) {
  const best = d.best_bet;
  let bestHTML = '';
  if (best) {
    bestHTML = `<div class="glass best-bet">
      <div class="bb-label">Apuesta de valor recomendada</div>
      <div class="bb-outcome">${best.outcome_label}</div>
      <div class="bb-metrics">
        <div class="bb-metric"><div class="bb-metric-val stake">${fmt(best.stake)}</div><div class="bb-metric-lbl">apostar (${cur})</div></div>
        <div class="bb-metric"><div class="bb-metric-val">+${best.edge_pct}%</div><div class="bb-metric-lbl">ventaja (edge)</div></div>
        <div class="bb-metric"><div class="bb-metric-val">${best.decimal_odds}</div><div class="bb-metric-lbl">cuota</div></div>
        <div class="bb-metric"><div class="bb-metric-val">${fmt(best.potential_profit)}</div><div class="bb-metric-lbl">ganancia potencial</div></div>
      </div></div>`;
  }

  let simHTML = '';
  if (d.simulation) {
    const s = d.simulation;
    simHTML = `<div class="glass sim-card">
      <div class="bb-label">Simulación Monte Carlo · ${s.n_bets} apuestas repetidas, 400 escenarios</div>
      <div class="sim-grid">
        <div class="sim-stat"><div class="sim-stat-val">${fmt(s.median_final)}</div><div class="sim-stat-lbl">banca mediana final</div></div>
        <div class="sim-stat"><div class="sim-stat-val">${fmt(s.p10)}</div><div class="sim-stat-lbl">escenario malo (p10)</div></div>
        <div class="sim-stat"><div class="sim-stat-val">${fmt(s.p90)}</div><div class="sim-stat-lbl">escenario bueno (p90)</div></div>
        <div class="sim-stat"><div class="sim-stat-val ${s.ruin_probability_pct>5?'ruin-warn':''}">${s.ruin_probability_pct}%</div><div class="sim-stat-lbl">prob. de ruina</div></div>
      </div></div>`;
  }

  let betsHTML = d.recommendations.map(r => `
    <div class="bet-row ${r.edge_pct>0?'value':''}">
      <span class="bet-name">${r.outcome_label}</span>
      <span><span class="bet-mini-lbl">edge</span><span class="bet-edge ${r.edge_pct>0?'pos':'neg'}">${r.edge_pct>0?'+':''}${r.edge_pct}%</span></span>
      <span><span class="bet-mini-lbl">modelo vs casa</span>${Math.round(r.model_prob*100)}% / ${Math.round(r.implied_prob*100)}%</span>
      <span><span class="bet-mini-lbl">apostar</span>${r.stake>0?fmt(r.stake):'—'}</span>
    </div>`).join('');

  $('kelly-results').innerHTML = `
    <div class="glass kelly-verdict ${d.has_value?'has-value':'no-value'}">
      <div class="kv-headline">${d.has_value?'Hay valor en este partido':'Sin valor — mejor no apostar'}</div>
      <div class="kv-text">${d.verdict}</div>
    </div>
    ${bestHTML}
    ${simHTML}
    <div class="section-title">Todos los resultados</div>
    <div class="allbets">${betsHTML}</div>
    ${d.fair_probabilities && d.fair_probabilities.bookmaker_margin_pct ? `<p style="text-align:center;color:var(--txt-faint);font-size:0.78rem;margin-top:1rem;font-family:'Space Mono',monospace">Margen de la casa: ${d.fair_probabilities.bookmaker_margin_pct}% — eso es lo que debes superar para tener ventaja.</p>` : ''}`;
}

// ═══════ VISTA 4: BACKTEST ═══════
$('bt-btn').addEventListener('click', async () => {
  let preds;
  try { preds = JSON.parse($('bt-data').value); }
  catch { alert('El JSON no es válido. Revisa la sintaxis.'); return; }
  try {
    const r = await fetch('/api/backtest', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ predictions: preds }) });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    renderBacktest(data);
    $('bt-results').hidden = false;
  } catch (e) { alert('Error: ' + e.message); }
});

function renderBacktest(d) {
  const accClass = d.accuracy_pct >= 50 ? 'good' : 'bad';
  const roiClass = d.roi_pct > 0 ? 'good' : 'bad';
  let detailsHTML = d.details.map(m => `
    <div class="bt-match">
      <span>${m.match}</span>
      <span><span class="bet-mini-lbl">predijo</span>${m.predicted}</span>
      <span><span class="bet-mini-lbl">real</span>${m.actual}</span>
      <span class="${m.correct?'bt-hit':'bt-miss'}">${m.correct?'✓':'✗'}</span>
    </div>`).join('');

  $('bt-results').innerHTML = `
    <div class="bt-metrics">
      <div class="glass bt-metric"><div class="bt-metric-val ${accClass}">${d.accuracy_pct}%</div><div class="bt-metric-lbl">acierto</div></div>
      <div class="glass bt-metric"><div class="bt-metric-val">${d.brier_score}</div><div class="bt-metric-lbl">brier score</div></div>
      <div class="glass bt-metric"><div class="bt-metric-val ${roiClass}">${d.roi_pct>0?'+':''}${d.roi_pct}%</div><div class="bt-metric-lbl">ROI apuestas valor</div></div>
      <div class="glass bt-metric"><div class="bt-metric-val">${d.value_bet_hit_rate}%</div><div class="bt-metric-lbl">acierto en valor</div></div>
    </div>
    <div class="glass bt-interp">${d.interpretation}</div>
    <div class="section-title">Detalle por partido</div>
    <div class="bt-details">${detailsHTML}</div>`;
}
