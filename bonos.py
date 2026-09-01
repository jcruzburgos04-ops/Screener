#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
BONOS SOBERANOS ARGENTINOS
================================================================================

QUE ARMA
--------
El payload de la seccion de bonos: precios en pesos, en dolares MEP y en cable,
el tipo de cambio implicito de cada bono, y el canje de leyes (que tan caro
esta el ley argentina contra su gemelo de Nueva York).

DE DONDE SALEN LOS DATOS
------------------------
data912.com, que publica la rueda local sin clave. Verificado que el runner de
Actions llega (200); desde una maquina sin salida a internet no se puede
probar, por eso corre en el workflow.

Cada bono cotiza en TRES especies del mismo papel:

    AL30    en pesos
    AL30D   en dolares MEP   (se liquida en la plaza local)
    AL30C   en dolares cable (se liquida afuera)

De ahi salen los dos tipos de cambio implicitos, que es lo que mira todo el
mundo: MEP = precio_pesos / precio_D, y cable = precio_pesos / precio_C.

LO QUE ESTA VERSION NO CALCULA, Y POR QUE
-----------------------------------------
TIR, paridad, duration y DV01 NO estan. Todos ellos necesitan el cronograma de
cupones y amortizacion de cada bono, que es un dato contractual del prospecto,
no algo que se pueda deducir de un precio.

Poner esos cronogramas de memoria seria justo lo que el proyecto no hace: una
TIR calculada sobre un cronograma mal recordado se ve perfecta y esta mal, que
es peor que no mostrarla. Van a entrar cuando esten cargados uno por uno con la
fuente anotada, en bonos_cronograma.csv.

Lo que si esta —precios, los dos dolares implicitos y el canje de leyes— sale
entero de la rueda y no depende de ningun cronograma.
================================================================================
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FUENTE = "https://data912.com/live/arg_bonds"
CABECERA = {"User-Agent": "Mozilla/5.0"}

# Los soberanos del canje 2020. La letra del medio dice la ley:
#   AL / AE  -> ley Argentina        GD -> ley Nueva York
# Se listan a mano porque el panel trae ademas provinciales, letras y otras
# cosas que no son la curva soberana.
SOBERANOS = [
    # (ticker, ley, año de vencimiento, gemelo bajo la otra ley)
    ("AL29", "Argentina", 2029, "GD29"),
    ("AL30", "Argentina", 2030, "GD30"),
    ("AL35", "Argentina", 2035, "GD35"),
    ("AE38", "Argentina", 2038, "GD38"),
    ("AL41", "Argentina", 2041, "GD41"),
    ("GD29", "Nueva York", 2029, "AL29"),
    ("GD30", "Nueva York", 2030, "AL30"),
    ("GD35", "Nueva York", 2035, "AL35"),
    ("GD38", "Nueva York", 2038, "AE38"),
    ("GD41", "Nueva York", 2041, "AL41"),
    ("GD46", "Nueva York", 2046, None),
]


def bajar(url):
    pedido = urllib.request.Request(url, headers=CABECERA)
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def precio(fila):
    """El ultimo operado; si no hubo, el punto medio de la punta."""
    if not fila:
        return None
    c = fila.get("c")
    if c:
        return float(c)
    bid, ask = fila.get("px_bid"), fila.get("px_ask")
    if bid and ask:
        return (float(bid) + float(ask)) / 2
    return float(bid or ask or 0) or None


def armar(crudo):
    por = {d["symbol"]: d for d in crudo if d.get("symbol")}
    salida = []
    for tk, ley, vto, gemelo in SOBERANOS:
        pesos = precio(por.get(tk))
        mep = precio(por.get(tk + "D"))
        cable = precio(por.get(tk + "C"))
        if not pesos:
            continue
        fila = {
            "t": tk, "ley": ley, "vto": vto, "gemelo": gemelo,
            "pesos": round(pesos, 2),
            "usd_mep": round(mep, 2) if mep else None,
            "usd_cable": round(cable, 2) if cable else None,
            # El tipo de cambio implicito: cuantos pesos por dolar sale comprar
            # el dolar comprando el bono en pesos y vendiendolo en dolares.
            "tc_mep": round(pesos / mep, 2) if mep else None,
            "tc_cable": round(pesos / cable, 2) if cable else None,
            "var": por[tk].get("pct_change"),
            "volumen": por[tk].get("v"),
        }
        # La brecha entre los dos dolares del mismo bono
        if fila["tc_mep"] and fila["tc_cable"]:
            fila["brecha"] = round(fila["tc_cable"] / fila["tc_mep"] - 1, 4)
        salida.append(fila)
    return salida


def canje_de_leyes(filas):
    """
    Cuanto cuesta el ley argentina contra su gemelo de Nueva York, por par.

    Es el numero que mira el mercado para saber si conviene tener uno u otro:
    arriba de 1 el ley Nueva York cuesta mas caro, que es lo normal porque el
    tribunal de Nueva York vale algo. Se compara en dolares MEP, no en pesos,
    para que el tipo de cambio no ensucie la relacion.
    """
    por = {f["t"]: f for f in filas}
    pares = []
    for f in filas:
        if f["ley"] != "Argentina" or not f["gemelo"]:
            continue
        g = por.get(f["gemelo"])
        if not g or not f["usd_mep"] or not g["usd_mep"]:
            continue
        pares.append({
            "arg": f["t"], "ny": g["t"], "vto": f["vto"],
            "ratio": round(g["usd_mep"] / f["usd_mep"], 4),
        })
    return pares


def main():
    ap = argparse.ArgumentParser(description="Arma el payload de bonos")
    ap.add_argument("--salida", default="sitio")
    ap.add_argument("--minimo", type=int, default=6,
                    help="si vienen menos bonos que esto, no se escribe")
    args = ap.parse_args()

    print(f"[1/2] Bajando {FUENTE}")
    try:
        crudo = bajar(FUENTE)
    except Exception as e:
        sys.exit(f"[X] No pude bajar los bonos: {e}")
    print(f"      {len(crudo)} especies en el panel")

    filas = armar(crudo)
    pares = canje_de_leyes(filas)
    print(f"      {len(filas)} soberanos con precio · {len(pares)} pares de leyes")
    for f in filas:
        print(f"      {f['t']:<5} ${f['pesos']:>10,.0f}  MEP {f['usd_mep']}  "
              f"cable {f['usd_cable']}  tc {f['tc_mep']}")

    if len(filas) < args.minimo:
        sys.exit(f"[X] Solo {len(filas)} bonos con precio: no escribo nada.")

    ahora = datetime.now(timezone.utc)
    payload = {
        "fecha": ahora.strftime("%Y-%m-%d %H:%M"),
        "ts": int(ahora.timestamp()),
        "bonos": filas,
        "canje": pares,
        # Se declara explicitamente lo que NO trae, para que el frontend no
        # tenga que adivinar por que faltan columnas.
        "sin_cronograma": True,
    }
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bonos.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False),
        encoding="utf-8")
    print(f"[2/2] Listo -> {out}/bonos.json")


if __name__ == "__main__":
    main()
