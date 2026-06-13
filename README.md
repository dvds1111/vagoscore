# ⚽ VagoScore

Predictor estadístico de partidos de fútbol. Sin APIs de pago — todo vía scraping inteligente con caché local.

## Fuentes de datos

| Fuente | Qué obtiene | Método |
|---|---|---|
| **Sofascore** | Rating de jugadores (últimos 10 partidos) | API interna JSON |
| **Transfermarkt** | Valor de mercado del plantel | HTML scraping |
| **ELO Ratings** | Ranking ELO de selecciones/clubes | HTML scraping + fallback |
| **H2H** | Historial de enfrentamientos | API interna Sofascore |

## Instalación

### 1. Requisitos
- Python 3.10 o superior
- pip

### 2. Clonar / descomprimir el proyecto
```bash
cd vagoscore
```

### 3. Crear entorno virtual (recomendado)
```bash
python -m venv venv

# Linux / Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 4. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 5. Correr la app
```bash
streamlit run app.py
```

Se abrirá automáticamente en `http://localhost:8501`

---

## Uso

1. En la barra lateral, escribe los nombres de los dos equipos
2. Seleccioná si es **selección nacional** o **club**
3. Opcionalmente pegá la alineación confirmada (un jugador por línea)
4. Ajustá los pesos del modelo si querés
5. Presioná **Predecir partido**

El primer análisis puede tardar 1-2 minutos (scraping). Los siguientes son instantáneos gracias al caché SQLite.

---

## Estructura del proyecto

```
vagoscore/
├── app.py                  # Interfaz Streamlit
├── requirements.txt
├── scrapers/
│   ├── base.py             # Headers, delays, retry
│   ├── sofascore.py        # Ratings y H2H
│   ├── transfermarkt.py    # Valores de mercado
│   └── elo.py              # Rankings ELO
├── engine/
│   ├── pipeline.py         # Orquestador principal
│   └── scorer.py           # Motor de pesos y predicción
└── cache/
    └── db.py               # SQLite cache manager
```

## Modelo de predicción

### Pesos por defecto

| Factor | Peso | Fuente |
|---|---|---|
| Forma reciente jugadores | 25% | Sofascore rating últimos 10 partidos |
| Ranking ELO | 25% | eloratings.net / clubelo.com |
| Química de alineación | 20% | Varianza de ratings, cobertura de datos |
| Historial H2H | 15% | Últimos 8 enfrentamientos (ponderados por recencia) |
| Valor de mercado | 15% | Transfermarkt (total plantel en M€) |

Todos los pesos son ajustables desde la interfaz.

### Cálculo de probabilidades

1. Cada factor se normaliza a escala 0-100
2. Se calcula el score ponderado total por equipo
3. La diferencia de scores se convierte en probabilidades vía función logística
4. Se añade probabilidad de empate con modelo gaussiano (base ~27%)
5. El marcador más probable se estima con distribución de Poisson sobre xG

### Química de alineación

Se mide como:
- **Consistencia** (baja varianza entre ratings de titulares)
- **Cobertura** (% de jugadores con datos reales vs. defaults)
- **Penalización** por eslabones débiles (jugadores con rating < 6.2)

---

## Notas sobre scraping

- Se usan delays aleatorios (1.5–4s entre requests) para no sobrecargar los servidores
- Rotación de User-Agents reales
- Caché SQLite con TTL por tipo de dato:
  - Sofascore ratings: 6 horas
  - Transfermarkt: 48 horas
  - ELO: 24 horas
  - H2H: 24 horas

---

## Limitaciones conocidas

- Sofascore bloquea scraping agresivo — si hay muchos errores, esperá unos minutos y volvé a intentar
- Los valores de Transfermarkt para selecciones pequeñas pueden no estar disponibles (se usa estimación)
- El ELO de clubes depende de clubelo.com que no cubre todas las ligas

## Próximas mejoras (roadmap)

- [ ] Soporte para lesionados / suspendidos (penalización automática)
- [ ] Contexto del partido (fase de torneo, local/visitante neutro)
- [ ] Modelo de aprendizaje con resultados históricos
- [ ] Exportar predicción como PDF
- [ ] API REST para integrar con otras apps
