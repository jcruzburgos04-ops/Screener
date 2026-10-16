# SONDA TEMPORAL (se borra): contesta las preguntas de Estrategia que desde la
# maquina de desarrollo no se pueden contestar, porque ahi Yahoo esta bloqueado.
import json, subprocess, sys, time
from datetime import date
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf
sys.path.insert(0, ".")
import estrategia as E
from screener import bajar_precios, calc_ash

R = 20261002
pub = json.loads(Path("pub/datos.json").read_text())
PS = {s["t"]: s for s in pub["simbolos"]}

def fechas(idx): return [int(x.strftime("%Y%m%d")) for x in idx]
def adict(t, d):
    return {"t": t, "d": fechas(d.index), "o": d["Open"].tolist(), "h": d["High"].tolist(),
            "l": d["Low"].tolist(), "c": d["Close"].tolist()}

print("=" * 70); print("1. ANCLA DE LAS VELAS DE 3 DIAS, CONTANDO DESDE 1997"); print("=" * 70)
spy = yf.download("SPY", period="max", auto_adjust=True, progress=False)
if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
fs = fechas(spy.index)
cal = [f for f in fs if f >= 19970102]
print(f"SPY: {len(fs)} ruedas desde {fs[0]}; desde el 2/1/1997: {len(cal)}; primera {cal[0]}")
i = cal.index(R)
print(f"2/10/2026 es la rueda #{i + 1} contando desde el 2/1/1997 (1 = 2/1/1997)")
print(f"(#{i + 1}) mod 3 = {(i + 1) % 3}  ->  {'CIERRA una vela de 3 dias' if (i + 1) % 3 == 0 else 'NO cierra vela'}")
for g in range(-2, 4):
    a = i + 1 + 3 * g
    print("   vela:", cal[a:a + 3])
# cuantas ruedas hay segun las reglas de feriados (sin cierres extraordinarios)
from datetime import timedelta
d0, cnt, extra = date(1997, 1, 2), 0, []
calset = set(cal); d = d0
while d <= date(2026, 10, 16):
    f = int(d.strftime("%Y%m%d"))
    if d.weekday() < 5 and d not in E.feriados_nyse(d.year):
        cnt += 1
        if f not in calset: extra.append(f)
    d += timedelta(1)
print(f"dias habiles por regla que el SPY NO opero (cierres extraordinarios): {extra}")
falt = [f for f in cal if not (a_ := E.a_date(f)).weekday() < 5 or a_ in E.feriados_nyse(a_.year)]
print(f"ruedas del SPY que la regla de feriados da como cerradas: {falt}")
ultimos = [f for f in cal if f <= 20261016][-6:]
print("ultimas ruedas del SPY:", ultimos)

print(); print("=" * 70); print("2. EL CALENDARIO PUBLICADO (850 barras) CONTRA EL HISTORIAL COMPLETO"); print("=" * 70)
pd_ = PS["SPY"]["d"]
win = [f for f in cal if pd_[0] <= f <= pd_[-1]]
print(f"publicado: {len(pd_)} barras {pd_[0]}..{pd_[-1]} · historial en esa ventana: {len(win)}")
print("faltan en lo publicado:", sorted(set(win) - set(pd_)), "· sobran:", sorted(set(pd_) - set(win)))

print(); print("=" * 70); print("3. LOS ADRs DEL MAPA: MONEDA Y BARRAS"); print("=" * 70)
mapa = E.cargar_adr()
for loc, adr in mapa.items():
    if not adr: continue
    try:
        md = yf.Ticker(adr).get_history_metadata() or {}
        h = yf.Ticker(adr).history(period="max", auto_adjust=True)
        f = fechas(h.index)
        print(f"  {loc:<10}-> {adr:<6} moneda {md.get('currency')!s:<4} bolsa {md.get('exchangeName')!s:<6} "
              f"barras {len(f):>5} desde {f[0] if f else '-'} ultima {f[-1] if f else '-'} "
              f"cierre {h['Close'].iloc[-1] if len(h) else float('nan'):.2f} vol20 {h['Volume'].tail(20).mean() if len(h) else 0:,.0f}")
    except Exception as e:
        print(f"  {loc} -> {adr}: ERROR {e}")
    time.sleep(0.5)

print(); print("=" * 70); print("4. HISTORIAL COMPLETO CONTRA LAS ULTIMAS 850 BARRAS, AL 2/10/2026"); print("=" * 70)
sims = pub["simbolos"] + [{"t": a, "g": "ADR estrategia", "mon": "USD"} for a in mapa.values()
                          if a and a not in PS]
usuario, _, afuera = E.universo_estrategia(sims, mapa)
print(f"universo de la estrategia: {len(usuario)} · afuera: {afuera}")
full = bajar_precios(usuario + ["SPY"], "max", lote=50, minimo=1)
print(f"vinieron {len(full)} de {len(usuario) + 1}")
S_full = {t: adict(t, d) for t, d in full.items()}
spyF = S_full["SPY"]
def cortar(s, n):
    return {k: (v[-n:] if isinstance(v, list) else v) for k, v in s.items()}
spy850 = cortar(spyF, 850)
campos = ["wma21", "wma26", "dias_cruce", "adr", "rs_puntaje", "sobre_min", "bajo_max", "sma50",
          "sma200", "macd3", "macd3_senal", "hist3", "hist3_ant", "ewo1", "ewo2", "ewo_senal",
          "atr_pct", "sma40", "ema34"]
peor = {c: (0.0, None) for c in campos}; dif_f = {k: [] for k in range(1, 9)}; n_ok = 0
filas_full = []
for t in usuario:
    if t not in S_full: continue
    a = E.evaluar(S_full[t], spyF, R, calendario=cal)
    b = E.evaluar(cortar(S_full[t], 850), spy850, R, calendario=spy850["d"])
    if a is None or b is None: continue
    filas_full.append(a); n_ok += 1
    for c in campos:
        x, y = a[c], b[c]
        if x is None and y is None: continue
        x = np.nan if x is None else x; y = np.nan if y is None else y
        if np.isnan(x) and np.isnan(y): continue
        e = abs(x - y) / max(1e-12, abs(x)) if np.isfinite(x) and np.isfinite(y) else np.inf
        if e > peor[c][0]: peor[c] = (e, t)
    for k in range(1, 9):
        if a[f"f{k}"] != b[f"f{k}"]: dif_f[k].append(t)
print(f"comparados: {n_ok}")
for c in campos: print(f"  {c:<12} desvio relativo maximo {peor[c][0]:.2e}  ({peor[c][1]})")
print("  filtros que cambian de decision:", {k: v for k, v in dif_f.items() if v} or "ninguno")
pub_dif = {k: [] for k in range(1, 9)}
for t in usuario:
    if t not in S_full or t not in PS: continue
    a = E.evaluar(S_full[t], spyF, R, calendario=cal); b = E.evaluar(PS[t], PS["SPY"], R)
    if a is None or b is None: continue
    for k in range(1, 9):
        if a[f"f{k}"] != b[f"f{k}"]: pub_dif[k].append(t)
print("  contra lo PUBLICADO (datos.json de hoy), decisiones distintas:", {k: v for k, v in pub_dif.items() if v} or "ninguna")

print(); print("=" * 70); print("5. UNIVERSO AMPLIO DEL RS, AL 2/10/2026"); print("=" * 70)
r = subprocess.run([sys.executable, "rs_amplio.py", "--datos", "pub/datos.json", "--salida", "/tmp/rs",
                    "--fecha", str(R)], capture_output=True, text=True)
print(r.stdout[-6000:]); print(r.stderr[-3000:])
U = np.array(json.loads(Path("/tmp/rs/rs_universo.json").read_text())["p"]) if r.returncode == 0 else np.array([])
for f in filas_full:
    f["rs"] = E.rs_de_puntaje(f["rs_puntaje"], U) if len(U) else np.nan
    f["f3"] = bool(np.isfinite(f["rs"]) and f["rs"] > 70)
    f["pasa"] = all(f[f"f{k}"] for k in range(1, 9))
E.prioridad(filas_full)
filas_full.sort(key=lambda f: -(f["prio"] if np.isfinite(f["prio"]) else -1))

print(); print("=" * 70); print("6. ASH DEL SPY AL 2/10/2026 (historial completo)"); print("=" * 70)
print(json.dumps(E.ash_spy(spyF, R)))
# variante con m = floor(offset*(n-1)), que es como lo escribe el manual de Pine v4
import screener
def alma_floor(s, n, offset=0.85, sigma=6.0):
    n = int(n); m = np.floor(offset * (n - 1)); dd = n / float(sigma)
    i_ = np.arange(n, dtype=float); w = np.exp(-((i_ - m) ** 2) / (2 * dd * dd))
    return screener._conv(s, w / w.sum())
orig = screener.alma; screener.alma = alma_floor
try: print("con ALMA m=floor():", json.dumps(E.ash_spy(spyF, R)))
finally: screener.alma = orig

print(); print("=" * 70); print("7. SENALES Y CASI-SENALES DEL 2/10/2026 (historial completo, RS amplio)"); print("=" * 70)
cols = ["t", "cierre", "dias_cruce", "fecha_cruce", "wma21", "wma26", "adr", "rs", "rs_puntaje", "sobre_min",
        "bajo_max", "regimen", "sma50", "sma200", "v3_fin", "v3_ant", "hist3", "hist3_ant", "macd3", "macd3_senal",
        "ewo1", "ewo2", "ewo_senal", "atr_pct", "prio", "sl", "sl_pct", "tp", "activacion", "sma40", "ema34"]
def lim(v):
    if isinstance(v, (bool, np.bool_)): return bool(v)
    if isinstance(v, (float, np.floating)): return None if not np.isfinite(v) else round(float(v), 6)
    return v
for f in filas_full:
    fallan = [k for k in range(1, 9) if not f[f"f{k}"]]
    if len(fallan) <= 1:
        print(("SENAL " if not fallan else f"CASI(f{fallan[0]}) ") + json.dumps({c: lim(f[c]) for c in cols}))
print("pasan cada filtro:", [sum(bool(f[f"f{k}"]) for f in filas_full) for k in range(1, 9)], "de", len(filas_full))
