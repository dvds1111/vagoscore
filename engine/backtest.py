"""
VagoScore — Motor de Backtesting

Corre el modelo sobre partidos YA jugados y compara las predicciones con
los resultados reales. Mide la calidad predictiva con métricas estándar:

  - Acierto (accuracy): ¿el resultado más probable fue el que ocurrió?
  - Brier score: error cuadrático de las probabilidades (menor = mejor)
  - Log loss: penaliza la confianza equivocada (menor = mejor)
  - ROI: retorno si se hubiera apostado siguiendo el modelo

Esto convierte a VagoScore de "creo que funciona" a "esto es lo que acierta".
"""

import math
from dataclasses import dataclass


@dataclass
class BacktestResult:
    total_matches: int
    correct_predictions: int
    accuracy_pct: float
    brier_score: float
    log_loss: float
    # Calibración por nivel de confianza
    high_conf_accuracy: float
    high_conf_count: int
    # Rendimiento de apuestas de valor
    value_bets_placed: int
    value_bets_won: int
    roi_pct: float
    profit_units: float
    details: list


def _brier_3way(probs: list, actual_idx: int) -> float:
    """
    Brier score para 3 resultados (1X2).
    probs = [p_home, p_draw, p_away] (suman 1)
    actual_idx = 0 (home), 1 (draw), 2 (away)
    """
    target = [0, 0, 0]
    target[actual_idx] = 1
    return sum((probs[i] - target[i]) ** 2 for i in range(3))


def _log_loss_3way(probs: list, actual_idx: int) -> float:
    """Log loss para el resultado que ocurrió."""
    p = max(1e-9, min(1 - 1e-9, probs[actual_idx]))
    return -math.log(p)


def run_backtest(predictions: list) -> dict:
    """
    Ejecuta el backtest sobre una lista de predicciones con resultado conocido.

    Cada elemento de `predictions` debe tener:
    {
      "match": "Brasil vs Marruecos",
      "date": "2023-03-25",
      "p_home": 0.45, "p_draw": 0.27, "p_away": 0.28,
      "actual": "away",                 # resultado real: home|draw|away
      "odds": {"home": 2.1, "draw": 3.4, "away": 3.2}   # opcional, para ROI
    }

    Returns: métricas agregadas + detalle por partido.
    """
    if not predictions:
        return {"error": "Sin datos para backtest", "total_matches": 0}

    outcome_to_idx = {"home": 0, "draw": 1, "away": 2}

    correct = 0
    brier_sum = 0.0
    logloss_sum = 0.0
    high_conf_correct = 0
    high_conf_total = 0

    # Apuestas de valor (umbral: edge > 5%)
    bets_placed = 0
    bets_won = 0
    total_staked = 0.0
    total_returned = 0.0

    details = []

    for pred in predictions:
        probs = [pred.get("p_home", 0), pred.get("p_draw", 0), pred.get("p_away", 0)]
        # Normalizar por si no suman 1
        s = sum(probs) or 1
        probs = [p / s for p in probs]

        actual = pred.get("actual")
        if actual not in outcome_to_idx:
            continue
        actual_idx = outcome_to_idx[actual]

        predicted_idx = probs.index(max(probs))
        is_correct = predicted_idx == actual_idx
        if is_correct:
            correct += 1

        # Métricas probabilísticas
        brier = _brier_3way(probs, actual_idx)
        logloss = _log_loss_3way(probs, actual_idx)
        brier_sum += brier
        logloss_sum += logloss

        # Calibración: predicciones de alta confianza (>50% en un resultado)
        max_prob = max(probs)
        if max_prob > 0.5:
            high_conf_total += 1
            if is_correct:
                high_conf_correct += 1

        # Simulación de apuesta de valor (flat stake de 1 unidad)
        bet_info = None
        odds = pred.get("odds")
        if odds:
            outcomes = ["home", "draw", "away"]
            best_edge = 0
            best_outcome = None
            for i, oc in enumerate(outcomes):
                o = odds.get(oc)
                if o and o > 1:
                    edge = probs[i] * o - 1
                    if edge > best_edge:
                        best_edge = edge
                        best_outcome = oc
            # Apostar si edge > 5%
            if best_outcome and best_edge > 0.05:
                bets_placed += 1
                total_staked += 1.0
                won = best_outcome == actual
                if won:
                    bets_won += 1
                    total_returned += odds[best_outcome]
                bet_info = {
                    "outcome": best_outcome,
                    "edge_pct": round(best_edge * 100, 1),
                    "odds": odds[best_outcome],
                    "won": won,
                }

        details.append({
            "match": pred.get("match", ""),
            "date": pred.get("date", ""),
            "predicted": ["home", "draw", "away"][predicted_idx],
            "actual": actual,
            "correct": is_correct,
            "confidence": round(max_prob * 100, 1),
            "brier": round(brier, 4),
            "bet": bet_info,
        })

    n = len([p for p in predictions if p.get("actual") in outcome_to_idx]) or 1

    profit = total_returned - total_staked
    roi = (profit / total_staked * 100) if total_staked > 0 else 0

    return {
        "total_matches": n,
        "correct_predictions": correct,
        "accuracy_pct": round(correct / n * 100, 1),
        "brier_score": round(brier_sum / n, 4),
        "log_loss": round(logloss_sum / n, 4),
        "high_conf_accuracy": round(high_conf_correct / high_conf_total * 100, 1) if high_conf_total else 0,
        "high_conf_count": high_conf_total,
        "value_bets_placed": bets_placed,
        "value_bets_won": bets_won,
        "value_bet_hit_rate": round(bets_won / bets_placed * 100, 1) if bets_placed else 0,
        "roi_pct": round(roi, 1),
        "profit_units": round(profit, 2),
        "details": details,
        "interpretation": _interpret(correct / n, brier_sum / n, roi),
    }


def _interpret(accuracy: float, brier: float, roi: float) -> str:
    """Lectura honesta de los resultados."""
    parts = []
    # Referencia: en fútbol, predecir siempre al favorito acierta ~50-55%.
    # Brier base (azar 3-way) ≈ 0.667; un modelo decente baja de 0.6.
    if accuracy >= 0.55:
        parts.append(f"Acierto del {round(accuracy*100,1)}% — por encima del azar y de predecir siempre al favorito.")
    elif accuracy >= 0.45:
        parts.append(f"Acierto del {round(accuracy*100,1)}% — en línea con modelos básicos.")
    else:
        parts.append(f"Acierto del {round(accuracy*100,1)}% — el modelo necesita ajuste.")

    if brier < 0.55:
        parts.append("Las probabilidades están bien calibradas (Brier bajo).")
    else:
        parts.append("La calibración de probabilidades puede mejorar (Brier alto).")

    if roi > 0:
        parts.append(f"ROI positivo del {round(roi,1)}% en apuestas de valor — señal prometedora, pero la muestra debe ser grande para confiar.")
    else:
        parts.append(f"ROI del {round(roi,1)}% — apostar mecánicamente no fue rentable en esta muestra.")

    parts.append("⚠️ El rendimiento pasado no garantiza resultados futuros. Una muestra pequeña puede engañar.")
    return " ".join(parts)
