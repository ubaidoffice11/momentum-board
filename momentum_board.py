"""
board.py — Momentum Board (leaderboard edition)

Live NSE momentum ranking. Reads universe.py (500 stocks + 38 ETFs), pulls prices
from Yahoo, ranks by weekly / monthly / yearly return, and shows a clean
leaderboard with rank badges and up/down arrows.

Run locally:  py -3.13 -m streamlit run board.py
Deploy:       push board.py + universe.py + requirements.txt to GitHub, then
              connect the repo at share.streamlit.io.
"""

import datetime as dt
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from universe import INDICES, STOCKS
except Exception:
    INDICES = {"Nifty 50 Bees": {"yahoo": "NIFTYBEES.NS"}}
    STOCKS = {"Reliance Industries Ltd.": {"yahoo": "RELIANCE.NS"},
              "HDFC Bank Ltd.": {"yahoo": "HDFCBANK.NS"}}

REFRESH_MINUTES = 5
CHUNK = 50

st.set_page_config(page_title="Momentum Board", page_icon="◆", layout="wide")

# ---------------------------------------------------------------- styling
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0A0E0F; --panel:#121A1C; --panel2:#16201F; --line:#202B2D;
    --text:#E4EBEB; --dim:#7E9092; --faint:#556264;
    --up:#2FD07E; --up-bg:rgba(47,208,126,.12);
    --down:#FF5A4D; --down-bg:rgba(255,90,77,.12);
    --gold:#E8B34A; --mono:'JetBrains Mono',ui-monospace,monospace;
  }
  .stApp{background:var(--bg)}
  html,body,[class*="css"]{font-family:'Sora',-apple-system,sans-serif}
  #MainMenu,footer,header[data-testid="stHeader"]{display:none}
  .block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1040px}

  .hd{display:flex;align-items:center;gap:12px;margin-bottom:2px}
  .diamond{width:26px;height:26px;transform:rotate(45deg);border-radius:6px;
    background:linear-gradient(135deg,var(--gold),#9c7521);
    box-shadow:0 0 20px -4px rgba(232,179,74,.6)}
  .wm{font-weight:800;font-size:22px;letter-spacing:-.02em;color:var(--text)}
  .wm span{color:var(--gold)}
  .live{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);
    font-size:11px;color:var(--up);margin-left:6px}
  .live .dot{width:7px;height:7px;border-radius:50%;background:var(--up);
    box-shadow:0 0 8px var(--up);animation:pulse 1.6s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .sub{color:var(--dim);font-size:12.5px;font-family:var(--mono);margin:2px 0 18px}

  /* streamlit widgets, toned to the theme */
  .stRadio [role="radiogroup"]{gap:6px}
  .stRadio label{color:var(--dim)!important;font-size:13px}
  div[data-baseweb="input"]{background:var(--panel)!important;border-color:var(--line)!important}
  .stTextInput input{color:var(--text)!important;font-family:var(--mono)!important}

  /* leaderboard cards */
  .lb{display:flex;flex-direction:column;gap:7px;margin-top:6px}
  .card{display:grid;grid-template-columns:44px 1fr auto;align-items:center;gap:14px;
    background:var(--panel);border:1px solid var(--line);border-radius:12px;
    padding:12px 16px;transition:border-color .15s, transform .15s}
  .card:hover{border-color:#33454a;transform:translateX(2px)}
  .rank{font-family:var(--mono);font-weight:700;font-size:16px;color:var(--dim);
    text-align:center;width:40px;height:34px;line-height:34px;border-radius:8px;
    background:var(--panel2)}
  .rank.top{color:#1a1206;background:linear-gradient(135deg,var(--gold),#c9922f)}
  .nm{font-weight:600;font-size:15px;color:var(--text);line-height:1.2}
  .tk{font-family:var(--mono);font-size:11.5px;color:var(--faint);margin-top:2px}
  .right{display:flex;align-items:center;gap:16px}
  .big{display:flex;align-items:center;gap:7px;font-family:var(--mono);font-weight:700;
    font-size:17px;min-width:118px;justify-content:flex-end}
  .big.up{color:var(--up)} .big.down{color:var(--down)} .big.flat{color:var(--faint)}
  .arrow{font-size:14px}
  .others{display:flex;gap:14px;font-family:var(--mono);font-size:11px;color:var(--dim);
    min-width:150px;justify-content:flex-end}
  .others b{color:var(--text);font-weight:500}
  .others .u{color:var(--up)} .others .d{color:var(--down)}
  .ltp{font-family:var(--mono);font-size:12px;color:var(--dim);min-width:78px;text-align:right}

  .note{color:var(--faint);font-size:11.5px;font-family:var(--mono);margin:14px 2px 0}
  .foot{color:var(--faint);font-size:11px;margin-top:20px;text-align:center;
    border-top:1px solid var(--line);padding-top:14px;line-height:1.6}
  @media (max-width:680px){
    .others{display:none}
    .ltp{display:none}
    .card{grid-template-columns:40px 1fr auto;padding:11px 13px}
    .big{min-width:96px;font-size:16px}
    .block-container{padding-left:.6rem;padding-right:.6rem}
  }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data
def _returns(close):
    close = close.dropna()
    if close.empty:
        return None
    cur = float(close.iloc[-1]); last = close.index[-1]
    def ref(d):
        s = close[close.index <= last - pd.Timedelta(days=d)]
        return float(s.iloc[-1]) if len(s) else None
    def pct(b):
        return None if not b else round((cur / b - 1) * 100, 2)
    return {"LTP": round(cur, 2), "1W": pct(ref(7)), "1M": pct(ref(30)), "1Y": pct(ref(365))}

@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def fetch(name_to_ticker):
    if yf is None:
        return pd.DataFrame()
    tickers = list(name_to_ticker.values())
    closes = {}
    for i in range(0, len(tickers), CHUNK):
        batch = tickers[i:i + CHUNK]
        try:
            raw = yf.download(batch, period="1y", interval="1d", auto_adjust=True,
                              progress=False, threads=True, group_by="ticker")
        except Exception:
            continue
        for tk in batch:
            try:
                closes[tk] = raw[tk]["Close"] if len(batch) > 1 else raw["Close"]
            except Exception:
                pass
    rows = []
    for name, tk in name_to_ticker.items():
        r = _returns(closes[tk]) if tk in closes else None
        if r and r["1W"] is not None:
            rows.append({"Name": name, "Ticker": tk.replace(".NS", ""), **r})
    return pd.DataFrame(rows)

def rank(df):
    for c in ["1W", "1M", "1Y"]:
        df[c + "R"] = df[c].rank(ascending=False, method="min").astype("Int64")
    return df


# ---------------------------------------------------------------- header
st.markdown(
    '<div class="hd"><div class="diamond"></div>'
    '<div class="wm">Momentum <span>Board</span></div>'
    '<span class="live"><span class="dot"></span>LIVE</span></div>'
    f'<div class="sub">NSE momentum · ranked by return · updated {dt.datetime.now():%H:%M} IST</div>',
    unsafe_allow_html=True)

if yf is None:
    st.error("yfinance isn't installed. Run:  py -3.13 -m pip install yfinance")
    st.stop()

c1, c2, c3 = st.columns([2, 2, 1.4])
with c1:
    horizon = st.radio("Rank by", ["Weekly", "Monthly", "Yearly"], horizontal=True, index=0,
                       label_visibility="collapsed")
with c2:
    query = st.text_input("Search", placeholder="search name or ticker…",
                          label_visibility="collapsed")
with c3:
    topn = st.selectbox("Show", ["Top 25", "Top 50", "Top 100", "All"], label_visibility="collapsed")

HKEY = {"Weekly": "1W", "Monthly": "1M", "Yearly": "1Y"}[horizon]
LIMIT = {"Top 25": 25, "Top 50": 50, "Top 100": 100, "All": 10_000}[topn]


def leaderboard(universe, total):
    name_to_tk = {n: m["yahoo"] for n, m in universe.items()}
    with st.spinner(f"Pulling {len(name_to_tk)} live prices…"):
        df = fetch(name_to_tk)
    if df.empty:
        st.warning("No data came back. If this is hosted, Yahoo may be rate-limiting — retry in a minute.")
        return
    got = len(df)
    df = rank(df)
    if query:
        m = df["Name"].str.contains(query, case=False) | df["Ticker"].str.contains(query, case=False)
        df = df[m]
    df = df.sort_values(HKEY + "R").head(LIMIT)

    def chip(v, label):
        if v is None:
            return f'<span>{label} —</span>'
        cls = "u" if v >= 0 else "d"
        return f'<span>{label} <b class="{cls}">{v:+.1f}%</b></span>'

    cards = []
    for _, r in df.iterrows():
        rk = int(r[HKEY + "R"])
        sel = r[HKEY]
        if sel is None:
            big = '<div class="big flat"><span class="arrow">·</span>—</div>'
        elif sel >= 0:
            big = f'<div class="big up"><span class="arrow">▲</span>+{sel:.2f}%</div>'
        else:
            big = f'<div class="big down"><span class="arrow">▼</span>{sel:.2f}%</div>'
        others = [h for h in ["1W", "1M", "1Y"] if h != HKEY]
        others_html = "".join(chip(r[h], h) for h in others)
        cards.append(
            f'<div class="card">'
            f'<div class="rank {"top" if rk<=3 else ""}">{rk}</div>'
            f'<div><div class="nm">{r["Name"].replace(" Ltd.","")}</div>'
            f'<div class="tk">{r["Ticker"]}</div></div>'
            f'<div class="right">{big}'
            f'<div class="others">{others_html}</div>'
            f'<div class="ltp">₹{r["LTP"]:,.2f}</div></div>'
            f'</div>')
    st.markdown(f'<div class="lb">{"".join(cards)}</div>', unsafe_allow_html=True)
    shown = len(df)
    miss = total - got
    st.markdown(f'<div class="note">Showing {shown} of {got} tracked · '
                f'{"all symbols live" if miss<=0 else f"{miss} not on Yahoo"}</div>',
                unsafe_allow_html=True)


tab1, tab2 = st.tabs([f"Stocks · {len(STOCKS)}", f"Indices & ETFs · {len(INDICES)}"])
with tab1:
    leaderboard(STOCKS, len(STOCKS))
with tab2:
    leaderboard(INDICES, len(INDICES))

st.markdown('<div class="foot">Momentum data for tracking only — not investment advice. '
            'Prices via Yahoo, ~15-min delayed.</div>', unsafe_allow_html=True)
