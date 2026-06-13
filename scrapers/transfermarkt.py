"""
VagoScore — Scraper Transfermarkt
Obtiene valor de mercado del equipo y jugadores.
HTML estático con lxml — más fácil de scrapear que Sofascore.
"""

import re
from typing import Optional
from .base import fetch_html, fetch_json, polite_sleep
from cache.db import cache_get, cache_set

TM_BASE = "https://www.transfermarkt.com"
TM_REFERER = "https://www.transfermarkt.com/"

# Slugs predefinidos para selecciones nacionales frecuentes
NATIONAL_TEAM_SLUGS = {
    "brazil":      ("brasilien", 3980),
    "brasil":      ("brasilien", 3980),
    "morocco":     ("marokko", 3898),
    "marruecos":   ("marokko", 3898),
    "france":      ("frankreich", 3377),
    "francia":     ("frankreich", 3377),
    "germany":     ("deutschland", 3262),
    "alemania":    ("deutschland", 3262),
    "argentina":   ("argentinien", 3437),
    "spain":       ("spanien", 3375),
    "españa":      ("spanien", 3375),
    "england":     ("england", 3376),
    "portugal":    ("portugal", 3947),
    "netherlands": ("niederlande", 3379),
    "países bajos":("niederlande", 3379),
    "colombia":    ("kolumbien", 3816),
    "mexico":      ("mexiko", 3816),
    "uruguay":     ("uruguay", 3440),
    "croatia":     ("kroatien", 3556),
    "croacia":     ("kroatien", 3556),
    "senegal":     ("senegal", 3670),
    "japan":       ("japan", 3811),
    "japón":       ("japan", 3811),
}


def _parse_value(value_str: str) -> float:
    """
    Convierte '€45.00m', '€900k', '€1.20bn' → float en millones de euros.
    """
    if not value_str:
        return 0.0
    v = value_str.replace("€", "").replace(",", ".").strip().lower()
    try:
        if "bn" in v:
            return float(v.replace("bn", "")) * 1000
        elif "m" in v:
            return float(v.replace("m", ""))
        elif "k" in v:
            return float(v.replace("k", "")) / 1000
        else:
            return float(v) / 1_000_000
    except ValueError:
        return 0.0


def get_national_team_value(team_name: str) -> dict:
    """
    Obtiene el valor total de la plantilla de una selección nacional.
    """
    cache_key = f"tm_national_{team_name.lower().replace(' ', '_')}"
    cached = cache_get(cache_key, "transfermarkt")
    if cached:
        return cached

    key = team_name.lower().strip()
    slug_data = NATIONAL_TEAM_SLUGS.get(key)

    if not slug_data:
        # Intento de búsqueda genérica
        print(f"[transfermarkt] Selección no encontrada en mapa: {team_name}")
        result = {
            "team": team_name,
            "total_value_m": 500.0,
            "avg_value_m": 25.0,
            "players": [],
            "source": "estimate",
        }
        cache_set(cache_key, result)
        return result

    slug, tm_id = slug_data
    url = f"{TM_BASE}/nationalmannschaft/kader/verein/{tm_id}"
    print(f"[transfermarkt] Scrapeando {url}")

    soup = fetch_html(url, referer=TM_REFERER)
    if not soup:
        result = {"team": team_name, "total_value_m": 500.0, "avg_value_m": 25.0, "players": [], "source": "error"}
        cache_set(cache_key, result)
        return result

    players = []
    # Tabla principal del plantel
    rows = soup.select("table.items tbody tr.odd, table.items tbody tr.even")
    for row in rows:
        name_el = row.select_one("td.hauptlink a")
        value_el = row.select_one("td.rechts.hauptlink")
        pos_el = row.select_one("td.posrela table tr:nth-child(2) td")

        if name_el and value_el:
            raw_val = value_el.get_text(strip=True)
            players.append({
                "name": name_el.get_text(strip=True),
                "position": pos_el.get_text(strip=True) if pos_el else "",
                "value_raw": raw_val,
                "value_m": _parse_value(raw_val),
            })

    if not players:
        # Fallback: intentar con selectores alternativos
        value_cells = soup.select("td.rechts.hauptlink")
        total_raw = value_cells[-1].get_text(strip=True) if value_cells else "€500m"
        total_m = _parse_value(total_raw)
    else:
        total_m = sum(p["value_m"] for p in players)

    avg_m = round(total_m / len(players), 2) if players else 25.0

    result = {
        "team": team_name,
        "total_value_m": round(total_m, 2),
        "avg_value_m": avg_m,
        "top_players": sorted(players, key=lambda x: x["value_m"], reverse=True)[:5],
        "players": players,
        "source": "transfermarkt",
    }
    cache_set(cache_key, result)
    return result


def get_club_value(team_name: str, league: str = None) -> dict:
    """
    Busca un club en Transfermarkt y obtiene valor total del plantel.
    Para clubes (no selecciones).
    """
    cache_key = f"tm_club_{team_name.lower().replace(' ', '_')}"
    cached = cache_get(cache_key, "transfermarkt")
    if cached:
        return cached

    search_url = f"{TM_BASE}/schnellsuche/ergebnis/schnellsuche?query={team_name.replace(' ', '+')}&Verein_page=0"
    soup = fetch_html(search_url, referer=TM_REFERER)

    if not soup:
        result = {"team": team_name, "total_value_m": 200.0, "avg_value_m": 15.0, "source": "error"}
        cache_set(cache_key, result)
        return result

    # Primer resultado de clubs
    first_club = soup.select_one("td.hauptlink a")
    if not first_club:
        result = {"team": team_name, "total_value_m": 200.0, "avg_value_m": 15.0, "source": "no_match"}
        cache_set(cache_key, result)
        return result

    club_url = TM_BASE + first_club["href"]
    # Ir a la página del plantel
    squad_url = re.sub(r"/startseite/", "/kader/", club_url)
    polite_sleep()

    soup2 = fetch_html(squad_url, referer=club_url)
    if not soup2:
        result = {"team": team_name, "total_value_m": 200.0, "avg_value_m": 15.0, "source": "error"}
        cache_set(cache_key, result)
        return result

    # Mismo parsing que selecciones
    value_el = soup2.select_one("div.data-header__market-value-wrapper a")
    total_raw = value_el.get_text(strip=True) if value_el else "€200m"
    total_m = _parse_value(total_raw)

    result = {
        "team": team_name,
        "total_value_m": round(total_m, 2),
        "avg_value_m": round(total_m / 25, 2),
        "source": "transfermarkt",
    }
    cache_set(cache_key, result)
    return result
