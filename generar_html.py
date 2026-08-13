#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
GENERADOR DEL SCREENER HTML
================================================================================

Baja los precios y escribe un archivo screener.html que se abre con doble clic.
Todos los calculos (ASH, EMAs, RSI, ADR, ADX, filtros) pasan a hacerse en el
navegador, asi que una vez generado el archivo no necesita ni Python ni internet.

    python generar_html.py                    # universo.csv -> screener.html
    python generar_html.py --barras 500       # menos historial = archivo mas liviano
    python generar_html.py --sin-fundamentales

Para actualizar los precios: volvé a correrlo. Reescribe el mismo archivo.
================================================================================
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from screener import (BENCHMARK, atrasos, bajar_fundamentales, bajar_precios,
                      cargar_precios, guardar_precios, leer_universo,
                      repescar_atrasados)

PLANTILLA = Path("plantilla.html")
SALIDA = Path("screener.html")


def serie(x, dec):
    """Redondea para que el archivo no pese de mas. 3 decimales alcanzan."""
    return [None if not np.isfinite(v) else round(float(v), dec) for v in x]


MONEDAS = {".SA": "BRL", ".DE": "EUR", ".PA": "EUR", ".F": "EUR", ".MI": "EUR",
           ".AS": "EUR", ".BR": "EUR", ".MC": "EUR", ".VI": "EUR", ".LS": "EUR",
           ".IR": "EUR", ".HE": "EUR", ".SW": "CHF", ".ST": "SEK", ".OL": "NOK",
           ".CO": "DKK", ".L": "GBP", ".IL": "USD", ".T": "JPY", ".TW": "TWD",
           ".HK": "HKD", ".MX": "MXN", ".TO": "CAD", ".V": "CAD", ".NE": "CAD",
           ".AX": "AUD", ".NZ": "NZD", ".SI": "SGD", ".KS": "KRW", ".KQ": "KRW",
           ".JO": "ZAR", ".SS": "CNY", ".SZ": "CNY", ".NS": "INR", ".BO": "INR"}


def moneda(ticker):
    """En que moneda cotiza el subyacente. Ninguno cotiza en pesos argentinos."""
    for suf, mon in MONEDAS.items():
        if ticker.endswith(suf):
            return mon
    return "USD"


def limpiar_para_web(d):
    """
    Ultima pasada antes de mandar los precios al navegador.

    El motor de JavaScript hace cuentas directas sobre estos arrays: un `null`
    en High o en Low se propaga como NaN y se lleva puesto el ADR, el ATR y el
    grafico del simbolo. Como el cache puede venir de una corrida vieja (de
    antes de que la descarga limpiara), se revisa igual aca.
    """
    d = d.dropna(subset=["Close"])
    d = d[d["Close"] > 0]
    for c in ("Open", "High", "Low"):
        d[c] = d[c].fillna(d["Close"])
    d["High"] = d[["High", "Open", "Close"]].max(axis=1)
    d["Low"] = d[["Low", "Open", "Close"]].min(axis=1)
    d["Volume"] = d["Volume"].fillna(0)
    return d[np.isfinite(d[["Open", "High", "Low", "Close"]]).all(axis=1)]


def armar_payload(precios, meta, uni, barras):
    grupos = dict(zip(uni["ticker"], uni["grupo"]))
    locales = dict(zip(uni["ticker"], uni["local"]))
    # Dias habiles de atraso de cada simbolo contra la ultima rueda de SU
    # mercado. Viaja al navegador para que la tabla pueda marcar con ⚠ los que
    # muestran un precio y una variacion que ya no son de hoy.
    tarde = atrasos(precios)
    simbolos = []
    for t, d in precios.items():
        # El cache puede tener papeles de un universo anterior: que no se cuelen.
        if t not in grupos and t != BENCHMARK:
            continue
        d = limpiar_para_web(d).iloc[-barras:]
        if len(d) < 120:
            continue
        m = meta.get(t, {})
        fechas = [int(x.strftime("%Y%m%d")) for x in d.index]
        px = float(d["Close"].iloc[-1])
        dec = 4 if px < 5 else (3 if px < 100 else 2)
        simbolos.append({
            "t": t, "g": grupos.get(t, ""), "local": locales.get(t, ""),
            "mon": moneda(t),
            "n": m.get("nombre", ""), "sec": m.get("sector", ""),
            "ind": m.get("industria", ""), "pais": m.get("pais", ""),
            "fl": m.get("float_shares") or m.get("shares_out") or None,
            "mc": m.get("mcap") or None,
            "at": int(tarde.get(t, 0)),
            "d": fechas,
            "o": serie(d["Open"], dec), "h": serie(d["High"], dec),
            "l": serie(d["Low"], dec), "c": serie(d["Close"], dec),
            "v": [int(v) if np.isfinite(v) else 0 for v in d["Volume"]],
        })
    ultima = max((s["d"][-1] for s in simbolos), default=0)
    return {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ultimo_cierre": ultima,
            "atrasados": sum(1 for s in simbolos if s["at"] > 0),
            "benchmark": BENCHMARK, "barras": barras, "simbolos": simbolos}


def main():
    ap = argparse.ArgumentParser(description="Genera el screener.html")
    ap.add_argument("--universo", default="universo.csv")
    ap.add_argument("--out", default=str(SALIDA))
    ap.add_argument("--periodo", default="3y")
    ap.add_argument("--barras", type=int, default=600,
                    help="barras diarias por simbolo que van al HTML")
    ap.add_argument("--sin-fundamentales", action="store_true")
    ap.add_argument("--usar-cache", action="store_true")
    args = ap.parse_args()

    if not PLANTILLA.exists():
        sys.exit(f"[X] Falta {PLANTILLA}, que es el molde del HTML.")

    uni = leer_universo(args.universo)
    tickers = uni["ticker"].tolist()
    pedir = tickers if BENCHMARK in tickers else tickers + [BENCHMARK]
    print(f"[1/3] Universo: {len(tickers)} simbolos")

    meta = {}
    if args.usar_cache:
        precios, meta, fecha = cargar_precios()
        if precios is None:
            sys.exit("[X] No hay cache. Corré sin --usar-cache la primera vez.")
        print(f"      usando el cache del {fecha}")
    else:
        print("[2/3] Bajando precios...")
        precios = bajar_precios(pedir, args.periodo)
        precios, _ = repescar_atrasados(precios, args.periodo)
        if not args.sin_fundamentales:
            print("      fundamentales (sector, float, market cap)...")
            meta = bajar_fundamentales(list(precios.keys()))
        guardar_precios(precios, meta)

    faltan = [t for t in tickers if t not in precios]
    if faltan:
        print(f"      sin datos: {', '.join(faltan)}")

    print("[3/3] Escribiendo el HTML...")
    payload = armar_payload(precios, meta, uni, args.barras)
    datos = json.dumps(payload, separators=(",", ":"), allow_nan=False)

    html = PLANTILLA.read_text(encoding="utf-8")
    marca = "/*__DATOS__*/ {fecha:\"\", simbolos:[]}"
    if marca not in html:
        sys.exit("[X] No encontre el marcador de datos en la plantilla.")
    Path(args.out).write_text(html.replace(marca, datos), encoding="utf-8")

    mb = Path(args.out).stat().st_size / 1e6
    print(f"\nListo -> {args.out}   ({len(payload['simbolos'])} simbolos, {mb:.1f} MB)")
    print("Abrilo con doble clic. No necesita servidor ni internet.")
    if mb > 25:
        print("[!] Pesado. Bajá el historial con --barras 400 si tarda en abrir.")


if __name__ == "__main__":
    main()
