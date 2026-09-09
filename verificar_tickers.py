#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
¿EXISTE ESTE TICKER EN YAHOO?  ·  para cargar CEDEARs nuevos sin adivinar
================================================================================

    python verificar_tickers.py BG CLS DELL
    python verificar_tickers.py --archivo candidatos.txt

Para cada simbolo dice si Yahoo devuelve barras, cuantas, la ultima rueda, el
ultimo precio, la moneda y el nombre. Con eso se decide si entra al universo.

POR QUE HACE FALTA
------------------
El panel de BYMA publica el CODIGO BYMA, no el subyacente, y el screener SOLO
baja subyacentes. En la mayoria coinciden, pero no siempre y ahi esta la trampa:

    BNG  -> BG        Bunge, porque en BYMA "BG" no existe
    BA   -> BA        Boeing
    BA.C -> BAC       Bank of America
    AOCA -> ACH       Aluminum Corp of China
    SKHY -> ?         SK Hynix no cotiza en Estados Unidos

Adivinar el subyacente y cargarlo mal no se nota: el papel simplemente no baja
nunca y queda de adorno en el universo, o peor, baja OTRA empresa. Esto lo
contesta con el dato, no con la memoria.

LA MONEDA IMPORTA, y es lo que mas se equivoca uno: si aparece ARS es que se
apunto al CEDEAR y no al subyacente, que es justo lo que este proyecto no hace
nunca. La salida la marca en la cara.

Y EL LARGO DEL HISTORIAL TAMBIEN. Que el simbolo exista NO alcanza: con menos
de MIN_BARRAS (220) barras diarias, limpiar_barras lo descarta ENTERO y en
silencio. Por eso se pide el periodo del sitio y no un mes: con "1mo" todos dan
22 barras y el numero no distingue a Apple de una empresa que listo la semana
pasada. Fue exactamente asi como di por bueno al SPCX.

EL NOMBRE TAMPOCO ES ADORNO: los tickers SE REASIGNAN. Silvergate se liquido y
hoy "SI" devuelve barras perfectas de Shoulder Innovations, que es otra
empresa. Sin mirar el nombre, eso se carga y baja el papel equivocado.

No se usa desde el navegador ni desde el sitio: es una herramienta de consola.
En un entorno sin salida a internet no se puede correr, y para eso esta el
workflow `tickers.yml`, que la corre en Actions.
================================================================================
"""
import argparse
import sys

import yfinance as yf

from screener import MIN_BARRAS

# Un CEDEAR cotiza en pesos. Si un candidato vuelve en ARS es que se apunto al
# codigo BYMA en vez de al subyacente, y eso mete el tipo de cambio adentro de
# todos los indicadores. Es el error que este archivo existe para evitar.
MONEDA_PROHIBIDA = "ARS"


def mirar(tk, periodo="3y"):
    """Lo que Yahoo sabe de un simbolo. Nunca levanta: devuelve el motivo."""
    fila = {"t": tk, "ok": False, "barras": 0, "ultima": "", "precio": None,
            "moneda": "", "nombre": "", "nota": ""}
    try:
        h = yf.Ticker(tk).history(period=periodo, auto_adjust=True)
    except Exception as e:                                   # noqa: BLE001
        fila["nota"] = f"error: {type(e).__name__}"
        return fila
    if h is None or h.empty:
        fila["nota"] = "sin barras"
        return fila
    h = h.dropna(subset=["Close"])
    if h.empty:
        fila["nota"] = "barras sin cierre"
        return fila
    fila["barras"] = len(h)
    fila["ultima"] = str(h.index[-1].date())
    fila["precio"] = round(float(h["Close"].iloc[-1]), 4)
    try:
        info = yf.Ticker(tk).get_info() or {}
    except Exception:                                        # noqa: BLE001
        info = {}
    fila["moneda"] = (info.get("currency") or "").upper()
    fila["nombre"] = (info.get("longName") or info.get("shortName") or "")[:44]
    if fila["moneda"] == MONEDA_PROHIBIDA:
        fila["nota"] = "*** EN PESOS: es el CEDEAR, no el subyacente ***"
    elif fila["barras"] < MIN_BARRAS:
        # Que exista no alcanza: con menos de MIN_BARRAS el screener lo
        # DESCARTA ENTERO en limpiar_barras, y en silencio.
        fila["nota"] = (f"*** SOLO {fila['barras']} BARRAS: el screener pide "
                        f"{MIN_BARRAS} y lo va a descartar ***")
    else:
        fila["ok"] = True
    return fila


def main():
    ap = argparse.ArgumentParser(description="Ver si Yahoo tiene estos simbolos")
    ap.add_argument("tickers", nargs="*", help="simbolos a probar")
    ap.add_argument("--archivo", help="un simbolo por linea")
    # 3 años, que es lo que pide el sitio. Con "1mo" TODOS dan 22 barras y el
    # numero no dice nada: fue exactamente asi como di por bueno al SPCX, que
    # existe pero es una salida a bolsa reciente y no llega a MIN_BARRAS.
    ap.add_argument("--periodo", default="3y")
    args = ap.parse_args()

    tks = list(args.tickers)
    if args.archivo:
        with open(args.archivo, encoding="utf-8") as fh:
            tks += [l.strip() for l in fh
                    if l.strip() and not l.startswith("#")]
    if not tks:
        ap.error("no me pasaste ningun simbolo")

    print(f"{'ticker':<12}{'ok':<4}{'barras':>7}{'ultima':>13}{'precio':>13}"
          f"  {'mon':<5}nombre / motivo")
    print("-" * 100)
    buenos, malos = [], []
    for tk in tks:
        f = mirar(tk, args.periodo)
        (buenos if f["ok"] else malos).append(f)
        print(f"{f['t']:<12}{'si' if f['ok'] else 'NO':<4}{f['barras']:>7}"
              f"{f['ultima']:>13}"
              f"{(f['precio'] if f['precio'] is not None else 0):>13,.4f}"
              f"  {f['moneda']:<5}{f['nombre'] or f['nota']}"
              + (f"   {f['nota']}" if f['nombre'] and f['nota'] else ""))
    print("-" * 100)
    print(f"{len(buenos)} de {len(tks)} sirven")
    if malos:
        print("no sirven: " + " ".join(f["t"] for f in malos))
    # Se devuelve 0 aunque falten: esto es una herramienta para MIRAR, y un
    # candidato que no existe es informacion, no un fallo del programa.
    return 0


if __name__ == "__main__":
    sys.exit(main())
