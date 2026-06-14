"""
VagoScore — Cliente de Transfermarkt API (felipeall/transfermarkt-api)

Obtiene el valor de mercado REAL en euros desde Transfermarkt, vía la API
REST de código abierto de felipeall. Esto reemplaza la estimación por el
valor oficial cuando está disponible.

Configuración (variable de entorno):
  TRANSFERMARKT_API_URL = URL base de la API
    - Pública de prueba: https://transfermarkt-api.fly.dev  (con rate-limit)
    - Tu propia instancia: https://tu-instancia.onrender.com

Si no se configura, usa la pública por defecto (puede ser lenta o caerse).
"""

import os
import requests
from cache.db import cache_get, cache_set

TM_BASE = os.environ.get("TRANSFERMARKT_API_URL", "https://transfermarkt-api.fly.dev").rstrip("/")
TM_TIMEOUT = 15


def _tm_request(endpoint: str, cache_type: str = "transfermarkt") -> dict:
    """Petición a la Transfermarkt API con caché."""
    cache_key = f"tm_{endpoint.replace('/', '_')}"
    cached = cache_get(cache_key, cache_type)
    if cached is not None:
        return cached
    try:
        url = f"{TM_BASE}/{endpoint.lstrip('/')}"
        resp = requests.get(url, timeout=TM_TIMEOUT, headers={"accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        cache_set(cache_key, data)
        return data
    except requests.RequestException as e:
        print(f"[transfermarkt] Error en {endpoint}: {e}")
        return {}


def search_club(name: str) -> dict:
    """Busca un club por nombre y devuelve el primer resultado."""
    data = _tm_request(f"clubs/search/{requests.utils.quote(name)}")
    results = data.get("results", [])
    return results[0] if results else {}


def search_player(name: str) -> dict:
    """Busca un jugador por nombre."""
    data = _tm_request(f"players/search/{requests.utils.quote(name)}")
    results = data.get("results", [])
    return results[0] if results else {}


def get_club_market_value(club_name: str) -> dict:
    """
    Valor de mercado total de un club en euros (real, de Transfermarkt).
    Devuelve {total_value_m, currency, source} o {} si falla.
    """
    club = search_club(club_name)
    club_id = club.get("id")
    if not club_id:
        return {}
    players = _tm_request(f"clubs/{club_id}/players")
    squad = players.get("players", [])
    total = 0.0
    valued = 0
    for p in squad:
        mv = p.get("marketValue")  # puede venir como número o None
        if isinstance(mv, (int, float)) and mv > 0:
            total += mv
            valued += 1
    if total <= 0:
        return {}
    return {
        "total_value_m": round(total / 1_000_000, 1),
        "currency": "EUR",
        "players_valued": valued,
        "is_estimate": False,
        "source": "Transfermarkt (real)",
    }


def get_player_market_value(player_name: str) -> dict:
    """Valor de mercado de un jugador individual en euros."""
    player = search_player(player_name)
    pid = player.get("id")
    if not pid:
        return {}
    profile = _tm_request(f"players/{pid}/profile")
    mv = profile.get("marketValue")
    return {
        "name": profile.get("name", player_name),
        "market_value": mv,
        "position": profile.get("position", {}).get("main") if isinstance(profile.get("position"), dict) else profile.get("position"),
        "age": profile.get("age"),
        "source": "Transfermarkt",
    }


def is_available() -> bool:
    """Comprueba si la API de Transfermarkt responde."""
    try:
        resp = requests.get(f"{TM_BASE}/", timeout=8)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def test_connection() -> dict:
    """Diagnóstico de la conexión con Transfermarkt API."""
    try:
        resp = requests.get(f"{TM_BASE}/", timeout=10)
        return {
            "ok": resp.status_code == 200,
            "base_url": TM_BASE,
            "http_status": resp.status_code,
            "detail": "Conexión OK" if resp.status_code == 200 else "No responde correctamente",
        }
    except requests.RequestException as e:
        return {"ok": False, "base_url": TM_BASE, "detail": str(e)[:200]}
