"""
VagoScore — Cache manager (SQLite)
Evita scraping repetido. TTL configurable por tipo de dato.
"""

import sqlite3
import json
import time
import os
import tempfile
from pathlib import Path

# En local guarda junto al código; en producción (Render) usa carpeta temporal escribible
if os.environ.get("FLASK_ENV") == "production":
    DB_PATH = Path(tempfile.gettempdir()) / "vagoscore.db"
else:
    DB_PATH = Path(__file__).parent / "vagoscore.db"

# TTL en segundos por tipo de dato
TTL = {
    "sofascore_player":  3600 * 6,   # 6h  — forma reciente
    "transfermarkt":     3600 * 48,  # 48h — valores de mercado
    "elo":               3600 * 24,  # 24h — ranking ELO
    "h2h":               3600 * 24,  # 24h — historial H2H
    "lineup":            3600 * 2,   # 2h  — alineación confirmada
    "team_stats":        3600 * 12,  # 12h — estadísticas de equipo
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key      TEXT PRIMARY KEY,
            data     TEXT NOT NULL,
            cached_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def cache_get(key: str, data_type: str) -> dict | None:
    """Devuelve datos cacheados si están vigentes, si no None."""
    ttl = TTL.get(data_type, 3600)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data, cached_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row and (time.time() - row["cached_at"]) < ttl:
            return json.loads(row["data"])
    return None


def cache_set(key: str, data: dict) -> None:
    """Guarda datos en caché."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, cached_at) VALUES (?, ?, ?)",
            (key, json.dumps(data, ensure_ascii=False), time.time())
        )
        conn.commit()


def cache_clear(pattern: str = None) -> int:
    """Limpia caché. Si pattern, solo entradas que contengan ese string."""
    with get_conn() as conn:
        if pattern:
            cur = conn.execute(
                "DELETE FROM cache WHERE key LIKE ?", (f"%{pattern}%",)
            )
        else:
            cur = conn.execute("DELETE FROM cache")
        conn.commit()
        return cur.rowcount


def cache_stats() -> dict:
    """Estadísticas del caché."""
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        size = os.path.getsize(DB_PATH) if DB_PATH.exists() else 0
        return {"entries": total, "size_kb": round(size / 1024, 1)}
