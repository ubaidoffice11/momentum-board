"""
Momentum Board — a live rotational-ranking alternative to your Google Sheet.

WHAT IT DOES
  • Pulls quotes via Fyers API v3 (the real-time NSE feed you already use).
  • Computes 1-week / 1-month / 1-year returns for every name.
  • Ranks the ETF universe and the stock universe SEPARATELY (1 = strongest).
  • Two tabs: "Indices / ETFs" and "Stocks".
  • Auto-refreshes every 5 minutes. No EXIT/status column.

RUN
  pip install -r requirements.txt
  streamlit run momentum_board.py

DEMO vs LIVE
  DEMO_MODE = True  -> runs immediately on a sample of your sheet, no Fyers needed.
  DEMO_MODE = False -> fill FYERS_CLIENT_ID + FYERS_ACCESS_TOKEN below for live data.

EFFICIENCY NOTE (matters for ~260 symbols)
  The 1W / 1M / 1Y reference closes only change once a day, so daily history is
  cached for 24h; only the live price is re-fetched every 5 min (batched, ~6 calls).
  That keeps you well inside Fyers rate limits.
"""

import datetime as dt
import time
import random
import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except Exception:
    _HAS_AUTOREFRESH = False

# ======================================================================
# 1.  CONFIG  — edit this block
# ======================================================================
DEMO_MODE = True                    # <-- set False once Fyers creds are filled
FYERS_CLIENT_ID = "XXXXXX-100"      # your Fyers app id
FYERS_ACCESS_TOKEN = ""             # daily access token from your TOTP/PIN flow
REFRESH_MINUTES = 5

# Universe — Fyers symbol format is "NSE:<TICKER>-EQ" (ETFs use -EQ too).
# Pre-filled with the 20 ETFs I parsed from your Index sheet; paste the rest.
INDICES = {
    "Nasdaq 100":            "NSE:MON100-EQ",
    "Silver Bees":           "NSE:SILVERBEES-EQ",
    "S&P 500 Top 50 TR":     "NSE:MASPTOP50-EQ",
    "NYSE FANG+ TR":         "NSE:MAFANG-EQ",
    "Gold Bees":             "NSE:GOLDBEES-EQ",
    "Nifty Metal":           "NSE:METALIETF-EQ",
    "Nifty Capital Market":  "NSE:MOCAPITAL-EQ",
    "Nifty Pharma":          "NSE:PHARMABEES-EQ",
    "Defence":               "NSE:MODEFENCE-EQ",
    "CPSE":                  "NSE:CPSEETF-EQ",
    "Hang Seng":             "NSE:HNGSNGBEES-EQ",
    "Nifty Midcap 100":      "NSE:MOM100-EQ",
    "Midcap 150":            "NSE:MIDCAPETF-EQ",
    "NIFTY Alpha 50":        "NSE:ALPHA-EQ",
    "Liquid Fund":           "NSE:LIQUIDCASE-EQ",
    "Nifty Smallcap 250":    "NSE:HDFCSML250-EQ",
    "Nifty 200 Alpha 30":    "NSE:ALPHAETF-EQ",
    "Nifty Next 50":         "NSE:JUNIORBEES-EQ",
    "Nifty Infrastructure":  "NSE:INFRAIETF-EQ",
    "Fin Services Ex-Bank":  "NSE:FINIETF-EQ",
    # ... paste your remaining ETFs here
}
STOCKS = {
    "HFCL Ltd.":                 "NSE:HFCL-EQ",
    "Kirloskar Oil Eng":         "NSE:KIRLOSENG-EQ",
    "Schneider Electric Infra":  "NSE:SCHNEIDER-EQ",
    "Welspun Corp":              "NSE:WELCORP-EQ",
    "Syrma SGS Technology":      "NSE:SYRMA-EQ",
    "Adani Energy Solutions":    "NSE:ADANIENSOL-EQ",
    "Laurus Labs":               "NSE:LAURUSLABS-EQ",
    "Honasa Consumer":           "NSE:HONASA-EQ",
    "Hitachi Energy India":      "NSE:POWERINDIA-EQ",
    "GE Vernova T&D India":      "NSE:GVT&D-EQ",
    # ... paste your remaining ~220 stocks here
}

# ======================================================================
# 2.  DEMO DATA  (used only when DEMO_MODE = True)
#     (name, 1M%, 1Y%) parsed from your PDF; 1W is illustrative in demo.
# ======================================================================
_DEMO_IDX = [
    ("Nasdaq 100",1.03,64.78),("Silver Bees",-5.27,86.56),("S&P 500 Top 50 TR",-2.08,32.25),
    ("NYSE FANG+ TR",-0.05,26.14),("Gold Bees",-2.29,41.35),("Nifty Metal",-0.23,33.30),
    ("Nifty Capital Market",5.85,18.97),("Nifty Pharma",7.30,16.16),("Defence",5.59,15.97),
    ("CPSE",-1.22,3.24),("Hang Seng",-0.04,10.84),("Nifty Midcap 100",5.44,6.71),
    ("Midcap 150",5.58,6.15),("NIFTY Alpha 50",5.85,2.39),("Liquid Fund",0.45,4.89),
    ("Nifty Smallcap 250",8.27,1.68),("Nifty 200 Alpha 30",4.78,2.81),("Nifty Next 50",4.75,6.78),
    ("Nifty Infrastructure",3.69,2.26),("Fin Services Ex-Bank",9.31,7.33),
]
_DEMO_STK = [
    ("HFCL Ltd.",27.67,167.50),("Kirloskar Oil Eng",36.87,171.63),("Schneider Electric Infra",30.94,51.18),
    ("Welspun Corp",17.70,75.58),("Syrma SGS Technology",17.75,106.44),("Adani Energy Solutions",7.71,91.63),
    ("Laurus Labs",10.81,86.69),("Honasa Consumer",14.30,72.80),("Hitachi Energy India",-1.91,64.22),
    ("GE Vernova T&D India",-4.05,86.73),
]

# ======================================================================
# 3.  DATA LAYER
# ======================================================================
def _fyers():
    from fyers_apiv3 import fyersModel
    return fyersModel.FyersModel(
        client_id=FYERS_CLIENT_ID, token=FYERS_ACCESS_TOKEN, is_async=False, log_path=""
    )

def _close_on_or_before(candles, target):
    """candles: list of [epoch,o,h,l,c,v] daily. Return close on/just before target date."""
    best = None
    for c in candles:
        d = dt.datetime.utcfromtimestamp(c[0]).date()
        if d <= target:
            best = c[4]
        else:
            break
    return best

@st.cache_data(ttl=86400, show_spinner=False)
def load_reference_closes(symbols, client_id, token):
    """Once per day: fetch ~14 months of daily candles per symbol,
    return {symbol: {'w':close_1w, 'm':close_1m, 'y':close_1y}}."""
    fy = _fyers()
    today = dt.date.today()
    t_from = (today - dt.timedelta(days=430)).strftime("%Y-%m-%d")
    t_to = today.strftime("%Y-%m-%d")
    ref = {}
    for sym in symbols:
        try:
            resp = fy.history({
                "symbol": sym, "resolution": "D", "date_format": "1",
                "range_from": t_from, "range_to": t_to, "cont_flag": "1",
            })
            candles = resp.get("candles", []) if isinstance(resp, dict) else []
            if not candles:
                ref[sym] = None
                continue
            ref[sym] = {
                "w": _close_on_or_before(candles, today - dt.timedelta(days=7)),
                "m": _close_on_or_before(candles, today - dt.timedelta(days=30)),
                "y": _close_on_or_before(candles, today - dt.timedelta(days=365)),
            }
            time.sleep(0.12)  # stay polite to the rate limiter
        except Exception:
            ref[sym] = None
    return ref

@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def load_live_prices(symbols, client_id, token):
    """Every 5 min: batched last-price for all symbols -> {symbol: ltp}."""
    fy = _fyers()
    out = {}
    syms = list(symbols)
    for i in range(0, len(syms), 50):                 # Fyers quotes: up to 50/call
        batch = syms[i:i + 50]
        try:
            resp = fy.quotes({"symbols": ",".join(batch)})
            for row in (resp.get("d", []) if isinstance(resp, dict) else []):
                sym = row.get("n")
                lp = (row.get("v") or {}).get("lp")
                if sym and lp is not None:
                    out[sym] = lp
        except Exception:
            pass
    return out

def build_live_frame(name_to_symbol):
    symbols = tuple(name_to_symbol.values())
    ref = load_reference_closes(symbols, FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN)
    ltp = load_live_prices(symbols, FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN)
    rows = []
    for name, sym in name_to_symbol.items():
        r, p = ref.get(sym), ltp.get(sym)
        if not r or p is None:
            continue
        def ret(base):
            return None if not base else round((p / base - 1) * 100, 2)
        rows.append({"Name": name, "Ticker": sym.replace("NSE:", "").replace("-EQ", ""),
                     "LTP": round(p, 2), "1W %": ret(r["w"]), "1M %": ret(r["m"]), "1Y %": ret(r["y"])})
    return pd.DataFrame(rows)

def build_demo_frame(demo_rows):
    rows = []
    for name, m1, y1 in demo_rows:
        rows.append({"Name": name, "Ticker": name[:10].upper().replace(" ", ""),
                     "LTP": round(random.uniform(50, 900), 2),
                     "1W %": round(m1 * random.uniform(0.10, 0.40), 2),   # illustrative in demo
                     "1M %": m1, "1Y %": y1})
    return pd.DataFrame(rows)

# ======================================================================
# 4.  RANKING
# ======================================================================
def add_ranks(df):
    for col, rk in [("1W %", "1W Rank"), ("1M %", "1M Rank"), ("1Y %", "1Y Rank")]:
        df[rk] = df[col].rank(ascending=False, method="min").astype("Int64")
    return df

# ======================================================================
# 5.  UI
# ======================================================================
st.set_page_config(page_title="Momentum Board", page_icon="◆", layout="wide")

st.markdown("""
<style>
  .stApp { background:#0E1416; }
  h1,h2,h3,p,span,div { color:#DDE4E4; }
  .blk { font-family:ui-monospace,monospace; }
</style>
""", unsafe_allow_html=True)

if _HAS_AUTOREFRESH and not DEMO_MODE:
    st_autorefresh(interval=REFRESH_MINUTES * 60 * 1000, key="mb_refresh")

c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("## ◆ Momentum Board")
    st.caption("Rotational rank engine · ranked by trailing return · "
               + ("**DEMO — sample data**" if DEMO_MODE else "**LIVE — Fyers**"))
with c2:
    st.metric("Last updated", dt.datetime.now().strftime("%H:%M:%S"),
              help="Refreshes every %d min during market hours (9:15–15:30 IST)." % REFRESH_MINUTES)

rank_by = st.radio("Rank by", ["Weekly", "Monthly", "Yearly"], horizontal=True, index=1)
_sort_col = {"Weekly": "1W Rank", "Monthly": "1M Rank", "Yearly": "1Y Rank"}[rank_by]

def render_tab(name_to_symbol, demo_rows):
    with st.spinner("Fetching…"):
        df = build_demo_frame(demo_rows) if DEMO_MODE else build_live_frame(name_to_symbol)
    if df.empty:
        st.warning("No data returned. In live mode, check your Fyers token and symbol formats.")
        return
    df = add_ranks(df).sort_values(_sort_col).reset_index(drop=True)
    df = df[["1W Rank", "1M Rank", "1Y Rank", "Name", "Ticker", "LTP", "1W %", "1M %", "1Y %"]]

    styler = (df.style
              .background_gradient(cmap="RdYlGn", subset=["1W %", "1M %", "1Y %"], vmin=-40, vmax=40)
              .format({"LTP": "{:,.2f}", "1W %": "{:+.2f}%", "1M %": "{:+.2f}%", "1Y %": "{:+.2f}%"}))
    st.dataframe(styler, use_container_width=True, hide_index=True, height=560,
                 column_config={
                     _sort_col: st.column_config.NumberColumn(_sort_col + "  ▼", width="small"),
                 })
    st.caption(f"{len(df)} names · sorted by {rank_by.lower()} return rank")

tab1, tab2 = st.tabs(["Indices / ETFs", "Stocks"])
with tab1:
    render_tab(INDICES, _DEMO_IDX)
with tab2:
    render_tab(STOCKS, _DEMO_STK)

with st.expander("Go live with Fyers"):
    st.markdown("""
1. Generate today's **access token** with your existing TOTP/PIN auth flow.
2. Set `DEMO_MODE = False` and paste `FYERS_CLIENT_ID` + `FYERS_ACCESS_TOKEN` at the top.
3. Paste your full ETF and stock lists into `INDICES` / `STOCKS` (format `NSE:TICKER-EQ`).
4. Re-run. History is cached 24h; prices refresh every 5 min automatically.

**On Streamlit Cloud:** the filesystem is ephemeral, so keep the token in
`st.secrets` rather than a file, and remember the daily-history cache resets on each
cold start (it simply re-fetches — no data lost).
""")