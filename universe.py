"""
universe.py — carga la lista de tickers desde tickers.txt

Para cambiar qué tickers se escanean, editá tickers.txt (NO este archivo).
Un ticker por línea; las líneas con # son comentarios.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_TICKERS_FILE = os.path.join(_HERE, "tickers.txt")
BENCHMARK = "SPY"

def load_universe(path=_TICKERS_FILE):
    if not os.path.exists(path):
        raise SystemExit(f"No encontré {path}. Creá un tickers.txt con un símbolo por línea.")
    out = []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            # tolera comas/espacios por si pegan varios juntos
            for tok in s.replace(",", " ").split():
                tok = tok.upper().strip()
                if tok and tok not in out:
                    out.append(tok)
    # garantiza que el benchmark esté presente
    if BENCHMARK not in out:
        out.insert(0, BENCHMARK)
    return out

UNIVERSE = load_universe()

if __name__ == "__main__":
    print(f"Total tickers: {len(UNIVERSE)}")
    print(", ".join(UNIVERSE))
