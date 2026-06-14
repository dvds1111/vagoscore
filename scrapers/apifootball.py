"""
VagoScore — Cliente API-Football
Datos en tiempo real: ligas, partidos, alineaciones (con fotos), cuotas, estadísticas.
Docs: https://www.api-football.com/documentation-v3
"""

import requests
from datetime import datetime, timedelta
from typing import Optional

import config
from cache.db import cache_get, cache_set


def _request(endpoint: str, params: dict = None, cache_type: str = "team_stats") -> dict:
    """
    Llamada genérica a API-Football con caché.
    """
    if not config.has_apifootball():
        return {"error": "API key no configurada", "response": []}

    # Clave de caché determinística
    param_str = "_".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    cache_key = f"apif_{endpoint.replace('/', '_')}_{param_str}"
    cached = cache_get(cache_key, cache_type)
    if cached:
        return cached

    url = f"{config.APIFOOTBALL_BASE}/{endpoint}"
    try:
        resp = requests.get(url, headers=config.APIFOOTBALL_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        cache_set(cache_key, data)
        return data
    except requests.RequestException as e:
        print(f"[apifootball] Error en {endpoint}: {e}")
        return {"error": str(e), "response": []}


# ─── Ligas / competiciones ────────────────────────────────────────────────────

def get_current_leagues() -> list[dict]:
    """
    Lista de competiciones activas en la temporada actual.
    Prioriza las principales (mundiales, Champions, top 5 ligas).
    """
    data = _request("leagues", {"current": "true"}, cache_type="elo")
    leagues = []
    for item in data.get("response", []):
        league = item.get("league", {})
        country = item.get("country", {})
        seasons = item.get("seasons", [])
        current_season = next((s for s in seasons if s.get("current")), None)
        if current_season:
            leagues.append({
                "id": league.get("id"),
                "name": league.get("name"),
                "type": league.get("type"),
                "logo": league.get("logo"),
                "country": country.get("name"),
                "flag": country.get("flag"),
                "season": current_season.get("year"),
            })

    # Ordenar: poner competiciones top primero
    priority = {
        "World Cup": 0, "UEFA Champions League": 1, "Premier League": 2,
        "La Liga": 3, "Serie A": 4, "Bundesliga": 5, "Ligue 1": 6,
        "UEFA Europa League": 7, "Copa America": 8, "Euro Championship": 9,
    }
    leagues.sort(key=lambda l: priority.get(l["name"], 999))
    return leagues


def get_upcoming_fixtures(league_id: int, season: int, days_ahead: int = 14) -> list[dict]:
    """
    Próximos partidos de una liga en los siguientes N días.
    """
    today = datetime.utcnow().date()
    end = today + timedelta(days=days_ahead)
    data = _request("fixtures", {
        "league": league_id,
        "season": season,
        "from": today.isoformat(),
        "to": end.isoformat(),
    }, cache_type="lineup")

    fixtures = []
    for item in data.get("response", []):
        fx = item.get("fixture", {})
        teams = item.get("teams", {})
        league = item.get("league", {})
        status = fx.get("status", {}).get("short", "")
        # Solo partidos no jugados (NS = not started, TBD)
        if status in ("NS", "TBD", "PST"):
            fixtures.append({
                "fixture_id": fx.get("id"),
                "date": fx.get("date"),
                "timestamp": fx.get("timestamp"),
                "venue": fx.get("venue", {}).get("name"),
                "city": fx.get("venue", {}).get("city"),
                "round": league.get("round"),
                "home": {
                    "id": teams.get("home", {}).get("id"),
                    "name": teams.get("home", {}).get("name"),
                    "logo": teams.get("home", {}).get("logo"),
                },
                "away": {
                    "id": teams.get("away", {}).get("id"),
                    "name": teams.get("away", {}).get("name"),
                    "logo": teams.get("away", {}).get("logo"),
                },
            })

    fixtures.sort(key=lambda f: f.get("timestamp", 0))
    return fixtures


def get_live_fixtures() -> list[dict]:
    """Partidos en vivo ahora mismo."""
    data = _request("fixtures", {"live": "all"}, cache_type="lineup")
    out = []
    for item in data.get("response", []):
        fx = item.get("fixture", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        out.append({
            "fixture_id": fx.get("id"),
            "elapsed": fx.get("status", {}).get("elapsed"),
            "home": teams.get("home", {}).get("name"),
            "away": teams.get("away", {}).get("name"),
            "home_logo": teams.get("home", {}).get("logo"),
            "away_logo": teams.get("away", {}).get("logo"),
            "score": f"{goals.get('home', 0)}-{goals.get('away', 0)}",
        })
    return out


# ─── Alineaciones con fotos ───────────────────────────────────────────────────

def get_fixture_lineups(fixture_id: int) -> dict:
    """
    Alineaciones confirmadas de un partido, con fotos de jugadores.
    Disponible ~20-40 min antes del partido.
    """
    data = _request("fixtures/lineups", {"fixture": fixture_id}, cache_type="lineup")
    result = {"home": None, "away": None}

    for i, team_lineup in enumerate(data.get("response", [])):
        team = team_lineup.get("team", {})
        formation = team_lineup.get("formation")
        coach = team_lineup.get("coach", {})

        starters = []
        for p in team_lineup.get("startXI", []):
            player = p.get("player", {})
            starters.append({
                "id": player.get("id"),
                "name": player.get("name"),
                "number": player.get("number"),
                "pos": player.get("pos"),
                "grid": player.get("grid"),
            })

        slot = "home" if i == 0 else "away"
        result[slot] = {
            "team_id": team.get("id"),
            "team_name": team.get("name"),
            "team_logo": team.get("logo"),
            "formation": formation,
            "coach": coach.get("name"),
            "coach_photo": coach.get("photo"),
            "starters": starters,
        }

    return result


def get_team_squad_photos(team_id: int) -> dict:
    """
    Mapa de player_id → foto, para enriquecer alineaciones.
    """
    data = _request("players/squads", {"team": team_id}, cache_type="transfermarkt")
    photos = {}
    for item in data.get("response", []):
        for p in item.get("players", []):
            photos[p.get("id")] = {
                "name": p.get("name"),
                "photo": p.get("photo"),
                "number": p.get("number"),
                "position": p.get("position"),
                "age": p.get("age"),
            }
    return photos


# ─── Cuotas (odds) ────────────────────────────────────────────────────────────

def get_fixture_odds(fixture_id: int) -> dict:
    """
    Cuotas de casas de apuestas para el mercado 1X2 (Match Winner).
    Devuelve cuotas promedio y mejores disponibles.
    """
    data = _request("odds", {"fixture": fixture_id, "bet": 1}, cache_type="lineup")

    home_odds, draw_odds, away_odds = [], [], []

    for item in data.get("response", []):
        for bookmaker in item.get("bookmakers", []):
            for bet in bookmaker.get("bets", []):
                if bet.get("name") == "Match Winner":
                    for value in bet.get("values", []):
                        v = value.get("value")
                        try:
                            odd = float(value.get("odd"))
                        except (ValueError, TypeError):
                            continue
                        if v == "Home":
                            home_odds.append(odd)
                        elif v == "Draw":
                            draw_odds.append(odd)
                        elif v == "Away":
                            away_odds.append(odd)

    def summarize(odds_list):
        if not odds_list:
            return None
        return {
            "avg": round(sum(odds_list) / len(odds_list), 2),
            "best": round(max(odds_list), 2),
            "count": len(odds_list),
        }

    return {
        "home": summarize(home_odds),
        "draw": summarize(draw_odds),
        "away": summarize(away_odds),
        "available": bool(home_odds),
    }


# ─── Estadísticas y forma ─────────────────────────────────────────────────────

def get_team_recent_form(team_id: int, league_id: int, season: int, last: int = 10) -> dict:
    """
    Últimos N partidos de un equipo: resultados y rating implícito.
    """
    data = _request("fixtures", {
        "team": team_id, "last": last,
    }, cache_type="team_stats")

    results = []
    wins = draws = losses = goals_for = goals_against = 0

    for item in data.get("response", []):
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        is_home = teams.get("home", {}).get("id") == team_id
        gf = goals.get("home" if is_home else "away") or 0
        ga = goals.get("away" if is_home else "home") or 0

        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1; outcome = "W"
        elif gf == ga:
            draws += 1; outcome = "D"
        else:
            losses += 1; outcome = "L"
        results.append(outcome)

    n = len(results) or 1
    # Forma como puntos por partido normalizado (0-100)
    points = wins * 3 + draws
    form_score = round((points / (n * 3)) * 100, 1)

    return {
        "team_id": team_id,
        "matches": len(results),
        "form": results,
        "wins": wins, "draws": draws, "losses": losses,
        "goals_for": goals_for, "goals_against": goals_against,
        "form_score": form_score,
        "avg_goals_scored": round(goals_for / n, 2),
        "avg_goals_conceded": round(goals_against / n, 2),
    }


def get_fixture_full(fixture_id: int) -> dict:
    """Datos completos de un partido por su ID."""
    data = _request("fixtures", {"id": fixture_id}, cache_type="lineup")
    resp = data.get("response", [])
    if not resp:
        return {}
    item = resp[0]
    fx = item.get("fixture", {})
    teams = item.get("teams", {})
    league = item.get("league", {})
    return {
        "fixture_id": fx.get("id"),
        "date": fx.get("date"),
        "league_id": league.get("id"),
        "league_name": league.get("name"),
        "season": league.get("season"),
        "round": league.get("round"),
        "venue": fx.get("venue", {}).get("name"),
        "home": {
            "id": teams.get("home", {}).get("id"),
            "name": teams.get("home", {}).get("name"),
            "logo": teams.get("home", {}).get("logo"),
        },
        "away": {
            "id": teams.get("away", {}).get("id"),
            "name": teams.get("away", {}).get("name"),
            "logo": teams.get("away", {}).get("logo"),
        },
    }


# ─── NUEVO v4: Detalle profundo de equipos y plantillas ───────────────────────

# Mapa de continentes por país (para agrupación jerárquica del selector)
COUNTRY_CONTINENT = {
    # Europa
    "England": "Europa", "Spain": "Europa", "Italy": "Europa", "Germany": "Europa",
    "France": "Europa", "Portugal": "Europa", "Netherlands": "Europa", "Belgium": "Europa",
    "Scotland": "Europa", "Turkey": "Europa", "Russia": "Europa", "Ukraine": "Europa",
    "Greece": "Europa", "Austria": "Europa", "Switzerland": "Europa", "Denmark": "Europa",
    "Sweden": "Europa", "Norway": "Europa", "Poland": "Europa", "Croatia": "Europa",
    "Serbia": "Europa", "Czech-Republic": "Europa", "Romania": "Europa", "Ireland": "Europa",
    # Sudamérica
    "Brazil": "Sudamérica", "Argentina": "Sudamérica", "Colombia": "Sudamérica",
    "Chile": "Sudamérica", "Uruguay": "Sudamérica", "Peru": "Sudamérica",
    "Ecuador": "Sudamérica", "Paraguay": "Sudamérica", "Bolivia": "Sudamérica",
    "Venezuela": "Sudamérica",
    # Norte/Centroamérica
    "USA": "Norteamérica", "Mexico": "Norteamérica", "Canada": "Norteamérica",
    "Costa-Rica": "Norteamérica", "Honduras": "Norteamérica", "Panama": "Norteamérica",
    # África
    "Egypt": "África", "Morocco": "África", "Nigeria": "África", "Senegal": "África",
    "Ghana": "África", "Cameroon": "África", "Algeria": "África", "Tunisia": "África",
    "South-Africa": "África", "Ivory-Coast": "África",
    # Asia
    "Japan": "Asia", "South-Korea": "Asia", "China": "Asia", "Saudi-Arabia": "Asia",
    "Qatar": "Asia", "Iran": "Asia", "Australia": "Asia", "India": "Asia",
}

# Competiciones mundiales y continentales (prioridad máxima en el selector)
WORLD_COMPS = {
    "World Cup", "Friendlies", "World Cup - Qualification",
    "UEFA Nations League", "CONMEBOL - Copa America", "Africa Cup of Nations",
    "AFC Asian Cup", "CONCACAF Gold Cup", "Euro Championship",
    "UEFA Champions League", "UEFA Europa League", "UEFA Europa Conference League",
    "CONMEBOL Libertadores", "CONMEBOL Sudamericana", "CONCACAF Champions League",
    "AFC Champions League", "CAF Champions League", "FIFA Club World Cup",
}


def get_leagues_grouped() -> dict:
    """
    Devuelve las ligas activas agrupadas jerárquicamente:
      1. Mundiales y continentales (lo primero)
      2. Por continente → por país
    """
    data = _request("leagues", {"current": "true"}, cache_type="elo")
    world, by_continent = [], {}

    for item in data.get("response", []):
        league = item.get("league", {})
        country = item.get("country", {})
        seasons = item.get("seasons", [])
        cs = next((s for s in seasons if s.get("current")), None)
        if not cs:
            continue
        entry = {
            "id": league.get("id"), "name": league.get("name"),
            "type": league.get("type"), "logo": league.get("logo"),
            "country": country.get("name"), "flag": country.get("flag"),
            "season": cs.get("year"),
        }
        name = league.get("name", "")
        cname = country.get("name", "")
        if name in WORLD_COMPS or cname == "World":
            world.append(entry)
        else:
            cont = COUNTRY_CONTINENT.get(cname, "Otras")
            by_continent.setdefault(cont, {}).setdefault(cname, []).append(entry)

    # Orden de mundiales (mundial primero, luego continentales de clubes)
    wc_priority = {
        "World Cup": 0, "World Cup - Qualification": 1, "UEFA Nations League": 2,
        "CONMEBOL - Copa America": 3, "Euro Championship": 3, "Africa Cup of Nations": 4,
        "UEFA Champions League": 5, "CONMEBOL Libertadores": 6, "UEFA Europa League": 7,
        "Friendlies": 20,
    }
    world.sort(key=lambda l: wc_priority.get(l["name"], 10))

    cont_order = ["Europa", "Sudamérica", "Norteamérica", "África", "Asia", "Otras"]
    ordered_continents = {}
    for c in cont_order:
        if c in by_continent:
            ordered_continents[c] = dict(sorted(by_continent[c].items()))

    return {"world": world, "continents": ordered_continents}


def get_team_statistics(team_id: int, league_id: int, season: int) -> dict:
    """
    Estadísticas de temporada de un equipo en una liga:
    forma, goles, racha, clean sheets, etc.
    """
    data = _request("teams/statistics", {
        "team": team_id, "league": league_id, "season": season,
    }, cache_type="team_stats")
    r = data.get("response", {})
    if not r:
        return {}
    fixtures = r.get("fixtures", {})
    goals = r.get("goals", {})
    return {
        "form": r.get("form", ""),
        "played": fixtures.get("played", {}).get("total", 0),
        "wins": fixtures.get("wins", {}).get("total", 0),
        "draws": fixtures.get("draws", {}).get("total", 0),
        "loses": fixtures.get("loses", {}).get("total", 0),
        "goals_for": goals.get("for", {}).get("total", {}).get("total", 0),
        "goals_against": goals.get("against", {}).get("total", {}).get("total", 0),
        "goals_for_avg": goals.get("for", {}).get("average", {}).get("total", "0"),
        "clean_sheets": r.get("clean_sheet", {}).get("total", 0),
        "biggest_streak_wins": r.get("biggest", {}).get("streak", {}).get("wins", 0),
    }


def get_team_squad_detailed(team_id: int) -> list:
    """
    Plantilla completa con datos por jugador: nombre, posición, edad, número, foto.
    """
    data = _request("players/squads", {"team": team_id}, cache_type="transfermarkt")
    squad = []
    for item in data.get("response", []):
        for p in item.get("players", []):
            squad.append({
                "id": p.get("id"), "name": p.get("name"),
                "age": p.get("age"), "number": p.get("number"),
                "position": p.get("position"), "photo": p.get("photo"),
            })
    return squad


def get_player_season(player_id: int, season: int) -> dict:
    """
    Estadísticas de un jugador en la temporada: rating medio, goles, asistencias.
    """
    data = _request("players", {"id": player_id, "season": season}, cache_type="team_stats")
    resp = data.get("response", [])
    if not resp:
        return {}
    p = resp[0]
    player = p.get("player", {})
    stats = p.get("statistics", [{}])[0] if p.get("statistics") else {}
    games = stats.get("games", {})
    goals = stats.get("goals", {})
    return {
        "id": player.get("id"), "name": player.get("name"),
        "photo": player.get("photo"), "age": player.get("age"),
        "nationality": player.get("nationality"),
        "position": games.get("position"),
        "rating": games.get("rating"),
        "appearances": games.get("appearences"),
        "goals": goals.get("total"), "assists": goals.get("assists"),
    }


def get_lineup_with_values(fixture_id: int, season: int = None) -> dict:
    """
    Alineación de un partido con datos enriquecidos por jugador:
    posición en la cancha (grid), número, rating de temporada.
    Combina /fixtures/lineups con /players para el rating.
    """
    base = get_fixture_lineups(fixture_id)
    # Enriquecer cada titular con su rating de temporada sería 1 request/jugador
    # (costoso). Por eso devolvemos la base con grid y dejamos rating opcional.
    return base


def get_elo_summary(team_name: str, is_national: bool = True) -> dict:
    """
    Wrapper para exponer el ELO numérico crudo desde el scraper de elo.
    """
    from scrapers import elo as elo_scraper
    try:
        if is_national:
            rating = elo_scraper.get_national_elo(team_name)
        else:
            rating = elo_scraper.get_club_elo(team_name)
        return {"team": team_name, "elo": rating, "source": "eloratings.net / clubelo.com"}
    except Exception as e:
        return {"team": team_name, "elo": None, "error": str(e)}
