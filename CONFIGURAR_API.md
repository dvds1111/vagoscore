# 🔑 Configurar tu clave de API-Football

VagoScore funciona sin la clave (usando scraping y datos de respaldo), pero con
API-Football se desbloquea todo: explorar competiciones, ver partidos próximos,
alineaciones con fotos, cuotas reales y más.

## Paso 1 — Conseguir la clave

Tienes dos caminos (elige uno):

**Opción A — Directo de api-football.com (recomendado)**
1. Ve a https://www.api-football.com
2. Crea una cuenta y elige un plan de pago
3. En tu Dashboard verás tu **API Key**
4. Tu host será: `v3.football.api-sports.io`

**Opción B — Vía RapidAPI**
1. Ve a https://rapidapi.com/api-sports/api/api-football
2. Suscríbete a un plan
3. Copia tu **X-RapidAPI-Key**
4. Tu host será: `api-football-v1.p.rapidapi.com`

## Paso 2 — Probar en tu Mac (local)

1. En la carpeta del proyecto, copia el archivo de ejemplo:
   ```bash
   cp .env.example .env
   ```
2. Abre `.env` con cualquier editor de texto y pega tu clave:
   ```
   APIFOOTBALL_KEY=tu_clave_real_aqui
   APIFOOTBALL_HOST=v3.football.api-sports.io
   ```
3. Guarda. Arranca el servidor:
   ```bash
   python server.py
   ```
4. Verás en la terminal: `API-Football: conectada` ✓

⚠️ El archivo `.env` **NUNCA** se sube a GitHub (está en `.gitignore`).
Tu clave queda solo en tu máquina.

## Paso 3 — Configurar en producción (Render)

Como `.env` no sube a GitHub, en Render debes poner la clave a mano:

1. En tu servicio de Render → pestaña **Environment**
2. Click en **Add Environment Variable**
3. Agrega estas dos:

   | Key | Value |
   |-----|-------|
   | `APIFOOTBALL_KEY` | tu clave real |
   | `APIFOOTBALL_HOST` | `v3.football.api-sports.io` |

4. Click **Save Changes** → Render redespliega solo

¡Listo! Tu app en producción ahora usa datos en tiempo real.

## ¿Por qué así y no pegando la clave en el código?

Si escribieras la clave dentro de un archivo `.py` y eso subiera a GitHub,
cualquiera podría verla y usar (o agotar) tu cuota — o generarte cobros.
Las variables de entorno mantienen el secreto fuera del código. Es la forma
en que se hace en cualquier empresa de software.

---

# 🤖 Configurar la IA (Google Gemini) — OPCIONAL

VagoScore puede usar IA para interpretar cada análisis en lenguaje natural.
Usamos **Google Gemini Flash** porque es de los más baratos (tiene capa gratuita).

## Paso 1 — Conseguir la clave (gratis)

1. Ve a https://aistudio.google.com/app/apikey
2. Inicia sesión con tu cuenta de Google
3. Click en **Create API Key**
4. Copia la clave (empieza con `AIza...`)

## Paso 2 — Configurar en Render

1. En tu servicio de Render → pestaña **Environment**
2. Add Environment Variable:

   | Key | Value |
   |-----|-------|
   | `GEMINI_API_KEY` | tu clave (AIza...) |

3. Save Changes → Render redespliega solo

¡Listo! Ahora aparece el botón "Generar análisis IA" en cada partido, y el
escáner de banca incluye una lectura del estratega.

## Nota de costo

Gemini Flash tiene una capa gratuita generosa (suficiente para uso personal).
Si la superas, cuesta centavos por millón de tokens. Cada análisis usa muy
pocos tokens, así que el gasto es mínimo.

⚠️ Igual que con API-Football: la clave va SOLO en las variables de entorno
de Render, nunca en el código ni en el chat.
