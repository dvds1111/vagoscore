"""
VagoScore — Adaptador API-Football → formato del scorer

Produce exactamente las estructuras que espera engine/scorer.py, pero
alimentadas con datos oficiales de API-Football en lugar de scraping.

Contrato esperado por el scorer:
  sofascore_x → {"team_avg_rating": float, "players": [{"avg_rating", "name", "position", "matches"}]}
  elo_x       → {"elo": int}
  market_x    → {"total_value_m": float}   (en millones de €)
  h2h_data    → {"matches": [...], "total": int}
"""

from datetime import datetime
import config
from scrapers.apifootball import _request


# ─── Resolución de equipos ────────────────────────────────────────────────────

def resolve_team(name: str) -> dict:
    """
    Busca un equipo por nombre y devuelve su id, nombre oficial y logo.
    Funciona tanto para clubes como para selecciones.
    """
    data = _request("teams", {"search": name}, cache_type="elo")
    resp = data.get("response", [])
    if not resp:
        return {}
    # Preferir coincidencia exacta de nombre
    lower = name.lower().strip()
    best = None
    for item in resp:
        team = item.get("team", {})
        if team.get("name", "").lower() == lower:
            best = item
            break
    if not best:
        best = resp[0]
    team = best.get("team", {})
    return {
        "id": team.get("id"),
        "name": team.get("name"),
        "logo": team.get("logo"),
        "national": team.get("national", False),
        "country": team.get("country"),
    }


def _current_season(is_national: bool) -> int:
    """Temporada actual aproximada según la fecha."""
    now = datetime.utcnow()
    # Las ligas de clubes europeas usan el año de inicio de temporada
    return now.year if now.month >= 7 else now.year - 1


# ─── 1. Ratings de jugadores (reemplaza Sofascore) ────────────────────────────

def get_team_ratings(team_id: int, season: int, league_id: int = None) -> dict:
    """
    Rating promedio del equipo y de sus jugadores en la temporada.
    Usa /players con paginación. Devuelve formato compatible con el scorer.
    """
    players = []
    page = 1
    max_pages = 3  # límite para no agotar cuota; ~60 jugadores

    params = {"team": team_id, "season": season}
    if league_id:
        params["league"] = league_id

    while page <= max_pages:
        params["page"] = page
        data = _request(f"players", {**params}, cache_type="team_stats")
        resp = data.get("response", [])
        if not resp:
            break
        for item in resp:
            player = item.get("player", {})
            stats_list = item.get("statistics", [])
            if not stats_list:
                continue
            # Tomar la estadística con más minutos (competición principal)
            stats = max(stats_list, key=lambda s: (s.get("games", {}) or {}).get("minutes", 0) or 0)
            games = stats.get("games", {}) or {}
            rating = games.get("rating")
            try:
                rating = float(rating) if rating else None
            except (ValueError, TypeError):
                rating = None
            if rating:
                players.append({
                    "id": player.get("id"),
                    "name": player.get("name"),
                    "avg_rating": round(rating, 2),
                    "position": games.get("position", "?"),
                    "matches": games.get("appearences", 0) or 0,
                    "photo": player.get("photo"),
                    "goals": (stats.get("goals", {}) or {}).get("total", 0),
                })
        paging = data.get("paging", {})
        if page >= paging.get("total", 1):
            break
        page += 1

    # Rating promedio del equipo: media de los 11 mejores por minutos jugados
    rated = sorted(players, key=lambda p: p["matches"], reverse=True)[:11]
    if rated:
        team_avg = round(sum(p["avg_rating"] for p in rated) / len(rated), 2)
    else:
        team_avg = 6.5

    return {
        "team_avg_rating": team_avg,
        "players": players,
        "source": "api-football",
    }


# ─── 2. Valor de mercado (reemplaza Transfermarkt) ────────────────────────────
# API-Football no expone valor de mercado en € directamente. Usamos un proxy
# robusto: el rating colectivo + nivel de competición. Documentado abajo.

def estimate_market_value(team_ratings: dict, elo: int) -> dict:
    """
    Estima el valor de plantilla a partir de la calidad medible.

    API-Football no entrega valor de mercado en euros (ese dato es propietario
    de Transfermarkt). En lugar de scrapear Transfermarkt (que bloquea con 403),
    derivamos un proxy estable de valor a partir de dos señales oficiales:
      - rating colectivo del plantel (calidad individual)
      - ELO del equipo (nivel competitivo demostrado)

    No es el valor exacto en €, pero es una aproximación monótona y consistente:
    equipos mejores obtienen valores más altos, que es lo único que el scorer
    necesita para comparar.
    """
    avg = team_ratings.get("team_avg_rating", 6.5)
    # Mapeo: rating 6.0 → ~50M, 7.0 → ~400M, 7.5 → ~900M (escala no lineal)
    rating_component = max(0, (avg - 5.8)) ** 2 * 280
    elo_component = max(0, (elo - 1500)) / 700 * 400
    estimated_m = round(rating_component + elo_component, 1)
    return {
        "total_value_m": max(10.0, estimated_m),
        "is_estimate": True,
        "source": "estimado (rating + ELO)",
    }


# ─── 3. ELO (reemplaza eloratings.net) ────────────────────────────────────────
# API-Football no da ELO. Lo derivamos de las estadísticas de temporada del
# equipo (forma, % victorias, diferencia de goles) en una escala tipo ELO.

def derive_elo(team_id: int, season: int, league_id: int = None) -> dict:
    """
    Deriva un valor tipo-ELO desde las estadísticas reales del equipo.

    eloratings.net bloquea scraping (403). En su lugar calculamos un rating
    en escala ELO (1300-2200) a partir de datos oficiales de rendimiento:
    porcentaje de puntos, diferencia de goles por partido y racha.
    """
    # Obtener últimos partidos del equipo
    data = _request("fixtures", {"team": team_id, "last": 20}, cache_type="team_stats")
    resp = data.get("response", [])

    if not resp:
        return {"elo": 1700, "is_estimate": True, "source": "default"}

    wins = draws = losses = gf = ga = 0
    for item in resp:
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        status = item.get("fixture", {}).get("status", {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        is_home = teams.get("home", {}).get("id") == team_id
        g_for = goals.get("home" if is_home else "away") or 0
        g_against = goals.get("away" if is_home else "home") or 0
        gf += g_for
        ga += g_against
        if g_for > g_against:
            wins += 1
        elif g_for == g_against:
            draws += 1
        else:
            losses += 1

    n = wins + draws + losses
    if n == 0:
        return {"elo": 1700, "is_estimate": True, "source": "default"}

    points_pct = (wins * 3 + draws) / (n * 3)         # 0..1
    gd_per_game = (gf - ga) / n                         # puede ser negativo

    # Escala ELO: base 1500, + hasta 600 por rendimiento, +/- por dif. goles
    elo = 1500 + points_pct * 600 + gd_per_game * 40
    elo = int(max(1300, min(2200, elo)))

    return {
        "elo": elo,
        "is_estimate": True,
        "source": "derivado de forma reciente",
        "record": {"wins": wins, "draws": draws, "losses": losses,
                   "goals_for": gf, "goals_against": ga, "matches": n},
    }


# ─── 4. Head-to-head (reemplaza Sofascore H2H) ────────────────────────────────

def get_h2h(team_a_id: int, team_b_id: int, last: int = 10) -> dict:
    """Historial de enfrentamientos directos, formato compatible con el scorer."""
    data = _request("fixtures/headtohead", {
        "h2h": f"{team_a_id}-{team_b_id}", "last": last,
    }, cache_type="h2h")

    matches = []
    for item in data.get("response", []):
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        fx = item.get("fixture", {})
        status = fx.get("status", {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        matches.append({
            "date": fx.get("date"),
            "home_id": teams.get("home", {}).get("id"),
            "away_id": teams.get("away", {}).get("id"),
            "home_name": teams.get("home", {}).get("name"),
            "away_name": teams.get("away", {}).get("name"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "winner_home": teams.get("home", {}).get("winner"),
            "winner_away": teams.get("away", {}).get("winner"),
        })

    return {"matches": matches, "total": len(matches)}


# ─── Forma reciente como lista W/D/L (para el panel del frontend) ─────────────

def get_recent_form_wdl(team_id: int, last: int = 10) -> list:
    """Lista de resultados recientes como ['W','D','L',...] del más reciente."""
    data = _request("fixtures", {"team": team_id, "last": last}, cache_type="team_stats")
    out = []
    items = data.get("response", [])
    # API devuelve ascendente por fecha; queremos más reciente primero
    for item in reversed(items):
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        status = item.get("fixture", {}).get("status", {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        is_home = teams.get("home", {}).get("id") == team_id
        gf = goals.get("home" if is_home else "away") or 0
        ga = goals.get("away" if is_home else "home") or 0
        out.append("W" if gf > ga else "D" if gf == ga else "L")
    return out[:last]


def get_recent_matches_detailed(team_id: int, last: int = 10) -> list:
    """
    Últimos partidos con detalle completo: rival, marcador, fecha, local/visita,
    resultado. Para mostrar la lista de últimos partidos enriquecida.
    """
    data = _request("fixtures", {"team": team_id, "last": last}, cache_type="team_stats")
    out = []
    for item in reversed(data.get("response", [])):
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        fx = item.get("fixture", {})
        league = item.get("league", {})
        status = fx.get("status", {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        is_home = teams.get("home", {}).get("id") == team_id
        home = teams.get("home", {})
        away = teams.get("away", {})
        gf = goals.get("home" if is_home else "away") or 0
        ga = goals.get("away" if is_home else "home") or 0
        opponent = away if is_home else home
        out.append({
            "date": fx.get("date"),
            "opponent": opponent.get("name"),
            "opponent_logo": opponent.get("logo"),
            "is_home": is_home,
            "goals_for": gf,
            "goals_against": ga,
            "score": f"{gf}-{ga}",
            "result": "W" if gf > ga else "D" if gf == ga else "L",
            "competition": league.get("name"),
        })
    return out[:last]



# ─── Alineación más probable (cuando no hay confirmada) ───────────────────────

def get_probable_lineup(team_id: int, season: int, league_id: int = None) -> dict:
    """
    Estima la alineación más probable de un equipo a partir de los jugadores
    con más minutos en la temporada y su posición habitual.

    Devuelve formato compatible con la cancha del frontend:
    {formation, starters: [{name, number, pos, grid, rating, photo, market_value}]}
    """
    # Obtener plantilla con estadísticas (rating + minutos + posición)
    ratings = get_team_ratings(team_id, season, league_id)
    players = ratings.get("players", [])
    if not players:
        return {}

    # Clasificar por posición usando el campo "position" del rating
    # Posiciones API-Football: Goalkeeper, Defender, Midfielder, Attacker
    by_pos = {"G": [], "D": [], "M": [], "F": []}
    for p in players:
        pos = (p.get("position") or "").lower()
        if "goal" in pos or pos == "g":
            by_pos["G"].append(p)
        elif "def" in pos or pos == "d":
            by_pos["D"].append(p)
        elif "mid" in pos or pos == "m":
            by_pos["M"].append(p)
        elif "att" in pos or "forward" in pos or pos == "f":
            by_pos["F"].append(p)
        else:
            by_pos["M"].append(p)  # por defecto medio

    # Ordenar cada grupo por partidos jugados (más titular = más probable)
    for k in by_pos:
        by_pos[k].sort(key=lambda x: x.get("matches", 0), reverse=True)

    # Formación 4-3-3 por defecto (la más común)
    formation = "4-3-3"
    needs = {"G": 1, "D": 4, "M": 3, "F": 3}

    # Ajustar si no hay suficientes en alguna línea
    if len(by_pos["F"]) < 3 and len(by_pos["M"]) >= 4:
        formation = "4-4-2"
        needs = {"G": 1, "D": 4, "M": 4, "F": 2}

    starters = []
    # Coordenadas grid: fila:columna (fila 1 = portero)
    grid_positions = {
        "G": [(1, 1)],
        "D": [(2, 1), (2, 2), (2, 3), (2, 4)],
        "M": [(3, 1), (3, 2), (3, 3), (3, 4)],
        "F": [(4, 1), (4, 2), (4, 3)],
    }

    number = 1
    for line in ["G", "D", "M", "F"]:
        count = needs[line]
        coords = grid_positions[line]
        for i in range(count):
            if i < len(by_pos[line]):
                p = by_pos[line][i]
                col = i + 1
                total_in_line = count
                # grid como "fila:columna" centrado
                grid = f"{grid_positions[line][0][0]}:{col}"
                starters.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "number": p.get("id", number) % 99 or number,
                    "pos": line,
                    "grid": grid,
                    "rating": p.get("avg_rating"),
                    "photo": p.get("photo"),
                    "matches": p.get("matches", 0),
                    "goals": p.get("goals", 0),
                })
            number += 1

    return {
        "formation": formation,
        "starters": starters,
        "is_probable": True,
        "coach": None,
        "source": "Alineación probable (jugadores con más minutos)",
    }
