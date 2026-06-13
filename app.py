"""
VagoScore — Interfaz principal (Streamlit)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from engine.pipeline import run_prediction
from engine.scorer import WeightConfig
from cache.db import cache_stats, cache_clear

# ─── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="VagoScore",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2.8rem;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(135deg, #1e7e34, #28a745);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        text-align: center;
        color: #6c757d;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .prob-card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #dee2e6;
    }
    .prob-number {
        font-size: 2.5rem;
        font-weight: 700;
    }
    .prob-label {
        font-size: 0.85rem;
        color: #6c757d;
        margin-top: 4px;
    }
    .win-a    { color: #1e7e34; }
    .draw-c   { color: #fd7e14; }
    .win-b    { color: #1565C0; }
    .score-badge {
        font-size: 1.6rem;
        font-weight: 700;
        background: #212529;
        color: white;
        padding: 8px 20px;
        border-radius: 8px;
        display: inline-block;
    }
    .factor-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 6px 0;
        font-size: 0.9rem;
    }
    .confidence-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚽ VagoScore")
    st.markdown("Predictor de partidos basado en datos reales")
    st.markdown("---")

    st.markdown("### 🎯 Partido")
    team_a = st.text_input("Equipo local", value="Brasil", placeholder="Ej: España")
    team_b = st.text_input("Equipo visitante", value="Marruecos", placeholder="Ej: Francia")

    match_type = st.radio(
        "Tipo de partido",
        ["🌍 Selecciones nacionales", "🏟️ Clubes"],
        index=0,
    )
    is_national = "Selecciones" in match_type

    st.markdown("---")
    st.markdown("### ⚖️ Pesos del modelo")
    st.caption("Deben sumar 1.0")

    w_form = st.slider("Forma reciente (Sofascore)", 0.0, 1.0, 0.25, 0.05)
    w_elo  = st.slider("Ranking ELO", 0.0, 1.0, 0.25, 0.05)
    w_chem = st.slider("Química alineación", 0.0, 1.0, 0.20, 0.05)
    w_h2h  = st.slider("Head-to-Head", 0.0, 1.0, 0.15, 0.05)
    w_mkt  = st.slider("Valor de mercado", 0.0, 1.0, 0.15, 0.05)

    total_w = round(w_form + w_elo + w_chem + w_h2h + w_mkt, 2)
    if abs(total_w - 1.0) > 0.01:
        st.error(f"⚠️ Los pesos suman {total_w:.2f}. Deben sumar exactamente 1.0")
        weights_ok = False
    else:
        st.success(f"✅ Pesos: {total_w:.2f}")
        weights_ok = True

    st.markdown("---")
    st.markdown("### 📋 Alineación (opcional)")
    st.caption("Un jugador por línea. Mejora la precisión.")
    lineup_a_raw = st.text_area(f"Titulares {team_a}", height=120,
        placeholder="Alisson\nDanilo\nMarquinhos\n...")
    lineup_b_raw = st.text_area(f"Titulares {team_b}", height=120,
        placeholder="Bono\nHakimi\nSaiss\n...")

    st.markdown("---")
    stats = cache_stats()
    st.caption(f"🗄️ Caché: {stats['entries']} entradas · {stats['size_kb']} KB")
    if st.button("🗑️ Limpiar caché"):
        cache_clear()
        st.success("Caché limpiado")

    predict_btn = st.button(
        "🔮 Predecir partido",
        type="primary",
        disabled=not weights_ok or not team_a or not team_b,
        use_container_width=True,
    )


# ─── Main content ─────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">VagoScore ⚽</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Predicción estadística de partidos · Sin APIs de pago</div>', unsafe_allow_html=True)

if not predict_btn:
    # Pantalla de inicio
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📊 Fuentes de datos")
        st.markdown("""
        - **Sofascore** — Ratings últimos 10 partidos
        - **Transfermarkt** — Valor de mercado
        - **ELO Ratings** — Fuerza histórica
        - **H2H** — Historial de enfrentamientos
        """)
    with col2:
        st.markdown("### ⚙️ Metodología")
        st.markdown("""
        - Pesos configurables por factor
        - Normalización sigmoidea
        - Modelo de Poisson para marcadores
        - Caché local para eficiencia
        """)
    with col3:
        st.markdown("### 🌍 Cobertura")
        st.markdown("""
        - Todas las selecciones FIFA
        - Principales ligas europeas
        - Champions & Europa League
        - Copas continentales
        """)

    st.info("👈 Configura el partido en la barra lateral y presiona **Predecir partido**")

else:
    # Parsear alineaciones
    lineup_a = [l.strip() for l in lineup_a_raw.strip().split("\n") if l.strip()] or None
    lineup_b = [l.strip() for l in lineup_b_raw.strip().split("\n") if l.strip()] or None

    weights = WeightConfig(
        sofascore_form=w_form,
        elo_rating=w_elo,
        chemistry=w_chem,
        h2h=w_h2h,
        market_value=w_mkt,
    )

    # Progress bar
    progress_bar = st.progress(0)
    status_text  = st.empty()

    def on_progress(msg, pct):
        progress_bar.progress(pct / 100)
        status_text.text(f"⏳ {msg}")

    with st.spinner("Analizando partido..."):
        try:
            results = run_prediction(
                team_a=team_a,
                team_b=team_b,
                is_national=is_national,
                lineup_a=lineup_a,
                lineup_b=lineup_b,
                weights=weights,
                progress_callback=on_progress,
            )
            progress_bar.progress(1.0)
            status_text.empty()
        except Exception as e:
            st.error(f"Error en el análisis: {e}")
            st.stop()

    pred  = results["prediction"]
    probs = pred["prediction"]
    scores = pred["scores"]

    # ── Cabecera del partido ──
    st.markdown("---")
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        st.markdown(f"## 🏠 {team_a}")
        total_a = scores[team_a]["total"]
        st.metric("VagoScore", f"{total_a:.1f} / 100")
    with c2:
        st.markdown("### VS", unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center"><span class="score-badge">{probs["most_likely_score"]}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="text-align:center;margin-top:8px;color:#6c757d;font-size:0.85rem">Marcador más probable</div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f"## ✈️ {team_b}")
        total_b = scores[team_b]["total"]
        st.metric("VagoScore", f"{total_b:.1f} / 100")

    # ── Probabilidades ──
    st.markdown("---")
    st.markdown("### Probabilidades de resultado")
    col_a, col_d, col_b = st.columns(3)

    with col_a:
        st.markdown(f"""
        <div class="prob-card">
            <div class="prob-number win-a">{probs['p_win_a']}%</div>
            <div class="prob-label">Victoria {team_a}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_d:
        st.markdown(f"""
        <div class="prob-card">
            <div class="prob-number draw-c">{probs['p_draw']}%</div>
            <div class="prob-label">Empate</div>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown(f"""
        <div class="prob-card">
            <div class="prob-number win-b">{probs['p_win_b']}%</div>
            <div class="prob-label">Victoria {team_b}</div>
        </div>
        """, unsafe_allow_html=True)

    # Barra de probabilidad visual
    fig_bar = go.Figure(go.Bar(
        x=[probs["p_win_a"], probs["p_draw"], probs["p_win_b"]],
        y=[f"Victoria {team_a}", "Empate", f"Victoria {team_b}"],
        orientation="h",
        marker_color=["#1e7e34", "#fd7e14", "#1565C0"],
        text=[f"{probs['p_win_a']}%", f"{probs['p_draw']}%", f"{probs['p_win_b']}%"],
        textposition="outside",
    ))
    fig_bar.update_layout(
        height=180,
        margin=dict(l=150, r=60, t=10, b=10),
        xaxis=dict(range=[0, 100], showgrid=False, visible=False),
        yaxis=dict(showgrid=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── xG y confianza ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"xG {team_a}", probs["xg_a"])
    c2.metric(f"xG {team_b}", probs["xg_b"])
    c3.metric("Confianza del modelo", f"{probs['confidence']}%")
    c4.metric("Favorito", probs["favorite"])

    # ── Radar por factor ──
    st.markdown("---")
    st.markdown("### Análisis por factor")

    factors = ["Forma reciente", "ELO", "Química", "H2H", "Valor mercado"]
    vals_a = [
        scores[team_a]["sofascore"],
        scores[team_a]["elo"],
        scores[team_a]["chemistry"],
        scores[team_a]["h2h"],
        scores[team_a]["market"],
    ]
    vals_b = [
        scores[team_b]["sofascore"],
        scores[team_b]["elo"],
        scores[team_b]["chemistry"],
        scores[team_b]["h2h"],
        scores[team_b]["market"],
    ]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=vals_a + [vals_a[0]],
        theta=factors + [factors[0]],
        fill="toself",
        name=team_a,
        line_color="#1e7e34",
        fillcolor="rgba(30,126,52,0.2)",
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=vals_b + [vals_b[0]],
        theta=factors + [factors[0]],
        fill="toself",
        name=team_b,
        line_color="#1565C0",
        fillcolor="rgba(21,101,192,0.2)",
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        height=400,
        margin=dict(l=60, r=60, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # ── Tabla comparativa por factor ──
    st.markdown("### Comparativa detallada")
    factor_labels = {
        "sofascore": f"Forma reciente (Sofascore) — peso {w_form:.0%}",
        "elo":       f"Ranking ELO — peso {w_elo:.0%}",
        "chemistry": f"Química de alineación — peso {w_chem:.0%}",
        "h2h":       f"Head-to-Head — peso {w_h2h:.0%}",
        "market":    f"Valor de mercado — peso {w_mkt:.0%}",
    }
    rows = []
    for key, label in factor_labels.items():
        va = scores[team_a][key]
        vb = scores[team_b][key]
        winner = "🟢 " + team_a if va > vb + 2 else ("🔵 " + team_b if vb > va + 2 else "⚪ Parejo")
        rows.append({
            "Factor": label,
            team_a: f"{va:.1f}",
            team_b: f"{vb:.1f}",
            "Ventaja": winner,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Jugadores clave ──
    raw = pred.get("raw", {})
    kp_a = raw.get("key_player_a")
    kp_b = raw.get("key_player_b")

    if kp_a or kp_b:
        st.markdown("---")
        st.markdown("### Jugadores clave")
        col_ka, col_kb = st.columns(2)
        if kp_a:
            with col_ka:
                st.markdown(f"**{team_a}**")
                st.metric(kp_a.get("name", "—"), f"{kp_a.get('avg_rating', 0):.2f} ⭐",
                          delta=f"Posición: {kp_a.get('position', '?')}")
        if kp_b:
            with col_kb:
                st.markdown(f"**{team_b}**")
                st.metric(kp_b.get("name", "—"), f"{kp_b.get('avg_rating', 0):.2f} ⭐",
                          delta=f"Posición: {kp_b.get('position', '?')}")

    # ── H2H Historial ──
    h2h = results.get("h2h", {})
    matches = h2h.get("matches", [])
    if matches:
        st.markdown("---")
        st.markdown(f"### Historial H2H — últimos {len(matches)} partidos")
        h2h_rows = []
        for m in matches:
            h2h_rows.append({
                "Local": m.get("home_team", ""),
                "Resultado": f"{m.get('home_score', 0)} - {m.get('away_score', 0)}",
                "Visitante": m.get("away_team", ""),
                "Torneo": m.get("tournament", ""),
            })
        st.dataframe(pd.DataFrame(h2h_rows), use_container_width=True, hide_index=True)

    # ── Errores / advertencias ──
    errors = results.get("errors", [])
    if errors:
        with st.expander(f"⚠️ {len(errors)} advertencia(s) durante el scraping"):
            for e in errors:
                st.warning(e)

    # ── Datos crudos ──
    with st.expander("🔍 Datos crudos (debug)"):
        st.json(results)
