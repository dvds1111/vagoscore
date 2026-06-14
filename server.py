"""
VagoScore — Backend web (Flask) · v2
Endpoints en tiempo real (API-Football) + Kelly + Backtesting.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_from_directory

import config
from engine.pipeline import run_prediction
from engine.scorer import WeightConfig
from engine.kelly import analyze_bankroll, simulate_growth
from engine.backtest import run_backtest
from engine.bankroll_scanner import derive_market_probabilities, scan_match, build_portfolio
from cache.db import cache_stats, cache_clear
from scrapers import apifootball as apif
from scrapers import gemini

app = Flask(__name__, static_folder="web", static_url_path="")


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "apifootball_connected": config.has_apifootball(),
        "gemini_connected": gemini.has_gemini(),
        "cache": cache_stats(),
    })


@app.route("/api/leagues")
def leagues():
    if not config.has_apifootball():
        return jsonify({"error": "API-Football no configurada", "leagues": []}), 200
    return jsonify({"leagues": apif.get_current_leagues()})


@app.route("/api/leagues/grouped")
def leagues_grouped():
    if not config.has_apifootball():
        return jsonify({"error": "API-Football no configurada", "world": [], "continents": {}}), 200
    return jsonify(apif.get_leagues_grouped())


@app.route("/api/team/squad/<int:team_id>")
def team_squad(team_id):
    return jsonify({"squad": apif.get_team_squad_detailed(team_id)})


@app.route("/api/team/stats")
def team_stats():
    team_id = request.args.get("team", type=int)
    league_id = request.args.get("league", type=int)
    season = request.args.get("season", type=int)
    if not all([team_id, league_id, season]):
        return jsonify({"error": "Faltan parámetros"}), 400
    return jsonify(apif.get_team_statistics(team_id, league_id, season))


@app.route("/api/lineup/detailed/<int:fixture_id>")
def lineup_detailed(fixture_id):
    season = request.args.get("season", type=int)
    return jsonify(apif.get_lineup_with_values(fixture_id, season))


@app.route("/api/player/<int:player_id>")
def player_detail(player_id):
    season = request.args.get("season", default=2024, type=int)
    return jsonify(apif.get_player_season(player_id, season))


@app.route("/api/fixtures")
def fixtures():
    league_id = request.args.get("league", type=int)
    season = request.args.get("season", type=int)
    days = request.args.get("days", default=14, type=int)
    if not league_id or not season:
        return jsonify({"error": "Faltan league y season"}), 400
    return jsonify({"fixtures": apif.get_upcoming_fixtures(league_id, season, days)})


@app.route("/api/live")
def live():
    if not config.has_apifootball():
        return jsonify({"live": []})
    return jsonify({"live": apif.get_live_fixtures()})


@app.route("/api/lineups/<int:fixture_id>")
def lineups(fixture_id):
    return jsonify(apif.get_fixture_lineups(fixture_id))


@app.route("/api/odds/<int:fixture_id>")
def odds(fixture_id):
    return jsonify(apif.get_fixture_odds(fixture_id))


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    team_a = (data.get("team_a") or "").strip()
    team_b = (data.get("team_b") or "").strip()
    if not team_a or not team_b:
        return jsonify({"error": "Faltan los nombres de los equipos"}), 400

    is_national = bool(data.get("is_national", True))
    lineup_a = data.get("lineup_a") or None
    lineup_b = data.get("lineup_b") or None

    w = data.get("weights")
    if w:
        try:
            weights = WeightConfig(
                sofascore_form=float(w.get("sofascore_form", 0.25)),
                elo_rating=float(w.get("elo_rating", 0.25)),
                chemistry=float(w.get("chemistry", 0.20)),
                h2h=float(w.get("h2h", 0.15)),
                market_value=float(w.get("market_value", 0.15)),
            )
            weights.validate()
        except ValueError as e:
            return jsonify({"error": f"Pesos inválidos: {e}"}), 400
    else:
        weights = None

    try:
        results = run_prediction(
            team_a=team_a, team_b=team_b, is_national=is_national,
            lineup_a=lineup_a, lineup_b=lineup_b, weights=weights,
        )
        return jsonify(results)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Error en el análisis: {e}"}), 500


@app.route("/api/kelly", methods=["POST"])
def kelly():
    data = request.get_json(force=True)
    try:
        model_probs = {
            "home": float(data["p_home"]) / 100,
            "draw": float(data["p_draw"]) / 100,
            "away": float(data["p_away"]) / 100,
        }
        odds = {
            "home": float(data["odds_home"]),
            "draw": float(data["odds_draw"]),
            "away": float(data["odds_away"]),
        }
        bankroll = float(data["bankroll"])
        kelly_mult = float(data.get("kelly_multiplier", 0.25))
        result = analyze_bankroll(
            model_probs=model_probs, odds=odds, bankroll=bankroll,
            kelly_fraction_multiplier=kelly_mult,
            team_a=data.get("team_a", "Local"),
            team_b=data.get("team_b", "Visitante"),
            currency=data.get("currency", "COP"),
        )
        if result.get("best_bet"):
            b = result["best_bet"]
            result["simulation"] = simulate_growth(
                win_prob=b["model_prob"], decimal_odds=b["decimal_odds"],
                kelly_mult=kelly_mult, bankroll=bankroll,
                n_bets=100, n_simulations=400,
            )
        return jsonify(result)
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Datos inválidos: {e}"}), 400


@app.route("/api/backtest", methods=["POST"])
def backtest():
    data = request.get_json(force=True)
    predictions = data.get("predictions", [])
    if not predictions:
        return jsonify({"error": "Sin predicciones para evaluar"}), 400
    return jsonify(run_backtest(predictions))


@app.route("/api/ai/analyze", methods=["POST"])
def ai_analyze():
    """Genera el análisis experto con IA (Gemini) de un partido ya predicho."""
    if not gemini.has_gemini():
        return jsonify({"available": False, "reason": "Gemini no configurado"}), 200
    data = request.get_json(force=True)
    prediction_data = data.get("prediction_data")
    if not prediction_data:
        return jsonify({"error": "Falta prediction_data"}), 400
    api_preds = data.get("api_predictions")
    injuries = data.get("injuries")
    result = gemini.analyze_match(prediction_data, api_preds, injuries)
    return jsonify(result)


@app.route("/api/fixture/predictions/<int:fixture_id>")
def fixture_predictions(fixture_id):
    return jsonify(apif.get_fixture_predictions(fixture_id))


@app.route("/api/fixture/injuries")
def fixture_injuries():
    team_id = request.args.get("team", type=int)
    season = request.args.get("season", type=int)
    if not team_id or not season:
        return jsonify({"injuries": []})
    return jsonify({"injuries": apif.get_team_injuries(team_id, season)})


@app.route("/api/scan", methods=["POST"])
def scan_bankroll():
    """
    Escáner de banca multi-partido.
    Recibe una liga y temporada, evalúa los próximos partidos en todos los
    mercados, y devuelve la cartera óptima de apuestas con Kelly.
    """
    data = request.get_json(force=True)
    league_id = data.get("league_id")
    season = data.get("season")
    bankroll = float(data.get("bankroll", 100000))
    kelly_mult = float(data.get("kelly_mult", 0.5))
    max_exposure = float(data.get("max_exposure", 0.25))
    currency = data.get("currency", "COP")
    days = int(data.get("days", 7))

    if not config.has_apifootball():
        return jsonify({"error": "API-Football requerida para el escáner"}), 200
    if not league_id or not season:
        return jsonify({"error": "Faltan league_id y season"}), 400

    from engine.pipeline import run_prediction
    from scrapers import apifootball_adapter as afa

    fixtures = apif.get_upcoming_fixtures(league_id, season, days)
    all_value_bets = []
    analyzed = []

    # Limitar a 8 partidos por escaneo para controlar cuota de API
    for fx in fixtures[:8]:
        fid = fx.get("fixture_id")
        home = fx.get("home", {}).get("name")
        away = fx.get("away", {}).get("name")
        if not home or not away:
            continue
        try:
            # Predicción del modelo
            pred = run_prediction(home, away, is_national=False)
            p = pred["prediction"]["prediction"]
            model_probs = derive_market_probabilities(
                p["p_win_a"] / 100, p["p_draw"] / 100, p["p_win_b"] / 100,
                p.get("xg_a", 1.3), p.get("xg_b", 1.1),
            )
            # Cuotas multi-mercado reales
            odds = apif.get_multi_market_odds(fid) if fid else {}
            match_info = {"match": f"{home} vs {away}", "fixture_id": fid,
                          "home": home, "away": away, "date": fx.get("date")}
            vbets = scan_match(match_info, model_probs, odds)
            all_value_bets.extend(vbets)
            analyzed.append(match_info["match"])
        except Exception as e:
            print(f"[scan] Error en {home} vs {away}: {e}")
            continue

    portfolio = build_portfolio(
        all_value_bets, bankroll=bankroll, kelly_mult=kelly_mult,
        max_exposure=max_exposure, currency=currency,
    )
    portfolio["analyzed_matches"] = analyzed
    portfolio["total_fixtures_scanned"] = len(analyzed)

    # Resumen IA opcional
    if gemini.has_gemini() and portfolio.get("has_value"):
        portfolio["ai_summary"] = gemini.explain_bankroll_scan(portfolio, bankroll, currency)

    return jsonify(portfolio)


@app.route("/api/cache/stats")
def cache_status():
    return jsonify(cache_stats())


@app.route("/api/cache/clear", methods=["POST"])
def cache_wipe():
    return jsonify({"cleared": cache_clear()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print("=" * 52)
    print(f"  VagoScore v2 corriendo en http://localhost:{port}")
    print(f"  API-Football: {'conectada' if config.has_apifootball() else 'sin clave'}")
    print("=" * 52)
    app.run(host="0.0.0.0", port=port, debug=debug)
