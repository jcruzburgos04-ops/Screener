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

RENDIMIENTOS
------------
TIR, TNA, paridad, duration y DV01 salen del cronograma de cupones y
amortizacion de cada bono, que es dato contractual del prospecto y no se deduce
de un precio. Viven en bonos_cronograma.csv, uno por linea, con una columna
`verificado` que dice si esa linea se contrasto contra una referencia externa.

Mientras un bono tenga alguna linea sin verificar, el payload lo marca y la
pantalla muestra su TIR como PROVISORIA. Una TIR calculada sobre un cronograma
mal recordado se ve perfecta y esta mal, que es peor que no mostrarla.

Ningun endpoint publico gratuito publica estos cronogramas: se probaron los 16
de data912 (solo precios y OHLC) y los de BYMA con POST (government-bonds,
corporate-bonds y negotiable-obligations dan 401). Por eso van a mano.

================================================================================
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import futuros

FUENTE = "https://data912.com/live/arg_bonds"

# Las obligaciones negociables salen de otra fuente, porque data912 publica sus
# PRECIOS (/live/arg_corp) pero no dice de quien es cada papel ni cuando vence,
# y una tabla de ONs sin emisor ni vencimiento no sirve para nada. bonistas.com
# publica emisor, vencimiento, ley, cupon y las condiciones de emision.
FUENTE_ONS = "https://bonistas.com/api/bonds"
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


def desglose(pagos, desde):
    """
    Lo mismo que `flujos` pero abierto, para la pantalla de detalle: en cada
    fecha, cuanto es renta, cuanto es amortizacion y cuanto queda vivo despues.

    Es el mismo recorrido y las mismas cuentas; se separa para no cambiarle la
    firma a `flujos`, que la usan tir() y duration() y ya esta probada.
    """
    futuros = sorted((p for p in pagos if p["fecha"] > desde),
                     key=lambda x: x["fecha"])
    r = sum(p["amortiza"] for p in futuros)
    out = []
    for p in futuros:
        renta = p["cupon_anual"] / 2.0 * r / 100.0
        r -= p["amortiza"]
        out.append({
            "f": p["fecha"].isoformat(),
            "cupon": p["cupon_anual"],
            "renta": round(renta, 4),
            "amort": round(p["amortiza"], 4),
            "total": round(renta + p["amortiza"], 4),
            "vivo": round(r, 4),
        })
    return out


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


def bajar_con_cache(url, cache, minutos):
    """
    Igual que bajar(), pero reusa lo ultimo bajado si tiene menos de `minutos`.

    Existe por educacion con la fuente: intradia.yml publica cada diez minutos
    durante toda la rueda y el panel de ONs pesa 1,6 MB. Bajarlo cinco veces por
    hora es castigar gratis a un servicio ajeno cuando los precios de la deuda
    corporativa no se mueven a ese ritmo. Con media hora de cache cada
    publicacion sigue saliendo COMPLETA -- no se cae la seccion en las vueltas
    intermedias -- y los pedidos bajan a dos por hora.
    """
    if cache:
        c = Path(cache)
        if c.exists():
            edad = (datetime.now(timezone.utc).timestamp() - c.stat().st_mtime) / 60
            if edad < minutos:
                try:
                    print(f"      (uso el cache de las ONs, {edad:.0f} min)")
                    return json.loads(c.read_text(encoding="utf-8"))
                except Exception:
                    pass  # cache roto: se baja de nuevo, no se cae nada
    datos = bajar(url)
    if cache:
        try:
            c = Path(cache)
            c.parent.mkdir(parents=True, exist_ok=True)
            c.write_text(json.dumps(datos, separators=(",", ":")), encoding="utf-8")
        except Exception as e:
            print(f"      (no pude guardar el cache de ONs: {e})")
    return datos


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
        # Un bono cuyo cronograma ya se agoto vencio: se va solo, sin lista que
        # mantener. En la practica deja de cotizar y ni siquiera llega hasta
        # aca, pero si el panel lo arrastrara un dia mas no puede quedar una
        # fila muerta con precio y sin rendimiento.
        if pagos and not [x for x in pagos if x["fecha"] > hoy]:
            continue
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
                    # La de Macaulay va aparte de la modificada, como en el
                    # informe de referencia: la primera son los años promedio
                    # en que se cobra la plata, la segunda cuanto cae el precio
                    # por cada punto de tasa. Se venia calculando y tirando.
                    "duration_mac": round(mac, 3) if mac == mac else None,
                    "dv01": round(dv, 5) if dv == dv else None,
                    "prox_pago": prox.isoformat(),
                    "pagos": len(flujo),
                    # Si el cronograma NO esta verificado contra el prospecto,
                    # la pantalla lo tiene que decir: una TIR provisoria que se
                    # muestra como firme es peor que no mostrarla.
                    "verificado": all(p.get("verificado") for p in pagos),
                    # El cronograma abierto, para la pantalla de detalle. Son
                    # ~30 filas por bono en el peor caso: no pesa.
                    "flujo": desglose(pagos, hoy),
                })
        salida.append(fila)
    return salida


# ---------------------------------------------------------------------------
# OBLIGACIONES NEGOCIABLES
#
# ACA EL RENDIMIENTO NO ES PROPIO Y HAY QUE DECIRLO. Para los soberanos el
# cronograma esta cargado y verificado, asi que la TIR se calcula aca y se
# puede auditar. Para las ONs no: son cientos de emisiones, cada una con sus
# condiciones, y no hay ninguna fuente publica con los flujos. Lo que se
# muestra es la TIR que publica bonistas, ATRIBUIDA, no presentada como propia.
#
# Que NO se toma de ahi: el campo de amortizacion. Dice "bullet (100% al
# vencimiento)" hasta para los soberanos del canje, que amortizan en cuotas
# desde 2024. Si esta mal en los que se pueden verificar, no se usa en los que
# no.
# ---------------------------------------------------------------------------

FAMILIAS_ON = ("ONS", "ONS-CABLE")

# Cada emision cotiza en varios plazos de liquidacion. Se prefiere 24hs, que es
# donde se opera de verdad.
ORDEN_PLAZO = {"24hs": 0, "CI": 1}


def _tna(fila):
    """
    La tasa del cupon, sacada del texto de las condiciones.

    NO se usa el campo `coupon`: ese es OTRA cosa -- el importe del proximo
    pago -- y confundirlos es justamente lo que destrabo los cronogramas de los
    soberanos. Una ON step-up no tiene UNA tasa: ahi devuelve None y la
    pantalla muestra un punto, que es lo honesto.
    """
    for texto in (fila.get("description") or "", fila.get("short_description") or ""):
        m = (re.search(r"TNA\)?:?\s*([\d.,]+)\s*%", texto)
             or re.search(r"-\s*([\d.,]+)%\s*-\s*vto", texto))
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------------
# Fechas: el vencimiento que se muestra, y el proximo pago
# ---------------------------------------------------------------------------
# LO QUE **NO** ESTABA MAL, aunque lo parecia. Contra el informe de cierre del
# 01/09/2026 nuestros dias daban UNO MENOS en los once papeles de tasa fija,
# sin una sola excepcion, que es la pinta clasica de un error de convencion.
# No lo era: ese informe es el cierre del 01-09 y liquida el 02-09, y nuestro
# dato es del 02-09 y liquida el 03-09. Un dia mas fresco, no un dia mal
# contado.
#
# Verificado contra los datos crudos: para las tres formas -- 24hs sobre dia
# habil, contado inmediato, y un vencimiento que cae sabado -- el
# `days_to_finish` que publica la fuente es EXACTAMENTE el vencimiento habil
# menos la liquidacion de ese plazo. Ya cuenta desde la liquidacion y ya corre
# los fines de semana.
#
# LO QUE SI ESTABA MAL es la FECHA que se muestra. La fuente publica el
# vencimiento NOMINAL: el TO26 figura venciendo el 17/10/2026, que es sabado,
# cuando lo que se cobra -- y contra lo que ella misma descuenta -- es el lunes
# 19/10. Se corrige para que la columna diga lo mismo que la cuenta.

MESES_EN = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
            "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
            "november": 11, "december": 12}


def _fecha_larga(s):
    """`September 2nd, 2026` -> date(2026, 9, 2). None si no se entiende."""
    m = re.match(r"\s*([A-Za-z]+)\s+(\d{1,2})[a-z]{0,2},?\s+(\d{4})", str(s or ""))
    if not m:
        return None
    mes = MESES_EN.get(m.group(1).lower())
    if not mes:
        return None
    try:
        return date(int(m.group(3)), mes, int(m.group(2)))
    except ValueError:
        return None


def fecha_de_la_fuente(crudo):
    """
    El dia al que corresponde el panel, segun la propia fuente
    (`estimation_date`). Se usa ESO y no el reloj de la maquina: el workflow
    corre en UTC y a las 02:00 UTC ya es otro dia que en Buenos Aires, asi que
    `date.today()` correria todos los plazos una vez por noche.
    """
    for f in crudo:
        d = _fecha_larga(f.get("estimation_date"))
        if d:
            return d
    return date.today()


def habil_siguiente(d):
    """
    Un pago que cae sabado o domingo se cobra el lunes. NO contempla feriados:
    no hay calendario publico sin sumar otra fuente. Es el mismo limite que ya
    tiene `futuros.ultimo_habil` y esta asumido igual.
    """
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def liquidacion(hoy, plazo="24hs"):
    """
    Cuando recibe el titulo el que compra: contado inmediato el mismo dia,
    24hs el habil siguiente. Es la fecha desde la que se cuenta todo.
    """
    if str(plazo or "").upper() == "CI":
        return habil_siguiente(hoy)
    return habil_siguiente(hoy + timedelta(days=1))


def _fecha(s):
    """La fecha ISO de la fuente, o None si no viene o no se entiende."""
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _entero(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def vencimiento_y_dias(fila, hoy):
    """
    (vencimiento corregido al habil, dias desde la liquidacion).

    Los dias se recalculan aca en vez de pasar `days_to_finish` para que la
    fecha y la cuenta no puedan discrepar cuando el vencimiento se corre. Da
    lo mismo que la fuente -- esta verificado -- pero ahora es verificable.
    Sin fecha usable se cae a lo que diga ella: peor, pero es lo que hay.
    """
    v = _fecha(fila.get("end_date"))
    if not v:
        return None, _entero(fila.get("days_to_finish"))
    v = habil_siguiente(v)
    return v.isoformat(), (v - liquidacion(hoy, fila.get("settlement"))).days


def proximo_pago(fila, hoy):
    """
    El proximo servicio del instrumento: cuando, cuanto, y si es el ultimo.

    Sale de dos campos que la fuente publica para casi todo lo que cotiza
    -- 881 de las 909 filas del panel --: `days_to_coupon`, los dias que
    faltan, y `coupon`, su IMPORTE cada 100 nominales.

    `coupon` ES UN IMPORTE, NO UNA TASA. Es la confusion que ya se pago cara
    una vez con los soberanos: el TO26 paga 15,50% anual sobre 100 de residual
    y el campo trae 7,75, que es el semestre.

    ES EL ULTIMO cuando `days_to_coupon` coincide con `days_to_finish`: no
    queda ningun servicio entre este y el vencimiento. Eso es lo que separa a
    una letra que capitaliza y paga todo junto -- que asi queda con su
    cronograma COMPLETO, de una sola linea -- de un bono al que le faltan
    cupones que la fuente no detalla. La pantalla dice cual de las dos cosas
    esta mirando; inventar los cupones del medio seria lo que este proyecto no
    hace.
    """
    dc = _entero(fila.get("days_to_coupon"))
    dv = _entero(fila.get("days_to_finish"))
    # Un `days_to_coupon` mayor que el plazo al vencimiento no es un pago: es
    # un dato roto, y en una columna se leeria como un cobro que no existe.
    if dc is None or dc < 0 or (dv is not None and dc > dv):
        return None
    liq = liquidacion(hoy, fila.get("settlement"))
    ultimo = dv is not None and dc == dv
    venc, dias_venc = vencimiento_y_dias(fila, hoy)
    if ultimo and venc:
        # Si es el ultimo, el pago ES el vencimiento: se toma la misma fecha
        # que muestra la fila en vez de reconstruirla desde los dias. Asi la
        # columna "vence" y la columna "proximo pago" no pueden decir cosas
        # distintas del mismo dia, que es lo que pasaba cuando las dos se
        # derivaban por caminos separados.
        f, d = date.fromisoformat(venc), dias_venc
    else:
        f = habil_siguiente(liq + timedelta(days=dc))
        d = (f - liq).days
    monto = fila.get("coupon")
    rinde = fila.get("coupon_yield")
    return {
        "fecha": f.isoformat(),
        "dias": d,
        "monto": round(monto, 4) if isinstance(monto, (int, float)) else None,
        # Sobre el valor tecnico, no sobre el precio. Lo publica la fuente.
        "sobre_vt": (round(rinde, 6)
                     if isinstance(rinde, (int, float)) and rinde else None),
        "ultimo": ultimo,
    }


def armar_ons(crudo, hoy=None):
    hoy = hoy or fecha_de_la_fuente(crudo)
    por = {}
    for f in crudo:
        if f.get("bond_family") not in FAMILIAS_ON:
            continue
        tk = f.get("ticker") or f.get("bond_name")
        if not tk or not f.get("last_price"):
            continue
        anterior = por.get(tk)
        if anterior and (ORDEN_PLAZO.get(anterior.get("settlement"), 9)
                         <= ORDEN_PLAZO.get(f.get("settlement"), 9)):
            continue
        por[tk] = f

    def redondo(v, dec):
        return round(v, dec) if isinstance(v, (int, float)) else None

    def fila(tk, f):
        vto, dias = vencimiento_y_dias(f, hoy)
        return {
            "t": tk,
            "emisor": f.get("emisor") or "—",
            "ley": "Nueva York" if f.get("bond_law") == "LNY" else "Argentina",
            "cable": f.get("bond_family") == "ONS-CABLE",
            "vto": vto or f.get("end_date"),
            "emitido": f.get("start_date"),
            "dias": dias,
            "precio": round(float(f["last_price"]), 2),
            "cupon": _tna(f),
            "var": redondo(f.get("day_difference"), 6),
            # Cuando cobra el que la compra hoy, y cuanto. Es lo unico del
            # cronograma que publica la fuente, y para las que ya no tienen
            # mas servicios por delante ES el cronograma entero.
            "pago": proximo_pago(f, hoy),
            # Los tres de abajo los calcula bonistas, no este programa. La
            # pantalla lo dice en la tarjeta.
            "tir": redondo(f.get("tir"), 6),
            "duration": redondo(f.get("modified_duration"), 3),
            "paridad": redondo(f.get("parity"), 4),
            "resumen": f.get("short_description") or "",
        }

    return [fila(tk, f) for tk, f in sorted(por.items())]


def emisores(ons):
    """
    Agrupa por emisor: es como mira esto el que arma una cartera para un
    cliente -- primero decide A QUIEN le presta y despues a que plazo. YPF a
    2029 y YPF a 2031 son la misma decision de credito.
    """
    por = {}
    for o in ons:
        por.setdefault(o["emisor"], []).append(o)
    salida = []
    for nombre, papeles in por.items():
        tirs = sorted(p["tir"] for p in papeles if p["tir"] is not None)
        # La mediana y no el promedio: una emision corta y rara mueve el
        # promedio y no dice nada del riesgo del emisor. Con cantidad par se
        # promedian las dos del medio, que es la mediana de verdad; quedarse
        # con la de arriba le sube la tasa a todo emisor con dos papeles.
        if tirs:
            m = len(tirs) // 2
            med = tirs[m] if len(tirs) % 2 else (tirs[m - 1] + tirs[m]) / 2
        else:
            med = None
        salida.append({"emisor": nombre, "papeles": len(papeles),
                       "tir_med": round(med, 6) if med is not None else None})
    salida.sort(key=lambda x: (x["tir_med"] is None, -(x["tir_med"] or 0)))
    return salida


# ---------------------------------------------------------------------------
# CURVAS EN PESOS: tasa fija, CER, TAMAR, dolar linked y duales
#
# NO HAY NINGUNA LISTA DE TICKERS ACA, Y ES A PROPOSITO. El pedido fue
# explicito: que no haya que venir a tocar codigo cada vez que vence una letra
# o se emite una nueva. Por eso el agrupamiento sale del campo `index` que ya
# trae bonistas -- Fijo, CER, Tamar, USDL, Dual, DualCER --, que ES la curva a
# la que pertenece cada papel. Si mañana el Tesoro emite una LECAP nueva
# aparece sola; cuando vence, desaparece sola.
#
# Los rendimientos tampoco se calculan aca: bonistas ya publica `tir`
# (efectiva anual), `tna` y `mtir` (la efectiva MENSUAL, que es la TEM con la
# que se mira este mercado). Se muestran atribuidos, igual que en las ONs.
# ---------------------------------------------------------------------------

# DOS CAMPOS, DOS TRABAJOS DISTINTOS. Costo dos vueltas entenderlo:
#
#   `bond_family` decide QUE ENTRA. Separa la letra en pesos S30S6 de su gemela
#   en dolares SS6D (LETRAS-FIJO contra LETRAS-FIJO-USD), y marca las patas
#   sinteticas de los duales. Agrupar por `index` sin filtrar antes metia las
#   dos en la misma curva, con dos puntos al mismo plazo y rendimientos muy
#   distintos: TO26 25,6% contra TO26D 46,5%.
#
#   `index` decide EN QUE CURVA VA. Una LECAP y un BONCAP son familias
#   distintas (LETRAS-FIJO y BONO-CAPITALIZABLE) pero la misma curva de tasa
#   fija, y quien opera las mira juntas. Agrupar por familia las partia en
#   nueve curvas donde el mercado ve cinco.
#
# Filtrar por familia y despues agrupar por indice da las dos cosas bien.
#
# El titulo y el orden son de los indices que se conocen; los que no, entran
# igual al final con la etiqueta que les pone la fuente. ESO es lo que hace que
# esto no haya que mantenerlo: en la primera corrida real aparecieron solos
# cuatro que no estaban declarados en ningun lado (Badlar, Bonos CER, Bonos
# Capitalizables y Bonos TAMAR).
CURVAS_PESOS = [
    ("Fijo",    "Tasa fija",    "LECAP y BONCAP: capitalizan una tasa fija en pesos."),
    ("CER",     "CER",          "LECER y BONCER: ajustan por inflación. Su rendimiento es "
                                "REAL: es lo que rinden POR ENCIMA de la inflación."),
    ("Tamar",   "TAMAR",        "Pagan la tasa mayorista de plazo fijo más un margen."),
    ("Badlar",  "BADLAR",       "Pagan la tasa de los plazos fijos mayoristas más un margen."),
    ("Dual",    "Duales",       "Pagan lo que resulte mayor entre dos patas: tasa fija o "
                                "TAMAR. El precio incluye esa opción."),
    ("DualCER", "Duales CER",   "Lo mismo, pero la otra pata ajusta por inflación."),
    ("USDL",    "Dólar linked", "Siguen al dólar oficial. Su rendimiento es EN DÓLARES: lo "
                                "que rinden por encima de la devaluación."),
]

# Familias que NO son de esta pestaña: los soberanos hard dollar tienen la suya
# con cronograma verificado, las ONs la suya, y los BOPREAL son otra cosa.
PREFIJOS_AJENOS = ("ONS", "BONO-USD-", "BOPREAL")

# Y las que terminan en -USD son la MISMA letra liquidada en dolares: la S30S6
# vale 115 y la SS6D 0,07. En una pestaña que se llama "Pesos" no van.
SUFIJO_EN_DOLARES = "-USD"


# Un papel que no opero hoy no tiene precio: tiene una PUNTA, que puede ser de
# hace dias. En el panel del 2/9/2026 habia 15 de 54 asi, y CUATRO DE LOS SEIS
# dolar linked estaban en ese grupo -- por eso esa curva salia con 0,8% y 10,8%
# mezclados sin nada en el medio: no era el mercado, eran cotizaciones rancias.
#
# Las dos condiciones son RELATIVAS a proposito, para que no quede un umbral
# que envejezca cuando cambien los volumenes del mercado:
#   1. que haya operado algo (volumen > 0), que no necesita umbral ninguno; y
#   2. que ese algo no sea una miga contra lo que opera el resto de SU curva.
# La segunda es la que saca al TY30P: negocio 0,01 contra una mediana de 7,72
# y el solo estiraba el eje de 300 a 1365 dias, aplastando los diez papeles
# que si se operan contra el margen izquierdo.
#
# No se los borra: se los marca. Siguen en la tabla, con su precio, y el
# grafico dice cuantos dejo afuera.
FRACCION_MEDIANA = 0.01

# La condicion relativa necesita una muestra para tener contra que comparar.
# Con dos papeles la "mediana" ES el mas grande y el otro queda afuera por
# nada. Debajo de esto se aplica solo la primera condicion, que no necesita
# muestra: opero o no opero.
MINIMO_PARA_RELATIVO = 5


def marcar_operados(filas):
    """
    Marca cada fila con `opero`: si su precio es de una rueda de verdad o es
    una punta vieja. Si la fuente no manda volumen para NINGUNA fila de la
    curva, no hay con que juzgar y pasan todas -- callarse media curva por un
    campo que no vino seria peor que el problema que esto arregla.
    """
    vols = sorted(f["volumen"] for f in filas
                  if isinstance(f.get("volumen"), (int, float)))
    if not vols:
        for f in filas:
            f["opero"] = True
        return filas
    piso = (vols[len(vols) // 2] * FRACCION_MEDIANA
            if len(vols) >= MINIMO_PARA_RELATIVO else 0)
    for f in filas:
        v = f.get("volumen")
        f["opero"] = bool(isinstance(v, (int, float)) and v > 0 and v >= piso)
    return filas


def _es_pata_sintetica(tk, familia):
    """
    Las patas sueltas de un dual (TXMJ8_CER, TTS26_CAP, BPOA8_PUT) no son
    especies que se puedan comprar: son la descomposicion que hace bonistas
    para valuar la opcion. Vienen con precio 0 o con TIR absurda -- el
    TTS26_CAP daba -95% -- y en una tabla se leen como oportunidades que no
    existen. La fuente las marca de dos formas y se filtran las dos: el ticker
    lleva guion bajo y la familia termina en -LEG.
    """
    return "_" in str(tk or "") or str(familia or "").endswith("-LEG")


def _ajena(familia):
    f = str(familia or "")
    return (f.endswith(SUFIJO_EN_DOLARES)
            or any(f == p or f.startswith(p) for p in PREFIJOS_AJENOS))


def armar_pesos(crudo, hoy=None):
    """
    Una curva por indice, con lo que este cotizando hoy. Se descarta lo que no
    tiene precio o no tiene rendimiento: una fila con todo en cero no dice nada
    y ensucia la curva.
    """
    hoy = hoy or fecha_de_la_fuente(crudo)
    conocidos = {k: (t, n) for k, t, n in CURVAS_PESOS}
    etiquetas, por_indice = {}, {}
    for f in crudo:
        fam, ind = f.get("bond_family"), f.get("index")
        tk = f.get("ticker") or f.get("bond_name")
        if not tk or _ajena(fam) or _es_pata_sintetica(tk, fam):
            continue
        if not f.get("last_price") or not f.get("tir"):
            continue
        # Sin indice no hay curva a la que pertenecer. Es raro, pero un papel
        # suelto no puede hacer que reviente todo el armado.
        if not ind:
            continue
        etiquetas.setdefault(ind, f.get("bond_family_label") or ind)
        papeles = por_indice.setdefault(ind, {})
        anterior = papeles.get(tk)
        if anterior and (ORDEN_PLAZO.get(anterior.get("settlement"), 9)
                         <= ORDEN_PLAZO.get(f.get("settlement"), 9)):
            continue
        papeles[tk] = f

    def redondo(v, dec):
        return round(v, dec) if isinstance(v, (int, float)) else None

    # Primero los conocidos en su orden; despues los que aparecieron solos.
    orden = [k for k, _, _ in CURVAS_PESOS if k in por_indice]
    orden += sorted((k for k in por_indice if k not in conocidos), key=str)

    salida = []
    for ind in orden:
        titulo, nota = conocidos.get(ind, (etiquetas.get(ind, ind), ""))
        filas = []
        for tk, f in por_indice[ind].items():
            vto, dias = vencimiento_y_dias(f, hoy)
            # Un papel que ya vencio no tiene nada que hacer en una curva. Se
            # mide contra la LIQUIDACION: uno que vence manana ya no se puede
            # comprar hoy a 24hs, porque recien se recibe cuando ya vencio.
            if (dias or 0) <= 0:
                continue
            filas.append({
                "t": tk,
                "vto": vto or f.get("end_date"),
                "dias": dias,
                "pago": proximo_pago(f, hoy),
                # Cuanto se movio hoy. Esta en todas las tablas del informe de
                # referencia y no estaba en ninguna de las nuestras. Es
                # `day_difference`, ya en tanto por uno: (ultimo - cierre
                # anterior) / cierre anterior.
                "var": redondo(f.get("day_difference"), 6),
                "precio": round(float(f["last_price"]), 3),
                "tir": redondo(f.get("tir"), 6),
                "tna": redondo(f.get("tna"), 6),
                # `mtir` es la efectiva MENSUAL: la TEM con la que se mira este
                # mercado. No se recalcula, se pasa.
                "tem": redondo(f.get("mtir"), 6),
                "duration": redondo(f.get("modified_duration"), 3),
                "paridad": redondo(f.get("parity"), 4),
                "volumen": redondo(f.get("volume"), 2),
                "resumen": f.get("short_description") or "",
            })
        if not filas:
            continue
        filas.sort(key=lambda x: (x["dias"] or 0, x["t"]))
        marcar_operados(filas)
        salida.append({"clave": str(ind), "titulo": titulo, "nota": nota,
                       "filas": filas,
                       "operados": sum(1 for f in filas if f["opero"])})
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
    ap.add_argument("--cache-ons", default="",
                    help="archivo donde guardar el panel de ONs entre corridas")
    ap.add_argument("--ons-minutos", type=int, default=30,
                    help="cuantos minutos vale el cache de ONs")
    args = ap.parse_args()

    print(f"[1/4] Bajando {FUENTE}")
    try:
        crudo = bajar(FUENTE)
    except Exception as e:
        sys.exit(f"[X] No pude bajar los bonos: {e}")
    print(f"      {len(crudo)} especies en el panel")

    hoy_real = date.today()
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

    # Las ONs van aparte y NO son motivo para no publicar: si bonistas no
    # contesta, los soberanos igual salen. Una seccion menos es mejor que la
    # pantalla entera vacia, y la renta fija no puede tirar abajo las acciones.
    # Un solo pedido a bonistas alcanza para las ONs Y para las curvas en
    # pesos: es el mismo panel. Bajarlo dos veces seria castigar a la fuente
    # por como esta organizado este programa.
    print(f"[2/4] Bajando {FUENTE_ONS}")
    ons, emis, pesos = [], [], []
    try:
        panel = bajar_con_cache(FUENTE_ONS, args.cache_ons, args.ons_minutos)
        ons = armar_ons(panel)
        emis = emisores(ons)
        pesos = armar_pesos(panel)
        print(f"      {len(ons)} obligaciones negociables de {len(emis)} emisores")
        for c in pesos:
            print(f"      curva {c['titulo']:<14} {len(c['filas'])} papeles")
    except Exception as e:
        print(f"      [!] no pude bajar bonistas ({e}); esas secciones salen vacias")

    # Los futuros son otra fuente (A3) y otra caida posible: si no contestan,
    # todo lo demas sale igual.
    print(f"[3/4] Bajando futuros de {futuros.FUENTE}")
    futs, spot, spot_fuente = [], None, None
    try:
        ruedas = futuros.bajar_ruedas(hoy=hoy_real)
        valor, fecha_a3500 = futuros.a3500(hoy_real)
        futs, spot, spot_fuente = futuros.armar(
            ruedas, hoy_real, valor,
            f"A3500 del {fecha_a3500[:10]}" if valor else None)
        print(f"      {len(futs)} contratos vivos · spot {spot} ({spot_fuente})")
    except Exception as e:
        print(f"      [!] no pude bajar los futuros ({e}); la seccion sale vacia")

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
        "ons": ons,
        "emisores": emis,
        "pesos": pesos,
        "futuros": futs,
        "spot": spot,
        # De donde salio el spot. La pantalla lo dice: no es lo mismo el A3500
        # oficial que una aproximacion con el contrato mas corto.
        "spot_fuente": spot_fuente,
    }
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bonos.json").write_text(
        json.dumps(payload, separators=(",", ":"), allow_nan=False),
        encoding="utf-8")
    print(f"[4/4] Listo -> {out}/bonos.json")


if __name__ == "__main__":
    main()
