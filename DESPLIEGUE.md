# 🚀 Desplegar VagoScore con URL pública (Render)

Esta guía te lleva de tu Mac a una URL pública en internet, gratis, en ~20 minutos.

---

## Requisitos previos

1. Una cuenta de **GitHub** (gratis) → https://github.com
2. Una cuenta de **Render** (gratis) → https://render.com (puedes registrarte con tu GitHub)
3. Tener `git` instalado en tu Mac (viene por defecto; verifica con `git --version`)

---

## Paso 1 — Subir el código a GitHub

Abre la terminal en la carpeta del proyecto:

```bash
cd ~/Downloads/vagoscore     # o donde lo tengas

# Inicializar repositorio
git init
git add .
git commit -m "VagoScore - primera versión"
```

Ahora crea un repositorio vacío en GitHub:
1. Ve a https://github.com/new
2. Nombre: `vagoscore` (o el que quieras)
3. Déjalo **público** o **privado**, da igual
4. **NO** marques "Add a README" (ya tenemos uno)
5. Click en **Create repository**

GitHub te mostrará unos comandos. Usa los de "push an existing repository":

```bash
git remote add origin https://github.com/TU-USUARIO/vagoscore.git
git branch -M main
git push -u origin main
```

(Te pedirá tu usuario y un token de GitHub. Si no tienes token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token → marca "repo".)

---

## Paso 2 — Desplegar en Render

1. Entra a https://dashboard.render.com
2. Click en **New +** → **Web Service**
3. Conecta tu cuenta de GitHub y selecciona el repositorio `vagoscore`
4. Render detectará automáticamente el archivo `render.yaml` y la configuración
5. Si te pide configurar manualmente, usa estos valores:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn server:app --bind 0.0.0.0:$PORT --timeout 180 --workers 1`
   - **Plan:** Free
6. Click en **Create Web Service**

Render empezará a construir y desplegar. Tarda 2-5 minutos la primera vez.

---

## Paso 3 — ¡Tu URL pública!

Cuando termine, Render te da una URL del estilo:

```
https://vagoscore.onrender.com
```

Esa es tu app, accesible desde cualquier lugar del mundo. 🎉

---

## ⚠️ Cosas que debes saber del plan gratis de Render

- **Se duerme tras 15 min de inactividad.** La primera visita después de dormir tarda ~30-50 segundos en despertar. Las siguientes son rápidas. (En planes pagos no se duerme.)
- **El scraping puede ser lento o fallar** desde la IP de Render, porque algunos sitios (Sofascore) bloquean IPs de datacenters. Si ves muchos errores de scraping en producción que no veías en tu Mac, es por esto. El código usa datos de respaldo (fallback) cuando falla, así que la app sigue funcionando.
- **El caché se borra al dormir/reiniciar.** Por eso lo movimos a carpeta temporal. No pierdes la app, solo el caché.

---

## Actualizar la app después de cambios

Cada vez que cambies código:

```bash
git add .
git commit -m "descripción del cambio"
git push
```

Render detecta el push y redespliega automáticamente. No tienes que hacer nada más.

---

## Alternativa: Railway (también gratis)

Si Render no te convence, Railway es muy similar:
1. https://railway.app → New Project → Deploy from GitHub repo
2. Selecciona el repo
3. Railway detecta Python automáticamente
4. En Settings → añade el Start Command: `gunicorn server:app --bind 0.0.0.0:$PORT --timeout 180`

Railway da $5 de crédito gratis al mes, suficiente para un proyecto pequeño.

---

## ¿Y un dominio propio?

Cuando quieras algo como `vagoscore.com` en vez de `vagoscore.onrender.com`:
1. Compra el dominio (Namecheap, Google Domains, ~$10/año)
2. En Render → tu servicio → Settings → Custom Domains → añade tu dominio
3. Render te da los registros DNS que debes poner en tu proveedor de dominio

Eso ya es cosmético — la app funciona igual con la URL gratuita de Render.
