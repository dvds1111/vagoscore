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
import config
from scrapers import apifootball_adapter as afa


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

    # ════════════════════════════════════════════════════════════════
    # ADQUISICIÓN DE DATOS — API-Football primero, scrapers como respaldo
    # ════════════════════════════════════════════════════════════════
    use_api = config.has_apifootball()
    api_meta = {"used": use_api, "team_a_id": None, "team_b_id": None}

    if use_api:
        log("Resolviendo equipos en API-Football...", 8)
        info_a = afa.resolve_team(team_a)
        info_b = afa.resolve_team(team_b)
        season = afa._current_season(is_national)
        api_meta["team_a_id"] = info_a.get("id")
        api_meta["team_b_id"] = info_b.get("id")
        results["team_a_logo"] = info_a.get("logo")
        results["team_b_logo"] = info_b.get("logo")

    # ── 1. Ratings de jugadores ──
    log(f"Obteniendo ratings de {team_a}...", 15)
    if use_api and info_a.get("id"):
        try:
            sofa_a = afa.get_team_ratings(info_a["id"], season)
            results["sofascore_a"] = sofa_a
        except Exception as e:
            log(f"Error ratings API {team_a}: {e}")
            results["errors"].append(f"ratings_a: {e}")
            sofa_a = {"team_avg_rating": 6.8, "players": []}
    else:
        try:
            sofa_a = get_team_lineup_ratings(team_a, lineup_a)
            results["sofascore_a"] = sofa_a
        except Exception as e:
            results["errors"].append(f"sofascore_a: {e}")
            sofa_a = {"team": team_a, "team_avg_rating": 6.8, "players": []}

    log(f"Obteniendo ratings de {team_b}...", 22)
    if use_api and info_b.get("id"):
        try:
            sofa_b = afa.get_team_ratings(info_b["id"], season)
            results["sofascore_b"] = sofa_b
        except Exception as e:
            log(f"Error ratings API {team_b}: {e}")
            results["errors"].append(f"ratings_b: {e}")
            sofa_b = {"team_avg_rating": 6.8, "players": []}
    else:
        try:
            sofa_b = get_team_lineup_ratings(team_b, lineup_b)
            results["sofascore_b"] = sofa_b
        except Exception as e:
            results["errors"].append(f"sofascore_b: {e}")
            sofa_b = {"team": team_b, "team_avg_rating": 6.8, "players": []}

    # ── 2. ELO ── (derivado de forma real si API; scraper si no)
    log("Calculando rankings ELO...", 40)
    if use_api and info_a.get("id"):
        try:
            elo_a = afa.derive_elo(info_a["id"], season)
        except Exception as e:
            results["errors"].append(f"elo_a: {e}")
            elo_a = {"elo": 1800}
    else:
        get_elo = get_national_elo if is_national else get_club_elo
        try:
            elo_a = get_elo(team_a)
        except Exception as e:
            results["errors"].append(f"elo_a: {e}")
            elo_a = {"team": team_a, "elo": 1800}
    results["elo_a"] = elo_a

    if use_api and info_b.get("id"):
        try:
            elo_b = afa.derive_elo(info_b["id"], season)
        except Exception as e:
            results["errors"].append(f"elo_b: {e}")
            elo_b = {"elo": 1750}
    else:
        get_elo = get_national_elo if is_national else get_club_elo
        try:
            elo_b = get_elo(team_b)
        except Exception as e:
            results["errors"].append(f"elo_b: {e}")
            elo_b = {"team": team_b, "elo": 1750}
    results["elo_b"] = elo_b

    # ── 3. Valor de plantilla ── (Transfermarkt real → estimado → scraper)
    log("Obteniendo valor de plantilla...", 55)
    if use_api:
        # Para clubes, intentar valor REAL de Transfermarkt primero
        market_a = market_b = None
        if not is_national:
            try:
                from scrapers import transfermarkt_api as tm
                if tm.is_available():
                    tm_a = tm.get_club_market_value(team_a)
                    tm_b = tm.get_club_market_value(team_b)
                    if tm_a:
                        market_a = tm_a
                    if tm_b:
                        market_b = tm_b
            except Exception as e:
                results["errors"].append(f"transfermarkt: {e}")
        # Lo que no se obtuvo de Transfermarkt, se estima
        if market_a is None:
            market_a = afa.estimate_market_value(sofa_a, elo_a.get("elo", 1700))
        if market_b is None:
            market_b = afa.estimate_market_value(sofa_b, elo_b.get("elo", 1700))
        results["market_a"] = market_a
        results["market_b"] = market_b
    else:
        get_value = get_national_team_value if is_national else get_club_value
        try:
            market_a = get_value(team_a)
        except Exception as e:
            results["errors"].append(f"market_a: {e}")
            market_a = {"team": team_a, "total_value_m": 500.0}
        try:
            market_b = get_value(team_b)
        except Exception as e:
            results["errors"].append(f"market_b: {e}")
            market_b = {"team": team_b, "total_value_m": 300.0}
        results["market_a"] = market_a
        results["market_b"] = market_b

    # ── 4. Head-to-head ──
    log("Obteniendo historial H2H...", 75)
    h2h_data = {"matches": [], "total": 0}
    if use_api and info_a.get("id") and info_b.get("id"):
        try:
            h2h_data = afa.get_h2h(info_a["id"], info_b["id"])
        except Exception as e:
            results["errors"].append(f"h2h: {e}")
    else:
        try:
            team_a_info = search_team(team_a)
            team_b_info = search_team(team_b)
            if team_a_info and team_b_info:
                h2h_data = get_head_to_head(team_a_info["id"], team_b_info["id"])
        except Exception as e:
            results["errors"].append(f"h2h: {e}")
    results["h2h"] = h2h_data

    # ── Forma reciente W/D/L + partidos detallados para los paneles ──
    form_a = form_b = None
    matches_a = matches_b = None
    if use_api:
        try:
            if info_a.get("id"):
                form_a = afa.get_recent_form_wdl(info_a["id"])
                matches_a = afa.get_recent_matches_detailed(info_a["id"])
            if info_b.get("id"):
                form_b = afa.get_recent_form_wdl(info_b["id"])
                matches_b = afa.get_recent_matches_detailed(info_b["id"])
        except Exception as e:
            results["errors"].append(f"form: {e}")
    results["form_a"] = form_a
    results["form_b"] = form_b
    results["matches_a"] = matches_a
    results["matches_b"] = matches_b
    results["api_meta"] = api_meta

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
    # Forma reciente (resultados W/D/L) — desde API-Football si disponible
    raw["form_a"] = results.get("form_a")
    raw["form_b"] = results.get("form_b")
    raw["matches_a"] = results.get("matches_a")
    raw["matches_b"] = results.get("matches_b")
    # Marca si el valor de mercado es estimado
    raw["market_is_estimate"] = market_a.get("is_estimate", False) if isinstance(market_a, dict) else False
    raw["elo_is_estimate"] = elo_a.get("is_estimate", False) if isinstance(elo_a, dict) else False
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
