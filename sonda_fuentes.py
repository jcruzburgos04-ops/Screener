#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONDA TEMPORAL (2) -- se borra cuando conteste.

La primera sonda encontro la punta: bonistas.com/api/bonds contesta 200 con
1,6 MB y la primera fila ya trae `bond_family: ONS / Obligaciones Negociables`,
`bond_law`, `coupon` y `coupon_yield`. O sea que ahi hay soberanos Y
obligaciones negociables, con cupon.

Falta saber dos cosas:
  1. Si ademas del cupon publica el CRONOGRAMA (fechas y amortizaciones). Es lo
     unico que le falta al screener para tener TIR en los once soberanos.
  2. Que campos trae en total, para saber que se puede mostrar de las ONs
     (calificacion de riesgo, emisor, vencimiento).

Se prueba tambien Rava, que en la pagina de perfil de cada especie muestra el
flujo de fondos: si lo trae incrustado en el HTML se puede leer.
"""
import json
import re
import ssl
import urllib.request
import urllib.error

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
H = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126 Safari/537.36"),
     "Accept": "application/json, text/plain, */*"}


def pedir(u, reintentos=2):
    """Reintenta: en la sonda anterior varios ERR fueron el DNS del runner
    fallando un momento, no el servidor."""
    ultimo = ""
    for _ in range(reintentos):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers=H), timeout=30, context=CTX) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
    return 0, ultimo.encode()[:120]


def titulo(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ---------------------------------------------------------------------------
titulo("1. bonistas.com/api/bonds -- QUE TRAE EXACTAMENTE")
e, b = pedir("https://bonistas.com/api/bonds")
print(f"[{e}] {len(b)} bytes")
datos = None
if e == 200:
    datos = json.loads(b)
    print(f"{len(datos)} filas")
    print("\nCAMPOS:")
    for k in sorted(datos[0]):
        print(f"   {k}")
    familias = {}
    for f in datos:
        familias.setdefault(f.get("bond_family_label") or f.get("bond_family"), []).append(f)
    print("\nFAMILIAS:")
    for fam, fs in sorted(familias.items(), key=lambda x: -len(x[1])):
        print(f"   {len(fs):>4}  {fam}")
    print("\nUNA FILA COMPLETA DE CADA FAMILIA:")
    for fam, fs in sorted(familias.items()):
        print(f"\n--- {fam} ---")
        print(json.dumps(fs[0], ensure_ascii=False, indent=1)[:1800])
    print("\nLOS SOBERANOS DEL CANJE:")
    for f in datos:
        n = str(f.get("bond_name") or "")
        if n in ("AL29", "AL30", "AL35", "AE38", "AL41",
                 "GD29", "GD30", "GD35", "GD38", "GD41", "GD46"):
            print("  " + json.dumps(f, ensure_ascii=False)[:900])

# ---------------------------------------------------------------------------
titulo("2. bonistas: ¿hay endpoint de flujo de fondos?")
e, b = pedir("https://bonistas.com/")
print(f"[{e}] home {len(b)} bytes")
if e == 200:
    txt = b.decode("utf-8", "replace")
    rutas = sorted(set(re.findall(r'["\'](/api/[a-zA-Z0-9_\-/\[\]{}.]{2,60})["\']', txt)))
    print(f"rutas /api/ en el HTML: {rutas}")
    # Next.js publica sus rutas en el build manifest
    for m in sorted(set(re.findall(r'/_next/static/[^"\']+_buildManifest\.js', txt)))[:2]:
        e2, b2 = pedir("https://bonistas.com" + m)
        print(f"\n[{e2}] {m}")
        if e2 == 200:
            paginas = sorted(set(re.findall(r'"(/[a-zA-Z0-9_\-/\[\]]{1,50})"',
                                            b2.decode("utf-8", "replace"))))
            print(f"  paginas: {paginas[:60]}")

for u in ("https://bonistas.com/api/bonds/AL30",
          "https://bonistas.com/api/bond/AL30",
          "https://bonistas.com/api/cashflow/AL30",
          "https://bonistas.com/api/cashflows",
          "https://bonistas.com/api/flows/AL30",
          "https://bonistas.com/api/payments/AL30",
          "https://bonistas.com/api/curve",
          "https://bonistas.com/api/soberanos",
          "https://bonistas.com/api/ons"):
    e, b = pedir(u)
    marca = "OK " if e == 200 else "   "
    print(f"  {marca}{e:<4} {len(b):>8}  {u}")
    if e == 200 and len(b) < 400000:
        print(f"        {b[:300].decode('utf-8','replace')}")

# ---------------------------------------------------------------------------
titulo("3. Rava: el flujo de fondos, ¿viene incrustado en el HTML?")
e, b = pedir("https://www.rava.com/perfil/AL30")
print(f"[{e}] {len(b)} bytes")
if e == 200:
    txt = b.decode("utf-8", "replace")
    for palabra in ("flujo", "amortiz", "cupon", "cronograma", "renta"):
        i = txt.lower().find(palabra)
        print(f"  '{palabra}': {'no aparece' if i < 0 else f'pos {i} -> ' + txt[max(0,i-120):i+260]!r}"[:460])
    rutas = sorted(set(re.findall(r'["\'](/[a-zA-Z0-9_\-/]*(?:flujo|api|perfil)[a-zA-Z0-9_\-/]{0,40})["\']', txt)))
    print(f"  rutas candidatas: {rutas[:40]}")

print("\n[fin]")
