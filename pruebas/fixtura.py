#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
DATOS DE PRUEBA  ·  vive acá adentro y NUNCA sale de acá
================================================================================

Las series sintéticas están en pruebas/ y no en el proyecto a propósito. Antes
había un `--demo` en generar_sitio.py y en generar_html.py, y eso significaba
que con una bandera mal puesta se podía publicar un sitio con precios
inventados que parecían de verdad: velas, variaciones, cruces del ASH, todo
creíble y todo falso. Ese riesgo no vale la comodidad.

El screener, hoy, o muestra precios de Yahoo o no muestra nada.

Esto arma pruebas/tmp/sitio con la misma forma que el sitio real, para que las
pruebas de interfaz tengan sobre qué correr:

    python fixtura.py            # arma pruebas/tmp/sitio
================================================================================
"""

import json
import os
import sys

import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

from generar_html import armar_payload          # noqa: E402
from screener import cargar_mapa_cedears, leer_universo   # noqa: E402

SECTORES = ['Technology', 'Financial Services', 'Energy', 'Healthcare',
            'Basic Materials', 'Utilities']
INDUSTRIAS = ['Semiconductors', 'Software', 'Banks', 'Oil & Gas',
              'Drug Manufacturers', 'Steel', 'Gold', 'Utilities - Regulated',
              'Auto Manufacturers', 'Aerospace', 'REIT', 'Airlines']


def series_falsas(tickers, n=760, semilla=7):
    """Caminatas aleatorias. No se parecen al mercado y no tienen por qué."""
    rng = np.random.default_rng(semilla)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    out = {}
    for k, t in enumerate(tickers):
        r = rng.normal(rng.normal(0.0004, 0.0004), rng.uniform(0.012, 0.03), n)
        c = 20 * np.exp(np.cumsum(r)) * (1 + k % 5)
        rango = c * rng.uniform(0.005, 0.02, n)
        out[t] = pd.DataFrame({"Open": c + rng.normal(0, rango / 3),
                               "High": c + rango, "Low": c - rango, "Close": c,
                               "Volume": rng.lognormal(13.5, 0.8, n).round()},
                              index=idx)
    return out


def armar(destino=None, barras=400, atrasar=True):
    destino = destino or os.path.join(AQUI, 'tmp', 'sitio')
    os.makedirs(destino, exist_ok=True)

    # las rutas van absolutas: la fixtura se corre desde pruebas/, no desde la raiz
    uni = leer_universo(os.path.join(RAIZ, 'universo.csv'),
                        cargar_mapa_cedears(os.path.join(RAIZ, 'cedears.csv')))
    tickers = uni['ticker'].tolist()
    precios = series_falsas(tickers + ['SPY'])

    # atrasos artificiales, para probar la marca ⚠ y el filtro
    if atrasar:
        for i, t in enumerate(tickers):
            if i % 17 == 0:
                precios[t] = precios[t].iloc[:-(1 + i % 3)]

    meta = {t: {'nombre': f'Empresa {t} S.A.',
                'sector': SECTORES[i % len(SECTORES)],
                'industria': INDUSTRIAS[i % len(INDUSTRIAS)],
                'pais': 'United States',
                'float_shares': 1e8 + i * 1e6, 'mcap': 5e9 + i * 1e7}
            for i, t in enumerate(precios)}

    payload = armar_payload(precios, meta, uni, barras)
    payload['faltantes'] = []

    plantilla = open(os.path.join(RAIZ, 'plantilla.html'), encoding='utf-8').read()
    marca = '/*__DATOS__*/ {fecha:"", simbolos:[]}'
    assert marca in plantilla, 'no encontre el marcador de datos en plantilla.html'
    with open(os.path.join(destino, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(plantilla.replace(marca, '{fecha:"",simbolos:[]}'))
    with open(os.path.join(destino, 'datos.json'), 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, separators=(',', ':'), allow_nan=False)
    # el archivo suelto, para probar el tercer modo de uso
    with open(os.path.join(destino, '..', 'screener.html'), 'w', encoding='utf-8') as fh:
        fh.write(plantilla.replace(marca, json.dumps(payload, separators=(',', ':'),
                                                     allow_nan=False)))

    print(f"fixtura -> {destino}  ({len(payload['simbolos'])} simbolos, "
          f"{payload['atrasados']} atrasados)")
    return payload


if __name__ == '__main__':
    armar(sys.argv[1] if len(sys.argv) > 1 else None)
