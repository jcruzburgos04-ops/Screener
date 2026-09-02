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
    }
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
    print(f"      -> {salida.name}")


if __name__ == "__main__":
    main()
