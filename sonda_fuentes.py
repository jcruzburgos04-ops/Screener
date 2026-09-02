#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONDA TEMPORAL (3) -- la ultima. Se borra cuando conteste.

La sonda 2 encontro las dos mitades del cronograma, en dos fuentes distintas:

  CUPONES -> bonistas.com/api/bonds, campo `description`, que enumera el
  step-up entero ("Cupon 1: 0.12% TNA / Cupones 2-3: 1.12% / ..."). Se verifico
  contra los dos bonos que ya estaban cargados a mano: para el AL30 dice
  0,50% -> 0,75% -> 1,75% en los mismos tramos que el CSV, y para el AL29 dice
  1,00% plano. Coincide.

  AMORTIZACION -> bonistas NO sirve: dice "bullet (100% al vencimiento)" para
  TODOS, y eso es falso en los bonos del canje (el AL30 viene amortizando desde
  2024). Rava, en cambio, publica el texto del prospecto: "La amortizacion se
  efectuara en TRECE (13) cuotas semestrales, siendo la primera representativa
  del 4% del capital, y las restantes doce equivalentes al 8% cada una".

Esta sonda saca los dos textos para los once soberanos, para poder cargar los
siete que faltan con la fuente anotada en vez de de memoria.
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

BONOS = ["AL29", "AL30", "AL35", "AE38", "AL41",
         "GD29", "GD30", "GD35", "GD38", "GD41", "GD46"]


def pedir(u, reintentos=3):
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
titulo("1. CUPONES: el campo `description` de bonistas, uno por bono")
e, b = pedir("https://bonistas.com/api/bonds")
if e == 200:
    todos = json.loads(b)
    vistos = {}
    for f in todos:
        n = f.get("bond_name")
        if n in BONOS and n not in vistos:
            vistos[n] = f
    for n in BONOS:
        f = vistos.get(n)
        print(f"\n--- {n} ---")
        if not f:
            print("   no esta en el panel")
            continue
        print(f"   vence {f.get('end_date')} · emitido {f.get('start_date')}")
        print(f"   TIR bonistas {f.get('tir')} · duration {f.get('modified_duration')} "
              f"· paridad {f.get('parity')} · precio {f.get('last_price')}")
        print("   " + str(f.get("description", "")).replace("\\n", "\n   "))
else:
    print(f"[{e}] no contesto")

# ---------------------------------------------------------------------------
titulo("2. ¿api/bond/<X> trae el flujo de fondos? (55 KB para el AL30)")
e, b = pedir("https://bonistas.com/api/bond/AL30")
print(f"[{e}] {len(b)} bytes")
if e == 200:
    d = json.loads(b)
    print(f"claves de primer nivel: {sorted(d)}")
    for k, v in d.items():
        if isinstance(v, list):
            print(f"\n  '{k}' es una lista de {len(v)}")
            if v and isinstance(v[0], dict):
                print(f"    campos: {sorted(v[0])}")
                for x in v[:4]:
                    print(f"    {json.dumps(x, ensure_ascii=False)[:300]}")
        elif isinstance(v, dict):
            print(f"\n  '{k}' es un dict con {sorted(v)[:30]}")

# ---------------------------------------------------------------------------
titulo("3. AMORTIZACION: el texto del prospecto en Rava")
for n in BONOS:
    e, b = pedir(f"https://www.rava.com/perfil/{n}")
    print(f"\n--- {n} --- [{e}] {len(b)} bytes")
    if e != 200:
        continue
    txt = b.decode("utf-8", "replace")
    # el bloque del prospecto: arranca en "Forma de amortizacion" o en la
    # enumeracion romana de los cupones
    i = txt.lower().find("amortiz")
    if i < 0:
        print("   no aparece 'amortiz'")
        continue
    bloque = txt[max(0, i - 1400):i + 700]
    bloque = re.sub(r"<[^>]+>", " ", bloque)
    bloque = re.sub(r"\\r\\n|\\n", "\n", bloque)
    bloque = re.sub(r"[ \t]+", " ", bloque)
    print("   " + bloque.strip().replace("\n", "\n   "))

print("\n[fin]")
