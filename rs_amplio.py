#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RS AMPLIO  ·  el universo contra el que se pasa a percentil el RS de Estrategia
================================================================================

POR QUE EXISTE
--------------
El filtro 3 de la estrategia es "RS > 70", y el RS es un PERCENTIL. Un
percentil depende de contra quien se mide: en el backtest del usuario era
contra ~5.500 acciones de NYSE/Nasdaq (sin ETFs) mas sus tickers. Contra los
~350 del screener daria otro numero, porque esos ya estan elegidos: son los
que el usuario sigue, no el mercado.

Asi que de noche se baja el ultimo ano de todo NYSE/Nasdaq, se calcula el
mismo puntaje que la pagina (estrategia.puntaje_rs) y se publica la lista
ORDENADA de puntajes en rs_universo.json. La pagina ubica cada papel en esa
lista. Se publica la lista entera y no cortes cada 1%: son ~50 KB y asi el
percentil sale exacto, no interpolado.

DE DONDE SALE LA LISTA
----------------------
De NASDAQ Trader (nasdaqlisted.txt + otherlisted.txt), que es la lista oficial
de lo que cotiza hoy y trae la marca de ETF. Se sacan ETFs, emisiones de
prueba, warrants, units, derechos, preferidas y notas: el backtest era sobre
acciones.

LO QUE NO RESUELVE
------------------
Es la lista de HOY: un papel que se deslisto el mes pasado no esta. Para el
percentil de hoy eso es lo correcto; para reconstruir el RS de una fecha vieja
(--fecha) hay un sesgo de supervivencia chico, y por eso la sonda lo dice.

Si la corrida sale mal (Yahoo corta, la lista no baja, entran menos de
MINIMO), NO escribe nada y devuelve error: el workflow deja el archivo de la
noche anterior, y la pagina muestra de que fecha es.

    python rs_amplio.py --datos sitio/datos.json --salida sitio
    python rs_amplio.py --datos sitio/datos.json --salida /tmp --fecha 20261002
================================================================================
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import estrategia as E
from screener import BENCHMARK, bajar_precios

LISTAS = ["https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
          "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"]
MINIMO = 3000
# Lo que no es una accion comun, por el nombre de la emision.
NO_ACCION = re.compile(r"\b(warrants?|units?|rights?|preferred|notes?|debentures?|"
                       r"% |subordinated|"
                       r"fixed[- ]rate|floating rate|trust preferred|"
                       r"contingent value)\b", re.I)


def bajar_lista(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def leer_lista(texto, otra):
    """
    nasdaqlisted: Symbol|Security Name|Market Category|Test Issue|...|ETF|...
    otherlisted:  ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|...|Test Issue|...
    La ultima linea es "File Creation Time", no un papel.
    """
    lineas = [x for x in texto.splitlines() if x.strip()]
    cab = lineas[0].split("|")
    col = {c: i for i, c in enumerate(cab)}
    sim = "ACT Symbol" if otra else "Symbol"
    out = []
    for ln in lineas[1:]:
        if ln.startswith("File Creation Time"):
            continue
        p = ln.split("|")
        if len(p) < len(cab):
            continue
        if p[col["ETF"]] == "Y" or p[col["Test Issue"]] == "Y":
            continue
        t, nombre = p[col[sim]].strip(), p[col["Security Name"]]
        if not t or "$" in t or NO_ACCION.search(nombre):
            continue
        # Clases con punto (BRK.B) -> Yahoo usa guion (BRK-B). Otra cosa con
        # punto (.WS, .U) es un warrant o una unit que se escapo del nombre.
        if "." in t:
            base, _, clase = t.partition(".")
            if len(clase) != 1:
                continue
            t = f"{base}-{clase}"
        out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    ap.add_argument("--datos", required=True,
                    help="datos.json publicado: de ahi salen los tickers del usuario")
    ap.add_argument("--salida", required=True)
    ap.add_argument("--fecha", type=int, default=None,
                    help="AAAAMMDD; por defecto, la ultima rueda del SPY")
    ap.add_argument("--periodo", default="2y")
    ap.add_argument("--lote", type=int, default=100)
    args = ap.parse_args()

    P = json.loads(Path(args.datos).read_text())
    usuario, _, _ = E.universo_estrategia(P["simbolos"], E.cargar_adr())

    lista, n_lista = [], 0
    for url, otra in zip(LISTAS, (False, True)):
        try:
            sims = leer_lista(bajar_lista(url), otra)
        except Exception as e:                               # noqa: BLE001
            sys.exit(f"[X] no pude bajar {url}: {e}")
        print(f"  {url.rsplit('/', 1)[1]}: {len(sims)} acciones")
        lista += sims
    n_lista = len(set(lista))
    pedir = sorted(set(lista) | set(usuario) | {BENCHMARK})
    print(f"  a pedir: {len(pedir)} ({n_lista} de las listas + los del usuario)")

    precios = bajar_precios(pedir, args.periodo, lote=args.lote, minimo=1)
    print(f"  vinieron {len(precios)} de {len(pedir)}")
    spy = precios.get(BENCHMARK)
    if spy is None:
        sys.exit("[X] no vino el SPY")
    fspy = [int(x.strftime("%Y%m%d")) for x in spy.index]
    fecha = args.fecha or fspy[-1]
    # La misma regla que la pagina: la vela de hoy recien desde las 16:30 de
    # Nueva York. Corrida a mano a media rueda, si no, los cortes saldrian de
    # un precio que todavia se mueve.
    if not args.fecha:
        from zoneinfo import ZoneInfo
        ny = datetime.now(ZoneInfo("America/New_York"))
        if fecha >= int(ny.strftime("%Y%m%d")) and ny.hour * 60 + ny.minute < 16 * 60 + 30:
            fecha = fspy[-2]
    if fecha not in fspy:
        sys.exit(f"[X] {fecha} no es una rueda del SPY")
    cs = spy["Close"].to_numpy(float)[:fspy.index(fecha) + 1]

    puntajes, propios, sin_vela, cortos = [], 0, 0, 0
    usu = set(usuario)
    for t, d in precios.items():
        f = [int(x.strftime("%Y%m%d")) for x in d.index]
        if fecha not in f:
            sin_vela += 1               # atrasado o deslistado: no se inventa
            continue
        c = d["Close"].to_numpy(float)[:f.index(fecha) + 1]
        p = E.puntaje_rs(c, cs)
        if not np.isfinite(p):
            cortos += 1                 # menos de un ano de historia
            continue
        puntajes.append(round(float(p), 6))
        propios += t in usu
    print(f"  con puntaje: {len(puntajes)} · sin la vela del {fecha}: {sin_vela} · "
          f"con menos de 253 ruedas: {cortos} · del usuario: {propios}")
    if len(puntajes) < MINIMO:
        sys.exit(f"[X] solo {len(puntajes)} papeles con puntaje (< {MINIMO}): no escribo")

    puntajes.sort()
    q = np.percentile(puntajes, [10, 30, 50, 70, 90])
    print("  percentiles 10/30/50/70/90 del puntaje: "
          + " / ".join(f"{x:.3f}" for x in q))
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "rs_universo.json").write_text(json.dumps({
        "fecha": fecha,
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n": len(puntajes), "n_listas": n_lista, "n_usuario": propios,
        "p": puntajes}, separators=(",", ":")))
    print(f"  escrito {salida / 'rs_universo.json'}")


if __name__ == "__main__":
    main()
