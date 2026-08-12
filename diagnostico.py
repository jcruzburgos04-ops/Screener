#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
DIAGNOSTICO DE PRECIOS  ·  quien viene atrasado y quien no vino
================================================================================

Lee un datos.json (o el cache de precios) y contesta la pregunta que importa:
"¿este precio es de hoy o me esta mostrando el de hace tres dias?".

    python diagnostico.py                      # sitio/datos.json
    python diagnostico.py otro/datos.json
    python diagnostico.py --cache              # cache_precios.pkl
    python diagnostico.py --todos              # lista tambien los que estan al dia
    python diagnostico.py --ticker NVDA        # el detalle de uno solo

COMO SE DECIDE QUE ALGO ESTA ATRASADO
-------------------------------------
Cada simbolo se compara contra la ultima rueda de SU MERCADO, no contra la
fecha maxima de todo el universo. Un dia de atraso en Brasil, Europa o Asia
suele ser un feriado local y no un error: comparar contra Nueva York marcaria
como rotos a 20 papeles sanos.
================================================================================
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from screener import atrasos, cargar_precios, sufijo_mercado


def a_fecha(aaaammdd):
    s = str(aaaammdd)
    return pd.Timestamp(f"{s[:4]}-{s[4:6]}-{s[6:8]}")


def desde_json(path):
    """{ticker: (fecha_ultima, cierre, variacion)} leido del payload de la web."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for s in d["simbolos"]:
        c = s["c"]
        var = (c[-1] / c[-2] - 1) if len(c) > 1 and c[-2] else float("nan")
        out[s["t"]] = (a_fecha(s["d"][-1]), c[-1], var, len(c))
    return out, d


def desde_cache():
    precios, _, fecha = cargar_precios()
    if not precios:
        sys.exit("[X] No hay cache_precios.pkl. Corré generar_sitio.py primero.")
    out = {}
    for t, df in precios.items():
        c = df["Close"]
        var = float(c.iloc[-1] / c.iloc[-2] - 1) if len(c) > 1 else float("nan")
        out[t] = (pd.Timestamp(df.index[-1]).normalize(), float(c.iloc[-1]), var, len(c))
    return out, {"fecha": fecha, "simbolos": []}


def main():
    ap = argparse.ArgumentParser(description="Reporta precios atrasados o faltantes")
    ap.add_argument("archivo", nargs="?", default="sitio/datos.json")
    ap.add_argument("--cache", action="store_true", help="mira cache_precios.pkl")
    ap.add_argument("--todos", action="store_true", help="lista todo, no solo lo atrasado")
    ap.add_argument("--ticker", help="el detalle de un simbolo")
    args = ap.parse_args()

    if args.cache:
        datos, cab = desde_cache()
        origen = "cache_precios.pkl"
    else:
        p = Path(args.archivo)
        if not p.exists():
            sys.exit(f"[X] No encuentro {p}. Corré generar_sitio.py, o usá --cache.")
        datos, cab = desde_json(p)
        origen = str(p)

    print(f"Origen      {origen}")
    print(f"Generado    {cab.get('fecha', '?')}")
    print(f"Simbolos    {len(datos)}")

    # se reusa la misma cuenta que usa el sitio, para que no haya dos verdades
    falsos = {t: pd.DataFrame({"Close": [v[1]]}, index=[v[0]]) for t, v in datos.items()}
    tarde = atrasos(falsos)

    mercados = Counter(sufijo_mercado(t) or "US" for t in datos)
    ultimas = {}
    for t, (f, *_ ) in datos.items():
        k = sufijo_mercado(t) or "US"
        ultimas[k] = max(ultimas.get(k, f), f)
    print("\nUltima rueda por mercado")
    for k, n in mercados.most_common():
        print(f"  {k:<5} {n:>4} simbolos   {ultimas[k].date()}")

    if args.ticker:
        t = args.ticker.upper()
        if t not in datos:
            sys.exit(f"[X] {t} no esta en los datos. "
                     f"¿Quedo en faltantes? {t in cab.get('faltantes', [])}")
        f, px, var, n = datos[t]
        print(f"\n{t}\n  ultima barra  {f.date()}"
              f"\n  cierre        {px}"
              f"\n  variacion     {var * 100:+.2f}%"
              f"\n  barras        {n}"
              f"\n  atraso        {tarde.get(t, 0)} ruedas")
        return

    peores = sorted(((n, t) for t, n in tarde.items() if n > 0), reverse=True)
    print(f"\nAtrasados: {len(peores)} de {len(datos)} "
          f"({len(peores) / max(1, len(datos)) * 100:.1f}%)")
    if peores:
        print(f"  {'ticker':<10} {'atraso':>7} {'ultima':>12} {'cierre':>10} {'var':>8}")
        for n, t in peores:
            f, px, var, _ = datos[t]
            v = f"{var * 100:+.2f}%" if np.isfinite(var) else "   —"
            print(f"  {t:<10} {n:>5} d {str(f.date()):>12} {px:>10.2f} {v:>8}")
        print("\n  Un dia de atraso fuera de EE.UU. suele ser feriado local.")
        print("  Dos o mas ruedas en un papel de Nueva York es Yahoo devolviendo")
        print("  la serie recortada: volvé a correr generar_sitio.py, que ahora")
        print("  los repesca de a uno.")

    f = cab.get("faltantes", [])
    if f:
        print(f"\nSin datos ({len(f)}): {', '.join(f)}")

    if args.todos:
        print("\nTodos, por fecha de ultima barra")
        for t, (fe, px, var, n) in sorted(datos.items(), key=lambda kv: kv[1][0]):
            print(f"  {t:<10} {fe.date()}  {px:>10.2f}  {n:>4} barras")


if __name__ == "__main__":
    main()
