"""
VagoScore — Módulo Quant Avanzado

Implementa tres mejoras de alto valor inspiradas en metodología de apuestas
cuantitativas, adaptadas de básquetbol a FÚTBOL y a los datos que la app ya
tiene (API-Football). Cada función está aislada para poder probarse sola.

1. HFA (Home-Field Advantage): ventaja de localía en la expectativa Elo.
2. Devigging MPTO (Margin Proportional to Odds): extrae la probabilidad
   "justa" del mercado de forma más precisa que el método proporcional simple.
3. Stop-loss de bankroll: reduce Kelly a la mitad si el drawdown supera un umbral.

También deja preparada (sin activar por defecto) una optimización de cartera
con scipy que maximiza el logaritmo esperado de la riqueza.
"""

import math


# ════════════════════════════════════════════════════════════════════════
# MÓDULO 1 (adaptado) — Expectativa Elo con Ventaja de Localía (HFA)
# ════════════════════════════════════════════════════════════════════════

# En fútbol, la ventaja de localía equivale históricamente a ~60-70 puntos Elo.
# (En las grandes ligas el local gana ~45-46% de los partidos, empata ~26%.)
DEFAULT_HFA = 65


def elo_expectancy(rating_team: int, rating_opp: int,
                   is_home: bool = False, hfa: int = DEFAULT_HFA) -> float:
    """
    Expectativa de resultado de un equipo según Elo, con ventaja de localía.

    E_A = 1 / (1 + 10^((R_B - (R_A + HFA)) / 400))

    El HFA solo se suma al equipo que juega de local. Devuelve un valor 0-1
    que representa la "fuerza relativa esperada" (no es directamente P(victoria)
    porque en fútbol existe el empate; eso se modela aparte).
    """
    adj = rating_team + (hfa if is_home else 0)
    return 1.0 / (1.0 + 10 ** ((rating_opp - adj) / 400))


def elo_probabilities_3way(elo_home: int, elo_away: int,
                           hfa: int = DEFAULT_HFA) -> dict:
    """
    Convierte dos Elo en probabilidades 1X2 (local/empate/visitante)
    incorporando la ventaja de localía y un modelo de empate calibrado
    para fútbol.
    """
    # Expectativa del local CON ventaja de localía
    e_home = elo_expectancy(elo_home, elo_away, is_home=True, hfa=hfa)
    # La expectativa Elo reparte el "no-empate". Modelamos el empate según
    # cuán parejos estén: máximo de empates cuando la expectativa ~0.5.
    diff = abs(e_home - 0.5)
    # Probabilidad de empate en fútbol: ~0.28 en partidos parejos, baja con la diferencia
    p_draw = 0.28 * math.exp(-(diff ** 2) / 0.08)
    # Repartir el resto según la expectativa Elo
    p_home = e_home * (1 - p_draw)
    p_away = (1 - e_home) * (1 - p_draw)
    # Normalizar
    total = p_home + p_draw + p_away
    return {
        "home": round(p_home / total, 4),
        "draw": round(p_draw / total, 4),
        "away": round(p_away / total, 4),
        "hfa_applied": hfa,
    }


# ════════════════════════════════════════════════════════════════════════
# MÓDULO 3 — Desparasitado de cuotas: Método MPTO
# ════════════════════════════════════════════════════════════════════════

def implied_raw(decimal_odds: float) -> float:
    """Probabilidad bruta implícita de una cuota decimal."""
    return 1.0 / decimal_odds if decimal_odds > 0 else 0.0


def devig_proportional(odds: list) -> list:
    """
    Método PROPORCIONAL simple (el que la app usaba antes).
    Divide cada probabilidad bruta por el total. Rápido pero asume que la
    casa reparte el margen por igual, lo cual no es cierto en favoritos extremos.
    """
    raw = [implied_raw(o) for o in odds]
    total = sum(raw)
    if total <= 0:
        return [0.0] * len(odds)
    return [r / total for r in raw]


def devig_mpto(odds: list, max_iter: int = 60, tol: float = 1e-9) -> list:
    """
    Método MPTO (Margin Proportional to Odds).

    Idea: la casa de apuestas no reparte el margen por igual entre opciones.
    Carga MÁS margen sobre los favoritos (cuotas bajas) y menos sobre los
    underdogs. MPTO modela esto: el margen aplicado a cada opción es
    proporcional a su cuota.

    Para una opción con cuota o_i y probabilidad justa p_i:
        1/o_i = p_i * (1 + margin * o_i / n)   (forma simplificada)

    Resolvemos el margen 'm' tal que las probabilidades justas sumen 1,
    por bisección (robusto y rápido).

    Devuelve las probabilidades justas (sin vig), más precisas que el método
    proporcional cuando hay favoritos marcados.
    """
    n = len(odds)
    raw = [implied_raw(o) for o in odds]
    overround = sum(raw)  # > 1 por el margen
    if overround <= 1.0:
        # Sin margen (raro): ya está limpio
        return raw

    # MPTO: fair_p_i = 1 / (o_i + m), buscamos m tal que sum(fair_p) = 1
    def total_with_margin(m):
        return sum(1.0 / (o + m) for o in odds)

    # Bisección sobre m. m=0 da overround>1; m grande baja el total hacia 0.
    lo, hi = 0.0, 10.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        t = total_with_margin(mid)
        if abs(t - 1.0) < tol:
            break
        if t > 1.0:
            lo = mid
        else:
            hi = mid
    m = (lo + hi) / 2
    fair = [1.0 / (o + m) for o in odds]
    # Normalización final por seguridad numérica
    s = sum(fair)
    return [f / s for f in fair]


def fair_probabilities(odds_home: float, odds_draw: float, odds_away: float,
                       method: str = "mpto") -> dict:
    """
    Probabilidades justas 1X2 quitando el margen de la casa.
    method: 'mpto' (preciso, por defecto) o 'proportional' (simple).
    """
    odds = [odds_home, odds_draw, odds_away]
    probs = devig_mpto(odds) if method == "mpto" else devig_proportional(odds)
    raw_total = sum(implied_raw(o) for o in odds)
    return {
        "home": round(probs[0], 4),
        "draw": round(probs[1], 4),
        "away": round(probs[2], 4),
        "margin_pct": round((raw_total - 1) * 100, 2),
        "method": method,
    }


# ════════════════════════════════════════════════════════════════════════
# MÓDULO 5 — Gestión de riesgo: Stop-loss de bankroll
# ════════════════════════════════════════════════════════════════════════

def apply_stop_loss(kelly_mult: float, current_bankroll: float,
                    peak_bankroll: float, drawdown_threshold: float = 0.25,
                    reduction: float = 0.5) -> dict:
    """
    Regla de stop-loss: si el bankroll cayó más que `drawdown_threshold`
    desde su máximo, reduce el multiplicador de Kelly por `reduction`.

    Protege la banca en malas rachas (reduce la exposición justo cuando
    el modelo está rindiendo peor de lo esperado).

    Devuelve el multiplicador ajustado y el estado del drawdown.
    """
    if peak_bankroll <= 0:
        return {"kelly_mult": kelly_mult, "drawdown_pct": 0.0, "triggered": False}

    drawdown = (peak_bankroll - current_bankroll) / peak_bankroll
    triggered = drawdown >= drawdown_threshold
    adjusted = kelly_mult * reduction if triggered else kelly_mult

    return {
        "kelly_mult": round(adjusted, 4),
        "original_mult": kelly_mult,
        "drawdown_pct": round(drawdown * 100, 1),
        "threshold_pct": round(drawdown_threshold * 100, 1),
        "triggered": triggered,
        "message": (
            f"⚠ Stop-loss activo: drawdown {drawdown*100:.0f}% ≥ "
            f"{drawdown_threshold*100:.0f}%. Kelly reducido a la mitad para "
            f"proteger la banca."
        ) if triggered else None,
    }


# ════════════════════════════════════════════════════════════════════════
# MÓDULO 5 (avanzado, PREPARADO PERO NO ACTIVADO) — Kelly simultáneo con scipy
# ════════════════════════════════════════════════════════════════════════

def optimize_portfolio_scipy(bets: list, bankroll: float = 1.0):
    """
    Optimización de cartera que maximiza el logaritmo esperado de la riqueza
    sobre TODOS los escenarios posibles, usando scipy.optimize.

    bets: lista de {p, decimal_odds} (probabilidad del modelo y cuota)

    Maximiza:  E[ln(riqueza)] = Σ_escenarios P(escenario) · ln(1 + Σ f_i·R_i·outcome)
    sujeto a:  Σ f_i ≤ 1,  0 ≤ f_i ≤ 1

    ⚠ NO se usa por defecto: para 5-8 apuestas la heurística de Kelly
    fraccionario da prácticamente el mismo resultado con mucho menos costo.
    Se deja lista por si se quiere activar para carteras donde la correlación
    entre apuestas importe. Requiere scipy y numpy instalados.

    Devuelve las fracciones óptimas f_i o None si scipy no está disponible.
    """
    try:
        import numpy as np
        from scipy.optimize import minimize
        from itertools import product
    except ImportError:
        return None

    m = len(bets)
    if m == 0:
        return []
    if m > 12:
        # 2^m escenarios sería demasiado; usar heurística de Whitrow
        return _whitrow_fallback(bets)

    probs = np.array([b["p"] for b in bets])
    net_odds = np.array([b["decimal_odds"] - 1 for b in bets])  # ganancia neta

    # Todos los escenarios win/lose (2^m)
    scenarios = list(product([0, 1], repeat=m))

    def neg_expected_log(fractions):
        total = 0.0
        for outcome in scenarios:
            outcome = np.array(outcome)
            # P(escenario) asumiendo independencia
            p_scn = np.prod([probs[i] if outcome[i] else (1 - probs[i])
                             for i in range(m)])
            # Riqueza resultante: gano f·odds en las ganadoras, pierdo f en las perdedoras
            wealth = 1.0 + np.sum(fractions * (outcome * net_odds - (1 - outcome)))
            if wealth <= 0:
                return 1e9  # ruina: penalización máxima
            total += p_scn * math.log(wealth)
        return -total

    constraints = [{"type": "ineq", "fun": lambda f: 1.0 - np.sum(f)}]
    bounds = [(0, 1)] * m
    x0 = np.full(m, 0.5 / m)

    result = minimize(neg_expected_log, x0, method="SLSQP",
                      bounds=bounds, constraints=constraints)
    return result.x.tolist() if result.success else _whitrow_fallback(bets)


def _whitrow_fallback(bets: list) -> list:
    """
    Heurística de Whitrow: para carteras masivas, asigna fracciones
    proporcionales a la ventaja probabilística pura (edge).
    Edge_i = p_i - 1/odds_i
    """
    edges = [max(0, b["p"] - 1.0 / b["decimal_odds"]) for b in bets]
    total = sum(edges)
    if total <= 0:
        return [0.0] * len(bets)
    return [e / total for e in edges]
