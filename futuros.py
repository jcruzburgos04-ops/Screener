#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
FUTUROS DE DOLAR (A3 / Matba Rofex)
================================================================================

QUE ARMA
--------
La curva de futuros de dolar: cada contrato con su precio, su ajuste, los dias
que le quedan, la tasa directa hasta el vencimiento, la TNA y la TEM
equivalentes, el volumen y el interes abierto.

DE DONDE
--------
`apicem.matbarofex.com.ar/api/v2/closing-prices`, que es publico y no pide
clave. Verificado que el runner de Actions llega. data912 NO tiene futuros --
su openapi.json lista 16 endpoints y ninguno es de derivados -- y BYMA tampoco.

POR QUE ESTO NO HAY QUE MANTENERLO A MANO
-----------------------------------------
Es el pedido explicito del usuario: que no haya que venir a tocar codigo cada
vez que vence un contrato. Nada de lo de aca tiene una lista de vencimientos:

  - LOS CONTRATOS SALEN DE LA API. Si A3 lista un DLR/ENE28 nuevo, aparece
    solo; si el AGO26 vence, deja de venir y desaparece solo.
  - EL VENCIMIENTO SE DEDUCE DEL SIMBOLO. `DLR092026` es septiembre de 2026, y
    los DLR liquidan el ULTIMO DIA HABIL del mes. Eso se calcula, no se anota.
  - LOS VENCIDOS SE DESCARTAN SOLOS comparando contra la fecha de hoy.
  - LA RUEDA SE PIDE POR RANGO, no por fecha exacta: se piden los ultimos dias
    y se usa la mas nueva que haya de cada contrato. Asi da igual que sea
    feriado, sabado, o que la rueda de hoy todavia no haya cerrado.

EL SPOT, Y POR QUE IMPORTA
--------------------------
La tasa directa es `precio_futuro / spot - 1`, asi que sin spot no hay tasa.
Se usa el A3500 (mayorista) del BCRA, que es contra lo que liquidan estos
contratos. Si el BCRA no contesta se cae al contrato mas corto -- el que esta
por vencer converge al spot por definicion -- y el payload dice cual de las dos
cosas se uso, para que la pantalla no presente una estimacion como si fuera el
dato oficial.
================================================================================
"""

import json
import re
import ssl
import urllib.request
import urllib.error
from datetime import date, timedelta

FUENTE = "https://apicem.matbarofex.com.ar/api/v2/closing-prices"
# El tipo de cambio mayorista A3500, serie 5 de las monetarias del BCRA.
FUENTE_A3500 = "https://api.bcra.gob.ar/estadisticas/v3.0/monetarias/5"

CABECERA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
            "Accept": "application/json, text/plain, */*"}

# El BCRA usa un certificado que no siempre valida en el runner, y aca no hay
# nada secreto que proteger: es una serie publica de tipo de cambio.
_SIN_VERIFICAR = ssl.create_default_context()
_SIN_VERIFICAR.check_hostname = False
_SIN_VERIFICAR.verify_mode = ssl.CERT_NONE


def bajar(url, verificar=True):
    pedido = urllib.request.Request(url, headers=CABECERA)
    ctx = None if verificar else _SIN_VERIFICAR
    with urllib.request.urlopen(pedido, timeout=30, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def ultimo_habil(anio, mes):
    """
    El ultimo dia habil del mes, que es cuando liquidan los DLR.

    Habil = ni sabado ni domingo. NO contempla feriados: no hay calendario de
    feriados disponible sin otra fuente, y el error maximo es de un par de
    dias sobre plazos de decenas o cientos. Lo que importa que este bien es el
    ORDEN de los contratos y la magnitud del plazo, y eso no se mueve.
    """
    if mes == 12:
        d = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(anio, mes + 1, 1) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def vencimiento(simbolo):
    """
    `DLR092026` -> 30/9/2026. Devuelve None si el simbolo no tiene esa forma,
    para que un contrato con nomenclatura rara se saltee en vez de romper todo.
    """
    m = re.match(r"^[A-Z]+(\d{2})(\d{4})$", str(simbolo or "").strip().upper())
    if not m:
        return None
    mes, anio = int(m.group(1)), int(m.group(2))
    if not 1 <= mes <= 12:
        return None
    return ultimo_habil(anio, mes)


MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]


def etiqueta(simbolo, vto):
    """DLR092026 -> 'DLR/SEP26', que es como los nombra el mercado."""
    prefijo = re.match(r"^([A-Z]+)", str(simbolo or "").upper())
    p = prefijo.group(1) if prefijo else "DLR"
    return f"{p}/{MESES[vto.month - 1].upper()}{str(vto.year)[2:]}"


def bajar_ruedas(dias_atras=12, hoy=None):
    """
    Las ultimas ruedas, por rango. Se pide un rango y no una fecha porque la
    fecha exacta falla cualquier fin de semana, feriado o antes del cierre.
    Si el rango corto viene vacio se ensancha: en enero puede haber una semana
    larga sin ruedas.
    """
    hoy = hoy or date.today()
    for atras in (dias_atras, dias_atras * 3, dias_atras * 8):
        desde = (hoy - timedelta(days=atras)).isoformat()
        url = f"{FUENTE}?product=DLR&market=ROFX&from={desde}&to={hoy.isoformat()}"
        try:
            d = bajar(url)
        except Exception as e:
            print(f"      [!] futuros: {type(e).__name__} pidiendo {atras} dias")
            continue
        filas = d if isinstance(d, list) else (d.get("data") or [])
        if filas:
            print(f"      {len(filas)} ruedas en los ultimos {atras} dias")
            return filas
        print(f"      (sin ruedas en los ultimos {atras} dias, ensancho)")
    return []


def ultima_rueda(filas):
    """De cada contrato, la rueda mas nueva que haya."""
    por = {}
    for f in filas:
        s = f.get("symbol")
        if not s:
            continue
        if s not in por or str(f.get("dateTime") or "") > str(por[s].get("dateTime") or ""):
            por[s] = f
    return por


def a3500(hoy=None):
    """
    El mayorista del BCRA. Devuelve (valor, fecha) o (None, None): que no
    conteste no puede tirar abajo la seccion.
    """
    hoy = hoy or date.today()
    desde = (hoy - timedelta(days=15)).isoformat()
    for url in (f"{FUENTE_A3500}?desde={desde}&hasta={hoy.isoformat()}",
                FUENTE_A3500,
                # La otra API del BCRA, la de cotizaciones. Se prueban las dos
                # porque cual de las dos anda cambio en el pasado y no hay
                # motivo para casarse con una.
                "https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones"):
        try:
            d = bajar(url, verificar=False)
        except Exception:
            continue
        res = (d.get("results") if isinstance(d, dict) else None) or []
        mejor = None
        for x in res:
            if not isinstance(x, dict):
                continue
            f = x.get("fecha")
            v = x.get("valor")
            # La de cotizaciones anida: {fecha, detalle:[{codigoMoneda, tipoCotizacion}]}
            if v is None:
                for det in (x.get("detalle") or []):
                    if str(det.get("codigoMoneda", "")).upper() == "USD":
                        v = det.get("tipoCotizacion")
                        break
            # la serie puede venir en cualquier orden: se toma la fecha mas alta
            if f and isinstance(v, (int, float)) and v and (mejor is None or f > mejor[1]):
                mejor = (float(v), f)
        if mejor:
            return mejor
    return None, None


def _spot_implicito(vivos):
    """
    El spot deducido de las tasas que publica A3.

    Si un contrato vale P, vence en D dias y A3 dice que su tasa implicita es
    R, entonces el spot que uso A3 es `P / (1 + R/100 * D/365)`. Despejarlo de
    varios contratos y quedarse con la MEDIANA da un numero consistente con el
    mercado y robusto a un contrato mal cotizado.

    Esto reemplazo al "uso el contrato mas corto", que sonaba razonable y no lo
    era: el mas corto quedo en 1534,5 contra un A3500 de 1509,5, o sea 1,7%
    arriba, y ese 1,7% se le sumaba a la tasa directa de TODOS los contratos.

    Es una deduccion, no el dato oficial, y el payload lo dice.
    """
    cand = []
    for dias, v, s, f, precio in vivos:
        r = f.get("impliedRate")
        if dias > 0 and isinstance(r, (int, float)) and r:
            base = 1 + (r / 100.0) * dias / 365.0
            if base > 0:
                cand.append(precio / base)
    if len(cand) >= 3:
        cand.sort()
        return cand[len(cand) // 2], "deducido de las tasas de A3"
    # Ultimo recurso: el contrato mas corto converge al spot al vencimiento.
    return vivos[0][4], "contrato más corto (aproximado)"


def armar(crudo, hoy=None, spot=None, spot_fuente=None):
    """
    La curva de futuros. `spot` opcional: si no viene, se usa el contrato mas
    corto, que converge al spot por definicion.
    """
    hoy = hoy or date.today()
    por = ultima_rueda(crudo)

    vivos = []
    for s, f in por.items():
        v = vencimiento(s)
        if v is None:
            continue
        # Los vencidos se caen solos: no hay lista que mantener.
        dias = (v - hoy).days
        if dias < 0:
            continue
        precio = f.get("close") or f.get("settlement")
        if not precio:
            continue
        vivos.append((dias, v, s, f, float(precio)))
    vivos.sort()

    if spot is None and vivos:
        spot, spot_fuente = _spot_implicito(vivos)

    salida = []
    for dias, v, s, f, precio in vivos:
        fila = {
            "t": etiqueta(s, v),
            "simbolo": s,
            "vto": v.isoformat(),
            "dias": dias,
            "precio": round(precio, 2),
            "ajuste": round(float(f["settlement"]), 2) if f.get("settlement") else None,
            "var": round(float(f["change"]), 2) if f.get("change") is not None else None,
            "var_pct": (round(float(f["changePercent"]), 4)
                        if f.get("changePercent") is not None else None),
            "volumen": f.get("volume"),
            "ia": f.get("openInterest"),
            "ia_var": f.get("openInterestChange"),
            # La que publica A3, no una cuenta propia. Se muestra atribuida.
            "implicita": (round(float(f["impliedRate"]), 4)
                          if isinstance(f.get("impliedRate"), (int, float)) else None),
            "rueda": str(f.get("dateTime") or "")[:10],
        }
        # Tasa directa hasta el vencimiento, y sus equivalentes anual y mensual.
        # El contrato que vence hoy no tiene tasa: dividir por cero dias no da
        # infinito, da nada.
        if spot and dias > 0:
            directa = precio / spot - 1
            fila["directa"] = round(directa, 6)
            fila["tna"] = round(directa * 365.0 / dias, 6)
            # TEM: la mensual equivalente, capitalizando. NO es directa/meses.
            fila["tem"] = round((1 + directa) ** (30.0 / dias) - 1, 6)
        salida.append(fila)

    return salida, (round(spot, 2) if spot else None), spot_fuente


def main():
    hoy = date.today()
    print(f"[1/2] Bajando futuros de {FUENTE}")
    crudo = bajar_ruedas(hoy=hoy)
    if not crudo:
        raise SystemExit("[X] No vino ninguna rueda de futuros")
    valor, fecha = a3500(hoy)
    if valor:
        print(f"      A3500 del BCRA: {valor:,.2f} ({fecha[:10]})")
    else:
        print("      (el BCRA no contesto; uso el contrato mas corto como spot)")
    filas, spot, fuente = armar(crudo, hoy, valor, f"A3500 del {fecha[:10]}" if valor else None)
    print(f"[2/2] {len(filas)} contratos vivos · spot {spot} ({fuente})\n")
    print(f"{'contrato':<12}{'vto':<12}{'dias':>5}{'precio':>10}{'ajuste':>10}"
          f"{'var%':>8}{'directa':>9}{'TNA':>8}{'TEM':>7}{'A3 impl':>9}"
          f"{'volumen':>10}{'int.ab.':>12}")
    for f in filas:
        print(f"{f['t']:<12}{f['vto']:<12}{f['dias']:>5}{f['precio']:>10,.2f}"
              f"{(f['ajuste'] or 0):>10,.2f}{(f['var_pct'] or 0):>8.2f}"
              f"{(f.get('directa') or 0)*100:>8.1f}%{(f.get('tna') or 0)*100:>7.2f}%"
              f"{(f.get('tem') or 0)*100:>6.2f}%{(f['implicita'] or 0):>8.2f}%"
              f"{(f['volumen'] or 0):>10,.0f}{(f['ia'] or 0):>12,.0f}")


if __name__ == "__main__":
    main()
