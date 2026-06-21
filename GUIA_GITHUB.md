# Guía: poner el Monitor en GitHub Actions + Pages

Resultado final: el scanner corre solo cada mañana (~7 UY) y consultás el
dashboard en una URL desde cualquier dispositivo, sin tocar nada.

────────────────────────────────────────────────────────
## PASO 1 — Crear el repositorio
────────────────────────────────────────────────────────
1. Entrá a github.com → botón "+" arriba a la derecha → "New repository".
2. Nombre: `market-monitor` (o el que quieras).
3. Dejalo **Public** (ver nota de privacidad abajo).
4. NO marques "Add README" (ya tenemos uno).
5. "Create repository".

────────────────────────────────────────────────────────
## PASO 2 — Subir los archivos
────────────────────────────────────────────────────────
Opción fácil (web): en la página del repo vacío → "uploading an existing file"
→ arrastrá TODOS estos archivos y carpetas:
   - fetch_data.py
   - universe.py
   - index.html
   - dashboard.html
   - data.json
   - README.md
   - .gitignore
   - la carpeta .github/ (con workflows/scan.yml dentro)
   - la carpeta data_cache/ (¡IMPORTANTE! es tu caché ya descargado)

⚠️ La web de GitHub a veces no deja arrastrar carpetas ocultas (.github).
Si te pasa, usá la opción terminal de abajo.

Opción terminal (desde tu carpeta del proyecto):
   git init
   git add .
   git commit -m "init: market monitor"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/market-monitor.git
   git push -u origin main

────────────────────────────────────────────────────────
## PASO 3 — Cargar la API key como Secret (NUNCA en el código)
────────────────────────────────────────────────────────
1. En el repo → Settings → Secrets and variables → Actions.
2. "New repository secret".
3. Name:  FMP_API_KEY
4. Secret: tu key de FMP (la que regeneraste).
5. "Add secret".

Esto guarda la key cifrada. El Action la lee en runtime; no aparece en logs
ni en el código.

────────────────────────────────────────────────────────
## PASO 4 — Activar GitHub Pages (para ver el dashboard)
────────────────────────────────────────────────────────
1. En el repo → Settings → Pages.
2. En "Source" elegí: Deploy from a branch.
3. Branch: `main`  /  carpeta: `/ (root)`  → Save.
4. Esperá 1-2 min. Te va a aparecer la URL:
   https://TU_USUARIO.github.io/market-monitor/
5. Esa URL es tu dashboard. Guardala / agregala a favoritos del celular.

────────────────────────────────────────────────────────
## PASO 5 — Probar el Action a mano (sin esperar a mañana)
────────────────────────────────────────────────────────
1. En el repo → pestaña "Actions".
2. Si pide habilitar workflows, aceptá.
3. Elegí "Daily Market Scan" → botón "Run workflow" → "Run workflow".
4. Mirá la corrida en vivo. Si sale verde ✓, funcionó: bajó datos, recalculó,
   commiteó el data.json nuevo, y Pages se actualiza solo.

⚠️ Si lo corrés hoy y ya gastaste la cuota de FMP, va a dar error 429.
Esperá al reset diario. Mañana a las 7 corre solo igual.

────────────────────────────────────────────────────────
## NOTA DE PRIVACIDAD
────────────────────────────────────────────────────────
Con repo público + Pages, la URL del dashboard es accesible para cualquiera
que la tenga. NO contiene nada sensible: sólo precios públicos de acciones y
cálculos técnicos. Tu API key va en Secrets (jamás se publica). La URL es
oscura (nadie la adivina). Si igual querés acceso privado, decímelo y vemos
alternativas (descargar data.json como artifact, o password del lado cliente).

────────────────────────────────────────────────────────
## CÓMO QUEDA EL FLUJO DIARIO
────────────────────────────────────────────────────────
  7:00 UY  → GitHub Actions corre fetch_data.py solo
           → baja datos EOD de FMP, recalcula RS/Warren Score
           → commitea data.json actualizado
           → GitHub Pages sirve el dashboard fresco
  Vos      → abrís la URL en el celular/compu cuando quieras. Listo.

Nada que correr a mano. Nunca más.
