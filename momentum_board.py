"""
momentum_board.py — Momentum Board (v3: live board + practice portfolios)

Adds paper-trading portfolios saved in the visitor's browser (localStorage):
  • create multiple portfolios, each with a strategy name
  • add stocks with a quantity — entry price is captured on the day added
  • live return since entry, per holding and for the whole portfolio

Everything renders inside one HTML component so styling applies reliably on
Streamlit Cloud, and the portfolio data lives in the user's own browser.
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
    st.error("Couldn't load prices right now (the data source may be busy). Refresh in a minute.")
    st.stop()

ist = dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)
DATA = {"stocks": stocks, "etfs": etfs,
        "stocksTotal": len(STOCKS), "etfsTotal": len(INDICES),
        "updated": ist.strftime("%d %b, %H:%M"), "today": ist.strftime("%Y-%m-%d")}

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
  body{font-family:'Sora',-apple-system,sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased}
  .app{display:flex;flex-direction:column;height:900px;max-width:820px;margin:0 auto;padding:0 14px}
  button{font-family:'Sora';cursor:pointer}

  .hd{display:flex;align-items:center;gap:11px;padding:16px 2px 10px}
  .dia{width:24px;height:24px;transform:rotate(45deg);border-radius:6px;flex-shrink:0;
    background:linear-gradient(135deg,var(--gold),#a9781f);box-shadow:0 0 18px -3px rgba(240,181,74,.55)}
  .ttl{font-weight:800;font-size:20px;letter-spacing:-.02em}
  .ttl b{color:var(--gold)}
  .live{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10.5px;color:var(--up)}
  .live i{width:6px;height:6px;border-radius:50%;background:var(--up);box-shadow:0 0 7px var(--up);animation:pl 1.6s infinite}
  @keyframes pl{0%,100%{opacity:1}50%{opacity:.3}}
  .upd{margin-left:auto;font-family:var(--mono);font-size:10.5px;color:var(--faint)}

  .mode{display:flex;gap:8px;margin:6px 0 12px}
  .mode button{flex:1;padding:12px;border-radius:12px;border:1px solid var(--line);background:var(--card);
    color:var(--dim);font-weight:700;font-size:14px;transition:.14s}
  .mode button.on{background:var(--text);color:#0B0F12;border-color:var(--text)}

  .tabs{display:flex;gap:8px;margin-bottom:10px}
  .tab{flex:1;text-align:center;padding:11px;border-radius:11px;background:var(--card);border:1px solid var(--line);
    color:var(--dim);font-weight:600;font-size:14px;cursor:pointer;transition:.14s;user-select:none}
  .tab.on{background:var(--gold);color:#221704;border-color:var(--gold)}
  .tab .c{font-family:var(--mono);font-size:11px;opacity:.6;margin-left:4px}

  .seg{display:flex;gap:5px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px;margin-bottom:10px}
  .seg button{flex:1;padding:9px;border:0;border-radius:8px;background:transparent;color:var(--dim);font-weight:600;font-size:13px;transition:.14s}
  .seg button.on{background:var(--gold);color:#221704}

  .search{position:relative;margin-bottom:12px}
  .search input{width:100%;padding:12px 14px 12px 40px;border-radius:11px;border:1px solid var(--line);
    background:var(--card);color:var(--text);font-family:'Sora';font-size:14px;outline:none;transition:.14s}
  .search input:focus{border-color:var(--gold)}
  .search input::placeholder{color:var(--faint)}
  .search .ic{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--faint);font-size:15px}

  .meta{display:flex;justify-content:space-between;align-items:center;padding:0 4px 8px;font-size:11.5px;color:var(--faint);font-family:var(--mono)}
  .meta .dir{color:var(--dim);cursor:pointer;user-select:none}
  .meta .dir:hover{color:var(--text)}

  .list{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:7px;padding:2px 2px 20px;
    scrollbar-width:thin;scrollbar-color:var(--line) transparent}
  .list::-webkit-scrollbar{width:8px}.list::-webkit-scrollbar-thumb{background:var(--line);border-radius:4px}

  .row{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:13px 15px;cursor:pointer;transition:.14s}
  .row:hover{border-color:#33424a;background:var(--card2)}
  .rtop{display:grid;grid-template-columns:38px 1fr auto;align-items:center;gap:13px}
  .rk{font-family:var(--mono);font-weight:700;font-size:15px;color:var(--dim);text-align:center;height:32px;line-height:32px;border-radius:9px;background:var(--card2)}
  .rk.g1{color:#221704;background:linear-gradient(135deg,var(--gold),#c9922f)}
  .rk.g2{color:#221704;background:linear-gradient(135deg,#d9dde0,#a7aeb2)}
  .rk.g3{color:#221704;background:linear-gradient(135deg,#e0a878,#b47a49)}
  .nm{font-weight:600;font-size:15px;line-height:1.25}
  .tk{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:2px}
  .big{display:flex;align-items:center;gap:6px;font-family:var(--mono);font-weight:700;font-size:16px;padding:5px 10px;border-radius:9px;white-space:nowrap}
  .big.up{color:var(--up);background:var(--up-bg)} .big.down{color:var(--down);background:var(--down-bg)} .big.flat{color:var(--faint);background:var(--card2)}
  .det{display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--line);grid-template-columns:repeat(4,1fr);gap:8px}
  .row.open .det{display:grid}
  .det .box{text-align:center}
  .det .k{font-size:10px;color:var(--faint);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
  .det .v{font-family:var(--mono);font-weight:500;font-size:13px}
  .det .v.up{color:var(--up)}.det .v.down{color:var(--down)}.det .v.flat{color:var(--faint)}
  .empty{text-align:center;color:var(--dim);padding:44px 20px;font-size:14px;line-height:1.6}

  /* ------ portfolio ------ */
  .pbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
  .pbar h2{font-size:16px;font-weight:700}
  .btn{padding:10px 15px;border-radius:10px;border:0;background:var(--gold);color:#221704;font-weight:700;font-size:13px}
  .btn.sec{background:var(--card);color:var(--text);border:1px solid var(--line)}
  .btn.dan{background:transparent;color:var(--down);border:1px solid var(--down)}
  .btn.sm{padding:7px 11px;font-size:12px}
  .pcard{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:15px;cursor:pointer;transition:.14s;margin-bottom:8px}
  .pcard:hover{border-color:#33424a;background:var(--card2)}
  .pcard .pn{font-weight:700;font-size:16px}
  .pcard .psub{font-size:12px;color:var(--dim);margin-top:3px;font-family:var(--mono)}
  .pcard .pret{float:right;font-family:var(--mono);font-weight:700;font-size:18px}
  .pret.up{color:var(--up)}.pret.down{color:var(--down)}.pret.flat{color:var(--faint)}

  .psum{background:linear-gradient(135deg,#141A1F,#10161b);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
  .psum .pbig{font-family:var(--mono);font-weight:800;font-size:30px;letter-spacing:-.01em}
  .psum .pbig.up{color:var(--up)}.psum .pbig.down{color:var(--down)}.psum .pbig.flat{color:var(--text)}
  .psum .prow{display:flex;justify-content:space-between;margin-top:10px;font-size:12.5px;color:var(--dim);font-family:var(--mono)}
  .psum .prow b{color:var(--text);font-weight:500}

  .hrow{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:7px;display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center}
  .hrow .hn{font-weight:600;font-size:14px}
  .hrow .hsub{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:2px}
  .hrow .hret{font-family:var(--mono);font-weight:700;font-size:15px;text-align:right}
  .hret.up{color:var(--up)}.hret.down{color:var(--down)}.hret.flat{color:var(--faint)}
  .hrow .hx{color:var(--faint);font-size:18px;cursor:pointer;padding:0 4px;background:none;border:0}
  .hrow .hx:hover{color:var(--down)}

  .field{margin-bottom:10px}
  .field label{display:block;font-size:12px;color:var(--dim);margin-bottom:5px}
  .inp{width:100%;padding:11px 13px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--text);font-family:'Sora';font-size:14px;outline:none}
  .inp:focus{border-color:var(--gold)}
  .addres{max-height:230px;overflow-y:auto;margin:8px 0}
  .ares{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border:1px solid var(--line);border-radius:9px;margin-bottom:6px;cursor:pointer}
  .ares:hover{border-color:var(--gold);background:var(--card2)}
  .ares.sel{border-color:var(--gold);background:var(--card2)}
  .ares .ap{font-family:var(--mono);font-size:12px;color:var(--dim)}

  .foot{text-align:center;font-size:10.5px;color:var(--faint);padding:6px 0 2px;font-family:var(--mono)}
  @media (max-width:560px){.app{height:100vh;padding:0 11px}.ttl{font-size:18px}.upd{display:none}}
</style></head>
<body>
<div class="app">
  <div class="hd">
    <div class="dia"></div>
    <div class="ttl">Momentum <b>Board</b></div>
    <span class="live"><i></i>LIVE</span>
    <span class="upd">updated __UPDATED__ IST</span>
  </div>

  <div class="mode">
    <button class="on" data-mode="board">&#128202; Live Board</button>
    <button data-mode="port">&#128188; My Portfolios</button>
  </div>

  <!-- ===== BOARD VIEW ===== -->
  <div id="boardView" style="flex:1;display:flex;flex-direction:column;min-height:0">
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
      <span>#1 = strongest &middot; tap a stock for all periods</span>
      <span class="dir" id="dir">Top gainers &#9660;</span>
    </div>
    <div class="list" id="list"></div>
  </div>

  <!-- ===== PORTFOLIO VIEW ===== -->
  <div id="portView" style="flex:1;display:none;flex-direction:column;min-height:0">
    <div id="pList" style="flex:1;display:flex;flex-direction:column;min-height:0"></div>
    <div id="pDetail" style="flex:1;display:none;flex-direction:column;min-height:0"></div>
    <div id="pAdd" style="flex:1;display:none;flex-direction:column;min-height:0"></div>
  </div>

  <div class="foot">Practice / demo investing &middot; not real money &middot; not investment advice &middot; prices ~15&nbsp;min delayed</div>
</div>

<script>
const DATA = __DATA__;
const TODAY = DATA.today;
document.getElementById('cStocks').textContent = DATA.stocks.length;
document.getElementById('cEtfs').textContent = DATA.etfs.length;

// price + name lookup across everything
const MAP = {};
DATA.stocks.concat(DATA.etfs).forEach(x=> MAP[x.t] = x);
const ALL = DATA.stocks.concat(DATA.etfs);

const PLABEL = {w:"This week", m:"This month", y:"This year"};
function cls(v){ return v==null?'flat':(v>=0?'up':'down'); }
function fmt(v){ return v==null?'—':((v>=0?'+':'')+v.toFixed(2)+'%'); }
function arrow(v){ return v==null?'&middot;':(v>=0?'&#9650;':'&#9660;'); }
function rup(n){ return '&#8377;'+Math.round(n).toLocaleString('en-IN'); }

/* ================= BOARD ================= */
let bstate = {tab:'stocks', period:'w', query:'', dir:'desc'};
function renderBoard(){
  const p=bstate.period; let rows=DATA[bstate.tab].slice();
  const val=rows.filter(x=>x[p]!=null).sort((a,b)=> bstate.dir==='desc'?b[p]-a[p]:a[p]-b[p]);
  const nul=rows.filter(x=>x[p]==null);
  val.forEach((x,i)=>x._rk=i+1); nul.forEach(x=>x._rk=null);
  let all=val.concat(nul);
  if(bstate.query){const q=bstate.query.toLowerCase();all=all.filter(x=>x.n.toLowerCase().includes(q)||x.t.toLowerCase().includes(q));}
  const el=document.getElementById('list');
  if(!all.length){el.innerHTML='<div class="empty">No stock found. Try another name.</div>';return;}
  el.innerHTML=all.map(x=>{
    const v=x[p];const g=x._rk===1?'g1':x._rk===2?'g2':x._rk===3?'g3':'';const rk=x._rk==null?'&ndash;':x._rk;
    const det=['w','m','y'].map(k=>`<div class="box"><div class="k">${PLABEL[k].replace('This ','')}</div><div class="v ${cls(x[k])}">${fmt(x[k])}</div></div>`).join('')
      +`<div class="box"><div class="k">Price</div><div class="v">${rup(x.l)}</div></div>`;
    return `<div class="row" onclick="this.classList.toggle('open')"><div class="rtop">
      <div class="rk ${g}">${rk}</div>
      <div><div class="nm">${x.n}</div><div class="tk">${x.t}</div></div>
      <div class="big ${cls(v)}">${arrow(v)} ${fmt(v)}</div></div><div class="det">${det}</div></div>`;
  }).join('');
  el.scrollTop=0;
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');bstate.tab=t.dataset.tab;renderBoard();});
document.querySelectorAll('#seg button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#seg button').forEach(x=>x.classList.remove('on'));b.classList.add('on');bstate.period=b.dataset.p;renderBoard();});
document.getElementById('q').addEventListener('input',e=>{bstate.query=e.target.value.trim();renderBoard();});
document.getElementById('dir').onclick=function(){bstate.dir=bstate.dir==='desc'?'asc':'desc';this.innerHTML=bstate.dir==='desc'?'Top gainers &#9660;':'Top losers &#9650;';renderBoard();};

/* ================= PORTFOLIOS (browser-saved) ================= */
const PKEY='mb_portfolios_v1';
function loadP(){try{return JSON.parse(localStorage.getItem(PKEY))||[];}catch(e){return window._pfallback||[];}}
function saveP(a){try{localStorage.setItem(PKEY,JSON.stringify(a));}catch(e){window._pfallback=a;}}
function uid(){return 'p'+Date.now()+Math.floor(Math.random()*999);}

function stats(port){
  let cost=0,val=0,earliest=null,n=0;
  port.holdings.forEach(h=>{
    const cur=MAP[h.t]?MAP[h.t].l:h.entry;
    cost+=h.entry*h.qty; val+=cur*h.qty; n++;
    if(!earliest||h.date<earliest) earliest=h.date;
  });
  const ret=cost>0?((val/cost-1)*100):0;
  return {cost,val,ret,earliest,n};
}
function daysHeld(d){return Math.max(0,Math.floor((new Date(TODAY)-new Date(d))/86400000));}

function showPort(which){
  document.getElementById('pList').style.display   = which==='list'?'flex':'none';
  document.getElementById('pDetail').style.display = which==='detail'?'flex':'none';
  document.getElementById('pAdd').style.display    = which==='add'?'flex':'none';
}

function renderPList(){
  const ports=loadP(); const el=document.getElementById('pList');
  let head=`<div class="pbar"><h2>My Portfolios</h2><button class="btn" onclick="newPort()">+ New portfolio</button></div>`;
  if(!ports.length){
    el.innerHTML=head+`<div class="empty">No portfolios yet.<br>Create one and give it a <b>strategy name</b><br>like &ldquo;Momentum Top 10&rdquo; or &ldquo;My Picks&rdquo;.<br><br>Then add stocks and watch how they'd do.</div>`;
    showPort('list');return;
  }
  const cards=ports.map(p=>{const s=stats(p);const c=s.ret>0?'up':s.ret<0?'down':'flat';
    return `<div class="pcard" onclick="openPort('${p.id}')">
      <span class="pret ${c}">${s.ret>0?'+':''}${s.ret.toFixed(2)}%</span>
      <div class="pn">${p.name}</div>
      <div class="psub">${s.n} stock${s.n!==1?'s':''} &middot; value ${rup(s.val)}</div></div>`;}).join('');
  el.innerHTML=head+`<div style="flex:1;overflow-y:auto">${cards}</div>`;
  showPort('list');
}
window.newPort=function(){
  const name=(prompt("Name your strategy / portfolio:","Momentum Top 10")||"").trim();
  if(!name)return;
  const ports=loadP(); ports.push({id:uid(),name:name,holdings:[]}); saveP(ports); openPort(ports[ports.length-1].id);
};
window.openPort=function(id){ renderDetail(id); };

function renderDetail(id){
  const ports=loadP(); const p=ports.find(x=>x.id===id); if(!p){renderPList();return;}
  const s=stats(p); const c=s.ret>0?'up':s.ret<0?'down':'flat';
  const el=document.getElementById('pDetail');
  let holds = p.holdings.length? p.holdings.map((h,i)=>{
    const cur=MAP[h.t]?MAP[h.t].l:h.entry; const ret=(cur/h.entry-1)*100; const cc=ret>0?'up':ret<0?'down':'flat';
    return `<div class="hrow">
      <div><div class="hn">${MAP[h.t]?MAP[h.t].n:h.t}</div>
        <div class="hsub">${h.qty} @ ${rup(h.entry)} &middot; ${daysHeld(h.date)}d &middot; now ${rup(cur)}</div></div>
      <div class="hret ${cc}">${ret>0?'+':''}${ret.toFixed(2)}%</div>
      <button class="hx" onclick="delHolding('${id}',${i})">&times;</button></div>`;
  }).join('') : `<div class="empty">No stocks yet. Tap &ldquo;+ Add stock&rdquo; to start.</div>`;
  el.innerHTML=`
    <div class="pbar"><button class="btn sec sm" onclick="renderPList()">&larr; Back</button>
      <button class="btn sm" onclick="openAdd('${id}')">+ Add stock</button></div>
    <div class="psum"><div style="font-size:12px;color:var(--dim);margin-bottom:2px">${p.name}</div>
      <div class="pbig ${c}">${s.ret>0?'+':''}${s.ret.toFixed(2)}%</div>
      <div class="prow"><span>Invested <b>${rup(s.cost)}</b></span><span>Now <b>${rup(s.val)}</b></span>
      <span>P&amp;L <b>${s.val-s.cost>=0?'+':''}${rup(s.val-s.cost)}</b></span></div>
      ${s.earliest?`<div class="prow"><span>Since ${s.earliest} (${daysHeld(s.earliest)} days)</span></div>`:''}</div>
    <div style="flex:1;overflow-y:auto;padding-bottom:10px">${holds}</div>
    <button class="btn dan sm" style="align-self:flex-start;margin-top:6px" onclick="delPort('${id}')">Delete portfolio</button>`;
  showPort('detail');
}
window.delHolding=function(id,i){const ports=loadP();const p=ports.find(x=>x.id===id);if(!p)return;p.holdings.splice(i,1);saveP(ports);renderDetail(id);};
window.delPort=function(id){if(!confirm("Delete this whole portfolio?"))return;let ports=loadP().filter(x=>x.id!==id);saveP(ports);renderPList();};

/* add-stock screen */
let addState={id:null,sel:null};
window.openAdd=function(id){addState={id:id,sel:null};renderAdd('');showPort('add');setTimeout(()=>{var e=document.getElementById('asearch');if(e)e.focus();},60);};
function renderAdd(q){
  const el=document.getElementById('pAdd');
  const ql=q.toLowerCase();
  const matches=(ql?ALL.filter(x=>x.n.toLowerCase().includes(ql)||x.t.toLowerCase().includes(ql)):ALL).slice(0,40);
  const res=matches.map(x=>`<div class="ares ${addState.sel===x.t?'sel':''}" onclick="pickAdd('${x.t}')">
      <div><div class="hn">${x.n}</div><div class="ap">${x.t}</div></div><div class="ap">${rup(x.l)}</div></div>`).join('')
      || '<div class="empty">No match.</div>';
  const sel=addState.sel?MAP[addState.sel]:null;
  el.innerHTML=`
    <div class="pbar"><button class="btn sec sm" onclick="renderDetail(addState.id)">&larr; Back</button><h2>Add a stock</h2></div>
    <div class="search"><span class="ic">&#128269;</span><input id="asearch" placeholder="Search stock to add…" oninput="renderAdd(this.value)"></div>
    <div class="addres">${res}</div>
    ${sel?`<div style="border-top:1px solid var(--line);padding-top:12px">
      <div class="field"><label>Selected: <b>${sel.n}</b> — buy price ${rup(sel.l)} (today)</label></div>
      <div class="field"><label>How many shares?</label><input class="inp" id="aqty" type="number" min="1" value="10"></div>
      <button class="btn" onclick="confirmAdd()">Add to portfolio</button></div>`:''}`;
  // keep focus/value on the search box across re-renders
  var s=document.getElementById('asearch'); if(s){s.value=q;}
}
window.pickAdd=function(t){addState.sel=t;const q=document.getElementById('asearch').value;renderAdd(q);};
window.confirmAdd=function(){
  const qty=Math.max(1,parseInt(document.getElementById('aqty').value)||1);
  const t=addState.sel; if(!t)return; const m=MAP[t];
  const ports=loadP(); const p=ports.find(x=>x.id===addState.id); if(!p)return;
  p.holdings.push({t:t, qty:qty, entry:m.l, date:TODAY}); saveP(ports); renderDetail(addState.id);
};

/* ================= MODE SWITCH ================= */
document.querySelectorAll('.mode button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.mode button').forEach(x=>x.classList.remove('on')); b.classList.add('on');
  const m=b.dataset.mode;
  document.getElementById('boardView').style.display = m==='board'?'flex':'none';
  document.getElementById('portView').style.display  = m==='port'?'flex':'none';
  if(m==='port') renderPList();
});

renderBoard();
</script>
</body></html>
"""

html = TEMPLATE.replace("__DATA__", json.dumps(DATA)).replace("__UPDATED__", DATA["updated"])
components.html(html, height=920, scrolling=False)
