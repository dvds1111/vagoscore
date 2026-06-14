"""
VagoScore — Pipeline principal
Orquesta todos los scrapers y llama al motor de scoring.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.sofascore import get_team_lineup_ratings, get_head_to_head, search_team
from scrapers.transfermarkt import get_national_team_value, get_club_value
from scrapers.elo import get_national_elo, get_club_elo
from engine.scorer import WeightConfig, compute_vagoscore


def run_prediction(
    team_a: str,
    team_b: str,
    is_national: bool = True,
    lineup_a: list[str] = None,
    lineup_b: list[str] = None,
    weights: WeightConfig = None,
    progress_callback=None,
) -> dict:
    """
    Pipeline completo: scraping → scoring → predicción.

    Args:
        team_a: Nombre del equipo local
        team_b: Nombre del equipo visitante
        is_national: True si son selecciones, False si son clubes
        lineup_a: Lista de nombres de titulares del equipo A (opcional)
        lineup_b: Lista de nombres de titulares del equipo B (opcional)
        weights: Configuración de pesos (si None, usa defaults)
        progress_callback: función(step: str, pct: int) para UI

    Returns:
        Diccionario completo con predicción y todos los datos intermedios
    """
    def log(msg, pct=0):
        print(f"[pipeline] {msg}")
        if progress_callback:
            progress_callback(msg, pct)

    results = {
        "team_a": team_a,
        "team_b": team_b,
        "errors": [],
    }

    # ── 1. Sofascore ratings ──
    log(f"Obteniendo ratings de {team_a} (Sofascore)...", 10)
    try:
        sofa_a = get_team_lineup_ratings(team_a, lineup_a)
        results["sofascore_a"] = sofa_a
    except Exception as e:
        log(f"Error Sofascore {team_a}: {e}")
        results["errors"].append(f"sofascore_a: {e}")
        sofa_a = {"team": team_a, "team_avg_rating": 6.8, "players": []}

    log(f"Obteniendo ratings de {team_b} (Sofascore)...", 25)
    try:
        sofa_b = get_team_lineup_ratings(team_b, lineup_b)
        results["sofascore_b"] = sofa_b
    except Exception as e:
        log(f"Error Sofascore {team_b}: {e}")
        results["errors"].append(f"sofascore_b: {e}")
        sofa_b = {"team": team_b, "team_avg_rating": 6.8, "players": []}

    # ── 2. Valores de mercado ──
    log(f"Obteniendo valores de mercado (Transfermarkt)...", 40)
    get_value = get_national_team_value if is_national else get_club_value
    try:
        market_a = get_value(team_a)
        results["market_a"] = market_a
    except Exception as e:
        log(f"Error Transfermarkt {team_a}: {e}")
        results["errors"].append(f"market_a: {e}")
        market_a = {"team": team_a, "total_value_m": 500.0}

    try:
        market_b = get_value(team_b)
        results["market_b"] = market_b
    except Exception as e:
        log(f"Error Transfermarkt {team_b}: {e}")
        results["errors"].append(f"market_b: {e}")
        market_b = {"team": team_b, "total_value_m": 300.0}

    # ── 3. ELO ratings ──
    log(f"Obteniendo rankings ELO...", 60)
    get_elo = get_national_elo if is_national else get_club_elo
    try:
        elo_a = get_elo(team_a)
        results["elo_a"] = elo_a
    except Exception as e:
        log(f"Error ELO {team_a}: {e}")
        results["errors"].append(f"elo_a: {e}")
        elo_a = {"team": team_a, "elo": 1800}

    try:
        elo_b = get_elo(team_b)
        results["elo_b"] = elo_b
    except Exception as e:
        log(f"Error ELO {team_b}: {e}")
        results["errors"].append(f"elo_b: {e}")
        elo_b = {"team": team_b, "elo": 1750}

    # ── 4. Head-to-head ──
    log(f"Obteniendo historial H2H...", 75)
    h2h_data = {"matches": [], "total": 0}
    try:
        team_a_info = search_team(team_a)
        team_b_info = search_team(team_b)
        if team_a_info and team_b_info:
            from scrapers.sofascore import get_head_to_head
            h2h_data = get_head_to_head(team_a_info["id"], team_b_info["id"])
        results["h2h"] = h2h_data
    except Exception as e:
        log(f"Error H2H: {e}")
        results["errors"].append(f"h2h: {e}")

    # ── 5. Score final ──
    log("Calculando VagoScore...", 90)
    prediction = compute_vagoscore(
        sofascore_a=sofa_a,
        sofascore_b=sofa_b,
        elo_a=elo_a,
        elo_b=elo_b,
        market_a=market_a,
        market_b=market_b,
        h2h_data=h2h_data,
        team_a_name=team_a,
        team_b_name=team_b,
        weights=weights,
    )
    results["prediction"] = prediction

    # ── Bloque de datos crudos consolidado para el frontend ──
    raw = prediction.get("raw", {}) if isinstance(prediction, dict) else {}
    raw["elo_a"] = elo_a.get("elo") if isinstance(elo_a, dict) else elo_a
    raw["elo_b"] = elo_b.get("elo") if isinstance(elo_b, dict) else elo_b
    # Valor de mercado en euros (total_value_m está en millones)
    mva = market_a.get("total_value_m") if isinstance(market_a, dict) else None
    mvb = market_b.get("total_value_m") if isinstance(market_b, dict) else None
    raw["market_value_a"] = round(mva * 1_000_000) if mva else None
    raw["market_value_b"] = round(mvb * 1_000_000) if mvb else None
    # Forma reciente (resultados W/D/L) desde H2H o sofascore si está disponible
    raw["form_a"] = sofa_a.get("recent_form") if isinstance(sofa_a, dict) else None
    raw["form_b"] = sofa_b.get("recent_form") if isinstance(sofa_b, dict) else None
    # Jugador clave (mejor rating de cada equipo)
    raw["key_player_a"] = _best_player(sofa_a)
    raw["key_player_b"] = _best_player(sofa_b)
    # H2H resumen legible
    if h2h_data and h2h_data.get("total"):
        raw["h2h_summary"] = f"{h2h_data.get('total', 0)} enfrentamientos registrados en el historial reciente."
    if isinstance(prediction, dict):
        prediction["raw"] = raw

    log("¡Predicción lista!", 100)

    return results


def _best_player(sofa_data):
    """Extrae el jugador con mejor rating de un equipo."""
    if not isinstance(sofa_data, dict):
        return None
    players = sofa_data.get("players", [])
    if not players:
        return None
    try:
        best = max(players, key=lambda p: p.get("avg_rating", 0) or 0)
        return {
            "name": best.get("name", "—"),
            "avg_rating": best.get("avg_rating", 0),
            "position": best.get("position", "?"),
            "matches": best.get("matches", 0),
        }
    except (ValueError, TypeError):
        return None
