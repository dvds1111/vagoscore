"""
VagoScore — Motor de scoring
Combina todas las fuentes con pesos ponderados y calcula probabilidades finales.
"""

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeightConfig:
    """Pesos configurables por el usuario."""
    sofascore_form: float = 0.25   # Forma reciente jugadores
    elo_rating:     float = 0.25   # Ranking ELO
    chemistry:      float = 0.20   # Química de alineación
    h2h:            float = 0.15   # Head-to-head
    market_value:   float = 0.15   # Valor de mercado

    def validate(self):
        total = sum([
            self.sofascore_form, self.elo_rating,
            self.chemistry, self.h2h, self.market_value
        ])
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Los pesos deben sumar 1.0 (actual: {total:.3f})")


@dataclass
class TeamScore:
    """Score parcial de un equipo por dimensión."""
    team_name: str
    sofascore_score: float = 0.0    # 0-100
    elo_score: float = 0.0          # 0-100
    chemistry_score: float = 0.0   # 0-100
    h2h_score: float = 0.0          # 0-100
    market_score: float = 0.0      # 0-100
    raw_data: dict = field(default_factory=dict)

    def weighted_total(self, weights: WeightConfig) -> float:
        return (
            self.sofascore_score * weights.sofascore_form +
            self.elo_score       * weights.elo_rating     +
            self.chemistry_score * weights.chemistry       +
            self.h2h_score       * weights.h2h             +
            self.market_score    * weights.market_value
        )


# ─── Normalizadores por dimensión ─────────────────────────────────────────────

def normalize_sofascore(avg_rating: float) -> float:
    """
    Sofascore rating va de ~5.0 (muy mal) a ~9.5 (excepcional).
    Normalizar a 0-100 con referencia 6.0 = 30, 7.0 = 60, 8.0 = 85, 9.0 = 98.
    Función sigmoidea centrada en 7.0.
    """
    # Clamp razonable
    r = max(5.0, min(10.0, avg_rating))
    # Sigmoidea: score = 100 / (1 + e^(-k*(r-7.0)))
    k = 1.8
    score = 100 / (1 + math.exp(-k * (r - 7.0)))
    return round(score, 2)


def normalize_elo(elo: int, min_elo: int = 1400, max_elo: int = 2200) -> float:
    """Mapea ELO al rango 0-100."""
    score = (elo - min_elo) / (max_elo - min_elo) * 100
    return round(max(0.0, min(100.0, score)), 2)


def normalize_market_value(value_m: float, max_m: float = 1500.0) -> float:
    """
    Valor de mercado en M€ normalizado a 0-100.
    Usa log para comprimir diferencias extremas.
    max_m: valor máximo esperado (plantilla más cara del mundo ~€1.5B)
    """
    if value_m <= 0:
        return 0.0
    score = math.log(1 + value_m) / math.log(1 + max_m) * 100
    return round(min(100.0, score), 2)


def compute_chemistry(player_ratings: list[dict]) -> float:
    """
    Estima la 'química' de la alineación basada en:
    - Consistencia de ratings (baja varianza = mejor química)
    - % de jugadores con rating real (no default)
    - Ausencia de puntos débiles extremos (ningún jugador <6.0)

    Devuelve score 0-100.
    """
    if not player_ratings:
        return 50.0

    ratings = [p["avg_rating"] for p in player_ratings]
    n = len(ratings)

    if n == 0:
        return 50.0

    avg = sum(ratings) / n

    # Varianza → consistencia
    variance = sum((r - avg) ** 2 for r in ratings) / n
    std = math.sqrt(variance)
    consistency_score = max(0, 100 - std * 20)  # std=0 → 100, std=5 → 0

    # Cobertura de datos reales
    real_data = sum(1 for p in player_ratings if p.get("source") == "sofascore")
    coverage = real_data / n

    # Penalizar eslabones débiles (jugadores bajo 6.2)
    weak_links = sum(1 for r in ratings if r < 6.2)
    weak_penalty = weak_links * 5

    chemistry = (consistency_score * 0.5 + normalize_sofascore(avg) * 0.3 + coverage * 20) - weak_penalty
    return round(max(0.0, min(100.0, chemistry)), 2)


def compute_h2h_score(h2h_data: dict, team_name: str) -> float:
    """
    Analiza el historial H2H y da un score a team_name.
    - Puntúa según W/D/L en últimos encuentros
    - Ponderación decreciente (más recientes pesan más)
    """
    matches = h2h_data.get("matches", [])
    if not matches:
        return 50.0  # Neutral si no hay datos

    points = 0.0
    total_weight = 0.0
    team_lower = team_name.lower()

    for i, match in enumerate(matches[:8]):  # máximo 8 encuentros
        weight = 1.0 / (i + 1)  # 1, 0.5, 0.33, 0.25...
        total_weight += weight

        home = (match.get("home_team") or "").lower()
        away = (match.get("away_team") or "").lower()
        hs = match.get("home_score", 0) or 0
        as_ = match.get("away_score", 0) or 0

        is_home = team_lower in home
        is_away = team_lower in away

        if not (is_home or is_away):
            # Matching flexible
            for part in team_lower.split():
                if part in home:
                    is_home = True
                elif part in away:
                    is_away = True

        if is_home:
            if hs > as_:
                points += weight * 3   # Victoria
            elif hs == as_:
                points += weight * 1   # Empate
            # Derrota = 0
        elif is_away:
            if as_ > hs:
                points += weight * 3
            elif hs == as_:
                points += weight * 1

    if total_weight == 0:
        return 50.0

    max_possible = total_weight * 3
    ratio = points / max_possible
    score = ratio * 100
    return round(score, 2)


# ─── Predicción final ─────────────────────────────────────────────────────────

def scores_to_probabilities(score_a: float, score_b: float) -> dict:
    """
    Convierte los scores totales de dos equipos en probabilidades de resultado.
    Incluye probabilidad de empate basada en proximidad de scores.
    """
    diff = score_a - score_b
    total = score_a + score_b if (score_a + score_b) > 0 else 100

    # Base ELO-style
    p_a_raw = 1 / (1 + 10 ** (-diff / 25))
    p_b_raw = 1 - p_a_raw

    # Draw probability: máximo cuando scores son iguales (~27%), decrece con diferencia
    abs_diff = abs(diff)
    draw_base = 0.27 * math.exp(-abs_diff / 30)
    draw_base = max(0.08, min(0.30, draw_base))

    scale = 1 - draw_base
    p_a = p_a_raw * scale
    p_b = p_b_raw * scale
    p_draw = draw_base

    norm = p_a + p_b + p_draw
    return {
        "p_win_a":  round(p_a / norm * 100, 1),
        "p_draw":   round(p_draw / norm * 100, 1),
        "p_win_b":  round(p_b / norm * 100, 1),
        "score_diff": round(diff, 2),
    }


def expected_goals(score_a: float, score_b: float) -> dict:
    """
    Estima xG aproximados basados en la diferencia de scores.
    Modelo simple: xG promedio ~1.5 goles/equipo, ajustado por score relativo.
    """
    baseline = 1.35
    diff = (score_a - score_b) / 100  # normalizado -1 a 1

    xg_a = round(baseline + diff * 0.8, 2)
    xg_b = round(baseline - diff * 0.8, 2)
    xg_a = max(0.3, min(4.0, xg_a))
    xg_b = max(0.3, min(4.0, xg_b))

    return {"xg_a": xg_a, "xg_b": xg_b}


def most_likely_score(xg_a: float, xg_b: float) -> str:
    """
    Dado xG de cada equipo, estima el marcador más probable
    usando distribución de Poisson.
    """
    import math

    def poisson(k: int, lam: float) -> float:
        return (lam ** k * math.exp(-lam)) / math.factorial(k)

    best_prob = 0.0
    best_score = "1-1"

    for ga in range(5):
        for gb in range(5):
            p = poisson(ga, xg_a) * poisson(gb, xg_b)
            if p > best_prob:
                best_prob = p
                best_score = f"{ga}-{gb}"

    return best_score


def confidence_score(
    team_a: TeamScore,
    team_b: TeamScore,
    weights: WeightConfig,
) -> float:
    """
    Estima la confianza de la predicción (0-100%).
    Factores: cantidad de datos reales, consistencia de señales.
    """
    # Datos reales disponibles
    data_quality_a = team_a.raw_data.get("players_with_data", 0) / max(1, len(team_a.raw_data.get("players", [1])))
    data_quality_b = team_b.raw_data.get("players_with_data", 0) / max(1, len(team_b.raw_data.get("players", [1])))
    data_quality = (data_quality_a + data_quality_b) / 2

    # Consistencia de las señales (¿todas apuntan al mismo ganador?)
    scores = [
        team_a.sofascore_score - team_b.sofascore_score,
        team_a.elo_score - team_b.elo_score,
        team_a.chemistry_score - team_b.chemistry_score,
        team_a.h2h_score - team_b.h2h_score,
        team_a.market_score - team_b.market_score,
    ]
    signs = [1 if s > 2 else (-1 if s < -2 else 0) for s in scores]
    agreement = abs(sum(signs)) / max(1, len([s for s in signs if s != 0]))

    confidence = 40 + data_quality * 30 + agreement * 30
    return round(min(95.0, confidence), 1)


# ─── Función principal ────────────────────────────────────────────────────────

def compute_vagoscore(
    sofascore_a: dict,
    sofascore_b: dict,
    elo_a: dict,
    elo_b: dict,
    market_a: dict,
    market_b: dict,
    h2h_data: dict,
    team_a_name: str,
    team_b_name: str,
    weights: WeightConfig = None,
) -> dict:
    """
    Función principal: recibe todos los datos scrapeados y devuelve la predicción completa.
    """
    if weights is None:
        weights = WeightConfig()
    weights.validate()

    # ── Team A ──
    a = TeamScore(team_name=team_a_name)
    a.sofascore_score = normalize_sofascore(sofascore_a.get("team_avg_rating", 6.5))
    a.elo_score       = normalize_elo(elo_a.get("elo", 1750))
    a.chemistry_score = compute_chemistry(sofascore_a.get("players", []))
    a.h2h_score       = compute_h2h_score(h2h_data, team_a_name)
    a.market_score    = normalize_market_value(market_a.get("total_value_m", 300))
    a.raw_data        = sofascore_a

    # ── Team B ──
    b = TeamScore(team_name=team_b_name)
    b.sofascore_score = normalize_sofascore(sofascore_b.get("team_avg_rating", 6.5))
    b.elo_score       = normalize_elo(elo_b.get("elo", 1750))
    b.chemistry_score = compute_chemistry(sofascore_b.get("players", []))
    b.h2h_score       = compute_h2h_score(h2h_data, team_b_name)
    b.market_score    = normalize_market_value(market_b.get("total_value_m", 300))
    b.raw_data        = sofascore_b

    # ── Scores totales ──
    total_a = a.weighted_total(weights)
    total_b = b.weighted_total(weights)

    # ── Probabilidades ──
    probs = scores_to_probabilities(total_a, total_b)
    xg    = expected_goals(total_a, total_b)
    score = most_likely_score(xg["xg_a"], xg["xg_b"])
    conf  = confidence_score(a, b, weights)

    # ── Jugador clave ──
    key_player_a = None
    key_player_b = None
    players_a = sofascore_a.get("players", [])
    players_b = sofascore_b.get("players", [])
    if players_a:
        key_player_a = max(players_a, key=lambda p: p.get("avg_rating", 0))
    if players_b:
        key_player_b = max(players_b, key=lambda p: p.get("avg_rating", 0))

    return {
        "team_a": team_a_name,
        "team_b": team_b_name,
        # Scores por dimensión
        "scores": {
            team_a_name: {
                "total": round(total_a, 2),
                "sofascore": a.sofascore_score,
                "elo": a.elo_score,
                "chemistry": a.chemistry_score,
                "h2h": a.h2h_score,
                "market": a.market_score,
            },
            team_b_name: {
                "total": round(total_b, 2),
                "sofascore": b.sofascore_score,
                "elo": b.elo_score,
                "chemistry": b.chemistry_score,
                "h2h": b.h2h_score,
                "market": b.market_score,
            },
        },
        # Predicción
        "prediction": {
            "p_win_a": probs["p_win_a"],
            "p_draw":  probs["p_draw"],
            "p_win_b": probs["p_win_b"],
            "xg_a": xg["xg_a"],
            "xg_b": xg["xg_b"],
            "most_likely_score": score,
            "confidence": conf,
            "favorite": team_a_name if total_a > total_b else (team_b_name if total_b > total_a else "draw"),
        },
        # Datos crudos para debug
        "raw": {
            "elo_a": elo_a,
            "elo_b": elo_b,
            "market_a": market_a,
            "market_b": market_b,
            "h2h_matches": len(h2h_data.get("matches", [])),
            "key_player_a": key_player_a,
            "key_player_b": key_player_b,
        },
        "weights_used": weights.__dict__,
    }
