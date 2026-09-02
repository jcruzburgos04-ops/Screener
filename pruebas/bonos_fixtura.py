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
    print(f"      -> {salida.name}")


if __name__ == "__main__":
    main()
