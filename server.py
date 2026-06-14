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
from engine.weight_optimizer import optimize_weights
from cache.db import cache_stats, cache_clear
from scrapers import apifootball as apif
from scrapers import gemini

app = Flask(__name__, static_folder="web", static_url_path="")


@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/api/status")
def status():
    import os
    # Diagnóstico: qué variables de entorno relacionadas con IA existen
    # (mostramos solo si existen y su longitud, NUNCA el valor real)
    deepseek_present = "DEEPSEEK_API_KEY" in os.environ
    deepseek_len = len(os.environ.get("DEEPSEEK_API_KEY", ""))
    # Buscar variables con nombres parecidos (errores comunes de tipeo)
    similar_keys = [k for k in os.environ.keys()
                    if "DEEPSEEK" in k.upper() or "DEEP_SEEK" in k.upper()
                    or "GEMINI" in k.upper() or "AI_KEY" in k.upper()]
    return jsonify({
        "apifootball_connected": config.has_apifootball(),
        "ai_connected": gemini.has_ai(),
        "cache": cache_stats(),
        "diagnostico_ia": {
            "variable_DEEPSEEK_API_KEY_existe": deepseek_present,
            "longitud_de_la_clave": deepseek_len,
            "empieza_con_sk": os.environ.get("DEEPSEEK_API_KEY", "").startswith("sk-"),
            "variables_parecidas_encontradas": similar_keys,
        },
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
    home_id = request.args.get("home_id", type=int)
    away_id = request.args.get("away_id", type=int)
    league_id = request.args.get("league", type=int)

    # 1. Intentar alineación CONFIRMADA
    confirmed = apif.get_lineup_with_values(fixture_id, season)
    has_confirmed = confirmed and (
        (confirmed.get("home", {}).get("starters")) or
        (confirmed.get("away", {}).get("starters"))
    )
    if has_confirmed:
        confirmed["status"] = "confirmed"
        return jsonify(confirmed)

    # 2. Si no hay confirmada, generar la PROBABLE para ambos equipos
    from scrapers import apifootball_adapter as afa
    result = {"status": "probable", "home": {}, "away": {}}
    if season and home_id:
        try:
            result["home"] = afa.get_probable_lineup(home_id, season, league_id)
        except Exception as e:
            print(f"[lineup] probable home error: {e}")
    if season and away_id:
        try:
            result["away"] = afa.get_probable_lineup(away_id, season, league_id)
        except Exception as e:
            print(f"[lineup] probable away error: {e}")
    return jsonify(result)


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


@app.route("/api/live/<int:fixture_id>")
def live_detail(fixture_id):
    """Detalle completo de un partido en vivo con sugerencias."""
    detail = apif.get_live_match_detail(fixture_id)
    if not detail:
        return jsonify({"error": "Partido no encontrado o no está en vivo"}), 200

    suggestions = []
    try:
        hg = detail["home"]["goals"] or 0
        ag = detail["away"]["goals"] or 0
        elapsed = detail.get("elapsed") or 0
        total_goals = hg + ag
        poss_home = detail["stats"].get("home", {}).get("Ball Possession")

        if elapsed and elapsed < 70:
            if total_goals >= 2:
                suggestions.append({
                    "market": "Más de 2.5 goles",
                    "reason": f"Ya van {total_goals} goles en el minuto {elapsed}. El ritmo favorece el over.",
                })
            elif total_goals == 0 and elapsed > 30:
                suggestions.append({
                    "market": "Menos de 2.5 goles",
                    "reason": f"0-0 al minuto {elapsed}. Partido trabado, el under gana fuerza.",
                })
        if hg > ag:
            suggestions.append({
                "market": f"Gana {detail['home']['name']}",
                "reason": f"Va ganando {hg}-{ag}" + (f" con {poss_home} de posesión." if poss_home else "."),
            })
        elif ag > hg:
            suggestions.append({
                "market": f"Gana {detail['away']['name']}",
                "reason": f"Va ganando {ag}-{hg} como visitante.",
            })
    except Exception as e:
        print(f"[live] suggestion error: {e}")

    detail["live_suggestions"] = suggestions
    detail["disclaimer"] = ("Sugerencias en vivo basadas solo en el estado actual "
                            "del partido. El fútbol cambia en segundos. No es consejo de apuesta.")
    return jsonify(detail)


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


@app.route("/api/ai/test")
def ai_test():
    """Prueba real la conexión con Deepseek y devuelve el error exacto si falla."""
    return jsonify(gemini.test_connection())


@app.route("/api/transfermarkt/test")
def tm_test():
    """Diagnóstico de la conexión con Transfermarkt API."""
    from scrapers import transfermarkt_api as tm
    return jsonify(tm.test_connection())


@app.route("/api/ai/analyze", methods=["POST"])
def ai_analyze():
    """Genera el análisis experto con IA (Deepseek) de un partido ya predicho."""
    if not gemini.has_ai():
        return jsonify({"available": False, "reason": "IA no configurada"}), 200
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
    bookmakers_used = set()

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
            raw = pred["prediction"].get("raw", {})

            ph, pd, pa = p["p_win_a"] / 100, p["p_draw"] / 100, p["p_win_b"] / 100

            # Ajuste por ventaja de localía (HFA): si tenemos Elo de ambos,
            # mezclamos la probabilidad del modelo con la probabilidad Elo que
            # incorpora la localía del equipo de casa. Blend 70/30 para no
            # sobre-corregir (el modelo ya captura parte de la fuerza).
            elo_h, elo_a = raw.get("elo_a"), raw.get("elo_b")
            if elo_h and elo_a:
                from engine.quant import elo_probabilities_3way
                elo_p = elo_probabilities_3way(elo_h, elo_a)
                ph = 0.7 * ph + 0.3 * elo_p["home"]
                pd = 0.7 * pd + 0.3 * elo_p["draw"]
                pa = 0.7 * pa + 0.3 * elo_p["away"]
                tot = ph + pd + pa
                ph, pd, pa = ph / tot, pd / tot, pa / tot

            model_probs = derive_market_probabilities(
                ph, pd, pa, p.get("xg_a", 1.3), p.get("xg_b", 1.1),
            )
            # Cuotas multi-mercado reales
            odds = apif.get_multi_market_odds(fid) if fid else {}
            for bm in odds.get("_bookmakers", []):
                bookmakers_used.add(bm)
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
    portfolio["bookmakers_used"] = sorted(bookmakers_used)

    # Resumen IA opcional
    if gemini.has_ai() and portfolio.get("has_value"):
        portfolio["ai_summary"] = gemini.explain_bankroll_scan(portfolio, bankroll, currency)

    return jsonify(portfolio)


@app.route("/api/optimize-weights", methods=["POST"])
def optimize_weights_endpoint():
    """
    Ajusta los pesos del modelo a partir de partidos históricos.
    Recibe una lista de partidos con sub-scores y resultado real, o
    los genera desde un conjunto de equipos/liga si se pide.
    """
    data = request.get_json(force=True)
    historical = data.get("historical", [])
    iterations = int(data.get("iterations", 3000))

    if not historical:
        return jsonify({
            "success": False,
            "reason": "No se proporcionaron partidos históricos. "
                      "Esta función necesita datos de partidos ya jugados con "
                      "sus sub-scores y resultados reales.",
        }), 200

    result = optimize_weights(historical, iterations=iterations)
    return jsonify(result)


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
