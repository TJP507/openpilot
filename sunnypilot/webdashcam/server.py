#!/usr/bin/env python3
"""
Web dash cam server.

A small, password protected web UI for browsing and downloading dash cam
recordings from a phone or laptop on the same network. It mirrors the on-device
Dash Cam panel: dates -> clips -> cameras, with per-clip download (remuxed to a
browser friendly MP4) and bulk download of a selection or a whole day.

Authentication is a session cookie set by a login page (rather than HTTP basic
auth, which browsers cache and cannot be logged out of). It is served over
HTTPS with a self-signed certificate, regenerated whenever the device IP
changes so the certificate always matches the address in use.

Started and stopped by the process manager based on the enable flag stored by
sunnypilot/webdashcam/config.py, and only ever runs while parked.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
import socket
import ssl
import struct
import subprocess
import threading
import time
import zlib

import psutil
from aiohttp import web

from cereal import car
import cereal.messaging as messaging

from openpilot.sunnypilot.cangauges import config as gauge_config
from openpilot.sunnypilot.faultcodes import config as faultcode_config
from openpilot.sunnypilot.webdashcam import config, library

HOST = "0.0.0.0"
CHUNK = 1 << 20  # 1 MiB
COOKIE = "wd_session"
SESSION_TTL = 60 * 60 * 24 * 30
_SESSION_MESSAGE = b"webdashcam-session-v1"

# The server binds every interface, but a request is only served when it arrives
# on one of these. Cellular data interfaces (rmnet*, wwan*, ppp*) are deliberately
# absent, so the dash cam UI can never be reached directly over 4G/LTE: such
# connections are refused before authentication, and no page or clip is ever sent.
# The Tailscale interface is allowed, but a download over it is confirmed in the
# browser first, since the device may be using metered LTE as its uplink.
ALLOWED_INTERFACE_PREFIXES = ("lo", "wlan", "p2p", "ap", "usb", "rndis", "eth", "tailscale")
CELLULAR_INTERFACE_PREFIXES = ("ppp", "rmnet", "wwan")

_IFACE_CACHE = {"at": -1.0, "by_ip": {}}
_DENIED_SEEN: set = set()


def _allowed_interface(name: str) -> bool:
  return name.startswith(ALLOWED_INTERFACE_PREFIXES)


def _interface_for_ip(ip: str) -> str | None:
  """Map a local address to the interface that owns it (cached briefly)."""
  now = time.monotonic()
  if now - _IFACE_CACHE["at"] > 5.0:
    by_ip = {}
    try:
      for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
          if addr.family == socket.AF_INET:
            by_ip[addr.address] = name
    except Exception:
      pass
    _IFACE_CACHE.update(at=now, by_ip=by_ip)
  return _IFACE_CACHE["by_ip"].get(ip)


def _local_interface(request: web.Request) -> str | None:
  """Interface the accepted connection arrived on, or None if unknown."""
  transport = request.transport
  sockname = transport.get_extra_info("sockname") if transport is not None else None
  if not sockname:
    return None
  return _interface_for_ip(sockname[0])


def _over_tailscale(request: web.Request) -> bool:
  name = _local_interface(request)
  return name is not None and name.startswith("tailscale")


def _primary_interface() -> str | None:
  """Interface carrying the lowest-metric IPv4 default route, or None."""
  best_iface, best_metric = None, None
  try:
    with open("/proc/net/route") as f:
      next(f, None)
      for line in f:
        fields = line.split()
        if len(fields) < 8 or fields[1] != "00000000":
          continue
        iface, metric = fields[0], int(fields[6])
        if best_metric is None or metric < best_metric:
          best_iface, best_metric = iface, metric
  except (OSError, ValueError):
    return None
  return best_iface


def _on_cellular() -> bool:
  """True while the device's default route is a cellular interface."""
  iface = _primary_interface()
  return iface is not None and iface.startswith(CELLULAR_INTERFACE_PREFIXES)


def _request_allowed(request: web.Request) -> bool:
  """True only when the connection arrived on an allowed interface."""
  name = _local_interface(request)
  if name is not None and _allowed_interface(name):
    return True
  if name is not None and name not in _DENIED_SEEN:
    _DENIED_SEEN.add(name)
    print(f"[webdashcam] refusing connection from interface {name}", flush=True)
  return False


_SM = None


def _is_parked() -> bool:
  """True when the car is offroad, or onroad with the gear selector in Park.

  The server now runs whenever it is enabled rather than only offroad, so it
  must refuse to serve while the car is not parked.
  """
  global _SM
  if _SM is None:
    _SM = messaging.SubMaster(["carState", "deviceState"])
  _SM.update(0)
  if not _SM["deviceState"].started:
    return True
  return bool(_SM["carState"].valid) and _SM["carState"].gearShifter == car.CarState.GearShifter.park

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>Dash Cam</title>
<style>
:root{--bg:#151515;--panel:#232323;--panel2:#2c2c2c;--text:#f2f2f2;--muted:#9aa0a6;--accent:#4a90d9}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text);-webkit-text-size-adjust:100%}
header{position:sticky;top:0;background:rgba(21,21,21,.95);backdrop-filter:blur(8px);padding:14px 16px;border-bottom:1px solid #2c2c2c;z-index:5}
.hdr{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:900px;margin:0 auto}
h1{font-size:20px;margin:0}
#sub{color:var(--muted);font-size:13px;margin-top:2px}
main{padding:12px;max-width:900px;margin:0 auto;padding-bottom:96px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.chip{padding:8px 14px;border-radius:999px;background:var(--panel);border:1px solid #333;color:var(--text);font-size:14px;cursor:pointer}
.chip.on{background:var(--accent);border-color:var(--accent)}
.row{display:flex;align-items:center;gap:12px;background:var(--panel);border-radius:12px;padding:12px 14px;margin-bottom:10px}
.row .grow{flex:1;min-width:0}
.row .title{font-size:16px}
.row .meta{font-size:13px;color:var(--muted);margin-top:3px}
.open{cursor:pointer}
.btn{display:inline-block;padding:7px 12px;border-radius:9px;background:var(--panel2);color:var(--text);text-decoration:none;font-size:13px;border:1px solid #3a3a3a;white-space:nowrap;cursor:pointer}
.btn:active{background:#3a3a3a}
.btn.pri{background:var(--accent);border-color:var(--accent)}
.btn.danger{color:#ff9a8a;border-color:#5a2a2a}
.check{width:22px;height:22px;border-radius:6px;border:2px solid #666;flex:0 0 auto;cursor:pointer;display:flex;align-items:center;justify-content:center}
.check.on{background:var(--accent);border-color:var(--accent)}
.check.on::after{content:"\\2713";font-size:15px;color:#fff}
.crumb{display:inline-block;color:var(--accent);cursor:pointer;margin-bottom:10px;font-size:14px}
.bar{position:fixed;left:0;right:0;bottom:0;background:rgba(21,21,21,.97);border-top:1px solid #2c2c2c;padding:12px 16px;display:flex;gap:10px;align-items:center;justify-content:space-between;max-width:900px;margin:0 auto}
.hidden{display:none!important}
.count{color:var(--muted);font-size:14px}
.empty{color:var(--muted);text-align:center;padding:40px 0}
.acts{white-space:nowrap}
</style>
</head>
<body>
<header>
  <div class="hdr">
    <div>
      <h1>Dash Cam</h1>
      <div id="sub">Loading&hellip;</div>
    </div>
    <span>
      <a class="btn" href="/gauges">Gauges</a>
      <a class="btn" href="/faults">Faults</a>
      <a class="btn danger" href="/logout">Log out</a>
    </span>
  </div>
</header>
<main>
  <div id="cams" class="chips hidden"></div>
  <div id="crumb"></div>
  <div id="list"></div>
</main>
<div id="bar" class="bar hidden">
  <span id="count" class="count"></span>
  <span>
    <button class="btn" id="dlsel" disabled>Download selected</button>
    <button class="btn pri" id="dlall">Download day</button>
  </span>
</div>
<script>
const CAMLABEL={front:"Front",wide:"Wide",driver:"Driver"};
const OVER_TAILSCALE=__OVER_TAILSCALE__;
const ON_CELLULAR=__ON_CELLULAR__;
const DL_WARN=ON_CELLULAR
  ? "This device is on cellular (LTE) right now. Downloading over Tailscale will use a LOT of mobile data. Continue?"
  : "This download goes over Tailscale. If the device is using an LTE connection it will use a LOT of mobile data. Continue?";
const state={dates:[],date:null,clips:[],cam:"all",sel:new Set()};
const $=(s)=>document.querySelector(s);
const fmt=(b)=>b>=1073741824?(b/1073741824).toFixed(2)+" GB":b>=1048576?(b/1048576).toFixed(1)+" MB":Math.round(b/1024)+" KB";
async function api(path){const r=await fetch(path);if(r.status===401){location.href="/login";throw new Error("auth");}if(!r.ok)throw new Error(r.status);return r.json();}
function guardDownload(url){if(OVER_TAILSCALE&&!confirm(DL_WARN))return;location.href=url;}
function wireDownload(el){el.onclick=(e)=>{e.preventDefault();guardDownload(el.getAttribute("href"));};}

async function loadDates(){
  state.date=null;state.clips=[];state.sel.clear();state.cam="all";
  const d=await api("/api/dates");
  state.dates=d.dates;
  $("#sub").textContent=d.dates.length+" day(s) with recordings";
  $("#cams").classList.add("hidden");
  renderDates();
}

function renderDates(){
  const el=$("#list");el.innerHTML="";
  $("#crumb").innerHTML="";
  $("#bar").classList.add("hidden");
  if(!state.dates.length){el.innerHTML='<div class="empty">No recordings found</div>';return;}
  for(const d of state.dates){
    const row=document.createElement("div");row.className="row";
    row.innerHTML=`<div class="grow open"><div class="title">${d.date}</div>
      <div class="meta">${d.count} clip(s)</div></div>
      <a class="btn" href="/zip?date=${d.date}">Download day</a>`;
    row.querySelector(".open").onclick=()=>openDate(d.date);
    wireDownload(row.querySelector("a.btn"));
    el.appendChild(row);
  }
}

async function openDate(date){
  state.date=date;state.sel.clear();
  const d=await api("/api/clips?date="+encodeURIComponent(date));
  state.clips=d.clips;
  $("#sub").textContent=date+" \\u2022 "+d.clips.length+" clip(s)";
  renderCams();
  renderClips();
}

function renderCams(){
  const el=$("#cams");el.classList.remove("hidden");
  el.innerHTML=["all","front","wide","driver"].map(c=>
    `<div class="chip ${state.cam===c?"on":""}" data-c="${c}">${c==="all"?"All cameras":CAMLABEL[c]}</div>`).join("");
  el.querySelectorAll(".chip").forEach(ch=>ch.onclick=()=>{state.cam=ch.dataset.c;renderCams();renderClips();});
}

function camList(){return state.cam==="all"?["front","wide","driver"]:[state.cam];}

function renderClips(){
  $("#crumb").innerHTML='<span class="crumb">\\u2039 All days</span>';
  $("#crumb").firstChild.onclick=loadDates;
  const el=$("#list");el.innerHTML="";
  const cams=camList();
  const clips=state.clips.filter(c=>c.cameras.some(x=>cams.includes(x.slug)));
  if(!clips.length){el.innerHTML='<div class="empty">No clips for this camera</div>';}
  for(const c of clips){
    const row=document.createElement("div");row.className="row";
    const total=c.cameras.filter(x=>cams.includes(x.slug)).reduce((a,x)=>a+x.size,0);
    const on=state.sel.has(c.seg);
    row.innerHTML=`<div class="check ${on?"on":""}"></div>
      <div class="grow"><div class="title">${c.time}</div>
      <div class="meta">segment ${c.seg.split("--").pop()} \\u2022 ${fmt(total)}</div></div>
      <div class="acts"></div>`;
    const acts=row.querySelector(".acts");
    for(const cam of cams){
      if(!c.cameras.some(x=>x.slug===cam))continue;
      const a=document.createElement("a");a.className="btn";
      a.href=`/clip/${encodeURIComponent(c.seg)}/${cam}`;
      a.textContent=(cams.length>1?(CAMLABEL[cam]+" "):"")+"\\u2193";
      a.style.marginLeft="6px";
      wireDownload(a);
      acts.appendChild(a);
    }
    row.querySelector(".check").onclick=()=>{state.sel.has(c.seg)?state.sel.delete(c.seg):state.sel.add(c.seg);renderClips();};
    el.appendChild(row);
  }
  updateBar();
}

function updateBar(){
  const n=state.sel.size;
  $("#bar").classList.remove("hidden");
  $("#count").textContent=n?n+" selected":"";
  $("#dlsel").disabled=!n;
  $("#dlsel").onclick=()=>download(true);
  $("#dlall").onclick=()=>download(false);
}

function download(onlySelected){
  let url=`/zip?date=${encodeURIComponent(state.date)}&cams=${camList().join(",")}`;
  if(onlySelected)url+="&segs="+[...state.sel].map(encodeURIComponent).join(",");
  guardDownload(url);
}

loadDates().catch(e=>{if(e.message!=="auth"){$("#sub").textContent="Error: "+e.message;}});
</script>
</body>
</html>
"""

LOGIN_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>Dash Cam - Sign in</title>
<style>
:root{--bg:#151515;--panel:#232323;--text:#f2f2f2;--muted:#9aa0a6;--accent:#4a90d9}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.card{background:var(--panel);padding:32px;border-radius:16px;width:min(92vw,380px)}
h1{font-size:22px;margin:0 0 6px}
p.sub{color:var(--muted);font-size:14px;margin:0 0 20px}
input{width:100%;padding:14px;border-radius:10px;border:1px solid #3a3a3a;background:#1b1b1b;color:var(--text);font-size:17px}
button{width:100%;margin-top:14px;padding:14px;border-radius:10px;border:0;background:var(--accent);color:#fff;font-size:17px;font-weight:600}
.err{color:#ff9a8a;font-size:14px;margin:0 0 14px}
</style>
</head>
<body>
<form class="card" method="post" action="/login">
  <h1>Dash Cam</h1>
  <p class="sub">Enter the password shown on the device (Settings &rarr; Device).</p>
  <!--ERR-->
  <input type="password" name="password" placeholder="Password" autofocus autocomplete="current-password"/>
  <button type="submit">Sign in</button>
</form>
</body>
</html>
"""


GAUGES_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>Gauges</title>
<style>
:root{--bg:#151515;--panel:#232323;--panel2:#2c2c2c;--text:#f2f2f2;--muted:#9aa0a6;--accent:#4a90d9}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{position:sticky;top:0;background:rgba(21,21,21,.95);padding:14px 16px;border-bottom:1px solid #2c2c2c;z-index:5}
.hdr{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:1100px;margin:0 auto}
h1{font-size:20px;margin:0}h3{margin:0 0 10px}
.btn{display:inline-block;padding:7px 12px;border-radius:9px;background:var(--panel2);
color:var(--text);text-decoration:none;font-size:13px;border:1px solid #3a3a3a;cursor:pointer}
.btn.pri{background:var(--accent);border-color:var(--accent)}
.btn.danger{color:#ff9a8a;border-color:#5a2a2a}
main{padding:14px;max-width:1100px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.tile{background:var(--panel);border-radius:12px;padding:12px 14px;border:1px solid #333}
.tile .lbl{color:var(--muted);font-size:13px}
.tile .val{font-size:34px;font-weight:700;margin-top:4px}
.tile .unit{color:var(--muted);font-size:14px;margin-left:6px;font-weight:400}
.track{height:10px;border-radius:6px;background:#3a3a3a;margin-top:10px;overflow:hidden}
.fill{height:100%;background:var(--accent)}
.off{opacity:.45}
section{margin-top:22px;border-top:1px solid #2c2c2c;padding-top:16px}
.row{display:flex;gap:8px;align-items:center;background:var(--panel);border-radius:10px;padding:8px 10px;margin-bottom:8px;flex-wrap:wrap}
input,select{background:#1b1b1b;border:1px solid #3a3a3a;color:var(--text);border-radius:8px;padding:7px 9px;font-size:14px}
input.sm{width:84px}
#add{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.muted{color:var(--muted)}
</style>
</head>
<body>
<header><div class="hdr"><h1>Live Gauges</h1>
  <span><a class="btn" href="/">Dash Cam</a> <a class="btn" href="/faults">Faults</a> <a class="btn danger" href="/logout">Log out</a></span>
</div></header>
<main>
  <div id="grid" class="grid"></div>
  <section>
    <h3>Configure</h3>
    <div id="list"></div>
    <div id="add">
      <select id="source">
        <option value="carState">carState</option>
        <option value="carControl">carControl</option>
        <option value="panda">panda</option>
        <option value="device">device</option>
        <option value="gps">gps</option>
        <option value="can">can (DBC)</option>
      </select>
      <input id="key" list="catalog" placeholder="vEgo  or  ENGINE_RPM.ENGINE_RPM" style="min-width:300px"/>
      <datalist id="catalog"></datalist>
      <input id="label" placeholder="label"/>
      <input id="unit" placeholder="unit" class="sm"/>
      <input id="scale" placeholder="scale" value="1" class="sm"/>
      <input id="min" placeholder="min" value="0" class="sm"/>
      <input id="max" placeholder="max" value="1" class="sm"/>
      <select id="style"><option>value</option><option>bar</option><option>arc</option></select>
      <button class="btn" id="addbtn">Add</button>
      <button class="btn pri" id="save">Save</button>
    </div>
    <p class="muted" id="msg"></p>
    <p class="muted" id="hint"></p>
  </section>
</main>
<script>
const $=(s)=>document.querySelector(s);
let cfg={gauges:[]};
async function api(p,o){const r=await fetch(p,o);if(r.status===401){location.href="/login";throw new Error("auth");}return r.json();}
function fmt(v){if(v===null||v===undefined)return"--";const a=Math.abs(v);return (a>=1000||a>=100)?v.toFixed(0):v.toFixed(1);}
function renderValues(snap){
  const gs=(snap&&snap.gauges)||[];
  $("#grid").innerHTML=gs.map(g=>{
    const val=(g.text!==null&&g.text!==undefined)?g.text:fmt(g.value);
    const frac=(g.value!==null&&g.value!==undefined&&g.max>g.min)?Math.max(0,Math.min(1,(g.value-g.min)/(g.max-g.min))):0;
    const bar=g.style==="value"?"":`<div class="track"><div class="fill" style="width:${(frac*100).toFixed(1)}%"></div></div>`;
    return `<div class="tile ${g.ok?"":"off"}"><div class="lbl">${g.label}</div>
      <div class="val">${val}<span class="unit">${g.unit||""}</span></div>${bar}</div>`;
  }).join("");
}
function renderList(){
  $("#list").innerHTML=cfg.gauges.map((g,i)=>`<div class="row">
    <b style="min-width:120px">${g.label}</b>
    <span class="muted">${g.source}:${g.key} x${g.scale} [${g.min}..${g.max}] ${g.style}</span>
    <span style="flex:1"></span><button class="btn danger" onclick="del(${i})">Remove</button></div>`).join("");
}
window.del=(i)=>{cfg.gauges.splice(i,1);renderList();};
function addGauge(){
  const key=$("#key").value.trim();
  if(!key){$("#msg").textContent="key required";return;}
  cfg.gauges.push({id:key.replace(/[^A-Za-z0-9_]/g,"_"),label:$("#label").value||key,source:$("#source").value,
    key:key,unit:$("#unit").value,scale:parseFloat($("#scale").value||"1"),
    min:parseFloat($("#min").value||"0"),max:parseFloat($("#max").value||"1"),style:$("#style").value});
  renderList();$("#key").value="";$("#label").value="";$("#msg").textContent="added (press Save)";
}
async function save(){
  const r=await api("/api/gauges/config",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(cfg)});
  if(r.config){cfg=r.config;renderList();}
  $("#msg").textContent=r.ok?"saved":"save failed";
}
async function loop(){
  try{const s=await api("/api/gauges");renderValues(s.values);}catch(e){}
  setTimeout(loop,300);
}
(async()=>{
  try{const c=await api("/api/gauges/catalog");
    $("#catalog").innerHTML=c.map(x=>`<option value="${x.key}">${x.dbc} ${x.addr}</option>`).join("");
    const bySrc={};for(const x of c){bySrc[x.dbc]=(bySrc[x.dbc]||0)+1;}
    $("#hint").textContent="DBC signals available: "+Object.entries(bySrc).map(([k,v])=>k+" ("+v+")").join(", ");
  }catch(e){}
  $("#addbtn").onclick=addGauge;$("#save").onclick=save;
  const s=await api("/api/gauges");cfg=s.config||cfg;renderList();renderValues(s.values);
  loop();
})();
</script>
</body></html>
"""


FAULTS_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>Fault Codes</title>
<style>
:root{--bg:#151515;--panel:#232323;--panel2:#2c2c2c;--text:#f2f2f2;--muted:#9aa0a6;--accent:#4a90d9;--fault:#eb645a;--good:#8cdc8c;--warn:#ffb478}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--text)}
header{position:sticky;top:0;background:rgba(21,21,21,.95);padding:14px 16px;border-bottom:1px solid #2c2c2c;z-index:5}
.hdr{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:900px;margin:0 auto}
h1{font-size:20px;margin:0}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:22px 0 10px}
.btn{display:inline-block;padding:7px 12px;border-radius:9px;background:var(--panel2);
color:var(--text);text-decoration:none;font-size:13px;border:1px solid #3a3a3a;cursor:pointer}
.btn.danger{color:#ff9a8a;border-color:#5a2a2a}
main{padding:14px;max-width:900px;margin:0 auto;padding-bottom:40px}
.banner{border-radius:12px;padding:16px;font-size:18px;font-weight:600}
.banner.ok{background:rgba(140,220,140,.12);color:var(--good);border:1px solid rgba(140,220,140,.35)}
.banner.bad{background:rgba(235,100,90,.12);color:var(--fault);border:1px solid rgba(235,100,90,.35)}
.f{display:flex;align-items:center;gap:12px;background:var(--panel);border-left:6px solid var(--fault);border-radius:10px;padding:12px 14px;margin-bottom:8px}
.f.good{border-left-color:var(--good)}
.f.warn{border-left-color:var(--warn)}
.f .grow{flex:1;min-width:0}
.f .lbl{font-size:16px}
.f .det{font-size:13px;color:var(--muted);margin-top:3px}
.right{color:var(--muted);font-size:13px;white-space:nowrap}
.muted{color:var(--muted);font-size:13px;margin-top:22px;line-height:1.5}
</style>
</head>
<body>
<header><div class="hdr"><h1>Fault Codes</h1>
  <span><a class="btn" href="/">Dash Cam</a> <a class="btn" href="/gauges">Gauges</a> <a class="btn danger" href="/logout">Log out</a></span>
</div></header>
<main>
  <div id="banner" class="banner ok">Loading&hellip;</div>
  <div id="vehicle"></div>
  <h3>System</h3>
  <div id="system"></div>
  <h3>Recent events</h3>
  <div id="events"></div>
  <p class="muted" id="note"></p>
</main>
<script>
const $=(s)=>document.querySelector(s);
async function api(p){const r=await fetch(p);if(r.status===401){location.href="/login";throw new Error("auth");}return r.json();}
function age(s){s=Math.round(s);if(s<90)return s+"s ago";if(s<3600)return Math.floor(s/60)+"m ago";return Math.floor(s/3600)+"h ago";}
function esc(t){const d=document.createElement("div");d.textContent=t;return d.innerHTML;}
function row(cls,lbl,det,right){
  const d=det?`<div class="det">${esc(det)}</div>`:"";
  const r=right?`<span class="right">${esc(right)}</span>`:"";
  return `<div class="f ${cls}"><div class="grow"><div class="lbl">${esc(lbl)}</div>${d}</div>${r}</div>`;
}
async function loop(){
  try{
    const s=await api("/api/faults");
    const active=(s.vehicle||[]).filter(x=>x.active);
    $("#banner").className="banner "+(active.length?"bad":"ok");
    $("#banner").textContent=active.length?active.length+" active fault"+(active.length>1?"s":""):"No active faults";
    $("#vehicle").innerHTML=active.map(x=>row("",x.label,x.detail,"")).join("");
    const panda=(s.panda||[]).filter(x=>x.active);
    let sys=panda.length?panda.map(x=>row("",x.label,"","")).join(""):row("good","No panda faults","","");
    if(s.thermal&&s.thermal!=="ok")sys+=row("warn","Device thermal: "+s.thermal,"","");
    $("#system").innerHTML=sys;
    const ev=s.events||[];
    $("#events").innerHTML=ev.length?ev.map(e=>row("warn",e.name,(e.types||[]).join(", "),age(e.age||0))).join(""):row("good","No fault events","","");
    $("#note").textContent=s.note||"";
  }catch(e){}
  setTimeout(loop,1000);
}
loop();
</script>
</body></html>
"""


async def handle_gauges_page(_request: web.Request) -> web.Response:
  return web.Response(text=GAUGES_HTML, content_type="text/html")


async def handle_api_gauges(_request: web.Request) -> web.Response:
  return web.json_response({"config": gauge_config.load(), "values": gauge_config.read_values()})


async def handle_api_gauges_catalog(_request: web.Request) -> web.Response:
  return web.json_response(gauge_config.read_catalog())


async def handle_api_gauges_config(request: web.Request) -> web.Response:
  try:
    data = await request.json()
  except Exception:
    return web.json_response({"error": "invalid json"}, status=400)
  if not isinstance(data, dict) or not isinstance(data.get("gauges"), list):
    return web.json_response({"error": "invalid config"}, status=400)
  gauge_config.save(data)
  return web.json_response({"ok": True, "config": gauge_config.load()})


async def handle_faults_page(_request: web.Request) -> web.Response:
  return web.Response(text=FAULTS_HTML, content_type="text/html")


async def handle_api_faults(_request: web.Request) -> web.Response:
  return web.json_response(faultcode_config.read_snapshot())


def _session_token() -> str | None:
  password = config.get_password()
  if not password:
    return None
  return hmac.new(password.encode(), _SESSION_MESSAGE, hashlib.sha256).hexdigest()


def _login_html(error: str = "") -> str:
  block = f'<p class="err">{error}</p>' if error else ""
  return LOGIN_TEMPLATE.replace("<!--ERR-->", block)


@web.middleware
async def auth_middleware(request: web.Request, handler):
  if not _request_allowed(request):
    return web.Response(status=403, text="Not available on this network.")
  if request.path == "/favicon.ico":
    return web.Response(status=204)
  if request.path in ("/login", "/logout"):
    return await handler(request)

  token = _session_token()
  if token is None:
    return web.Response(status=503, text="Web dash cam is not enabled.")

  cookie = request.cookies.get(COOKIE, "")
  if cookie and secrets.compare_digest(cookie, token):
    return await handler(request)

  if request.path == "/":
    raise web.HTTPFound("/login")
  return web.Response(status=401, text="Authentication required.")


async def handle_index(request: web.Request) -> web.Response:
  html = (INDEX_HTML
          .replace("__OVER_TAILSCALE__", "true" if _over_tailscale(request) else "false")
          .replace("__ON_CELLULAR__", "true" if _on_cellular() else "false"))
  return web.Response(text=html, content_type="text/html")


async def handle_login_get(_request: web.Request) -> web.Response:
  return web.Response(text=_login_html(), content_type="text/html")


async def handle_login_post(request: web.Request) -> web.Response:
  data = await request.post()
  password = str(data.get("password", ""))
  token = _session_token()
  if token is not None and secrets.compare_digest(password, config.get_password()):
    response = web.HTTPFound("/")
    response.set_cookie(COOKIE, token, max_age=SESSION_TTL, httponly=True, secure=True, samesite="Lax")
    raise response
  return web.Response(text=_login_html("Incorrect password."), content_type="text/html", status=401)


async def handle_logout(_request: web.Request) -> web.Response:
  response = web.HTTPFound("/login")
  response.del_cookie(COOKIE)
  return response


async def handle_dates(_request: web.Request) -> web.Response:
  counts = library.list_date_counts()
  dates = [{"date": d, "count": counts[d]} for d in sorted(counts, reverse=True)]
  return web.json_response({"dates": dates})


async def handle_clips(request: web.Request) -> web.Response:
  date = request.query.get("date", "")
  if not date:
    return web.json_response({"error": "missing date"}, status=400)
  clips = []
  for name, seg_dir, mtime in library.list_segments():
    if library.date_of(mtime) != date:
      continue
    info = library.segment_info(name, seg_dir, mtime)
    if info["cameras"]:
      clips.append(info)
  clips.sort(key=lambda c: c["mtime"], reverse=True)
  return web.json_response({"date": date, "clips": clips})


async def handle_clip(request: web.Request) -> web.StreamResponse:
  if not _is_parked():
    raise web.HTTPForbidden(text="Downloads are only available while parked (gear P).")
  seg = request.match_info["seg"]
  camera = request.match_info["camera"]
  src = library.camera_path(seg, camera)
  if src is None:
    raise web.HTTPNotFound(text="clip not found")

  inline = request.query.get("play") == "1"
  filename = f"{seg}_{camera}.mp4"
  response = web.StreamResponse(headers={
    "Content-Type": "video/mp4",
    "Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{filename}"',
    "Cache-Control": "no-store",
  })
  global _ACTIVE_STREAMS
  await response.prepare(request)
  _ACTIVE_STREAMS += 1
  try:
    async for chunk in _mp4_chunks(src):
      await response.write(chunk)
    await response.write_eof()
  finally:
    _ACTIVE_STREAMS -= 1
  return response


async def handle_zip(request: web.Request) -> web.StreamResponse:
  if not _is_parked():
    raise web.HTTPForbidden(text="Downloads are only available while parked (gear P).")
  date = request.query.get("date", "")
  cams = [c for c in request.query.get("cams", "").split(",") if c in library.FOLDER_CAMERA]
  if not cams:
    cams = list(library.FOLDER_CAMERA)
  wanted = {s for s in request.query.get("segs", "").split(",") if s}

  entries: list = []
  for name, _seg_dir, mtime in library.list_segments():
    if date and library.date_of(mtime) != date:
      continue
    if wanted and name not in wanted:
      continue
    for cam in cams:
      path = library.camera_path(name, cam)
      if path is not None:
        entries.append((f"{name}_{cam}.mp4", mtime, path))

  if not entries:
    raise web.HTTPNotFound(text="nothing to download")

  label = date or time.strftime("%Y-%m-%d")
  response = web.StreamResponse(headers={
    "Content-Type": "application/zip",
    "Content-Disposition": f'attachment; filename="dashcam_{label}.zip"',
    "Cache-Control": "no-store",
  })
  global _ACTIVE_STREAMS
  await response.prepare(request)
  _ACTIVE_STREAMS += 1
  try:
    zipper = _ZipStream(response)
    for name, mtime, path in entries:
      await zipper.add(name, mtime, _mp4_chunks(path))
    await zipper.finish()
    await response.write_eof()
  finally:
    _ACTIVE_STREAMS -= 1
  return response


async def _mp4_chunks(path: str):
  """Yield the remuxed MP4 for one clip. Kills ffmpeg if the client goes away."""
  proc = await asyncio.create_subprocess_exec(
    *library.mp4_stream_command(path),
    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
  try:
    assert proc.stdout is not None
    while True:
      chunk = await proc.stdout.read(CHUNK)
      if not chunk:
        break
      yield chunk
  finally:
    if proc.returncode is None:
      try:
        proc.kill()
      except ProcessLookupError:
        pass
    await proc.wait()


def _dos_datetime(mtime: float) -> tuple[int, int]:
  t = time.localtime(mtime)
  dos_time = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
  dos_date = (max(t.tm_year - 1980, 0) << 9) | (t.tm_mon << 5) | t.tm_mday
  return dos_time, dos_date


class _ZipStream:
  """Minimal streaming ZIP writer (store method, data descriptors).

  The archive is written straight to the client as it is produced, so a large
  selection never has to be buffered in memory or on disk. Sizes and CRCs are
  unknown up front, so each entry uses a data descriptor; a ZIP64 end record is
  emitted when the archive as a whole exceeds the 4 GiB classic limit.
  """

  def __init__(self, response: web.StreamResponse):
    self._response = response
    self._entries: list = []
    self._offset = 0

  async def _write(self, data: bytes) -> None:
    await self._response.write(data)
    self._offset += len(data)

  async def add(self, name: str, mtime: float, chunks) -> None:
    raw_name = name.encode("utf-8")
    dos_time, dos_date = _dos_datetime(mtime)
    offset = self._offset
    header = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0x0008, 0, dos_time, dos_date,
                         0, 0, 0, len(raw_name), 0)
    await self._write(header + raw_name)

    crc = 0
    size = 0
    async for chunk in chunks:
      crc = zlib.crc32(chunk, crc)
      size += len(chunk)
      await self._write(chunk)

    crc &= 0xFFFFFFFF
    await self._write(struct.pack("<IIII", 0x08074B50, crc, size, size))
    self._entries.append((raw_name, crc, size, offset, dos_time, dos_date))

  async def finish(self) -> None:
    central_offset = self._offset
    for raw_name, crc, size, offset, dos_time, dos_date in self._entries:
      record = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0x0008, 0, dos_time, dos_date,
                           crc, size, size, len(raw_name), 0, 0, 0, 0, 0, offset)
      await self._write(record + raw_name)

    central_size = self._offset - central_offset
    count = len(self._entries)
    if central_offset > 0xFFFFFFFF or central_size > 0xFFFFFFFF or count > 0xFFFF:
      zip64_offset = self._offset
      await self._write(struct.pack("<IQHHIIQQQQ", 0x06064B50, 44, 45, 45, 0, 0,
                                    count, count, central_size, central_offset))
      await self._write(struct.pack("<IIQI", 0x07064B50, 0, zip64_offset, 1))
      await self._write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 0xFFFF, 0xFFFF,
                                    0xFFFFFFFF, 0xFFFFFFFF, 0))
    else:
      await self._write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count,
                                    central_size, central_offset, 0))


_CERT_SIGNATURE = ""
_CERT_LAST_SEEN = ""
_ACTIVE_STREAMS = 0


def _cert_sans() -> list[str]:
  """SAN entries so the self-signed cert is valid on the LAN and over Tailscale."""
  sans = ["IP:127.0.0.1", "DNS:localhost"]
  tailscale_ips = config.tailscale_ips()
  for ip in config.lan_ips() + tailscale_ips:
    entry = f"IP:{ip}"
    if entry not in sans:
      sans.append(entry)
  # Only name the tailnet once Tailscale has an address, otherwise a stale
  # status file could contribute a name the device is not reachable at.
  if tailscale_ips:
    for name in config.tailscale_names():
      entry = f"DNS:{name}"
      if entry not in sans:
        sans.append(entry)
  return sans


def _cert_signature() -> str:
  return "|".join(_cert_sans())


def _wait_for_address(timeout: float = 90.0) -> None:
  """Wait until at least one LAN or Tailscale address exists before building the cert."""
  deadline = time.monotonic() + timeout
  while not (config.lan_ips() or config.tailscale_ips()) and time.monotonic() < deadline:
    time.sleep(1)


def _ensure_cert() -> tuple[str, str]:
  """Return (cert, key), generating a self-signed pair for the current addresses if needed.

  SANs cover the LAN address(es) and the Tailscale IP / MagicDNS name so HTTPS
  works no matter which one is used. The cellular address is deliberately
  excluded: it changes constantly and is not reachable from the LAN or tailnet.
  """
  global _CERT_SIGNATURE, _CERT_LAST_SEEN
  cert, key = config.CERT_PATH, config.KEY_PATH
  _wait_for_address()
  sans = _cert_sans()
  _CERT_SIGNATURE = _CERT_LAST_SEEN = "|".join(sans)
  marker = cert + ".ip"
  try:
    with open(marker) as f:
      previous = f.read().strip()
  except OSError:
    previous = ""

  if os.path.exists(cert) and os.path.exists(key) and previous == _CERT_SIGNATURE:
    return cert, key

  subprocess.run(
    ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
     "-keyout", key, "-out", cert, "-days", "3650",
     "-subj", "/CN=webdashcam", "-addext", f"subjectAltName={','.join(sans)}"],
    check=True, capture_output=True)
  os.chmod(key, 0o600)
  with open(marker, "w") as f:
    f.write(_CERT_SIGNATURE)
  return cert, key


def _cert_watchdog() -> None:
  """Restart the server when the address set changes so the TLS cert is rebuilt.

  Interfaces come up and go away (Wi-Fi, Tailscale), and the cert is only built
  at start, so without this a new address would be rejected as a hostname
  mismatch until the next reboot. The restart is deferred while a download runs.
  """
  global _CERT_LAST_SEEN
  while True:
    time.sleep(5)
    current = _cert_signature()
    if _ACTIVE_STREAMS == 0 and current == _CERT_LAST_SEEN and current != _CERT_SIGNATURE:
      print("[webdashcam] address set changed; restarting to rebuild TLS certificate", flush=True)
      os._exit(0)
    _CERT_LAST_SEEN = current


def main() -> None:
  app = web.Application(middlewares=[auth_middleware], client_max_size=CHUNK)
  app.add_routes([
    web.get("/", handle_index),
    web.get("/login", handle_login_get),
    web.post("/login", handle_login_post),
    web.get("/logout", handle_logout),
    web.get("/api/dates", handle_dates),
    web.get("/api/clips", handle_clips),
    web.get("/clip/{seg}/{camera}", handle_clip),
    web.get("/zip", handle_zip),
    web.get("/gauges", handle_gauges_page),
    web.get("/api/gauges", handle_api_gauges),
    web.get("/api/gauges/catalog", handle_api_gauges_catalog),
    web.post("/api/gauges/config", handle_api_gauges_config),
    web.get("/faults", handle_faults_page),
    web.get("/api/faults", handle_api_faults),
  ])

  cert, key = _ensure_cert()
  threading.Thread(target=_cert_watchdog, daemon=True, name="webdashcam-cert").start()
  ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
  ssl_context.load_cert_chain(cert, key)
  web.run_app(app, host=HOST, port=config.PORT, ssl_context=ssl_context, access_log=None, print=None)


if __name__ == "__main__":
  main()
