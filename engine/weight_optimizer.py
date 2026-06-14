"""
VagoScore — Optimizador de pesos basado en datos históricos

Ajusta automáticamente los pesos de las 5 señales del modelo para que
predigan lo mejor posible los resultados ya conocidos.

Método: búsqueda aleatoria (random search) sobre el espacio de pesos que
suman 1, evaluando cada combinación con el Brier score (menor = mejor) sobre
un conjunto de partidos históricos con resultado real.

⚠️ Importante (honestidad estadística):
  - Optimizar sobre datos pasados NO garantiza rendimiento futuro.
  - Con pocos partidos, el riesgo de "sobreajuste" (overfitting) es alto:
    los pesos se acomodan al ruido del pasado, no a una señal real.
  - Por eso exigimos un mínimo de partidos y reportamos la mejora honestamente,
    avisando cuando la muestra es pequeña.
"""

import random
from dataclasses import asdict
from engine.scorer import WeightConfig, compute_vagoscore


MIN_MATCHES_RECOMMENDED = 30   # por debajo de esto, advertimos sobreajuste


def _brier_3way(probs: dict, actual: str) -> float:
    """
    Brier score para 3 resultados (1=local, X=empate, 2=visitante).
    probs: {'home':p, 'draw':p, 'away':p} en 0-1
    actual: 'home' | 'draw' | 'away'
    """
    target = {"home": 0, "draw": 0, "away": 0}
    target[actual] = 1
    return sum((probs[k] - target[k]) ** 2 for k in target)


def _random_weights() -> WeightConfig:
    """Genera un set de pesos aleatorio que suma 1.0 (Dirichlet simple)."""
    vals = [random.random() for _ in range(5)]
    s = sum(vals)
    vals = [v / s for v in vals]
    return WeightConfig(
        sofascore_form=round(vals[0], 3),
        elo_rating=round(vals[1], 3),
        chemistry=round(vals[2], 3),
        h2h=round(vals[3], 3),
        market_value=round(vals[4], 3),
    )


def _evaluate_weights(weights: WeightConfig, historical: list) -> float:
    """
    Evalúa un set de pesos sobre los partidos históricos.
    Devuelve el Brier score medio (menor = mejor).

    historical: lista de dicts, cada uno con:
        {
          "team_scores_a": {...},  # los 5 sub-scores ya calculados de A
          "team_scores_b": {...},  # los 5 sub-scores de B
          "actual": "home"|"draw"|"away"
        }
    Trabajamos con sub-scores pre-calculados para no re-scrapear nada.
    """
    if not historical:
        return 1.0

    total_brier = 0.0
    n = 0
    for match in historical:
        sa = match["team_scores_a"]
        sb = match["team_scores_b"]
        # Score ponderado de cada equipo con estos pesos
        score_a = (
            sa["sofascore"] * weights.sofascore_form +
            sa["elo"] * weights.elo_rating +
            sa["chemistry"] * weights.chemistry +
            sa["h2h"] * weights.h2h +
            sa["market"] * weights.market_value
        )
        score_b = (
            sb["sofascore"] * weights.sofascore_form +
            sb["elo"] * weights.elo_rating +
            sb["chemistry"] * weights.chemistry +
            sb["h2h"] * weights.h2h +
            sb["market"] * weights.market_value
        )
        # Convertir diferencia de score a probabilidades (logística + empate)
        probs = _scores_to_probs(score_a, score_b)
        total_brier += _brier_3way(probs, match["actual"])
        n += 1

    return total_brier / n if n else 1.0


def _scores_to_probs(score_a: float, score_b: float) -> dict:
    """
    Convierte dos scores (0-100) en probabilidades 1X2.
    Misma lógica que el scorer principal: logística sobre la diferencia.
    """
    import math
    diff = score_a - score_b
    # Probabilidad base de no-empate vía logística
    p_a_raw = 1 / (1 + math.exp(-diff / 12))
    # Empate: máximo cuando los equipos están parejos
    draw = 0.28 * math.exp(-(diff ** 2) / 800)
    p_a = p_a_raw * (1 - draw)
    p_b = (1 - p_a_raw) * (1 - draw)
    # Normalizar
    s = p_a + draw + p_b
    return {"home": p_a / s, "draw": draw / s, "away": p_b / s}


def optimize_weights(historical: list, iterations: int = 3000,
                     seed: int = None) -> dict:
    """
    Encuentra los mejores pesos por búsqueda aleatoria.

    Args:
        historical: partidos históricos con sub-scores y resultado real
        iterations: cuántas combinaciones probar

    Returns:
        dict con los pesos óptimos, el Brier base vs optimizado, y avisos.
    """
    if seed is not None:
        random.seed(seed)

    n_matches = len(historical)
    if n_matches < 5:
        return {
            "success": False,
            "reason": f"Se necesitan al menos 5 partidos históricos (tienes {n_matches}).",
        }

    # Brier con los pesos por defecto (punto de partida)
    default_weights = WeightConfig()
    base_brier = _evaluate_weights(default_weights, historical)

    # Búsqueda aleatoria
    best_weights = default_weights
    best_brier = base_brier

    for _ in range(iterations):
        candidate = _random_weights()
        brier = _evaluate_weights(candidate, historical)
        if brier < best_brier:
            best_brier = brier
            best_weights = candidate

    improvement = ((base_brier - best_brier) / base_brier * 100) if base_brier else 0

    # Aviso de sobreajuste si la muestra es pequeña
    warning = None
    if n_matches < MIN_MATCHES_RECOMMENDED:
        warning = (
            f"Solo {n_matches} partidos en la muestra. Con menos de "
            f"{MIN_MATCHES_RECOMMENDED}, los pesos pueden estar sobreajustados "
            f"al pasado y no mejorar las predicciones futuras. Úsalos con cautela."
        )

    return {
        "success": True,
        "n_matches": n_matches,
        "base_brier": round(base_brier, 4),
        "optimized_brier": round(best_brier, 4),
        "improvement_pct": round(improvement, 1),
        "default_weights": asdict(default_weights),
        "optimized_weights": asdict(best_weights),
        "iterations": iterations,
        "warning": warning,
        "verdict": _opt_verdict(improvement, n_matches, best_weights),
    }


def _opt_verdict(improvement: float, n: int, w: WeightConfig) -> str:
    # Encontrar la señal con más peso
    weights_map = {
        "forma de jugadores": w.sofascore_form, "ranking ELO": w.elo_rating,
        "química de equipo": w.chemistry, "head-to-head": w.h2h,
        "valor de mercado": w.market_value,
    }
    top_signal = max(weights_map, key=weights_map.get)
    top_pct = round(weights_map[top_signal] * 100)

    if improvement < 1:
        return (f"Los pesos por defecto ya funcionan bien sobre estos {n} partidos "
                f"(mejora menor al 1%). No vale la pena cambiarlos.")
    return (f"Sobre {n} partidos, ajustar los pesos reduce el error de predicción "
            f"un {improvement:.1f}%. La señal más predictiva resultó ser "
            f"«{top_signal}» ({top_pct}% del peso).")
