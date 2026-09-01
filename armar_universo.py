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

# Sufijos que data912 agrega al mismo papel para las especies en dolares:
# AAL / AALC (cable) / AALD (MEP). Solo interesa el de pesos.
SUFIJOS_MONEDA = ("C", "D")


def bajar(url):
    pedido = urllib.request.Request(url, headers=CABECERA)
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def especie_base(sym, todos):
    """
    True si `sym` es la especie en pesos y no la variante C/D del mismo papel.
    Se comprueba contra el conjunto: si sacarle la ultima letra da un simbolo
    que tambien existe, es una variante.
    """
    if len(sym) > 1 and sym[-1] in SUFIJOS_MONEDA and sym[:-1] in todos:
        return False
    return True


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
        if not s or not especie_base(s, todos):
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
