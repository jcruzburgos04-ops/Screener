#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONDA TEMPORAL -- ¿de donde salen los precios mas rapido?

La pregunta del usuario: si data912 o BYMA sirven los datos mas rapido y con
mas informacion que Yahoo. Se mide en vez de opinar, y se mide lo que importa:

  1. COBERTURA. De los 465 simbolos del universo, ¿cuantos trae cada fuente?
     Una fuente el doble de rapida que cubre la mitad no sirve.
  2. TIEMPO Y PEDIDOS. Yahoo se pide en lotes; data912 sirve paneles enteros de
     una. La diferencia esta en la CANTIDAD DE PEDIDOS, no en la velocidad de
     cada uno, y eso es lo que hay que medir.
  3. HISTORIAL. El screener necesita 400 barras diarias por simbolo. Es lo
     pesado de la corrida nocturna. Si ninguna fuente alternativa lo sirve en
     bloque, la nocturna se queda en Yahoo aunque la intradia cambie.
  4. QUE MONEDA. Un precio de CEDEAR esta en pesos y mezcla el movimiento del
     papel con el tipo de cambio: eso NO se puede usar (invariante 2).
"""
import json
import ssl
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126 Safari/537.36",
     "Accept": "application/json, text/plain, */*"}


def pedir(u, cuerpo=None, reintentos=3):
    ultimo = ""
    for _ in range(reintentos):
        try:
            datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
            h = dict(H)
            if datos: h["Content-Type"] = "application/json"
            t0 = time.time()
            with urllib.request.urlopen(urllib.request.Request(u, headers=h, data=datos),
                                        timeout=40, context=CTX) as r:
                b = r.read()
            return r.status if False else 200, b, time.time() - t0
        except urllib.error.HTTPError as e:
            return e.code, b"", 0.0
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
    return 0, ultimo.encode()[:120], 0.0


def titulo(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# --- el universo REAL, resuelto igual que lo hace screener.py ---
# 401 de las 471 lineas son .BA y hay que pasarlas por cedears.csv: sin eso la
# sonda medía 65 simbolos en vez de 465 y la cobertura salia absurda.
mapa = {}
for linea in Path("cedears.csv").read_text(encoding="utf-8").splitlines():
    linea = linea.strip()
    if not linea or linea.startswith("#"): continue
    q = [x.strip() for x in linea.split(",")]
    if len(q) < 2 or not q[1] or q[0].lower() == "local": continue
    mapa[q[0].upper()] = q[1].upper()

uni, sin_mapear = [], []
for linea in Path("universo.csv").read_text(encoding="utf-8").splitlines():
    linea = linea.strip()
    if not linea or linea.startswith("#"): continue
    q = [x.strip() for x in linea.split(",")]
    if q[0].lower() == "ticker": continue
    tk = q[0].upper()
    if len(q) > 2 and q[2]:
        uni.append(q[2].upper())
    elif tk.endswith(".BA"):
        base = tk[:-3]
        if base in mapa: uni.append(mapa[base])
        else: sin_mapear.append(tk)
    else:
        uni.append(tk)
uni = sorted(set(uni))
print(f"universo: {len(uni)} simbolos a cubrir  ({len(sin_mapear)} .BA sin mapear)")

titulo("1. COBERTURA Y TIEMPO DE CADA FUENTE, EN UN SOLO PEDIDO")
fuentes = [
    ("data912 usa_stocks",  "https://data912.com/live/usa_stocks",  None, "symbol"),
    ("data912 usa_adrs",    "https://data912.com/live/usa_adrs",    None, "symbol"),
    ("data912 mep",         "https://data912.com/live/mep",         None, "ticker"),
    ("data912 arg_cedears", "https://data912.com/live/arg_cedears", None, "symbol"),
]
cobertura = {}
for nombre, url, cuerpo, clave in fuentes:
    est, b, seg = pedir(url, cuerpo)
    if est != 200:
        print(f"  [{est}] {nombre}: no contesta"); continue
    d = json.loads(b)
    filas = d if isinstance(d, list) else d.get("data", [])
    simbolos = {str(f.get(clave) or "").upper() for f in filas}
    cubre = simbolos & set(uni)
    cobertura[nombre] = cubre
    print(f"  [200] {nombre:<22} {seg:5.2f}s  {len(b)/1024:7.0f} KB  "
          f"{len(filas):>5} filas  cubre {len(cubre):>3}/{len(uni)} del universo")
    if filas:
        print(f"        campos: {sorted(filas[0])}")
        print(f"        ejemplo: {json.dumps(filas[0], ensure_ascii=False)[:260]}")

est, b, seg = pedir("https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/cedears",
                    {"excludeZeroPxAndQty": True, "T1": True, "T0": False})
if est == 200:
    d = json.loads(b)
    filas = d if isinstance(d, list) else d.get("data", [])
    print(f"  [200] {'BYMA cedears':<22} {seg:5.2f}s  {len(b)/1024:7.0f} KB  {len(filas):>5} filas")
    if filas:
        print(f"        campos: {sorted(filas[0])[:30]}")
else:
    print(f"  [{est}] BYMA cedears: no contesta")

titulo("2. LO MISMO CONTRA YAHOO: cuantos pedidos y cuanto tarda")
# Asi lo pide hoy actualizar_rapido.py: el endpoint chart, de a un simbolo.
muestra = uni[:12]
t0 = time.time(); okey = 0
for tk in muestra:
    est, b, _ = pedir(f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
                      f"?range=1mo&interval=1d", reintentos=1)
    if est == 200 and len(b) > 500: okey += 1
seg = time.time() - t0
print(f"  {okey}/{len(muestra)} simbolos en {seg:.2f}s  ->  {seg/len(muestra):.3f}s por simbolo")
print(f"  extrapolado a {len(uni)}: {seg/len(muestra)*len(uni):.0f}s y {len(uni)} pedidos")

titulo("3. ¿ALGUNA SIRVE EL HISTORIAL EN BLOQUE?")
# El screener necesita 400 barras diarias por simbolo. Es lo caro de la
# nocturna. data912 tiene historial, pero ¿de a uno o en bloque?
for u in ("https://data912.com/historical/stocks/AAPL",
          "https://data912.com/historical/cedears/AAPL",
          "https://data912.com/historical/stocks",
          "https://data912.com/historical/cedears"):
    est, b, seg = pedir(u, reintentos=1)
    n = ""
    if est == 200:
        try:
            d = json.loads(b); n = f"{len(d)} filas"
            if d and isinstance(d[0], dict): n += f"  campos {sorted(d[0])}"
        except Exception: n = "no es JSON"
    print(f"  [{est}] {seg:5.2f}s {len(b)/1024:7.0f} KB  {u}\n        {n}")

titulo("4. ¿EN QUE MONEDA VIENEN? (invariante 2: nunca el precio del CEDEAR)")
est, b, _ = pedir("https://data912.com/live/arg_cedears")
if est == 200:
    d = json.loads(b)
    for f in d[:3]:
        print(f"  {json.dumps(f, ensure_ascii=False)[:200]}")
    print("  ^ si estos numeros son miles, estan en PESOS y no se pueden usar")
est, b, _ = pedir("https://data912.com/live/usa_stocks")
if est == 200:
    d = json.loads(b)
    for f in d[:3]:
        print(f"  {json.dumps(f, ensure_ascii=False)[:200]}")
    print("  ^ estos deberian estar en dolares")

titulo("5. QUE SIMBOLOS DEL UNIVERSO NO CUBRE data912")
todo = set()
for c in cobertura.values(): todo |= c
faltan = sorted(set(uni) - todo)
print(f"  cubre {len(todo)}/{len(uni)}  ·  faltan {len(faltan)}")
print("  " + " ".join(faltan[:120]))

print("\n[fin]")
