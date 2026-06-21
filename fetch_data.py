#!/usr/bin/env python3
"""
fetch_data.py — Motor de datos para el dashboard de mercado.

Qué hace:
  1. Baja OHLCV histórico (~260 ruedas) de cada ticker desde FMP.
  2. Cachea el histórico en data_cache/ (solo se baja completo la 1ra vez;
     después actualiza incrementalmente para no quemar la cuota).
  3. Calcula TODOS los indicadores derivados: EMA200, SMA50, RSI14,
     volumen relativo, vs máx/mín 52W, RS Score (vs SPY) y Warren Score.
  4. Escribe data.json — el único archivo que lee el dashboard.

Uso:
    export FMP_API_KEY="tu_key"        # o editá KEY abajo
    python3 fetch_data.py              # corrida normal (incremental)
    python3 fetch_data.py --full       # fuerza re-descarga completa
    python3 fetch_data.py --mock       # genera data.json sintético (sin API)

Cuota FMP free = 250 llamadas/día. El universo son ~340 tickers, así que la
PRIMERA corrida completa se hace en 2 días (el script baja lo que puede y
sigue al otro día). Las corridas siguientes usan 1 llamada por ticker para
traer solo las ruedas nuevas — entra cómodo en la cuota diaria.
"""

import os, sys, json, time, math, urllib.request, urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------- config
KEY = os.environ.get("FMP_API_KEY", "CtJXcTT2q3suyne9eEn4WVRLIEGwyPn3")
# API "stable" de FMP (la v3/legacy fue discontinuada para cuentas nuevas)
STABLE = "https://financialmodelingprep.com/stable"
CACHE_DIR = "data_cache"
OUT = "data.json"
HIST_DAYS = 260          # ruedas a mantener (suficiente para EMA200 + 52W)
DAILY_CALL_BUDGET = 240  # margen bajo el límite de 250
BENCHMARK = "SPY"

from universe import UNIVERSE

# ---------------------------------------------------------------- http
class QuotaError(Exception): pass

def _get(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "scanner/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise QuotaError("Rate limit / cuota diaria agotada (429)")
            if e.code == 403:
                body = e.read().decode()[:200]
                raise QuotaError(f"403 Forbidden — key inválida o endpoint no incluido en plan free. {body}")
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None

def fetch_history(symbol):
    """Devuelve lista de barras [{date, open, high, low, close, volume}] asc.
       API stable: /historical-price-eod/full devuelve una LISTA directa
       (no envuelta en {"historical": [...]} como la legacy)."""
    url = f"{STABLE}/historical-price-eod/full?symbol={symbol}&apikey={KEY}"
    data = _get(url)
    # tolerante a ambos formatos por las dudas
    if isinstance(data, dict) and "historical" in data:
        data = data["historical"]
    if not isinstance(data, list) or not data:
        return None
    bars = sorted(data, key=lambda b: b["date"])
    bars = bars[-HIST_DAYS:]  # nos quedamos con las últimas N ruedas
    return [{"date": b["date"], "open": b.get("open"), "high": b.get("high"),
             "low": b.get("low"), "close": b.get("close"),
             "volume": b.get("volume", 0) or 0} for b in bars]

def fetch_profiles(symbols):
    """Trae sector + market cap + nombre. La API stable pide 1 símbolo por
       llamada en /profile, pero el costo es bajo: lo hacemos una sola vez
       y lo cacheamos en data_cache/_profiles.json (rara vez cambia)."""
    cache_file = os.path.join(CACHE_DIR, "_profiles.json")
    cached = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f: cached = json.load(f)
        except Exception: cached = {}
    out = dict(cached)
    missing = [s for s in symbols if s not in cached]
    for s in missing:
        data = _get(f"{STABLE}/profile?symbol={s}&apikey={KEY}")
        if isinstance(data, list) and data:
            p = data[0]
            out[s] = {
                "sector": p.get("sector") or "—",
                "mktCap": p.get("marketCap") or p.get("mktCap") or 0,
                "companyName": p.get("companyName") or s,
            }
    if out != cached:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_file, "w") as f: json.dump(out, f)
    return out

# ---------------------------------------------------------------- cache
def cache_path(sym): return os.path.join(CACHE_DIR, f"{sym}.json")

def load_cache(sym):
    p = cache_path(sym)
    if os.path.exists(p):
        try:
            with open(p) as f: return json.load(f)
        except Exception: return None
    return None

def save_cache(sym, bars):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path(sym), "w") as f: json.dump(bars, f)

# ---------------------------------------------------------------- indicadores
def sma(vals, n):
    if len(vals) < n: return None
    return sum(vals[-n:]) / n

def ema(vals, n):
    if len(vals) < n: return None
    k = 2 / (n + 1)
    e = sum(vals[:n]) / n
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e

def rsi(closes, n=14):
    if len(closes) < n + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[:n]) / n; al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n-1) + gains[i]) / n
        al = (al * (n-1) + losses[i]) / n
    if al == 0: return 100.0
    rs = ag / al
    return 100 - (100 / (1 + rs))

def pct_change(closes, lookback):
    if len(closes) <= lookback: return None
    old = closes[-1-lookback]
    if old == 0: return None
    return (closes[-1] / old - 1) * 100

def rel_strength_raw(closes, bench_closes):
    """
    Fuerza relativa estilo IBD: performance ponderada del ticker / benchmark
    en múltiples horizontes (~1,3,6,12 meses en ruedas), ponderando recientes.
    Devuelve un número crudo; el percentil (0-100) se calcula después sobre
    todo el universo.
    """
    horizons = [(63, 0.4), (126, 0.2), (189, 0.2), (252, 0.2)]
    score = 0.0; wsum = 0.0
    for days, w in horizons:
        c = pct_change(closes, days)
        b = pct_change(bench_closes, days)
        if c is None or b is None: continue
        score += w * (c - b)   # exceso vs benchmark
        wsum += w
    if wsum == 0: return None
    return score / wsum

def rel_volatility(closes, short=5, hist=252):
    """Desvío estándar de retornos últimas 5 ruedas vs histórico 1 año.
       <1 = comprimido (lo que el dashboard llama VOL<0.8)."""
    if len(closes) < hist + 1: 
        hist = len(closes) - 1
        if hist < short + 5: return None
    rets = [closes[i]/closes[i-1]-1 for i in range(1, len(closes))]
    def std(x):
        if len(x) < 2: return 0
        m = sum(x)/len(x)
        return math.sqrt(sum((v-m)**2 for v in x)/len(x))
    s_short = std(rets[-short:])
    s_hist = std(rets[-hist:])
    if s_hist == 0: return None
    return s_short / s_hist

# ---------------------------------------------------------------- percentil
def to_percentiles(values_by_sym):
    """Convierte un dict {sym: raw} en {sym: percentil 0-100}."""
    items = [(s, v) for s, v in values_by_sym.items() if v is not None]
    items.sort(key=lambda x: x[1])
    n = len(items)
    out = {}
    for i, (s, _) in enumerate(items):
        out[s] = round((i / (n - 1)) * 100, 1) if n > 1 else 50.0
    return out

# ---------------------------------------------------------------- warren score
def warren_score(m):
    """
    Score compuesto 0-100. Reconstruido de los criterios visibles en el
    dashboard: RS alto, precio sobre EMA200 y SMA50, >25% sobre mínimo 52w,
    y volatilidad comprimida. Ponderado. Ajustable a gusto.
    """
    pts = 0.0
    # RS Score (peso fuerte): 0-40
    if m.get("rsScore") is not None:
        pts += (m["rsScore"] / 100) * 40
    # Sobre EMA200: 15
    if m.get("vsEma200") is not None and m["vsEma200"] > 0: pts += 15
    # Sobre SMA50: 12
    if m.get("vsSma50") is not None and m["vsSma50"] > 0: pts += 12
    # >25% sobre mínimo 52w: 13
    if m.get("vsMin52w") is not None and m["vsMin52w"] > 25: pts += 13
    # Volatilidad comprimida (<0.8): 10
    if m.get("relVol") is not None and m["relVol"] < 0.8: pts += 10
    # RSI en zona sana (40-75): 10
    if m.get("rsi") is not None and 40 <= m["rsi"] <= 75: pts += 10
    return round(min(pts, 100))

def warren_criteria(m):
    """Los checks booleanos que muestra la tabla Warren Score."""
    return {
        "ema200": bool(m.get("vsEma200") is not None and m["vsEma200"] > 0),
        "sma50":  bool(m.get("vsSma50") is not None and m["vsSma50"] > 0),
        "min25":  bool(m.get("vsMin52w") is not None and m["vsMin52w"] > 25),
        "lowvol": bool(m.get("relVol") is not None and m["relVol"] < 0.8),
    }

# ---------------------------------------------------------------- build
def compute_metrics(sym, bars, bench_closes, profile):
    closes = [b["close"] for b in bars if b["close"]]
    vols   = [b["volume"] for b in bars if b["volume"] is not None]
    if len(closes) < 60:
        return None
    price = closes[-1]
    prev = closes[-2] if len(closes) > 1 else price
    e200 = ema(closes, 200); s50 = sma(closes, 50)
    hi52 = max(closes[-252:]) if len(closes) >= 5 else max(closes)
    lo52 = min(closes[-252:]) if len(closes) >= 5 else min(closes)
    vol_avg5 = sma(vols, 5); vol_avg40 = sma(vols, 40) if len(vols) >= 40 else sma(vols, len(vols))
    vol_today = vols[-1] if vols else 0
    m = {
        "symbol": sym,
        "name": profile.get("companyName", sym),
        "sector": profile.get("sector", "—"),
        "mktCap": profile.get("mktCap", 0),
        "price": round(price, 2),
        "changePct": round((price/prev - 1) * 100, 2) if prev else 0,
        "rsi": round(rsi(closes) or 0, 1),
        "vsEma200": round((price/e200 - 1) * 100, 1) if e200 else None,
        "vsSma50": round((price/s50 - 1) * 100, 1) if s50 else None,
        "vsMax52w": round((price/hi52 - 1) * 100, 1) if hi52 else None,
        "vsMin52w": round((price/lo52 - 1) * 100, 1) if lo52 else None,
        "volRel": round(vol_today / vol_avg5, 2) if vol_avg5 else None,
        "vol5_40": round(vol_avg5 / vol_avg40, 2) if (vol_avg5 and vol_avg40) else None,
        "relVol": round(rel_volatility(closes) or 0, 2),
        "_rsRaw": rel_strength_raw(closes, bench_closes),
        "spark": [round(c, 2) for c in closes[-30:]],   # mini-serie para sparkline
    }
    return m

def build(mock=False, full=False):
    started = datetime.now(timezone.utc)
    if mock:
        return build_mock()

    # benchmark primero
    print(f"[1/4] Benchmark {BENCHMARK}…")
    bench_bars = load_cache(BENCHMARK) if not full else None
    if not bench_bars:
        bench_bars = fetch_history(BENCHMARK)
        if bench_bars: save_cache(BENCHMARK, bench_bars)
    if not bench_bars:
        print("  ✗ No pude traer el benchmark. Abortando."); sys.exit(1)
    bench_closes = [b["close"] for b in bench_bars]

    print("[2/4] Perfiles (sector + market cap) — se cachean 1 sola vez…")
    profiles = {}
    prof_before = 0
    pf = os.path.join(CACHE_DIR, "_profiles.json")
    if os.path.exists(pf):
        try: prof_before = len(json.load(open(pf)))
        except Exception: prof_before = 0
    try:
        profiles = fetch_profiles(UNIVERSE)
    except QuotaError as e:
        print(f"  ! {e}")
        try: profiles = json.load(open(pf))
        except Exception: profiles = {}
    prof_calls = max(0, len(profiles) - prof_before)
    print(f"    perfiles nuevos bajados: {prof_calls} (resto desde caché)")

    print("[3/4] Históricos por ticker (con caché incremental)…")
    calls = 1 + prof_calls            # benchmark + perfiles ya consumieron cuota
    fetched = skipped = cached_used = 0
    today = started.strftime("%Y-%m-%d")
    metrics = []
    quota_hit = False
    for sym in UNIVERSE:
        if sym == BENCHMARK:
            pm = compute_metrics(sym, bench_bars, bench_closes, profiles.get(sym, {}))
            if pm: metrics.append(pm)
            continue
        bars = None if full else load_cache(sym)
        need_fetch = bars is None or (bars and bars[-1]["date"] < today)
        if need_fetch and not quota_hit and calls < DAILY_CALL_BUDGET:
            try:
                fresh = fetch_history(sym); calls += 1
                if fresh:
                    bars = fresh; save_cache(sym, bars); fetched += 1
            except QuotaError as e:
                print(f"  ! cuota agotada en {sym}: {e}")
                quota_hit = True
        elif need_fetch and (quota_hit or calls >= DAILY_CALL_BUDGET):
            skipped += 1     # lo dejamos para la próxima corrida
        if not bars:
            continue
        if not need_fetch:
            cached_used += 1
        pm = compute_metrics(sym, bars, bench_closes, profiles.get(sym, {}))
        if pm: metrics.append(pm)
    print(f"    bajados hoy: {fetched} · desde caché: {cached_used} · "
          f"pendientes para mañana: {skipped} · llamadas usadas: ~{calls}")
    if skipped:
        print(f"  ⓘ Faltan {skipped} tickers por cuota diaria (250/día). "
              f"Volvé a correr el script mañana y completa solo. El dashboard "
              f"ya funciona con los {len(metrics)} que tenés.")

    print("[4/4] RS Score (percentil) + Warren Score…")
    rs_pct = to_percentiles({m["symbol"]: m["_rsRaw"] for m in metrics})
    for m in metrics:
        m["rsScore"] = rs_pct.get(m["symbol"], 50.0)
        # delta RS aprox: comparamos rs raw actual vs el de hace ~5 ruedas
        m["warrenScore"] = warren_score(m)
        m["criteria"] = warren_criteria(m)
        m.pop("_rsRaw", None)

    payload = {
        "generated": started.isoformat(),
        "benchmark": BENCHMARK,
        "count": len(metrics),
        "tickers": sorted(metrics, key=lambda x: x["warrenScore"], reverse=True),
    }
    with open(OUT, "w") as f: json.dump(payload, f)
    print(f"✓ {OUT} escrito — {len(metrics)} tickers.")
    return payload

# ---------------------------------------------------------------- mock
def build_mock():
    """Genera data.json sintético realista para desarrollar/ver la UI sin API."""
    import random
    random.seed(42)
    from universe import UNIVERSE as U
    sectors = ["Technology","Communication Services","Consumer Discretionary",
               "Consumer Staples","Healthcare","Financial Services","Industrials",
               "Energy","Materials","Real Estate","Utilities","ETF"]
    metrics = []
    for sym in U:
        sec = "ETF" if sym in ("SPY","QQQ","IWM","DIA","XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB","XLRE","XLC","TQQQ","SMH","ARKK") else random.choice(sectors[:-1])
        base = random.uniform(20, 600)
        trend = random.uniform(-0.4, 0.6)
        spark = []
        p = base
        for _ in range(30):
            p *= (1 + random.gauss(trend*0.01, 0.02))
            spark.append(round(p, 2))
        price = spark[-1]
        rs = round(random.betavariate(2,2)*100, 1)
        m = {
            "symbol": sym, "name": sym, "sector": sec,
            "mktCap": random.choice([3e12,1e12,5e11,1e11,5e10,1e10]),
            "price": round(price,2),
            "changePct": round(random.gauss(0.5,2.5),2),
            "rsi": round(random.uniform(25,80),1),
            "vsEma200": round(random.gauss(15,30),1),
            "vsSma50": round(random.gauss(5,12),1),
            "vsMax52w": round(-abs(random.gauss(8,10)),1),
            "vsMin52w": round(abs(random.gauss(40,30)),1),
            "volRel": round(random.uniform(0.3,3.0),2),
            "vol5_40": round(random.uniform(0.5,2.5),2),
            "relVol": round(random.uniform(0.4,1.8),2),
            "rsScore": rs,
            "spark": spark,
        }
        m["warrenScore"] = warren_score(m)
        m["criteria"] = warren_criteria(m)
        metrics.append(m)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "benchmark": BENCHMARK, "count": len(metrics), "mock": True,
        "tickers": sorted(metrics, key=lambda x: x["warrenScore"], reverse=True),
    }
    with open(OUT, "w") as f: json.dump(payload, f)
    print(f"✓ {OUT} (MOCK) — {len(metrics)} tickers.")
    return payload

if __name__ == "__main__":
    args = set(sys.argv[1:])
    build(mock="--mock" in args, full="--full" in args)
