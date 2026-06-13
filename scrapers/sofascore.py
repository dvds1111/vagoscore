"""
VagoScore — Scraper Sofascore
Obtiene ratings de jugadores en los últimos 10 partidos.
Usa la API interna no oficial de Sofascore (JSON).
"""

import re
from typing import Optional
from .base import fetch_json, fetch_html, polite_sleep
from cache.db import cache_get, cache_set

SOFASCORE_API = "https://api.sofascore.com/api/v1"
SOFASCORE_REFERER = "https://www.sofascore.com/"

# Headers especiales que Sofascore espera
SOFA_HEADERS = {
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/",
    "Cache-Control": "no-cache",
}


def search_team(team_name: str) -> Optional[dict]:
    """
    Busca un equipo en Sofascore y devuelve su ID + nombre oficial.
    """
    cache_key = f"sofa_team_search_{team_name.lower().replace(' ', '_')}"
    cached = cache_get(cache_key, "sofascore_player")
    if cached:
        return cached

    url = f"{SOFASCORE_API}/search/multi-search/{team_name.replace(' ', '%20')}"
    data = fetch_json(url, referer=SOFASCORE_REFERER, headers_extra=SOFA_HEADERS)
    if not data:
        return None

    # Buscar en resultados de tipo 'team'
    teams = []
    for section in data.get("results", []):
        for item in section.get("results", {}).get("hits", []):
            obj = item.get("entity", {})
            if obj.get("type") == "team":
                teams.append({
                    "id": obj.get("id"),
                    "name": obj.get("name"),
                    "slug": obj.get("slug"),
                    "country": obj.get("country", {}).get("name", ""),
                })

    result = teams[0] if teams else None
    if result:
        cache_set(cache_key, result)
    return result


def get_team_players(team_id: int) -> list[dict]:
    """
    Obtiene la plantilla (roster) de un equipo con IDs de jugadores.
    """
    cache_key = f"sofa_roster_{team_id}"
    cached = cache_get(cache_key, "sofascore_player")
    if cached:
        return cached

    url = f"{SOFASCORE_API}/team/{team_id}/players"
    data = fetch_json(url, referer=SOFASCORE_REFERER, headers_extra=SOFA_HEADERS)
    if not data:
        return []

    players = []
    for p in data.get("players", []):
        player = p.get("player", {})
        players.append({
            "id": player.get("id"),
            "name": player.get("name"),
            "shortName": player.get("shortName", player.get("name", "")),
            "position": player.get("position", ""),
            "jerseyNumber": p.get("jerseyNumber", ""),
        })

    cache_set(cache_key, players)
    return players


def get_player_recent_rating(player_id: int, player_name: str) -> dict:
    """
    Obtiene el rating promedio de los últimos 10 partidos de un jugador.
    Devuelve rating promedio, min, max, partidos con rating.
    """
    cache_key = f"sofa_rating_{player_id}"
    cached = cache_get(cache_key, "sofascore_player")
    if cached:
        return cached

    polite_sleep(0.5, 1.5)
    url = f"{SOFASCORE_API}/player/{player_id}/statistics/career"
    data = fetch_json(url, referer=SOFASCORE_REFERER, headers_extra=SOFA_HEADERS)

    if not data:
        result = {"player_id": player_id, "name": player_name, "avg_rating": 6.5, "matches": 0, "source": "default"}
        cache_set(cache_key, result)
        return result

    # Extraer ratings de temporada actual
    ratings = []
    for season_stats in data.get("statistics", []):
        for stat in season_stats.get("statistics", []):
            r = stat.get("rating")
            if r and isinstance(r, (int, float)) and r > 0:
                ratings.append(float(r))

    ratings = ratings[:10]  # últimos 10 con rating
    if ratings:
        avg = round(sum(ratings) / len(ratings), 2)
        result = {
            "player_id": player_id,
            "name": player_name,
            "avg_rating": avg,
            "ratings": ratings,
            "matches": len(ratings),
            "min_rating": min(ratings),
            "max_rating": max(ratings),
            "source": "sofascore",
        }
    else:
        result = {
            "player_id": player_id,
            "name": player_name,
            "avg_rating": 6.5,
            "matches": 0,
            "source": "default",
        }

    cache_set(cache_key, result)
    return result


def get_team_lineup_ratings(team_name: str, lineup: list[str] = None) -> dict:
    """
    Para un equipo y una alineación dada (lista de nombres),
    devuelve el rating promedio de cada jugador titular.

    Si lineup es None, usa la plantilla completa (aproximación).
    """
    print(f"[sofascore] Buscando equipo: {team_name}")
    team = search_team(team_name)
    if not team:
        print(f"[sofascore] Equipo no encontrado: {team_name}")
        return {"team": team_name, "players": [], "team_avg_rating": 6.5, "error": "team_not_found"}

    print(f"[sofascore] Encontrado: {team['name']} (ID: {team['id']})")
    players = get_team_players(team["id"])

    if lineup:
        # Filtrar solo los jugadores de la alineación (match parcial de nombre)
        lineup_lower = [n.lower() for n in lineup]
        players = [
            p for p in players
            if any(part in p["name"].lower() or part in p["shortName"].lower()
                   for name in lineup_lower for part in name.split())
        ]

    # Limitar a 11 titulares máximo
    players = players[:11]

    player_ratings = []
    for p in players:
        print(f"[sofascore]   → rating de {p['name']}...")
        rating = get_player_recent_rating(p["id"], p["name"])
        rating["position"] = p.get("position", "")
        rating["jersey"] = p.get("jerseyNumber", "")
        player_ratings.append(rating)
        polite_sleep(0.3, 0.8)

    if player_ratings:
        team_avg = round(sum(r["avg_rating"] for r in player_ratings) / len(player_ratings), 2)
    else:
        team_avg = 6.5

    return {
        "team": team_name,
        "team_id": team["id"],
        "players": player_ratings,
        "team_avg_rating": team_avg,
        "players_with_data": sum(1 for r in player_ratings if r.get("source") == "sofascore"),
    }


def get_head_to_head(team1_id: int, team2_id: int) -> dict:
    """
    Obtiene historial H2H entre dos equipos desde Sofascore.
    """
    cache_key = f"sofa_h2h_{min(team1_id, team2_id)}_{max(team1_id, team2_id)}"
    cached = cache_get(cache_key, "h2h")
    if cached:
        return cached

    url = f"{SOFASCORE_API}/team/{team1_id}/vs/{team2_id}/matches"
    data = fetch_json(url, referer=SOFASCORE_REFERER, headers_extra=SOFA_HEADERS)

    if not data:
        return {"matches": [], "error": "no_data"}

    matches = []
    for event in data.get("events", [])[:10]:  # últimos 10
        home = event.get("homeTeam", {})
        away = event.get("awayTeam", {})
        score = event.get("homeScore", {})
        matches.append({
            "date": event.get("startTimestamp", 0),
            "home_team": home.get("name"),
            "away_team": away.get("name"),
            "home_score": score.get("current", 0),
            "away_score": event.get("awayScore", {}).get("current", 0),
            "tournament": event.get("tournament", {}).get("name", ""),
        })

    result = {"matches": matches, "total": len(matches)}
    cache_set(cache_key, result)
    return result
