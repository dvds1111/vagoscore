"""
VagoScore — Scraper ELO
Fuentes:
  - Selecciones: eloratings.net (World Football Elo Ratings)
  - Clubes: clubelo.com
"""

from .base import fetch_html, fetch_json
from cache.db import cache_get, cache_set

# ELO conocidos (fallback cuando el scraping falla)
ELO_FALLBACK = {
    "brazil": 2060, "brasil": 2060,
    "morocco": 1830, "marruecos": 1830,
    "france": 2050, "francia": 2050,
    "argentina": 2140,
    "england": 1990,
    "spain": 1990, "españa": 1990,
    "germany": 1980, "alemania": 1980,
    "portugal": 1980,
    "netherlands": 1970, "países bajos": 1970,
    "colombia": 1870,
    "uruguay": 1900,
    "croatia": 1910, "croacia": 1910,
    "senegal": 1820,
    "japan": 1800, "japón": 1800,
    "mexico": 1850,
    "usa": 1840,
    "chile": 1820,
}

# clubelo.com — ranking de clubes por ELO
CLUB_ELO_API = "http://api.clubelo.com"


def get_national_elo(team_name: str) -> dict:
    """
    Obtiene el ELO de una selección nacional desde eloratings.net
    o el fallback hardcoded si el scraping falla.
    """
    cache_key = f"elo_national_{team_name.lower().replace(' ', '_')}"
    cached = cache_get(cache_key, "elo")
    if cached:
        return cached

    key = team_name.lower().strip()

    # Intentar scraping de eloratings.net
    try:
        url = "https://www.eloratings.net/"
        soup = fetch_html(url, retries=2, timeout=10)
        if soup:
            rows = soup.select("tr.tablerows")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name_cell = cells[1].get_text(strip=True).lower()
                    if key in name_cell or name_cell in key:
                        rank = cells[0].get_text(strip=True)
                        elo = cells[2].get_text(strip=True)
                        try:
                            result = {
                                "team": team_name,
                                "elo": int(elo),
                                "rank": int(rank),
                                "source": "eloratings.net",
                            }
                            cache_set(cache_key, result)
                            return result
                        except ValueError:
                            pass
    except Exception as e:
        print(f"[elo] Error scrapeando eloratings.net: {e}")

    # Fallback con datos hardcoded
    elo_value = ELO_FALLBACK.get(key, 1750)
    result = {
        "team": team_name,
        "elo": elo_value,
        "rank": None,
        "source": "fallback",
    }
    cache_set(cache_key, result)
    return result


def get_club_elo(team_name: str) -> dict:
    """
    Obtiene el ELO de un club desde clubelo.com API.
    """
    cache_key = f"elo_club_{team_name.lower().replace(' ', '_')}"
    cached = cache_get(cache_key, "elo")
    if cached:
        return cached

    # clubelo.com tiene API REST pública
    slug = team_name.replace(" ", "")
    url = f"{CLUB_ELO_API}/{slug}"

    try:
        data = fetch_json(url, timeout=8)
        if data and isinstance(data, list) and len(data) > 0:
            latest = data[-1]
            result = {
                "team": team_name,
                "elo": int(float(latest.get("Elo", 1500))),
                "rank": latest.get("Rank"),
                "source": "clubelo.com",
            }
            cache_set(cache_key, result)
            return result
    except Exception as e:
        print(f"[elo] Error en clubelo.com para {team_name}: {e}")

    result = {"team": team_name, "elo": 1500, "rank": None, "source": "fallback"}
    cache_set(cache_key, result)
    return result


def elo_win_probability(elo_a: int, elo_b: int) -> dict:
    """
    Calcula probabilidades de resultado usando la fórmula ELO estándar.
    La diferencia de ELO se convierte en probabilidad via función logística.

    P(A wins) = 1 / (1 + 10^((ELO_B - ELO_A) / 400))

    Ajuste para empate: se distribuye probabilidad central entre A, draw, B.
    """
    diff = elo_a - elo_b

    # Probabilidad base (modelo ELO puro)
    p_a_raw = 1 / (1 + 10 ** (-diff / 400))
    p_b_raw = 1 - p_a_raw

    # El fútbol tiene ~25-28% de empates en media global
    # Distribuimos probabilidad de empate tomando de ambos lados
    draw_base = 0.27
    scale = 1 - draw_base

    # Proporción relativa entre A y B
    p_a = p_a_raw * scale
    p_b = p_b_raw * scale
    p_draw = draw_base

    # Ajuste fino: si la diferencia es muy grande, el empate baja
    if abs(diff) > 300:
        excess = (abs(diff) - 300) / 700 * 0.10
        p_draw = max(0.10, p_draw - excess)
        if diff > 0:
            p_a += excess
        else:
            p_b += excess

    total = p_a + p_b + p_draw
    return {
        "p_a_win": round(p_a / total, 4),
        "p_draw": round(p_draw / total, 4),
        "p_b_win": round(p_b / total, 4),
        "elo_diff": diff,
    }
