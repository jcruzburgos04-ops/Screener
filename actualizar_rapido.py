#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ACTUALIZACION RAPIDA  ·  los precios del dia, sin rehacer el historial
================================================================================

POR QUE EXISTE
--------------
El navegador NO puede pedirle precios a Yahoo por su cuenta: la respuesta viene
sin la cabecera CORS y Chrome la bloquea con un "Failed to fetch". Eso no se
arregla desde este proyecto, es una decision de Yahoo.

La salida que no depende de nadie: que el sitio se actualice solo cada media
hora mientras el mercado esta abierto. Asi, cuando abris el link, lo que hay
publicado es de hace un rato y no del cierre de anoche.

QUE HACE, Y POR QUE ES BARATO
-----------------------------
La corrida nocturna baja 3 años de historial de 465 papeles: es pesada y a
Yahoo no le gusta que se la pidan seguido. Esta, en cambio, agarra el
datos.json que YA esta publicado, le pide a Yahoo solo el ultimo mes de cada
simbolo y le pega las barras nuevas encima. Mismo resultado en pantalla, una
fraccion del trabajo.

    python actualizar_rapido.py --previo sitio_previo/datos.json --salida sitio

Si algo sale mal devuelve un codigo distinto de cero y el workflow no publica:
mejor los precios del cierre anterior que un archivo a medio armar.
================================================================================
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from generar_html import serie
from screener import atrasos_por_fecha, bajar_precios

PLANTILLA = Path("plantilla.html")
MARCA = '/*__DATOS__*/ {fecha:"", simbolos:[]}'


def a_fecha(aaaammdd):
    s = str(aaaammdd)
    return pd.Timestamp(f"{s[:4]}-{s[4:6]}-{s[6:8]}")


def fusionar(simbolo, nuevo, tope):
    """
    Pega las barras nuevas sobre las viejas del payload.

    La ultima barra guardada se reemplaza SIEMPRE: si la corrida anterior fue a
    mitad de rueda, esa barra quedo con un cierre provisorio y hay que pisarla
    con el valor de ahora. Devuelve True si algo cambio.
    """
    if nuevo is None or len(nuevo) == 0:
        return False
    fechas = [int(x.strftime("%Y%m%d")) for x in nuevo.index]
    desde = fechas[0]
    k = len(simbolo["d"])
    while k > 0 and simbolo["d"][k - 1] >= desde:
        k -= 1

    px = float(nuevo["Close"].iloc[-1])
    dec = 4 if px < 5 else (3 if px < 100 else 2)
    antes = (simbolo["d"][-1], simbolo["c"][-1])

    simbolo["d"] = (simbolo["d"][:k] + fechas)[-tope:]
    for campo, col in (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close")):
        simbolo[campo] = (simbolo[campo][:k] + serie(nuevo[col], dec))[-tope:]
    simbolo["v"] = (simbolo["v"][:k]
                    + [int(v) if pd.notna(v) else 0 for v in nuevo["Volume"]])[-tope:]
    return (simbolo["d"][-1], simbolo["c"][-1]) != antes


def main():
    ap = argparse.ArgumentParser(description="Actualiza los precios del dia")
    ap.add_argument("--previo", default="sitio_previo/datos.json",
                    help="el datos.json que ya esta publicado")
    ap.add_argument("--salida", default="sitio")
    ap.add_argument("--periodo", default="1mo",
                    help="cuanto pedirle a Yahoo: con 1mo sobra")
    ap.add_argument("--min-actualizados", type=int, default=200,
                    help="si se actualizan menos que esto, no se publica")
    args = ap.parse_args()

    previo = Path(args.previo)
    if not previo.exists():
        sys.exit(f"[X] No encuentro {previo}. Corré la actualizacion completa primero.")
    payload = json.loads(previo.read_text(encoding="utf-8"))
    simbolos = payload.get("simbolos") or []
    if not simbolos:
        sys.exit("[X] El datos.json publicado no tiene simbolos.")

    tickers = [s["t"] for s in simbolos]
    print(f"[1/3] Publicado: {len(tickers)} simbolos, ultimo cierre "
          f"{payload.get('ultimo_cierre')}")

    # minimo=1: acá alcanza con una barra. El minimo de 220 es para la corrida
    # completa, donde una serie corta significa que Yahoo devolvio basura.
    print(f"[2/3] Pidiendo el ultimo {args.periodo} de cada simbolo...")
    precios = bajar_precios(tickers, args.periodo, minimo=1)
    if not precios:
        sys.exit("[X] Yahoo no devolvio nada. No publico.")

    tope = int(payload.get("barras") or 400)
    porIndice = {s["t"]: s for s in simbolos}
    cambiados = 0
    for t, d in precios.items():
        s = porIndice.get(t)
        if s is not None and fusionar(s, d, tope):
            cambiados += 1

    ultimas = {s["t"]: a_fecha(s["d"][-1]) for s in simbolos}
    tarde = atrasos_por_fecha(ultimas)
    for s in simbolos:
        s["at"] = int(tarde.get(s["t"], 0))
    payload["ultimo_cierre"] = max(s["d"][-1] for s in simbolos)
    payload["atrasados"] = sum(1 for s in simbolos if s["at"] > 0)
    payload["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload["parcial"] = True     # se armo durante la rueda, no despues del cierre

    print(f"      {len(precios)} contestaron, {cambiados} con barras nuevas, "
          f"{payload['atrasados']} atrasados")
    if len(precios) < args.min_actualizados:
        sys.exit(f"[X] Solo {len(precios)} de {len(tickers)} contestaron: "
                 "vino incompleto, dejo el sitio anterior en pie")

    print("[3/3] Escribiendo el sitio...")
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    html = PLANTILLA.read_text(encoding="utf-8")
    if MARCA not in html:
        sys.exit("[X] No encontre el marcador de datos en la plantilla.")
    (out / "index.html").write_text(html.replace(MARCA, '{fecha:"",simbolos:[]}'),
                                    encoding="utf-8")
    (out / "datos.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    print(f"\nListo -> {out}/   ultimo cierre {payload['ultimo_cierre']}")


if __name__ == "__main__":
    main()
