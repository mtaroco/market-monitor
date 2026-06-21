# Universo ~120 tickers: caps principales y más líquidas de cada sector.
# Dimensionado para entrar en la cuota free de FMP (250 req/día):
#   ~120 históricos + perfiles cacheados = actualización diaria completa.
# Para escalar a +300, hay que migrar la capa de datos (yfinance) — ver README.
UNIVERSE = [
    # Technology (15)
    "AAPL","MSFT","NVDA","AVGO","ORCL","CRM","AMD","ADBE","CSCO","ACN","QCOM","AMAT","MU","INTC","TXN",
    # Communication Services (9)
    "GOOGL","META","NFLX","DIS","CMCSA","TMUS","T","VZ","NBIS",
    # Consumer Discretionary (12)
    "AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","BKNG","TJX","GM","CMG","ROKU",
    # Consumer Staples (9)
    "WMT","PG","KO","PEP","COST","PM","MO","MDLZ","CL",
    # Healthcare (13)
    "LLY","UNH","JNJ","MRK","ABBV","TMO","ABT","DHR","PFE","AMGN","ISRG","GILD","MRNA",
    # Financials (15)
    "BRK-B","JPM","V","MA","BAC","WFC","GS","MS","AXP","BLK","C","SCHW","SPGI","COF","BK",
    # Industrials (13)
    "GE","CAT","RTX","HON","UNP","BA","LMT","DE","UPS","ETN","FDX","DAL","UAL",
    # Energy (8)
    "XOM","CVX","COP","SLB","EOG","MPC","PSX","OXY",
    # Materials (7)
    "LIN","SHW","APD","FCX","NEM","NUE","DOW",
    # Real Estate (6)
    "PLD","AMT","EQIX","CCI","PSA","O",
    # Utilities (6)
    "NEE","DUK","SO","D","AEP","SRE",
    # ETFs de referencia / factor (12)
    "SPY","QQQ","IWM","DIA","XLK","XLF","XLE","XLV","XLI","XLY","SMH","TQQQ",
]
seen=set(); UNIVERSE=[x for x in UNIVERSE if not (x in seen or seen.add(x))]
BENCHMARK="SPY"
if __name__=="__main__":
    print(f"Total tickers: {len(UNIVERSE)}")
