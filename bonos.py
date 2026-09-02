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
from datetime import date, datetime, timezone
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


def armar_ons(crudo):
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

    return [{
        "t": tk,
        "emisor": f.get("emisor") or "—",
        "ley": "Nueva York" if f.get("bond_law") == "LNY" else "Argentina",
        "cable": f.get("bond_family") == "ONS-CABLE",
        "vto": f.get("end_date"),
        "emitido": f.get("start_date"),
        "dias": f.get("days_to_finish"),
        "precio": round(float(f["last_price"]), 2),
        "cupon": _tna(f),
        # Los tres de abajo los calcula bonistas, no este programa. La pantalla
        # lo dice en la tarjeta.
        "tir": redondo(f.get("tir"), 6),
        "duration": redondo(f.get("modified_duration"), 3),
        "paridad": redondo(f.get("parity"), 4),
        "resumen": f.get("short_description") or "",
    } for tk, f in sorted(por.items())]


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

# El agrupamiento va por `bond_family` y NO por `index`, y la diferencia
# importa: con `index` la letra en pesos S30S6 y su gemela en dolares SS6D
# caian las dos en "Fijo", y la curva quedaba con dos puntos al mismo plazo y
# rendimientos muy distintos (TO26 25,6% contra TO26D 46,5%). Son instrumentos
# distintos y la fuente ya los separa: LETRAS-FIJO contra LETRAS-FIJO-USD.
#
# El orden y el texto son de las familias que se conocen; las que no, entran
# igual al final con la etiqueta que les pone la fuente. ESO es lo que hace que
# esto no haya que mantenerlo: si mañana el Tesoro estrena una familia nueva,
# aparece sola con su nombre en vez de desaparecer en silencio.
CURVAS_PESOS = [
    ("LETRAS-FIJO",    "Tasa fija",    "LECAP y BONCAP: capitalizan una tasa fija en pesos."),
    ("LETRAS-CER",     "CER",          "Ajustan por inflación. Su rendimiento es REAL: es lo "
                                       "que rinden POR ENCIMA de la inflación."),
    ("TAMAR",          "TAMAR",        "Pagan la tasa mayorista de plazo fijo más un margen."),
    ("DUAL",           "Duales",       "Pagan lo que resulte mayor entre dos patas: tasa fija "
                                       "o TAMAR. El precio incluye esa opción."),
    ("DUAL-CER-TAMAR", "Duales CER",   "Lo mismo, pero la otra pata ajusta por inflación."),
    ("DOLAR-LINKED",   "Dólar linked", "Siguen al dólar oficial. Su rendimiento es EN DÓLARES: "
                                       "lo que rinden por encima de la devaluación."),
]

# Familias que NO son de esta pestaña: los soberanos hard dollar tienen la suya
# con cronograma verificado, las ONs la suya, y los BOPREAL son otra cosa.
PREFIJOS_AJENOS = ("ONS", "BONO-USD-", "BOPREAL")

# Y las que terminan en -USD son la MISMA letra liquidada en dolares: la S30S6
# y la SS6D son el mismo papel, con precio 115 y 0,07 respectivamente. En una
# pestaña que se llama "Pesos" no van, y mezclarlas ademas mete dos puntos al
# mismo plazo con rendimientos distintos. La fuente ya las separa por familia
# (LETRAS-FIJO contra LETRAS-FIJO-USD), asi que el corte es por el sufijo de la
# familia y no por una lista de tickers: se sigue manteniendo solo.
SUFIJO_EN_DOLARES = "-USD"


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


def armar_pesos(crudo):
    """
    Una curva por familia, con lo que este cotizando hoy. Se descarta lo que no
    tiene precio o no tiene rendimiento: una fila con todo en cero no dice nada
    y ensucia la curva.
    """
    conocidas = {k: (t, n) for k, t, n in CURVAS_PESOS}
    etiquetas, por_familia = {}, {}
    for f in crudo:
        fam = f.get("bond_family")
        tk = f.get("ticker") or f.get("bond_name")
        if not tk or _ajena(fam) or _es_pata_sintetica(tk, fam):
            continue
        if not f.get("last_price") or not f.get("tir"):
            continue
        etiquetas.setdefault(fam, f.get("bond_family_label") or fam)
        papeles = por_familia.setdefault(fam, {})
        anterior = papeles.get(tk)
        if anterior and (ORDEN_PLAZO.get(anterior.get("settlement"), 9)
                         <= ORDEN_PLAZO.get(f.get("settlement"), 9)):
            continue
        papeles[tk] = f

    def redondo(v, dec):
        return round(v, dec) if isinstance(v, (int, float)) else None

    # Primero las conocidas en su orden; despues las que aparecieron solas.
    orden = [k for k, _, _ in CURVAS_PESOS if k in por_familia]
    orden += sorted(k for k in por_familia if k not in conocidas)

    salida = []
    for fam in orden:
        titulo, nota = conocidas.get(fam, (etiquetas.get(fam, fam), ""))
        filas = []
        for tk, f in por_familia[fam].items():
            # Un papel que ya vencio no tiene nada que hacer en una curva.
            if (f.get("days_to_finish") or 0) <= 0:
                continue
            filas.append({
                "t": tk,
                "vto": f.get("end_date"),
                "dias": f.get("days_to_finish"),
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
        salida.append({"clave": fam, "titulo": titulo, "nota": nota, "filas": filas})
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
