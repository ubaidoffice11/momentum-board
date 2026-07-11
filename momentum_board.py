"""
momentum_board.py — Momentum Board (v2, polished + user-friendly)

Live NSE momentum ranking. Reads universe.py, pulls prices from Yahoo, and
renders a fast, app-like leaderboard: search any stock, switch between
This Week / This Month / This Year, tap a stock to see all three at once.

The whole interface is drawn inside a single HTML component so the styling
applies reliably on Streamlit Cloud (injected CSS gets stripped otherwise).
"""

import datetime as dt
import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
st.markdown(
    "<style>.block-container{padding:0!important;max-width:100%!important}"
    "header[data-testid='stHeader']{display:none}"
    "#MainMenu,footer{display:none}.stApp{background:#0B0F12}</style>",
    unsafe_allow_html=True)


# ------------------------------------------------------------------ data
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
    return {"l": round(cur, 2), "w": pct(ref(7)), "m": pct(ref(30)), "y": pct(ref(365))}

@st.cache_data(ttl=REFRESH_MINUTES * 60, show_spinner=False)
def fetch(pairs):
    """pairs: tuple of (name, yahoo_ticker). Returns list of dict rows."""
    if yf is None:
        return []
    tickers = [t for _, t in pairs]
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
    for name, tk in pairs:
        r = _returns(closes[tk]) if tk in closes else None
        if r and r["w"] is not None:
            rows.append({"n": name.replace(" Ltd.", "").replace(" Limited", ""),
                         "t": tk.replace(".NS", ""), **r})
    return rows


stock_pairs = tuple((n, m["yahoo"]) for n, m in STOCKS.items())
etf_pairs = tuple((n, m["yahoo"]) for n, m in INDICES.items())

with st.spinner("Loading live prices — first load takes a minute…"):
    stocks = fetch(stock_pairs)
    etfs = fetch(etf_pairs)

if not stocks and not etfs:
    st.error("Couldn't load prices right now (the data source may be busy). "
             "Refresh in a minute.")
    st.stop()

ist = dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)
DATA = {
    "stocks": stocks, "etfs": etfs,
    "stocksTotal": len(STOCKS), "etfsTotal": len(INDICES),
    "updated": ist.strftime("%d %b, %H:%M"),
}

# ------------------------------------------------------------------ UI
TEMPLATE = r"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#0B0F12; --card:#141A1F; --card2:#182028; --line:#232D34;
    --text:#EAF0F0; --dim:#8A9BA0; --faint:#5A6A70;
    --up:#2FCE7C; --up-bg:rgba(47,206,124,.13);
    --down:#FF5C57; --down-bg:rgba(255,92,87,.13);
    --gold:#F0B54A; --mono:'JetBrains Mono',ui-monospace,monospace;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Sora',-apple-system,sans-serif;background:var(--bg);color:var(--text);
    -webkit-font-smoothing:antialiased}
  .app{display:flex;flex-direction:column;height:860px;max-width:820px;margin:0 auto;padding:0 14px}

  .hd{display:flex;align-items:center;gap:11px;padding:16px 2px 12px}
  .dia{width:24px;height:24px;transform:rotate(45deg);border-radius:6px;flex-shrink:0;
    background:linear-gradient(135deg,var(--gold),#a9781f);box-shadow:0 0 18px -3px rgba(240,181,74,.55)}
  .ttl{font-weight:800;font-size:20px;letter-spacing:-.02em}
  .ttl b{color:var(--gold);font-weight:800}
  .live{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10.5px;color:var(--up)}
  .live i{width:6px;height:6px;border-radius:50%;background:var(--up);box-shadow:0 0 7px var(--up);animation:pl 1.6s infinite}
  @keyframes pl{0%,100%{opacity:1}50%{opacity:.3}}
  .upd{margin-left:auto;font-family:var(--mono);font-size:10.5px;color:var(--faint)}
  .lede{font-size:13px;color:var(--dim);padding:0 2px 14px;line-height:1.5}

  .tabs{display:flex;gap:8px;margin-bottom:10px}
  .tab{flex:1;text-align:center;padding:11px;border-radius:11px;background:var(--card);
    border:1px solid var(--line);color:var(--dim);font-weight:600;font-size:14px;cursor:pointer;
    transition:.14s;user-select:none}
  .tab.on{background:var(--text);color:#0B0F12;border-color:var(--text)}
  .tab .c{font-family:var(--mono);font-size:11px;opacity:.6;margin-left:4px}

  .seg{display:flex;gap:5px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px;margin-bottom:10px}
  .seg button{flex:1;padding:9px;border:0;border-radius:8px;background:transparent;color:var(--dim);
    font-family:'Sora';font-weight:600;font-size:13px;cursor:pointer;transition:.14s}
  .seg button.on{background:var(--gold);color:#221704}

  .search{position:relative;margin-bottom:12px}
  .search input{width:100%;padding:12px 14px 12px 40px;border-radius:11px;border:1px solid var(--line);
    background:var(--card);color:var(--text);font-family:'Sora';font-size:14px;outline:none;transition:.14s}
  .search input:focus{border-color:var(--gold)}
  .search input::placeholder{color:var(--faint)}
  .search .ic{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--faint);font-size:15px}

  .meta{display:flex;justify-content:space-between;align-items:center;padding:0 4px 8px;
    font-size:11.5px;color:var(--faint);font-family:var(--mono)}
  .meta .dir{color:var(--dim);cursor:pointer;user-select:none}
  .meta .dir:hover{color:var(--text)}

  .list{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:7px;padding:2px 2px 20px;
    scrollbar-width:thin;scrollbar-color:var(--line) transparent}
  .list::-webkit-scrollbar{width:8px}.list::-webkit-scrollbar-thumb{background:var(--line);border-radius:4px}

  .row{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:13px 15px;
    cursor:pointer;transition:.14s}
  .row:hover{border-color:#33424a;background:var(--card2)}
  .top{display:grid;grid-template-columns:38px 1fr auto;align-items:center;gap:13px}
  .rk{font-family:var(--mono);font-weight:700;font-size:15px;color:var(--dim);text-align:center;
    height:32px;line-height:32px;border-radius:9px;background:var(--card2)}
  .rk.g1{color:#221704;background:linear-gradient(135deg,var(--gold),#c9922f)}
  .rk.g2{color:#221704;background:linear-gradient(135deg,#d9dde0,#a7aeb2)}
  .rk.g3{color:#221704;background:linear-gradient(135deg,#e0a878,#b47a49)}
  .nm{font-weight:600;font-size:15px;line-height:1.25}
  .tk{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:2px}
  .big{display:flex;align-items:center;gap:6px;font-family:var(--mono);font-weight:700;font-size:16px;
    padding:5px 10px;border-radius:9px;white-space:nowrap}
  .big.up{color:var(--up);background:var(--up-bg)}
  .big.down{color:var(--down);background:var(--down-bg)}
  .big.flat{color:var(--faint);background:var(--card2)}

  .det{display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--line);
    grid-template-columns:repeat(4,1fr);gap:8px}
  .row.open .det{display:grid}
  .det .box{text-align:center}
  .det .k{font-size:10px;color:var(--faint);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
  .det .v{font-family:var(--mono);font-weight:500;font-size:13px}
  .det .v.up{color:var(--up)}.det .v.down{color:var(--down)}.det .v.flat{color:var(--faint)}

  .empty{text-align:center;color:var(--dim);padding:50px 20px;font-size:14px}
  .foot{text-align:center;font-size:10.5px;color:var(--faint);padding:6px 0 2px;font-family:var(--mono)}

  @media (max-width:560px){
    .app{height:100vh;padding:0 11px}
    .ttl{font-size:18px}.upd{display:none}
  }
</style></head>
<body>
<div class="app">
  <div class="hd">
    <div class="dia"></div>
    <div class="ttl">Momentum <b>Board</b></div>
    <span class="live"><i></i>LIVE</span>
    <span class="upd">updated __UPDATED__ IST</span>
  </div>
  <div class="lede">See which stocks are moving up or down, ranked live. Pick a time period, or search for any name.</div>

  <div class="tabs">
    <div class="tab on" data-tab="stocks">Stocks <span class="c" id="cStocks"></span></div>
    <div class="tab" data-tab="etfs">Index / ETFs <span class="c" id="cEtfs"></span></div>
  </div>

  <div class="seg" id="seg">
    <button data-p="w" class="on">This Week</button>
    <button data-p="m">This Month</button>
    <button data-p="y">This Year</button>
  </div>

  <div class="search">
    <span class="ic">&#128269;</span>
    <input id="q" placeholder="Search a stock…  e.g. Reliance, HDFC, Tata">
  </div>

  <div class="meta">
    <span>#1 = strongest &middot; tap any stock for all periods</span>
    <span class="dir" id="dir">Top gainers &#9660;</span>
  </div>

  <div class="list" id="list"></div>
  <div class="foot">Momentum data for tracking only — not investment advice &middot; prices ~15&nbsp;min delayed</div>
</div>

<script>
const DATA = __DATA__;
document.getElementById('cStocks').textContent = DATA.stocks.length;
document.getElementById('cEtfs').textContent = DATA.etfs.length;
const PLABEL = {w:"This week", m:"This month", y:"This year"};
let state = {tab:'stocks', period:'w', query:'', dir:'desc'};

function cls(v){ return v==null ? 'flat' : (v>=0 ? 'up':'down'); }
function fmt(v){ if(v==null) return '—'; return (v>=0?'+':'')+v.toFixed(2)+'%'; }
function arrow(v){ return v==null?'&middot;':(v>=0?'&#9650;':'&#9660;'); }

function render(){
  const p = state.period;
  let rows = DATA[state.tab].slice();
  const valued = rows.filter(x=>x[p]!=null).sort((a,b)=> state.dir==='desc'? b[p]-a[p] : a[p]-b[p]);
  const nulls  = rows.filter(x=>x[p]==null);
  valued.forEach((x,i)=> x._rk=i+1); nulls.forEach(x=> x._rk=null);
  let all = valued.concat(nulls);

  if(state.query){
    const q = state.query.toLowerCase();
    all = all.filter(x=> x.n.toLowerCase().includes(q) || x.t.toLowerCase().includes(q));
  }

  const el = document.getElementById('list');
  if(all.length===0){ el.innerHTML = '<div class="empty">No stock found. Try another name.</div>'; return; }

  el.innerHTML = all.map(x=>{
    const v = x[p];
    const rkClass = x._rk===1?'g1':x._rk===2?'g2':x._rk===3?'g3':'';
    const rk = x._rk==null?'&ndash;':x._rk;
    const det = ['w','m','y'].map(k=>
      `<div class="box"><div class="k">${PLABEL[k].replace('This ','')}</div>`+
      `<div class="v ${cls(x[k])}">${fmt(x[k])}</div></div>`).join('')
      + `<div class="box"><div class="k">Price</div><div class="v">&#8377;${x.l.toLocaleString('en-IN')}</div></div>`;
    return `<div class="row" onclick="this.classList.toggle('open')">
      <div class="top">
        <div class="rk ${rkClass}">${rk}</div>
        <div><div class="nm">${x.n}</div><div class="tk">${x.t}</div></div>
        <div class="big ${cls(v)}">${arrow(v)} ${fmt(v)}</div>
      </div>
      <div class="det">${det}</div>
    </div>`;
  }).join('');
  document.getElementById('list').scrollTop = 0;
}

document.querySelectorAll('.tab').forEach(t=> t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  t.classList.add('on'); state.tab=t.dataset.tab; render();
});
document.querySelectorAll('#seg button').forEach(b=> b.onclick=()=>{
  document.querySelectorAll('#seg button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); state.period=b.dataset.p; render();
});
document.getElementById('q').addEventListener('input', e=>{ state.query=e.target.value.trim(); render(); });
document.getElementById('dir').onclick = function(){
  state.dir = state.dir==='desc'?'asc':'desc';
  this.innerHTML = state.dir==='desc' ? 'Top gainers &#9660;' : 'Top losers &#9650;';
  render();
};
render();
</script>
</body></html>
"""

html = TEMPLATE.replace("__DATA__", json.dumps(DATA)).replace("__UPDATED__", DATA["updated"])
components.html(html, height=880, scrolling=False)
