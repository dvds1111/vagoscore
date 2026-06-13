"""
VagoScore — Scraper base
Headers rotativos, delays aleatorios, reintentos con backoff.
"""

import time
import random
import requests
from bs4 import BeautifulSoup
from typing import Optional

# Pool de User-Agents reales
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def get_headers(referer: str = None) -> dict:
    h = BASE_HEADERS.copy()
    h["User-Agent"] = random.choice(USER_AGENTS)
    if referer:
        h["Referer"] = referer
    return h


def polite_sleep(min_s: float = 1.5, max_s: float = 4.0) -> None:
    """Espera aleatoria para no saturar el servidor."""
    time.sleep(random.uniform(min_s, max_s))


def fetch_html(
    url: str,
    referer: str = None,
    retries: int = 3,
    timeout: int = 15,
    session: requests.Session = None,
) -> Optional[BeautifulSoup]:
    """
    Descarga una página y devuelve BeautifulSoup.
    Reintenta con backoff exponencial si falla.
    """
    sess = session or requests.Session()
    for attempt in range(retries):
        try:
            polite_sleep(1.0 + attempt, 3.0 + attempt * 2)
            resp = sess.get(
                url,
                headers=get_headers(referer),
                timeout=timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"[scraper] intento {attempt+1}/{retries} fallido para {url}: {e}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None


def fetch_json(
    url: str,
    referer: str = None,
    headers_extra: dict = None,
    retries: int = 3,
    timeout: int = 15,
    session: requests.Session = None,
) -> Optional[dict]:
    """
    Descarga JSON directamente (APIs internas de sitios).
    """
    sess = session or requests.Session()
    h = get_headers(referer)
    h["Accept"] = "application/json, text/plain, */*"
    if headers_extra:
        h.update(headers_extra)
    for attempt in range(retries):
        try:
            polite_sleep(1.0 + attempt, 3.0 + attempt * 2)
            resp = sess.get(url, headers=h, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[scraper-json] intento {attempt+1}/{retries} fallido: {e}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None
