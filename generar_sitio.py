#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
GENERADOR DEL SITIO  ·  para publicar en GitHub Pages
================================================================================

Arma una carpeta lista para subir:

    sitio/
      index.html    ~70 KB   la pagina, sin datos adentro
      datos.json    ~9 MB    los precios

Partido en dos, el navegador cachea cada cosa por su lado: la pagina se pinta
enseguida y los precios se bajan mientras tanto, con barra de progreso. Cuando
solo cambian los datos, el HTML sigue en cache.

    python generar_sitio.py                 # baja y arma sitio/
    python generar_sitio.py --usar-cache    # rearma sin volver a descargar
    python generar_sitio.py --barras 400    # menos historial, archivo mas chico
    python generar_sitio.py --demo          # datos sinteticos

CUANTO HISTORIAL HACE FALTA
---------------------------
400 barras alcanzan para todo lo que muestra la pagina: EMA 200 necesita 200,
el maximo de 52 semanas necesita 252 y el ASH semanal queda con ~80 semanas.
Por eso el sitio se genera con 400 y no con 600: un tercio menos de peso sin
perder nada en pantalla.
================================================================================
"""

import argparse
import json
import sys
from pathlib import Path

from generar_html import armar_payload
from screener import (BENCHMARK, actualizar_cuarentena, atrasos,
                      bajar_fundamentales, bajar_precios, cargar_cuarentena,
                      cargar_precios, datos_demo, guardar_precios,
                      leer_universo, repescar_atrasados,
                      simbolos_en_cuarentena)

PLANTILLA = Path("plantilla.html")
MARCA = '/*__DATOS__*/ {fecha:"", simbolos:[]}'


def main():
    ap = argparse.ArgumentParser(description="Arma el sitio para publicar")
    ap.add_argument("--salida", default="sitio")
    ap.add_argument("--universo", default="universo.csv")
    ap.add_argument("--periodo", default="3y")
    ap.add_argument("--barras", type=int, default=400)
    ap.add_argument("--sin-fundamentales", action="store_true")
    ap.add_argument("--usar-cache", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if not PLANTILLA.exists():
        sys.exit(f"[X] Falta {PLANTILLA}")

    uni = leer_universo(args.universo)
    tickers = uni["ticker"].tolist()
    pedir = tickers if BENCHMARK in tickers else tickers + [BENCHMARK]
    print(f"[1/3] Universo: {len(tickers)} simbolos")

    meta = {}
    if args.demo:
        precios = datos_demo(pedir)
    elif args.usar_cache:
        precios, meta, fecha = cargar_precios()
        if not precios:
            sys.exit("[X] No hay cache. Corré sin --usar-cache.")
        print(f"      cache del {fecha}")
        meta = meta or {}
    else:
        print("[2/3] Bajando precios...")
        # Misma cuarentena que usa el servidor local: los deslistados de verdad
        # (WBA, TTM, LFC...) no se piden por una semana. Antes el sitio los
        # reintentaba todas las noches y se comia los reintentos de a uno.
        cuarentena = cargar_cuarentena()
        castigados = simbolos_en_cuarentena(cuarentena)
        precios = bajar_precios(pedir, args.periodo, saltear=castigados)
        if not precios:
            sys.exit("[X] Yahoo no devolvio datos.")
        precios, _ = repescar_atrasados(precios, args.periodo)
        actualizar_cuarentena(cuarentena, [t for t in pedir if t not in castigados],
                              set(precios))
        if not args.sin_fundamentales:
            print("      fundamentales (sector, industria, float)...")
            meta = bajar_fundamentales(list(precios.keys()))
        guardar_precios(precios, meta)

    faltan = [t for t in tickers if t not in precios]
    payload = armar_payload(precios, meta, uni, args.barras)
    payload["demo"] = args.demo
    payload["faltantes"] = faltan
    # armar_payload tambien descarta lo que tiene menos de 120 barras: esos
    # tambien son "sin datos" desde el punto de vista de la pagina.
    quedaron = {s["t"] for s in payload["simbolos"]}
    payload["faltantes"] = sorted(set(faltan) | {t for t in tickers if t not in quedaron})

    tarde = {t: n for t, n in atrasos(precios).items() if n > 0 and t in quedaron}
    if tarde:
        peores = sorted(tarde.items(), key=lambda kv: -kv[1])[:15]
        print(f"      [!] {len(tarde)} con la ultima barra atrasada: "
              + ", ".join(f"{t}({n}d)" for t, n in peores)
              + (" ..." if len(tarde) > 15 else ""))

    print("[3/3] Escribiendo el sitio...")
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)

    html = PLANTILLA.read_text(encoding="utf-8")
    if MARCA not in html:
        sys.exit("[X] No encontre el marcador de datos en la plantilla.")
    # la pagina va SIN datos: los busca en datos.json, al lado
    (out / "index.html").write_text(
        html.replace(MARCA, '{fecha:"",simbolos:[]}'), encoding="utf-8")
    (out / "datos.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    # GitHub Pages ignora las carpetas que empiezan con _ si no esta este archivo
    (out / ".nojekyll").write_text("")

    kb = (out / "index.html").stat().st_size / 1024
    mb = (out / "datos.json").stat().st_size / 1e6
    print(f"\nListo -> {out}/")
    print(f"  index.html  {kb:6.0f} KB")
    print(f"  datos.json  {mb:6.1f} MB   ({len(payload['simbolos'])} simbolos, "
          f"{args.barras} barras)")
    print(f"  atrasados   {payload['atrasados']:6d}   "
          f"({payload['atrasados'] / max(1, len(payload['simbolos'])) * 100:.0f}% "
          f"del total)")
    if payload["faltantes"]:
        print(f"  sin datos: {', '.join(payload['faltantes'])}")
    print("\nSubi esa carpeta a GitHub Pages, o dejá que lo haga el workflow.")


if __name__ == "__main__":
    main()
