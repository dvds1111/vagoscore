"""
VagoScore — Capa de IA (Google Gemini)

Toma todo el análisis estadístico de un partido y genera una interpretación
experta en lenguaje natural: lectura táctica, factores clave, y una valoración
honesta del valor de apuesta.

La clave se lee de la variable de entorno GEMINI_API_KEY (nunca hardcodeada).
Si no hay clave, el módulo se desactiva limpiamente y la app sigue funcionando.

Modelo: gemini-2.0-flash (rápido y muy económico).
"""

import os
import json
import requests

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def has_gemini() -> bool:
    return bool(GEMINI_KEY)


def _call_gemini(prompt: str, max_tokens: int = 800) -> str:
    """Llamada base a Gemini. Devuelve texto o '' si falla."""
    if not GEMINI_KEY:
        return ""
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": max_tokens,
                },
            },
            timeout=25,
        )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()
    except requests.RequestException as e:
        print(f"[gemini] Error: {e}")
        return ""


def analyze_match(prediction_data: dict, api_predictions: dict = None,
                  injuries: dict = None) -> dict:
    """
    Genera el análisis experto de un partido combinando:
      - el VagoScore y sus 5 señales
      - las predicciones propias de API-Football (si hay)
      - lesiones (si hay)

    Devuelve {summary, key_factors[], betting_read, available} 
    """
    if not has_gemini():
        return {"available": False}

    pred = prediction_data.get("prediction", {})
    p = pred.get("prediction", {})
    scores = pred.get("scores", {})
    raw = pred.get("raw", {})
    team_a = prediction_data.get("team_a", "Local")
    team_b = prediction_data.get("team_b", "Visitante")

    # Construir un contexto compacto y estructurado para la IA
    context = {
        "partido": f"{team_a} vs {team_b}",
        "vagoscore": {
            team_a: scores.get(team_a, {}).get("total"),
            team_b: scores.get(team_b, {}).get("total"),
        },
        "probabilidades_modelo": {
            "gana_local": p.get("p_win_a"),
            "empate": p.get("p_draw"),
            "gana_visitante": p.get("p_win_b"),
        },
        "marcador_probable": p.get("most_likely_score"),
        "xg": {team_a: p.get("xg_a"), team_b: p.get("xg_b")},
        "elo": {team_a: raw.get("elo_a"), team_b: raw.get("elo_b")},
        "forma_reciente": {team_a: raw.get("form_a"), team_b: raw.get("form_b")},
    }
    if api_predictions:
        context["api_football_prediccion"] = {
            "consejo": api_predictions.get("advice"),
            "porcentajes": api_predictions.get("percent"),
        }
    if injuries:
        context["lesionados"] = injuries

    prompt = f"""Eres un analista de fútbol experto y honesto que trabaja para VagoScore, una herramienta de análisis estadístico. Analiza este partido con los datos disponibles.

DATOS DEL ANÁLISIS:
{json.dumps(context, ensure_ascii=False, indent=2)}

Responde ÚNICAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura exacta:
{{
  "summary": "2-3 frases con la lectura general del partido en español, mencionando qué dicen los números",
  "key_factors": ["factor 1 breve", "factor 2 breve", "factor 3 breve"],
  "betting_read": "1-2 frases honestas sobre dónde podría estar el valor de apuesta, o si conviene no apostar. Sé prudente y recuerda que nada es seguro en el fútbol."
}}

Sé concreto, usa los datos reales que te di, y mantén un tono profesional pero accesible."""

    text = _call_gemini(prompt, max_tokens=700)
    if not text:
        return {"available": False}

    # Limpiar posibles fences de markdown
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip().rstrip("`").strip()

    try:
        parsed = json.loads(text)
        parsed["available"] = True
        return parsed
    except json.JSONDecodeError:
        # Si no devolvió JSON limpio, usar el texto como summary
        return {"available": True, "summary": text, "key_factors": [], "betting_read": ""}


def explain_bankroll_scan(scan_results: dict, bankroll: float, currency: str) -> str:
    """
    Genera un resumen en lenguaje natural del escáner de banca multi-partido:
    explica la estrategia, por qué esas apuestas, y la gestión de riesgo.
    """
    if not has_gemini():
        return ""

    bets = scan_results.get("recommended_bets", [])
    if not bets:
        return ""

    bets_summary = [
        {
            "partido": b.get("match"),
            "apuesta": b.get("bet_label"),
            "edge": b.get("edge_pct"),
            "monto": b.get("stake"),
        }
        for b in bets[:8]
    ]

    prompt = f"""Eres el estratega de banca de VagoScore. Explica de forma clara y honesta esta cartera de apuestas recomendada para una jornada.

BANCA: {bankroll:,.0f} {currency}
EXPOSICIÓN TOTAL: {scan_results.get('total_exposure_pct')}%
APUESTAS RECOMENDADAS:
{json.dumps(bets_summary, ensure_ascii=False, indent=2)}

En 3-4 frases en español, explica: la lógica de la cartera, por qué estas apuestas tienen valor, y un recordatorio prudente sobre la gestión de riesgo. No uses markdown ni listas, solo texto fluido."""

    return _call_gemini(prompt, max_tokens=400)
