#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arma pruebas/bonos_fixtura.json pasando un panel SINTETICO por el armar() de
bonos.py de verdad.

Por que asi y no escribiendo el JSON a mano: la fixtura queda atada a la forma
real del payload. Cuando bonos.py agrega un campo (paso con `flujo`), la
fixtura lo trae sola y la prueba de interfaz lo ve. Un JSON escrito a mano se
queda viejo en silencio, que es exactamente como la vista de bonos termino
mostrando menos de lo que el payload traia.

Los PRECIOS son sinteticos, como todo lo de esta carpeta. Los CRONOGRAMAS no:
son los mismos de bonos_cronograma.csv, porque lo que se prueba es que la
cuenta y la pantalla anden, y para eso el cronograma tiene que ser el de verdad.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bonos  # noqa: E402

# Un panel como el que devuelve data912: cada bono en pesos, en D (MEP) y en C
# (cable). Los precios salen de una rueda real observada, redondeados.
PANEL = {
    "AL29": (82750, 54.14, 52.08, 0.37),
    "AL30": (85280, 55.64, 53.47, 0.32),
    "AL35": (115900, 75.76, 72.60, -0.11),
    "AE38": (120180, 78.54, 75.50, 0.13),
    "AL41": (107700, 70.41, 67.30, 0.44),
    "GD29": (85600, 56.00, 53.56, -0.10),
    "GD30": (88870, 57.94, 55.90, 0.20),
    "GD35": (121300, 79.28, 76.10, 0.05),
    "GD38": (127800, 83.53, 80.20, 0.18),
    "GD41": (114200, 74.65, 71.40, 0.22),
    "GD46": (112400, 73.46, 70.30, -0.08),
}


def panel():
    filas = []
    for tk, (pesos, mep, cable, var) in PANEL.items():
        filas.append({"symbol": tk, "c": pesos, "pct_change": var, "v": 1000})
        filas.append({"symbol": tk + "D", "c": mep, "pct_change": var, "v": 1000})
        filas.append({"symbol": tk + "C", "c": cable, "pct_change": var, "v": 1000})
    return filas


# Un puñado de ONs con la forma exacta que devuelve bonistas: varias del mismo
# emisor, la misma especie repetida en dos plazos de liquidacion (que armar_ons
# tiene que deduplicar), una step-up sin tasa unica y una sin precio.
CRUDO_ONS = [
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "YMCJD", "emisor": "YPF S.A.",
     "end_date": "2031-01-15", "start_date": "2024-01-15", "days_to_finish": 1596,
     "last_price": 101.5, "tir": 0.0812, "modified_duration": 3.55, "parity": 1.012,
     "settlement": "24hs", "short_description": "Bono USD Ley Arg. - 8.50% - vto. 01/2031",
     "description": "**Cupón:**\n- Tasa nominal anual (TNA): 8.50%"},
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "YMCJD", "emisor": "YPF S.A.",
     "end_date": "2031-01-15", "start_date": "2024-01-15", "days_to_finish": 1596,
     "last_price": 99.9, "tir": 0.09, "modified_duration": 3.55, "parity": 1.0,
     "settlement": "CI", "short_description": "x", "description": "x"},
    {"bond_family": "ONS-CABLE", "bond_law": "LNY", "ticker": "YMCIC", "emisor": "YPF S.A.",
     "end_date": "2029-06-30", "start_date": "2021-02-12", "days_to_finish": 1034,
     "last_price": 89.95, "tir": 0.0677, "modified_duration": 1.43, "parity": 1.033,
     "settlement": "24hs", "short_description": "Bono USD Ley NY - vto. 06/2029",
     "description": "**Cupón:**\nCupones con tasas crecientes:\n"
                    "  - Cupones 1-3: 2.50% TNA\n  - Cupones 4-17: 9.00% TNA"},
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "PN36D",
     "emisor": "Pan American Energy", "end_date": "2031-11-13",
     "start_date": "2024-11-13", "days_to_finish": 1898, "last_price": 109.3,
     "tir": 0.0574, "modified_duration": 4.24, "parity": 1.069, "settlement": "24hs",
     "short_description": "Bono USD Ley Arg. - 7.25% - vto. 11/2031",
     "description": "**Cupón:**\n- Tasa nominal anual (TNA): 7.25%"},
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "TLC5D", "emisor": "Telecom",
     "end_date": "2028-03-01", "start_date": "2023-03-01", "days_to_finish": 546,
     "last_price": 104.0, "tir": 0.0721, "modified_duration": 1.38, "parity": 1.03,
     "settlement": "24hs", "short_description": "Bono USD Ley Arg. - 9.50% - vto. 03/2028",
     "description": "**Cupón:**\n- Tasa nominal anual (TNA): 9.50%"},
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "XXXXD", "emisor": "Fantasma",
     "end_date": "2030-01-01", "last_price": None, "settlement": "24hs"},
    {"bond_family": "BONO-USD-LPA", "bond_law": "LA", "ticker": "AL30",
     "emisor": "Argentino", "end_date": "2030-07-09", "last_price": 55.64,
     "settlement": "24hs"},
]


# Instrumentos en pesos con la forma de bonistas. Incluye a proposito:
#   - una pata sintetica de un dual (TTS26_CAP) con TIR absurda, que armar_pesos
#     tiene que descartar: no es una especie comprable;
#   - un papel YA VENCIDO (dias negativos), que se tiene que caer solo;
#   - uno sin precio, que tampoco puede entrar.
CRUDO_PESOS = [
    {"ticker": "S30S6", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2026-09-30", "days_to_finish": 27,
     "last_price": 115.455, "tir": 0.2731, "tna": 0.2439, "mtir": 0.0203,
     "modified_duration": 0.058, "parity": 1.0031, "volume": 33385.4,
     "settlement": "24hs", "short_description": "Bono Tasa Fija ARS - vto. 09/2026"},
    {"ticker": "S30S6", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2026-09-30", "days_to_finish": 27,
     "last_price": 114.0, "tir": 0.28, "tna": 0.25, "mtir": 0.021,
     "modified_duration": 0.058, "parity": 1.0, "volume": 10.0,
     "settlement": "CI", "short_description": "x"},
    {"ticker": "T30A7", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2027-04-30", "days_to_finish": 240,
     "last_price": 132.99, "tir": 0.2913, "tna": 0.2784, "mtir": 0.0212,
     "modified_duration": 0.62, "parity": 1.0, "volume": 157.34,
     "settlement": "24hs", "short_description": "Bono Tasa Fija ARS - vto. 04/2027"},
    {"ticker": "TZXM9", "bond_family": "LETRAS-CER", "index": "CER", "end_date": "2029-03-28", "days_to_finish": 937,
     "last_price": 89.89, "tir": 0.0978, "tna": 0.0937, "mtir": 0.0078,
     "modified_duration": 2.336, "parity": 0.7872, "volume": 14.3,
     "settlement": "24hs", "short_description": "Bono CER - vto. 03/2029"},
    {"ticker": "TZV27", "bond_family": "DOLAR-LINKED", "index": "USDL", "end_date": "2027-06-30", "days_to_finish": 300,
     "last_price": 147790, "tir": 0.026, "tna": 0.0257, "mtir": 0.0021,
     "modified_duration": 0.801, "parity": 0.979, "volume": 0.078,
     "settlement": "24hs", "short_description": "Bono DL (sin cupón) - vto. 06/2027"},
    {"ticker": "TTS26", "bond_family": "DUAL", "index": "Dual", "end_date": "2026-09-15", "days_to_finish": 12,
     "last_price": 168.8, "tir": 0.3123, "tna": 0.2749, "mtir": 0.0229,
     "modified_duration": 0.025, "parity": 0.9996, "volume": 10568.7,
     "settlement": "24hs", "short_description": "Bono Dual - vto. 09/2026"},
    # pata sintetica: TIR de -95%, no es comprable
    {"ticker": "TTS26_CAP", "bond_family": "TAMAR-FIJA", "index": "Fijo", "end_date": "2026-09-15", "days_to_finish": 12,
     "last_price": 168.8, "tir": -0.958, "tna": -2.78, "mtir": -0.232,
     "modified_duration": 0.782, "parity": 1.118, "settlement": "CI"},
    # ya vencido
    {"ticker": "VIEJO", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2026-08-01", "days_to_finish": -30,
     "last_price": 100.0, "tir": 0.3, "tna": 0.28, "mtir": 0.022, "settlement": "24hs"},
    # sin precio
    {"ticker": "SINPX", "bond_family": "LETRAS-CER", "index": "CER", "end_date": "2028-01-01", "days_to_finish": 480,
     "last_price": 0, "tir": 0, "settlement": "24hs"},
]

# Ruedas de futuros como las devuelve A3. Incluye un contrato YA VENCIDO, que
# se tiene que caer solo, y dos ruedas del mismo contrato para verificar que se
# usa la mas nueva.
CRUDO_FUT = [
    {"symbol": "DLR092026", "dateTime": "2026-09-01T00:00:00.000Z", "close": 1500.0,
     "settlement": 1500.0, "change": -1.0, "changePercent": -0.07, "volume": 100,
     "openInterest": 900000, "openInterestChange": -1000, "impliedRate": 22.0},
    {"symbol": "DLR092026", "dateTime": "2026-09-02T00:00:00.000Z", "close": 1509.0,
     "settlement": 1509.5, "change": -2.5, "changePercent": -0.17, "volume": 390944,
     "openInterest": 997504, "openInterestChange": -203080, "impliedRate": 22.5},
    {"symbol": "DLR102026", "dateTime": "2026-09-02T00:00:00.000Z", "close": 1536.5,
     "settlement": 1536.5, "change": -1.5, "changePercent": -0.10, "volume": 146967,
     "openInterest": 1906733, "openInterestChange": 364335, "impliedRate": 22.58},
    {"symbol": "DLR122026", "dateTime": "2026-09-02T00:00:00.000Z", "close": 1619.5,
     "settlement": 1619.5, "change": -2.5, "changePercent": -0.15, "volume": 6462,
     "openInterest": 318356, "openInterestChange": 215, "impliedRate": 22.20},
    {"symbol": "DLR062027", "dateTime": "2026-09-02T00:00:00.000Z", "close": 1805.0,
     "settlement": 1802.0, "change": -2.0, "changePercent": -0.11, "volume": 0,
     "openInterest": 4566, "openInterestChange": 419, "impliedRate": 23.68},
    # vencido: se cae solo
    {"symbol": "DLR012026", "dateTime": "2026-09-02T00:00:00.000Z", "close": 1200.0,
     "settlement": 1200.0, "volume": 0, "openInterest": 0},
    # simbolo con forma rara: se saltea en vez de romper
    {"symbol": "RARO", "dateTime": "2026-09-02T00:00:00.000Z", "close": 1.0},
]


def main():
    raiz = Path(__file__).resolve().parent.parent
    cron = bonos.leer_cronogramas(raiz / "bonos_cronograma.csv")
    # Fecha FIJA: si se usara date.today() la fixtura cambiaria sola cada dia y
    # las pruebas que miran una TIR concreta empezarian a fallar por si solas.
    # Ya paso con yahoo.js, que dependia de la fecha de armado.
    hoy = date(2026, 9, 1)
    filas = bonos.armar(panel(), cron, hoy)
    payload = {
        "fecha": "2026-09-01 23:51", "ts": 1788306660,
        "bonos": filas,
        "canje": bonos.canje_de_leyes(filas),
        "con_tir": sum(1 for f in filas if f.get("tir") is not None),
        "verificados": sum(1 for f in filas if f.get("verificado")),
        "ons": bonos.armar_ons(CRUDO_ONS),
        "emisores": bonos.emisores(bonos.armar_ons(CRUDO_ONS)),
        "pesos": bonos.armar_pesos(CRUDO_PESOS),
    }
    import futuros
    # Sin spot explicito: se deduce de las implicitas de A3, que es lo que pasa
    # en produccion cuando el BCRA no contesta. Asi la prueba ve el aviso.
    fut, spot, fuente = futuros.armar(CRUDO_FUT, hoy)
    payload["futuros"] = fut
    payload["spot"] = spot
    payload["spot_fuente"] = fuente
    salida = Path(__file__).resolve().parent / "bonos_fixtura.json"
    salida.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False),
                      encoding="utf-8")
    con = [f["t"] for f in filas if f.get("tir") is not None]
    print(f"      {len(filas)} bonos · con TIR: {' '.join(con) or 'ninguno'}")
    for f in filas:
        if f.get("tir") is not None:
            print(f"      {f['t']:<5} TIR {f['tir']*100:6.2f}%  TNA {f['tna']*100:6.2f}%  "
                  f"paridad {f['paridad']*100:5.1f}%  dur {f['duration']:.2f}  "
                  f"DV01 {f['dv01']:.4f}  vivo {f['vivo']:.0f}  pagos {f['pagos']}")
    print(f"      {len(payload['ons'])} ONs de {len(payload['emisores'])} emisores")
    print(f"      {sum(len(c['filas']) for c in payload['pesos'])} papeles en pesos "
          f"en {len(payload['pesos'])} curvas · {len(payload['futuros'])} futuros")
    print(f"      -> {salida.name}")


if __name__ == "__main__":
    main()
