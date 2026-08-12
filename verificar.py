#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
VERIFICAR UN SIMBOLO  ·  para comparar a ojo contra TradingView
================================================================================

Imprime las ultimas barras y los indicadores de UN papel. Es la herramienta
para cuando un precio no cierra: se mira acá y se compara con el grafico.

    python verificar.py NVDA
    python verificar.py PBR --barras 15
    python verificar.py AAPL --cache          # sin bajar nada, del cache
    python verificar.py TS --semanal

DOS TRAMPAS CONOCIDAS ANTES DE DECIR "EL DATO ESTA MAL"
-------------------------------------------------------
1. DOBLE LISTADO. SHOP, AEM, KGC, HL, NG, PAAS y B cotizan tambien en Toronto
   con el mismo ticker. Si la diferencia es de ~1,40 estás mirando dolares
   canadienses: compará contra NASDAQ:SHOP, no contra TSX:SHOP.
2. CEDEARS. Acá nunca se baja el precio del CEDEAR sino el del subyacente,
   asi que compará contra el papel en su mercado de origen, no contra el
   panel de BYMA.
================================================================================
"""

import argparse
import sys

import pandas as pd

from screener import (CFG_ASH, a_semanal, bajar_precios, calc_adr_pct, calc_adx,
                      calc_ash, calc_atr, calc_rsi, cargar_mapa_cedears,
                      cargar_precios, ema, ultima_fecha)


def main():
    ap = argparse.ArgumentParser(description="Muestra OHLC e indicadores de un simbolo")
    ap.add_argument("ticker")
    ap.add_argument("--barras", type=int, default=10)
    ap.add_argument("--periodo", default="1y")
    ap.add_argument("--semanal", action="store_true")
    ap.add_argument("--cache", action="store_true", help="usa cache_precios.pkl")
    ap.add_argument("--length", type=int, default=CFG_ASH["length"])
    ap.add_argument("--smooth", type=int, default=CFG_ASH["smooth"])
    ap.add_argument("--modo", default=CFG_ASH["modo"])
    ap.add_argument("--ma", default=CFG_ASH["ma_type"])
    args = ap.parse_args()

    t = args.ticker.upper()
    mapa = cargar_mapa_cedears()
    base = t[:-3] if t.endswith(".BA") else t
    if base in mapa and mapa[base] != t:
        print(f"[i] {t} es un CEDEAR: analizo el subyacente {mapa[base]}")
        t = mapa[base]

    if args.cache:
        precios, _, fecha = cargar_precios()
        if not precios or t not in precios:
            sys.exit(f"[X] {t} no esta en el cache. Corré sin --cache.")
        df = precios[t]
        print(f"[i] del cache del {fecha}")
    else:
        df = bajar_precios([t], args.periodo).get(t)
        if df is None:
            sys.exit(f"[X] Yahoo no devolvio nada para {t} (o vino con menos "
                     "barras que el minimo). Probá con otro periodo.")

    marco = a_semanal(df) if args.semanal else df
    cfg = dict(CFG_ASH, length=args.length, smooth=args.smooth,
               modo=args.modo, ma_type=args.ma)
    bu, be, ash = calc_ash(marco, **cfg)

    tabla = pd.DataFrame({
        "Open": marco["Open"], "High": marco["High"], "Low": marco["Low"],
        "Close": marco["Close"], "Volume": marco["Volume"],
        "bulls": bu, "bears": be, "ASH": ash,
        "RSI": calc_rsi(marco["Close"]), "ADR%": calc_adr_pct(marco),
        "ATR": calc_atr(marco), "ADX": calc_adx(marco),
        "EMA20": ema(marco["Close"], 20), "EMA50": ema(marco["Close"], 50),
    }).tail(args.barras)

    pd.set_option("display.width", 200, "display.max_columns", 40)
    print(f"\n{t}   {'semanal' if args.semanal else 'diario'}   "
          f"ASH {cfg['modo']} {cfg['length']}/{cfg['smooth']} {cfg['ma_type']}")
    print(f"ultima barra: {ultima_fecha(marco).date()}   "
          f"{len(marco)} barras en total\n")
    print(tabla.round(4).to_string())
    print("\nSi el cierre no coincide con TradingView, revisá las dos trampas "
          "que estan comentadas arriba de este archivo (doble listado y CEDEAR).")


if __name__ == "__main__":
    main()
