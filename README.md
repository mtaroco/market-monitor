# Monitor de Mercado — Scanner técnico EOD

Dashboard personal de análisis técnico (~125 acciones US líderes por sector),
estilo "Warren Bife". Calcula RS Score y Warren Score (fórmulas propias) sobre
datos EOD de FMP (Financial Modeling Prep).

## Archivos
- `fetch_data.py`  → baja datos de FMP, calcula indicadores, escribe `data.json`
- `universe.py`    → la lista de ~125 tickers (editá a gusto)
- `dashboard.html` → la interfaz (lee `data.json`)
- `data.json`      → estado del mercado (lo regenera el script)
- `data_cache/`    → caché de históricos y perfiles (se crea solo)

## Setup inicial (una sola vez)

### Certificados SSL (sólo macOS, si da CERTIFICATE_VERIFY_FAILED)
Si Python no puede conectarse por HTTPS, corré:
    /Applications/Python\ 3.13/Install\ Certificates.command
(ajustá el número de versión al tuyo). Esto se hace una vez.

### API key
Configurala como variable de entorno (recomendado):
    export FMP_API_KEY="tu_key_de_fmp"
O editá la línea `KEY = ...` en `fetch_data.py`.

## Uso diario
    python3 fetch_data.py          # corrida normal (caché incremental)
    python3 fetch_data.py --full   # fuerza re-descarga completa
    python3 fetch_data.py --mock   # datos sintéticos para probar la UI sin API

Después, levantá el dashboard (NO lo abras con doble-click — el navegador
bloquea fetch() sobre file://):
    python3 -m http.server 8000
    # y entrá a http://localhost:8000/dashboard.html

## Sobre la cuota de FMP (250 req/día)
El universo de ~125 tickers está dimensionado para esto. Plan de corridas:
  • Día 1: baja perfiles (~125) + parte de históricos. Quedan algunos pendientes.
  • Día 2: perfiles ya cacheados → completa los históricos faltantes.
  • Día 3+: sólo ~125 históricos/día para actualizar → entra cómodo y estable.
Si ves "429 / cuota agotada", ya usaste tus 250 llamadas del día. Esperá al
reset (cada 24h) y volvé a correr. No hay cargos.

## Escalar a +300 tickers
FMP free (250/día) no alcanza para actualizar +300 a diario. Si querés el
universo grande, hay que migrar la capa de datos a yfinance (Yahoo, sin límite
práctico de cuota). Es un cambio sólo en fetch_data.py; el dashboard no cambia.

## Notas
- **RS Score**: fuerza relativa vs SPY (multi-horizonte) como percentil 0-100.
- **Warren Score**: score compuesto 0-100 (RS + posición vs medias + volatilidad
  + RSI). Las ponderaciones están en warren_score() — ajustables a tu criterio.
- Automatización: poné fetch_data.py en cron diario post-cierre (~17hs UY) o en
  GitHub Actions.
- Regenerá la API key en FMP si quedó expuesta.
