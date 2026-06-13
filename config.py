"""
VagoScore — Configuración central
Lee secretos desde variables de entorno. NUNCA hardcodear la clave aquí.
"""

import os
from pathlib import Path

# Cargar .env en local (en producción Render inyecta las variables directamente)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


# ─── API-Football ─────────────────────────────────────────────────────────────
# Soporta tanto el host directo (api-football-v1) como RapidAPI.
APIFOOTBALL_KEY = os.environ.get("APIFOOTBALL_KEY", "")

# Si usas RapidAPI, el host es 'api-football-v1.p.rapidapi.com'.
# Si usas el endpoint directo de api-football.com, es 'v3.football.api-sports.io'.
APIFOOTBALL_HOST = os.environ.get("APIFOOTBALL_HOST", "v3.football.api-sports.io")

# Detecta automáticamente el tipo de auth según el host
USE_RAPIDAPI = "rapidapi" in APIFOOTBALL_HOST.lower()

if USE_RAPIDAPI:
    APIFOOTBALL_BASE = f"https://{APIFOOTBALL_HOST}/v3"
    APIFOOTBALL_HEADERS = {
        "x-rapidapi-key": APIFOOTBALL_KEY,
        "x-rapidapi-host": APIFOOTBALL_HOST,
    }
else:
    APIFOOTBALL_BASE = f"https://{APIFOOTBALL_HOST}"
    APIFOOTBALL_HEADERS = {
        "x-apisports-key": APIFOOTBALL_KEY,
    }


def has_apifootball() -> bool:
    """True si la clave está configurada."""
    return bool(APIFOOTBALL_KEY)


# ─── Entorno ──────────────────────────────────────────────────────────────────
IS_PRODUCTION = os.environ.get("FLASK_ENV") == "production"
