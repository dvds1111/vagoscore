"""
VagoScore — Motor de gestión de banca (Criterio de Kelly)

El criterio de Kelly calcula la fracción óptima de la banca a apostar para
maximizar el crecimiento logarítmico del capital a largo plazo.

Fórmula:  f* = (b·p − q) / b   =   (p·cuota − 1) / (cuota − 1)
  donde:
    p     = probabilidad real de ganar (estimada por nuestro modelo)
    q     = 1 − p
    b     = cuota decimal − 1 (ganancia neta por unidad apostada)
    cuota = cuota decimal de la casa

VALOR (edge) = p·cuota − 1.  Solo hay apuesta de valor si edge > 0,
es decir, si nuestra probabilidad supera la probabilidad implícita de la cuota.

⚠️ Kelly COMPLETO es matemáticamente óptimo pero muy volátil. La práctica
profesional usa Kelly FRACCIONARIO (1/4 a 1/2) para reducir varianza.
Esta es una herramienta de cálculo, NO un consejo financiero.
"""

import math
from dataclasses import dataclass


def implied_probability(decimal_odds: float) -> float:
    """Probabilidad que la casa de apuestas asigna (incluye su margen)."""
    if decimal_odds <= 1:
        return 1.0
    return round(1 / decimal_odds, 4)


def remove_margin(odds_home: float, odds_draw: float, odds_away: float) -> dict:
    """
    Quita el margen de la casa ('vig') para obtener probabilidades 'justas'.
    Método de normalización proporcional.
    """
    if not all([odds_home, odds_draw, odds_away]):
        return {}
    raw = [1/odds_home, 1/odds_draw, 1/odds_away]
    total = sum(raw)  # > 1 por el margen
    margin = round((total - 1) * 100, 2)
    fair = [r / total for r in raw]
    return {
        "fair_home": round(fair[0], 4),
        "fair_draw": round(fair[1], 4),
        "fair_away": round(fair[2], 4),
        "bookmaker_margin_pct": margin,
    }


def kelly_fraction(p: float, decimal_odds: float) -> float:
    """
    Fracción de Kelly completo para una apuesta.
    Devuelve 0 si no hay valor (no apostar).
    """
    if decimal_odds <= 1 or p <= 0:
        return 0.0
    b = decimal_odds - 1
    q = 1 - p
    f = (b * p - q) / b
    return max(0.0, round(f, 4))


@dataclass
class BetRecommendation:
    outcome: str          # "home" | "draw" | "away"
    outcome_label: str    # nombre legible
    model_prob: float     # nuestra probabilidad (0-1)
    decimal_odds: float
    implied_prob: float   # prob. de la casa
    edge_pct: float       # ventaja %
    kelly_full: float     # fracción Kelly completo
    kelly_used: float     # fracción tras aplicar el multiplicador
    stake: float          # cantidad a apostar
    potential_profit: float
    potential_return: float


def analyze_bankroll(
    model_probs: dict,       # {"home": 0.45, "draw": 0.27, "away": 0.28}
    odds: dict,              # {"home": 2.10, "draw": 3.40, "away": 3.20}
    bankroll: float,
    kelly_fraction_multiplier: float = 0.25,  # 1/4 Kelly por defecto
    team_a: str = "Local",
    team_b: str = "Visitante",
    currency: str = "COP",
) -> dict:
    """
    Analiza un partido y recomienda apuestas de valor con sizing de Kelly.

    Args:
        model_probs: probabilidades del modelo (suman ~1)
        odds: cuotas decimales de la casa
        bankroll: capital total disponible
        kelly_fraction_multiplier: 0.25 = cuarto Kelly, 0.5 = medio, 1.0 = completo
        currency: divisa para mostrar

    Returns:
        Análisis completo con recomendaciones, valor esperado y métricas de riesgo.
    """
    labels = {"home": f"Gana {team_a}", "draw": "Empate", "away": f"Gana {team_b}"}

    recommendations = []
    fair = {}

    # Calcular probabilidades justas si tenemos las 3 cuotas
    if all(odds.get(k) for k in ("home", "draw", "away")):
        fair = remove_margin(odds["home"], odds["draw"], odds["away"])

    for outcome in ("home", "draw", "away"):
        p = model_probs.get(outcome, 0)
        o = odds.get(outcome)
        if not o or o <= 1:
            continue

        imp = implied_probability(o)
        edge = p * o - 1               # valor esperado por unidad
        kf = kelly_fraction(p, o)
        kf_used = kf * kelly_fraction_multiplier
        stake = round(bankroll * kf_used, 0)
        profit = round(stake * (o - 1), 0)

        rec = BetRecommendation(
            outcome=outcome,
            outcome_label=labels[outcome],
            model_prob=round(p, 4),
            decimal_odds=o,
            implied_prob=imp,
            edge_pct=round(edge * 100, 2),
            kelly_full=kf,
            kelly_used=round(kf_used, 4),
            stake=stake,
            potential_profit=profit,
            potential_return=round(stake + profit, 0),
        )
        recommendations.append(rec)

    # Ordenar por edge (mayor valor primero)
    recommendations.sort(key=lambda r: r.edge_pct, reverse=True)

    # Apuestas de valor = edge positivo
    value_bets = [r for r in recommendations if r.edge_pct > 0]
    best = value_bets[0] if value_bets else None

    total_recommended_stake = round(sum(r.stake for r in value_bets), 0)

    # Métrica de riesgo: % de banca comprometida
    exposure_pct = round((total_recommended_stake / bankroll) * 100, 1) if bankroll else 0

    value_bets_dict = [r.__dict__ for r in value_bets]

    return {
        "bankroll": bankroll,
        "currency": currency,
        "kelly_multiplier": kelly_fraction_multiplier,
        "fair_probabilities": fair,
        "recommendations": [r.__dict__ for r in recommendations],
        "value_bets": value_bets_dict,
        "best_bet": best.__dict__ if best else None,
        "has_value": bool(value_bets),
        "total_stake": total_recommended_stake,
        "exposure_pct": exposure_pct,
        "verdict": _verdict(value_bets_dict, exposure_pct, team_a, team_b),
    }


def _verdict(value_bets, exposure_pct, team_a, team_b) -> str:
    """Resumen legible de la recomendación."""
    if not value_bets:
        return ("Ninguna apuesta tiene valor positivo según el modelo. "
                "Las cuotas no compensan el riesgo — lo óptimo es NO apostar este partido.")
    best = value_bets[0]
    return (f"Apuesta de valor detectada: «{best['outcome_label']}» con un edge de "
            f"{best['edge_pct']}%. El modelo le da {round(best['model_prob']*100,1)}% "
            f"vs {round(best['implied_prob']*100,1)}% implícito en la cuota. "
            f"Exposición total recomendada: {exposure_pct}% de la banca.")


def simulate_growth(
    win_prob: float,
    decimal_odds: float,
    kelly_mult: float,
    bankroll: float,
    n_bets: int = 100,
    n_simulations: int = 500,
) -> dict:
    """
    Simulación Monte Carlo del crecimiento de la banca repitiendo
    una apuesta con las mismas características N veces.
    Muestra la distribución de resultados (mediana, percentiles, ruina).
    """
    import random

    kf = kelly_fraction(win_prob, decimal_odds) * kelly_mult
    final_bankrolls = []
    ruin_count = 0

    for _ in range(n_simulations):
        capital = bankroll
        for _ in range(n_bets):
            if capital < bankroll * 0.01:  # ruina práctica
                ruin_count += 1
                capital = 0
                break
            stake = capital * kf
            if random.random() < win_prob:
                capital += stake * (decimal_odds - 1)
            else:
                capital -= stake
        final_bankrolls.append(capital)

    final_bankrolls.sort()
    n = len(final_bankrolls)

    def pct(p):
        return round(final_bankrolls[min(n-1, int(n * p))], 0)

    return {
        "kelly_fraction_used": round(kf, 4),
        "median_final": pct(0.5),
        "p10": pct(0.1),
        "p90": pct(0.9),
        "best_case": round(max(final_bankrolls), 0),
        "worst_case": round(min(final_bankrolls), 0),
        "ruin_probability_pct": round((ruin_count / n_simulations) * 100, 1),
        "n_bets": n_bets,
        "starting_bankroll": bankroll,
    }
