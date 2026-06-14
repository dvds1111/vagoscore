"""
VagoScore — Escáner de banca multi-partido (Kelly de cartera)

Evalúa varios partidos a la vez, en TODOS los mercados disponibles
(1X2, over/under 2.5, ambos marcan, doble oportunidad), detecta dónde
hay valor según el modelo, y reparte el capital con Kelly fraccionario
tratando la jornada como una CARTERA, no apuestas aisladas.

Reglas de gestión de riesgo (equilibrado por defecto):
  - Medio Kelly (½) por defecto
  - Tope de exposición total del 25% de la banca por jornada
  - Si la suma de stakes supera el tope, se escala todo proporcionalmente

⚠️ Herramienta de cálculo, no consejo financiero. El rendimiento pasado
no garantiza resultados futuros.
"""

from engine.kelly import kelly_fraction, implied_probability


# ─── Modelos de probabilidad por mercado ──────────────────────────────────────

def derive_market_probabilities(p_home: float, p_draw: float, p_away: float,
                                 xg_home: float, xg_away: float) -> dict:
    """
    A partir de las probabilidades 1X2 del modelo y los xG, deriva
    probabilidades para los demás mercados.
    """
    import math

    probs = {
        # 1X2
        "Home": p_home,
        "Draw": p_draw,
        "Away": p_away,
        # Doble oportunidad
        "Home/Draw": p_home + p_draw,
        "Home/Away": p_home + p_away,
        "Draw/Away": p_draw + p_away,
    }

    # Over/Under 2.5 vía Poisson sobre xG total
    total_xg = max(0.1, (xg_home or 1.2) + (xg_away or 1.0))
    # P(0,1,2 goles) con Poisson
    def poisson(k, lam):
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
    p_under_25 = poisson(0, total_xg) + poisson(1, total_xg) + poisson(2, total_xg)
    probs["Under 2.5"] = round(p_under_25, 4)
    probs["Over 2.5"] = round(1 - p_under_25, 4)

    # Ambos marcan (BTTS): aproximación con prob. de que cada equipo marque
    p_home_scores = 1 - poisson(0, max(0.1, xg_home or 1.2))
    p_away_scores = 1 - poisson(0, max(0.1, xg_away or 1.0))
    p_btts_yes = p_home_scores * p_away_scores
    probs["Yes"] = round(p_btts_yes, 4)
    probs["No"] = round(1 - p_btts_yes, 4)

    return probs


# Etiquetas legibles por opción de mercado
MARKET_LABELS = {
    "Home": "Gana local", "Draw": "Empate", "Away": "Gana visitante",
    "Over 2.5": "Más de 2.5 goles", "Under 2.5": "Menos de 2.5 goles",
    "Yes": "Ambos marcan: Sí", "No": "Ambos marcan: No",
    "Home/Draw": "Local o empate", "Home/Away": "Local o visitante",
    "Draw/Away": "Empate o visitante",
}

# Mapeo de mercado interno → claves de cuotas de API-Football
ODDS_MAP = {
    "match_winner": ["Home", "Draw", "Away"],
    "over_under": ["Over 2.5", "Under 2.5"],
    "btts": ["Yes", "No"],
    "double_chance": ["Home/Draw", "Home/Away", "Draw/Away"],
}


def scan_match(match_info: dict, model_probs: dict, odds: dict) -> list:
    """
    Para un partido, encuentra todas las apuestas de valor en todos los mercados.

    Args:
        match_info: {match, fixture_id, home, away}
        model_probs: dict de probabilidades por opción (de derive_market_probabilities)
        odds: cuotas multi-mercado de API-Football {match_winner:{Home:..}, ...}

    Returns: lista de apuestas con valor (edge > 0)
    """
    value_bets = []

    for market_key, options in ODDS_MAP.items():
        market_odds = odds.get(market_key, {})
        for opt in options:
            # Buscar la cuota (las claves de over/under en la API pueden variar)
            odd = market_odds.get(opt)
            if odd is None and market_key == "over_under":
                # API a veces usa "Over"/"Under" con línea aparte
                odd = market_odds.get(opt.split()[0])
            if not odd or odd <= 1:
                continue

            p = model_probs.get(opt, 0)
            if p <= 0:
                continue

            edge = p * odd - 1
            if edge > 0.03:  # umbral mínimo de valor: 3%
                kf = kelly_fraction(p, odd)
                value_bets.append({
                    "match": match_info.get("match"),
                    "fixture_id": match_info.get("fixture_id"),
                    "home": match_info.get("home"),
                    "away": match_info.get("away"),
                    "date": match_info.get("date"),
                    "market": market_key,
                    "option": opt,
                    "bet_label": MARKET_LABELS.get(opt, opt),
                    "model_prob": round(p, 4),
                    "implied_prob": implied_probability(odd),
                    "decimal_odds": odd,
                    "edge_pct": round(edge * 100, 2),
                    "kelly_full": kf,
                })

    return value_bets


def build_portfolio(all_value_bets: list, bankroll: float,
                    kelly_mult: float = 0.5, max_exposure: float = 0.25,
                    currency: str = "COP", max_bets: int = 12) -> dict:
    """
    Construye la cartera de apuestas de una jornada con Kelly de cartera.

    Args:
        all_value_bets: todas las apuestas de valor de todos los partidos
        bankroll: capital total
        kelly_mult: fracción de Kelly (0.5 = medio)
        max_exposure: tope de exposición total (0.25 = 25% de la banca)
        max_bets: máximo de apuestas en la cartera

    Returns: cartera con stakes finales y métricas de riesgo.
    """
    if not all_value_bets:
        return {
            "recommended_bets": [], "total_stake": 0, "total_exposure_pct": 0,
            "n_bets": 0, "has_value": False,
            "verdict": "No se encontraron apuestas de valor en los partidos analizados. "
                       "Lo óptimo es no apostar esta jornada.",
        }

    # Ordenar por edge descendente y limitar
    bets = sorted(all_value_bets, key=lambda b: b["edge_pct"], reverse=True)[:max_bets]

    # Evitar apuestas contradictorias del mismo partido (ej. Over y Under)
    # Regla simple: máximo 1 apuesta por partido (la de mayor edge)
    seen_matches = set()
    filtered = []
    for b in bets:
        mid = b["fixture_id"] or b["match"]
        if mid in seen_matches:
            continue
        seen_matches.add(mid)
        filtered.append(b)
    bets = filtered

    # Stake bruto por Kelly fraccionario
    for b in bets:
        b["kelly_used"] = round(b["kelly_full"] * kelly_mult, 4)
        b["stake_raw"] = bankroll * b["kelly_used"]

    total_raw = sum(b["stake_raw"] for b in bets)
    max_total = bankroll * max_exposure

    # Si excede el tope de exposición, escalar todo proporcionalmente
    scale = 1.0
    if total_raw > max_total and total_raw > 0:
        scale = max_total / total_raw

    total_stake = 0
    for b in bets:
        b["stake"] = round(b["stake_raw"] * scale, 0)
        b["potential_profit"] = round(b["stake"] * (b["decimal_odds"] - 1), 0)
        b["potential_return"] = round(b["stake"] + b["potential_profit"], 0)
        total_stake += b["stake"]
        # Limpiar campos internos
        del b["stake_raw"]

    exposure_pct = round((total_stake / bankroll) * 100, 1) if bankroll else 0

    # Retorno esperado de la cartera (suma de EV)
    expected_value = sum(
        b["stake"] * (b["model_prob"] * b["decimal_odds"] - 1) for b in bets
    )

    return {
        "recommended_bets": bets,
        "total_stake": round(total_stake, 0),
        "total_exposure_pct": exposure_pct,
        "max_exposure_pct": round(max_exposure * 100, 1),
        "kelly_mult": kelly_mult,
        "n_bets": len(bets),
        "has_value": True,
        "expected_value": round(expected_value, 0),
        "was_scaled": scale < 1.0,
        "currency": currency,
        "verdict": _portfolio_verdict(bets, exposure_pct, expected_value, scale < 1.0, currency),
    }


def _portfolio_verdict(bets, exposure_pct, ev, was_scaled, currency) -> str:
    n = len(bets)
    best = bets[0]
    msg = (f"Cartera de {n} apuesta{'s' if n != 1 else ''} de valor para la jornada. "
           f"La mejor: «{best['bet_label']}» en {best['match']} (edge {best['edge_pct']}%). "
           f"Exposición total: {exposure_pct}% de la banca. "
           f"Valor esperado de la cartera: +{ev:,.0f} {currency}.")
    if was_scaled:
        msg += (" Se redujeron los montos proporcionalmente para respetar el tope "
                "de exposición de la jornada.")
    return msg
