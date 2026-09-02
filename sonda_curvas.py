#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONDA TEMPORAL (2). Lo compacto primero: la sonda anterior imprimio tanto que
la lista de familias -- que era el dato -- se fue por arriba del tail del log.
"""
import json, ssl, urllib.request, urllib.error
from datetime import date, timedelta

CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
H = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126 Safari/537.36",
     "Accept":"application/json, text/plain, */*"}

def pedir(u, reintentos=3):
    ultimo=""
    for _ in range(reintentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=H),
                                        timeout=30,context=CTX) as r:
                return 200, r.read()
        except urllib.error.HTTPError as e: return e.code, b""
        except Exception as e: ultimo=f"{type(e).__name__}: {e}"
    return 0, ultimo.encode()[:120]

print("="*78); print("FUTUROS A3 -- ultimo dato disponible por contrato"); print("="*78)
# Pedir un RANGO y quedarse con la rueda mas nueva de cada simbolo. Asi no
# importa si hoy es feriado, fin de semana o si todavia no abrio: siempre sale
# el ultimo cierre que haya.
desde = (date.today()-timedelta(days=12)).isoformat()
url = ("https://apicem.matbarofex.com.ar/api/v2/closing-prices"
       f"?product=DLR&market=ROFX&from={desde}&to={date.today().isoformat()}")
est,b = pedir(url)
print(f"[{est}] {len(b)} bytes  {url}")
if est==200:
    d=json.loads(b); filas=d if isinstance(d,list) else d.get("data",[])
    print(f"{len(filas)} filas")
    if filas:
        print(f"campos: {sorted(filas[0])}")
        ult={}
        for f in filas:
            s=f.get("symbol")
            if not s: continue
            if s not in ult or f.get("dateTime","")>ult[s].get("dateTime",""):
                ult[s]=f
        print(f"\n{len(ult)} contratos distintos · rueda mas nueva: "
              f"{max(f.get('dateTime','') for f in ult.values())}")
        print(f"\n{'symbol':<12}{'fecha':<12}{'settle':>10}{'close':>10}{'var%':>8}"
              f"{'implied':>9}{'volumen':>10}{'openInt':>12}")
        for s,f in sorted(ult.items()):
            print(f"{s:<12}{str(f.get('dateTime'))[:10]:<12}{f.get('settlement') or 0:>10.2f}"
                  f"{f.get('close') or 0:>10.2f}{f.get('changePercent') or 0:>8.2f}"
                  f"{f.get('impliedRate') or 0:>9.2f}{f.get('volume') or 0:>10}"
                  f"{f.get('openInterest') or 0:>12,.0f}")
        print("\nfila cruda completa:")
        print(json.dumps(list(ult.values())[-1], ensure_ascii=False, indent=1))

print()
print("="*78); print("FAMILIAS DE bonistas -- compacto"); print("="*78)
est,b = pedir("https://bonistas.com/api/bonds")
if est==200:
    todos=json.loads(b)
    fam={}
    for f in todos:
        fam.setdefault((f.get("bond_family"), f.get("bond_family_label")), []).append(f)
    print(f"{len(todos)} filas · {len(fam)} familias\n")
    print(f"{'clave':<22}{'etiqueta':<40}{'n':>5}  ejemplos")
    for (k,lab),fs in sorted(fam.items(), key=lambda x:-len(x[1])):
        tk=sorted({str(x.get('bond_name') or '') for x in fs})
        print(f"{str(k):<22}{str(lab):<40}{len(fs):>5}  {' '.join(tk[:10])}")
    # una fila de cada familia, SOLO los campos que importan para una curva
    CLAVE=("bond_name","ticker","end_date","days_to_finish","last_price","tir","tna",
           "mtir","modified_duration","parity","coupon","index","settlement","volume",
           "emisor","bond_law","short_description")
    print("\nlos campos que importan, una fila por familia:")
    for (k,lab),fs in sorted(fam.items()):
        f=fs[0]
        print(f"\n  [{k}] {lab}")
        print("   "+json.dumps({c:f.get(c) for c in CLAVE if f.get(c) is not None},
                               ensure_ascii=False)[:520])
print("\n[fin]")
