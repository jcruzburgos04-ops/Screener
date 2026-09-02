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
from datetime import date, datetime, timezone
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


# ---------------------------------------------------------------------------
# MATEMATICA DE RENTA FIJA
#
# Todo lo de aca es verificable sin depender de ningun dato de mercado: se
# prueba contra casos analiticos donde la respuesta se conoce de antemano (un
# bono a la par rinde su cupon, un cupon cero rinde lo que dice la formula).
# Lo que NO es verificable asi es el cronograma, que es dato del prospecto.
# ---------------------------------------------------------------------------

def flujos(pagos, desde):
    """
    Los pagos futuros de un bono, en unidades de 100 de nominal ORIGINAL.

    En cada fecha el bono paga:
      - renta: cupon_anual/2 aplicado sobre el RESIDUAL, no sobre el nominal.
        Por eso un bono que ya amortizo la mitad paga la mitad de renta aunque
        el cupon no haya cambiado.
      - amortizacion: el porcentaje del nominal original que devuelve.

    Devuelve [(fecha, importe)] y el residual vigente hoy.
    """
    pagos = sorted(pagos, key=lambda x: x["fecha"])
    # EL RESIDUAL ES LO QUE QUEDA POR AMORTIZAR, no "100 menos lo ya pagado".
    # La primera version restaba de 100 las amortizaciones pasadas que hubiera
    # en el CSV, y como el CSV solo lleva pagos futuros daba 92 cuando lo que
    # quedaba por amortizar sumaba 60: el AL30 viene amortizando desde julio de
    # 2024 y esa historia no esta cargada. Definido asi el cronograma es
    # autoconsistente y no necesita arrastrar el pasado.
    futuros = [p for p in pagos if p["fecha"] > desde]
    residual = sum(p["amortiza"] for p in futuros)
    out, r = [], residual
    for p in futuros:
        renta = p["cupon_anual"] / 2.0 * r / 100.0
        out.append((p["fecha"], renta + p["amortiza"]))
        r -= p["amortiza"]
    return out, residual


def tir(precio, flujo, desde):
    """
    Tasa interna de retorno EFECTIVA ANUAL, que es como se cotiza en la plaza
    local. Se resuelve por biseccion y no por Newton: Newton puede divergir con
    flujos irregulares, y aca la velocidad no importa (once bonos).
    """
    if precio <= 0 or not flujo:
        return float("nan")
    def npv(y):
        return sum(c / (1.0 + y) ** ((f - desde).days / 365.0) for f, c in flujo)
    lo, hi = -0.95, 10.0
    if npv(lo) < precio or npv(hi) > precio:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > precio:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def duration(precio, flujo, desde, y):
    """
    Duration de Macaulay y modificada, y el DV01.

    La modificada dice cuanto cae el precio por cada punto porcentual que sube
    la tasa; el DV01, cuanto cae en dolares por cada punto basico. Es lo que se
    mira para dimensionar el riesgo de tasa de una posicion.
    """
    if precio <= 0 or not flujo or y != y:
        return float("nan"), float("nan"), float("nan")
    mac = 0.0
    for f, c in flujo:
        t = (f - desde).days / 365.0
        mac += t * c / (1.0 + y) ** t
    mac /= precio
    mod = mac / (1.0 + y)
    return mac, mod, mod * precio * 0.0001


def valor_tecnico(pagos, desde, residual):
    """
    Residual mas los intereses corridos desde el ultimo cupon. Es el valor
    "contable" del bono; la paridad es el precio contra esto.
    """
    pasados = [p for p in pagos if p["fecha"] <= desde]
    futuros = [p for p in pagos if p["fecha"] > desde]
    if not futuros:
        return residual
    prox = futuros[0]
    ult = max((p["fecha"] for p in pasados), default=None)
    if ult is None:
        return residual
    total = (prox["fecha"] - ult).days or 1
    corridos = (desde - ult).days
    renta = prox["cupon_anual"] / 2.0 * residual / 100.0
    return residual + renta * corridos / total


def leer_cronogramas(ruta="bonos_cronograma.csv"):
    """
    Lee el CSV de cronogramas. Una linea rota se saltea y se avisa, igual que
    con cedears.csv: perder un bono es mejor que arrastrar una fecha corrida.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return {}
    por = {}
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = [x.strip() for x in linea.split(",")]
        if len(partes) < 5:
            print(f"      [!] cronograma linea {n}: incompleta, la salteo")
            continue
        try:
            bono, fecha, cupon, amort, ver = partes[:5]
            por.setdefault(bono, []).append({
                "fecha": datetime.strptime(fecha, "%Y-%m-%d").date(),
                "cupon_anual": float(cupon),
                "amortiza": float(amort),
                "verificado": ver == "1",
            })
        except Exception:
            print(f"      [!] cronograma linea {n}: no la entiendo, la salteo")
    return por


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


def armar(crudo, cronogramas=None, hoy=None):
    por = {d["symbol"]: d for d in crudo if d.get("symbol")}
    cronogramas = cronogramas or {}
    hoy = hoy or date.today()
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

        # --- rendimiento, solo si hay cronograma ---
        # Se calcula sobre el precio en dolares MEP, que es la moneda del bono.
        # Sobre el precio en pesos daria una TIR en pesos, que no significa
        # nada para un bono que paga dolares.
        pagos = cronogramas.get(tk)
        if pagos and mep:
            flujo, residual = flujos(pagos, hoy)
            if flujo:
                y = tir(mep, flujo, hoy)
                mac, mod, dv = duration(mep, flujo, hoy, y)
                vt = valor_tecnico(pagos, hoy, residual)
                prox = min(p["fecha"] for p in pagos if p["fecha"] > hoy)
                fila.update({
                    "tir": round(y, 6) if y == y else None,
                    # TNA: la tasa nominal anual equivalente, capitalizada
                    # semestralmente. Es como la pide el que compara contra un
                    # plazo fijo.
                    "tna": round(((1 + y) ** 0.5 - 1) * 2, 6) if y == y else None,
                    "paridad": round(mep / vt, 4) if vt else None,
                    "vivo": round(residual, 2),
                    "duration": round(mod, 3) if mod == mod else None,
                    "dv01": round(dv, 5) if dv == dv else None,
                    "prox_pago": prox.isoformat(),
                    "pagos": len(flujo),
                    # Si el cronograma NO esta verificado contra el prospecto,
                    # la pantalla lo tiene que decir: una TIR provisoria que se
                    # muestra como firme es peor que no mostrarla.
                    "verificado": all(p.get("verificado") for p in pagos),
                })
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

    cron = leer_cronogramas()
    print(f"      cronogramas cargados: {', '.join(sorted(cron)) or 'ninguno'}")
    filas = armar(crudo, cron)
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
        # cuantos tienen rendimiento y cuantos de esos estan verificados
        "con_tir": sum(1 for f in filas if f.get("tir") is not None),
        "verificados": sum(1 for f in filas if f.get("verificado")),
    }
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bonos.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False),
        encoding="utf-8")
    print(f"[2/2] Listo -> {out}/bonos.json")


if __name__ == "__main__":
    main()
