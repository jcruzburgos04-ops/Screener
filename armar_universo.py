#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
RENOVAR EL PANEL DE CEDEARs  ·  contra la lista que se negocia de verdad
================================================================================

POR QUE EXISTE
--------------
`cedears.csv` se armo a mano del panel de BYMA del 12/6/2026 y desde entonces
BYMA habilito tandas nuevas. Actualizarlo a ojo es tedioso y se presta a que
falte alguno sin que nadie se entere.

DE DONDE SALEN LOS DATOS
------------------------
De `data912.com`, que publica la rueda local sin clave. Se verifico que el
runner de GitHub Actions llega (200) a estos endpoints; desde una maquina de
desarrollo sin salida a internet NO se puede probar, por eso este script se
corre desde el workflow.

    /live/arg_cedears   la lista completa con precios
    /live/mep           el mismo panel con MEP/CCL por ticker

LO QUE ESTE SCRIPT NO HACE
--------------------------
NO inventa el mapeo a subyacente. La mayoria de los codigos BYMA coinciden con
el ticker de origen (MU/MU, AMAT/AMAT) y esos se resuelven solos, pero los que
no coinciden --DISN->DIS, BA.C->BAC, TEN->TS-- no se pueden deducir de un
listado de precios. Los nuevos que no se puedan mapear salen listados aparte
para cargarlos a mano UNA vez, que es la unica forma de no meter un subyacente
equivocado. Bajar el CEDEAR en vez del subyacente da indicadores mal, que es
peor que no tenerlos.

    python armar_universo.py                # solo informa, no toca nada
    python armar_universo.py --escribir     # actualiza cedears.csv
================================================================================
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from screener import cargar_mapa_cedears

FUENTE = "https://data912.com/live/arg_cedears"
CABECERA = {"User-Agent": "Mozilla/5.0"}

# data912 lista TRES especies del mismo papel: la de pesos (AAL), la de cable
# (AALC) y la de MEP (AALD). Solo interesa la de pesos.
#
# OJO CON EL FILTRO POR SUFIJO: no alcanza con sacar la ultima letra y ver si la
# base existe. GOGLC es la especie cable de GOOGL, pero "GOGL" no figura en el
# panel, asi que pasaba como si fuera un CEDEAR nuevo -- y agregarlo mapeado a
# si mismo habria hecho que se baje el precio del CEDEAR en vez del subyacente,
# que es el error que el proyecto NO se puede permitir.
#
# El discriminador de verdad esta en el precio: un CEDEAR en pesos vale miles
# (AAL: 10.300) y su especie en dolares vale unidades (AALC: 6,48). Eso sale de
# los datos y no de adivinar la nomenclatura.
PISO_PESOS = 200.0


def bajar(url):
    pedido = urllib.request.Request(url, headers=CABECERA)
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def especie_base(d, todos):
    """
    True si la fila es la especie en PESOS y no la variante en dolares.

    HACEN FALTA LAS DOS REGLAS, ninguna alcanza sola:

      - por precio: en pesos son miles y en dolares unidades. Pero se rompe con
        los papeles caros: HWMC y HWMD (las variantes de HWM) cotizan arriba de
        200 dolares y pasaban el corte como si fueran CEDEARs nuevos.
      - por sufijo: si sacarle la C o la D final da un simbolo que TAMBIEN esta
        en el panel, es una variante. Pero se rompe con GOGLC, porque la base
        no es GOGL sino GOOGL.

    Juntas se tapan mutuamente. Los codigos con punto (B.C, CAR.D) son siempre
    variantes.
    """
    sym = d.get("symbol") or ""
    if "." in sym:
        return False
    if len(sym) > 1 and sym[-1] in ("C", "D") and sym[:-1] in todos:
        return False
    px = d.get("c") or d.get("px_ask") or d.get("px_bid") or 0
    return float(px or 0) >= PISO_PESOS


def main():
    ap = argparse.ArgumentParser(description="Renueva el panel de CEDEARs")
    ap.add_argument("--escribir", action="store_true",
                    help="actualiza cedears.csv (por defecto solo informa)")
    ap.add_argument("--min-volumen", type=float, default=0.0,
                    help="ignora los que no negociaron ni esto en la rueda")
    args = ap.parse_args()

    print(f"[1/3] Bajando el panel de {FUENTE}")
    try:
        crudo = bajar(FUENTE)
    except Exception as e:
        sys.exit(f"[X] No pude bajar el panel: {e}")
    todos = {d["symbol"] for d in crudo if d.get("symbol")}
    vivos = {}
    for d in crudo:
        s = d.get("symbol")
        if not s or not especie_base(d, todos):
            continue
        if (d.get("v") or 0) < args.min_volumen:
            continue
        vivos[s] = d
    print(f"      {len(crudo)} especies en el panel · {len(vivos)} papeles en pesos")

    mapa = cargar_mapa_cedears()
    print(f"[2/3] Tenemos {len(mapa)} mapeos en cedears.csv")

    nuevos = sorted(s for s in vivos if s not in mapa)
    ya_no = sorted(s for s in mapa if s not in todos)

    # Los que coinciden con su ticker de origen se resuelven solos; los demas
    # hay que mirarlos a mano.
    # Solo se auto-mapea lo que es un ticker plausible de EEUU: puras letras y
    # de 1 a 5 caracteres. Los brasileños (VALE3, PETR3, ITUB3) terminan en
    # numero y su subyacente cotiza con OTRO codigo (VALE, PBR, ITUB), asi que
    # van siempre a mano.
    obvios = [s for s in nuevos if s.isalpha() and 1 <= len(s) <= 5]
    dudosos = [s for s in nuevos if s not in obvios]

    print(f"\n=== {len(nuevos)} CEDEARs en el panel que NO estan en cedears.csv ===")
    if obvios:
        print(f"\n  se mapean solos ({len(obvios)}), el codigo BYMA es el ticker:")
        for i in range(0, len(obvios), 12):
            print("    " + "  ".join(obvios[i:i + 12]))
    if dudosos:
        print(f"\n  HAY QUE MAPEARLOS A MANO ({len(dudosos)}): el codigo no es")
        print("  un ticker comun, asi que el subyacente no se puede deducir.")
        for i in range(0, len(dudosos), 10):
            print("    " + "  ".join(dudosos[i:i + 10]))

    if ya_no:
        print(f"\n=== {len(ya_no)} en cedears.csv que ya no aparecen en el panel ===")
        for i in range(0, len(ya_no), 12):
            print("    " + "  ".join(ya_no[i:i + 12]))
        print("  (puede ser que no negociaron hoy; NO se borran solos)")

    if not args.escribir:
        print("\n[3/3] Modo informe: no se toco nada. Con --escribir se agregan")
        print("      los que se mapean solos; los dudosos quedan siempre a mano.")
        return

    if not obvios:
        print("\n[3/3] No hay nada nuevo que agregar solo.")
        return

    ruta = Path("cedears.csv")
    texto = ruta.read_text(encoding="utf-8").rstrip("\n")
    agregado = "\n".join(f"{s},{s}" for s in obvios)
    ruta.write_text(f"{texto}\n# --- agregados por armar_universo.py ---\n{agregado}\n",
                    encoding="utf-8")
    print(f"\n[3/3] cedears.csv: +{len(obvios)} mapeos.")
    if dudosos:
        print(f"      Faltan {len(dudosos)} a mano: {' '.join(dudosos)}")


if __name__ == "__main__":
    main()
