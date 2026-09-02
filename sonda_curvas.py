#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONDA TEMPORAL -- curvas en pesos y futuros de dolar.

Dos preguntas, y la segunda es la que puede bloquear todo:

  1. QUE FAMILIAS DE INSTRUMENTOS publica bonistas. Si trae LECAP, BONCER,
     TAMAR, dolar linked y duales etiquetados por el, las curvas se arman solas
     y se mantienen solas: cuando vence una letra desaparece del panel y cuando
     se emite otra aparece, sin tocar codigo. Si hubiera que clasificar por
     patron de ticker, cada emision nueva seria una edicion a mano -- que es
     justo lo que el usuario NO quiere.

  2. DE DONDE SALEN LOS FUTUROS DE DOLAR. data912 no los tiene: su openapi.json
     lista 16 endpoints y ninguno es de futuros. Se prueban A3/Matba Rofex,
     BYMA y las paginas de bonistas que hablan de tasas forward.
"""
import json
import re
import ssl
import urllib.request
import urllib.error
from datetime import date

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126 Safari/537.36",
     "Accept": "application/json, text/plain, */*"}


def pedir(u, reintentos=3, cuerpo=None):
    ultimo = ""
    for _ in range(reintentos):
        try:
            h = dict(H); datos = None
            if cuerpo is not None:
                datos = json.dumps(cuerpo).encode(); h["Content-Type"] = "application/json"
            with urllib.request.urlopen(urllib.request.Request(u, headers=h, data=datos),
                                        timeout=30, context=CTX) as r:
                return 200, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
    return 0, ultimo.encode()[:120]


def titulo(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ---------------------------------------------------------------------------
titulo("1. FAMILIAS DE INSTRUMENTOS EN bonistas -- ¿alcanzan para las curvas?")
est, b = pedir("https://bonistas.com/api/bonds")
familias = {}
if est == 200:
    todos = json.loads(b)
    print(f"{len(todos)} filas")
    for f in todos:
        familias.setdefault(f.get("bond_family_label") or f.get("bond_family"), []).append(f)
    print("\nTODAS LAS FAMILIAS:")
    for fam, fs in sorted(familias.items(), key=lambda x: -len(x[1])):
        tickers = sorted({str(x.get("bond_name") or "") for x in fs})
        print(f"  {len(fs):>4}  {str(fam):<42} {' '.join(tickers[:14])}")
    print("\nUNA FILA COMPLETA DE CADA FAMILIA (para saber que campos hay):")
    for fam, fs in sorted(familias.items()):
        print(f"\n--- {fam} ---")
        print(json.dumps(fs[0], ensure_ascii=False, indent=1)[:1500])
else:
    print(f"[{est}] no contesta")

titulo("2. ¿HAY CAMPO DE TEM / TASA EFECTIVA MENSUAL, O HAY QUE CALCULARLA?")
if familias:
    campos = set()
    for fs in familias.values():
        campos |= set(fs[0])
    print("union de campos de todas las familias:")
    print("  " + "  ".join(sorted(campos)))

titulo("3. FUTUROS DE DOLAR: quien los sirve")
FUT = [
    ("A3 closing-prices DLR",
     "https://apicem.matbarofex.com.ar/api/v2/closing-prices?product=DLR&market=ROFX"
     f"&from={date.today().isoformat()}&to={date.today().isoformat()}"),
    ("A3 closing-prices sin fecha",
     "https://apicem.matbarofex.com.ar/api/v2/closing-prices?product=DLR&market=ROFX"),
    ("A3 products", "https://apicem.matbarofex.com.ar/api/v2/products"),
    ("A3 derivatives", "https://apicem.matbarofex.com.ar/api/v2/derivatives"),
    ("matba home", "https://www.matbarofex.com.ar/"),
    ("data912 arg_futures", "https://data912.com/live/arg_futures"),
    ("data912 futures", "https://data912.com/live/futures"),
    ("data912 arg_options", "https://data912.com/live/arg_options"),
]
for nombre, u in FUT:
    est, b = pedir(u, reintentos=2)
    marca = "OK " if est == 200 else "   "
    print(f"  {marca}{est:<4} {len(b):>9}  {nombre}")
    if est == 200 and b:
        try:
            d = json.loads(b)
            filas = d if isinstance(d, list) else (d.get("data") or d.get("results") or [])
            print(f"        {len(filas)} filas" if isinstance(filas, list) else f"        dict {sorted(d)[:20]}")
            if isinstance(filas, list) and filas:
                print(f"        campos: {sorted(filas[0])}")
                for x in filas[:3]:
                    print(f"        {json.dumps(x, ensure_ascii=False)[:300]}")
        except Exception:
            print(f"        no es JSON: {b[:200].decode('utf-8','replace')}")

titulo("4. BYMA: ¿tiene futuros?")
base = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/"
for ep in ("futures", "derivatives", "index-futures", "dollar-futures", "rofex"):
    est, b = pedir(base + ep, reintentos=1, cuerpo={"excludeZeroPxAndQty": True, "T1": True})
    print(f"  {est:<4} {len(b):>8}  {ep}  {b[:160].decode('utf-8','replace') if est==200 else ''}")

titulo("5. bonistas: las paginas de carry trade y forward rates")
# Next.js incrusta los datos del servidor en __NEXT_DATA__: si la pagina de
# carry trade muestra futuros, los datos estan ahi.
for ruta in ("/carry-trade", "/forward-rates", "/dolar-mayorista"):
    est, b = pedir("https://bonistas.com" + ruta, reintentos=2)
    print(f"\n  [{est}] {ruta}  {len(b)} bytes")
    if est != 200:
        continue
    txt = b.decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', txt, re.S)
    if m:
        try:
            d = json.loads(m.group(1))
            props = d.get("props", {}).get("pageProps", {})
            print(f"        pageProps: {sorted(props)[:20]}")
            for k, v in props.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    print(f"        '{k}': {len(v)} filas · campos {sorted(v[0])[:18]}")
                    print(f"          {json.dumps(v[0], ensure_ascii=False)[:300]}")
        except Exception as e:
            print(f"        __NEXT_DATA__ ilegible: {e}")
    rutas = sorted(set(re.findall(r'["\'](/api/[a-zA-Z0-9_\-/]{2,50})["\']', txt)))
    if rutas:
        print(f"        rutas /api/: {rutas}")

print("\n[fin]")
