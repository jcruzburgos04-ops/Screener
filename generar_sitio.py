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

CUANTO HISTORIAL HACE FALTA
---------------------------
850 barras, y las manda la EMA 600 del combo de fondo: necesita 600 ruedas
solo para imprimir su primer valor, mas las 220 que dibuja el grafico son 820.
Antes eran 400, que alcanzaban cuando la media mas larga era la EMA 200. El
archivo pasa de ~8,7 MB a ~18 MB: es el precio de tener ese combo, y se decidio
a proposito. Lo demas entra de sobra (52 semanas son 252, el ASH semanal ~80).
================================================================================
"""

import argparse
import json
import sys
from pathlib import Path

from generar_html import armar_payload
import screener
from screener import (BENCHMARK, actualizar_cuarentena, atrasos,
                      bajar_fundamentales, bajar_precios, cargar_cuarentena,
                      cargar_precios, guardar_precios, leer_universo,
                      repescar_atrasados, simbolos_en_cuarentena)

PLANTILLA = Path("plantilla.html")
MARCA = '/*__DATOS__*/ {fecha:"", simbolos:[]}'


def main():
    ap = argparse.ArgumentParser(description="Arma el sitio para publicar")
    ap.add_argument("--salida", default="sitio")
    ap.add_argument("--universo", default="universo.csv")
    # Del modulo, NO escrito aca: tenerlo repetido fue justamente lo que dejo
    # la primera corrida con 754 barras en vez de 850. El periodo lo decide
    # la EMA 600 y vive en screener.PERIODO.
    ap.add_argument("--periodo", default=screener.PERIODO)
    ap.add_argument("--barras", type=int, default=850)
    ap.add_argument("--sin-fundamentales", action="store_true")
    ap.add_argument("--usar-cache", action="store_true")
    args = ap.parse_args()

    if not PLANTILLA.exists():
        sys.exit(f"[X] Falta {PLANTILLA}")

    uni = leer_universo(args.universo)
    tickers = uni["ticker"].tolist()
    pedir = tickers if BENCHMARK in tickers else tickers + [BENCHMARK]
    print(f"[1/3] Universo: {len(tickers)} simbolos")

    meta = {}
    if args.usar_cache:
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
        # Los que vinieron con poco historial PORQUE COTIZAN DESDE HACE POCO
        # entran igual, marcados. No es aflojar MIN_BARRAS: el que vino corto
        # sin explicacion (una serie recortada por Yahoo) sigue quedando afuera.
        nuevitos = screener.rescatar_recien_listados()
        if nuevitos:
            precios.update(nuevitos)
            print("      recien listados, entran con poco historial: "
                  + ", ".join(f"{t}({len(d)}b)" for t, d in sorted(nuevitos.items())))
        actualizar_cuarentena(cuarentena, [t for t in pedir if t not in castigados],
                              set(precios))
        if not args.sin_fundamentales:
            print("      fundamentales (sector, industria, float)...")
            meta = bajar_fundamentales(list(precios.keys()))
        guardar_precios(precios, meta)

    faltan = [t for t in tickers if t not in precios]
    payload = armar_payload(precios, meta, uni, args.barras)
    payload["faltantes"] = faltan
    # armar_payload tambien descarta lo que no llega a MIN_BARRAS_NUEVO: esos
    # tambien son "sin datos" desde el punto de vista de la pagina.
    quedaron = {s["t"] for s in payload["simbolos"]}
    payload["faltantes"] = sorted(set(faltan) | {t for t in tickers if t not in quedaron})
    # Y aparte, los que SI vinieron pero con menos ruedas de las que existen: la
    # serie recortada de Yahoo. Meterlos en la misma bolsa hacia que la pagina
    # dijera "Yahoo no los devolvio", que para estos es falso. Son tres
    # situaciones con tres acciones distintas: el que no vino se INVESTIGA
    # (cambio de ticker?), el recortado se ESPERA a que vuelva entero, y el
    # recien listado ya ENTRO, unas lineas mas arriba.
    payload["cortos"] = {t: n for t, n in sorted(screener.CORTOS.items())
                         if t in payload["faltantes"]}
    # Y los que vinieron cortos pero SI entraron, por ser recien listados. La
    # pantalla los marca porque media tabla les viene vacia -- sin EMA 200, sin
    # maximo de 52 semanas, sin ASH semanal -- y eso hay que poder explicarlo.
    # Se saca del payload y no de screener.NUEVOS a proposito: un simbolo que
    # esta ADENTRO con menos de MIN_BARRAS solo pudo haber entrado por el rescate,
    # asi que la lista se deduce sola y no puede desincronizarse. Ademas sigue
    # saliendo bien con --usar-cache, donde no hubo descarga y NUEVOS esta vacio.
    payload["nuevos"] = {s["t"]: len(s["d"]) for s in payload["simbolos"]
                         if len(s["d"]) < screener.MIN_BARRAS}
    # El umbral viaja para que la pantalla no lo tenga escrito a mano y se
    # desincronice si alguna vez se cambia.
    payload["min_barras"] = screener.MIN_BARRAS

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
    novino = [t for t in payload["faltantes"] if t not in payload["cortos"]]
    if novino:
        print(f"  no los devolvio Yahoo: {', '.join(novino)}")
    if payload["cortos"]:
        print("  serie recortada, quedan afuera: "
              + ", ".join(f"{t}({n}b)" for t, n in payload["cortos"].items()))
    if payload["nuevos"]:
        print("  listaron hace poco, entran igual: "
              + ", ".join(f"{t}({n}b)" for t, n in payload["nuevos"].items()))
    print("\nSubi esa carpeta a GitHub Pages, o dejá que lo haga el workflow.")


if __name__ == "__main__":
    main()
