#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
LA MATEMATICA DE RENTA FIJA Y LOS CRONOGRAMAS
===============================================================================
Se prueba en dos niveles, y la diferencia importa:

  1. LA CUENTA, contra casos analiticos donde la respuesta se conoce de
     antemano y no depende de ningun dato de mercado: un bono a la par rinde su
     cupon, un cupon cero rinde lo que dice la formula, la duration de Macaulay
     de un cupon cero es su plazo. Si esto falla, esta mal el programa.

  2. LOS CRONOGRAMAS, contra la pantalla de referencia del usuario (1/9/2026) y
     contra el importe del proximo cupon que publica bonistas. Si esto falla,
     esta mal bonos_cronograma.csv, no el programa.

Se separan a proposito: cuando el AL30 daba 8,91% en vez de 8,65% CON LA
PARIDAD Y LA DURATION YA COINCIDIENDO, eso solo ya decia que el error estaba en
el importe del cupon y no en las fechas ni en la formula.
===============================================================================
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bonos  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
fallas = 0


def ok(nombre, cond, extra=None):
    global fallas
    if cond:
        print(f"  ok     {nombre}")
    else:
        fallas += 1
        print(f"  FALLA  {nombre}" + (f"  -> {extra}" if extra is not None else ""))


def cerca(a, b, tol):
    return a == a and b == b and abs(a - b) <= tol


print("== la cuenta, contra casos con respuesta conocida ==")
hoy = date(2026, 1, 1)
cero = [{"fecha": date(2027, 1, 1), "cupon_anual": 0.0, "amortiza": 100.0}]
flujo, res = bonos.flujos(cero, hoy)
ok("un cupon cero a un año rinde lo que dice la formula",
   cerca(bonos.tir(100 / 1.10, flujo, hoy), 0.10, 1e-4), bonos.tir(100 / 1.10, flujo, hoy))
ok("el residual de un bullet es 100", res == 100.0, res)
ok("y paga una sola vez", len(flujo) == 1, len(flujo))

mac, mod, dv = bonos.duration(100 / 1.10, flujo, hoy, 0.10)
ok("la duration de Macaulay de un cupon cero es su plazo", cerca(mac, 1.0, 1e-3), mac)
ok("la modificada es esa sobre (1+y)", cerca(mod, mac / 1.10, 1e-9), mod)
ok("el DV01 es la modificada por el precio por un punto basico",
   cerca(dv, mod * (100 / 1.10) * 1e-4, 1e-12), dv)

par, a, m = [], 2026, 7
for i in range(10):
    par.append({"fecha": date(a, m, 1), "cupon_anual": 8.0,
                "amortiza": 100.0 if i == 9 else 0.0})
    a, m = (a + 1, 1) if m == 7 else (a, 7)
flujo, res = bonos.flujos(par, date(2026, 1, 1))
y = bonos.tir(100.0, flujo, date(2026, 1, 1))
ok("un bono a la par rinde su cupon (efectiva anual)", cerca(y, 1.04 ** 2 - 1, 2e-3), y)

# El residual es lo que queda por amortizar, no "100 menos lo ya pagado". Ese
# error daba 92 cuando lo que faltaba sumaba 60.
mitad = [{"fecha": date(2025, 1, 1), "cupon_anual": 5.0, "amortiza": 40.0},
         {"fecha": date(2027, 1, 1), "cupon_anual": 5.0, "amortiza": 60.0}]
flujo, res = bonos.flujos(mitad, date(2026, 1, 1))
ok("el residual son las amortizaciones que FALTAN", res == 60.0, res)
ok("la renta se calcula sobre el residual y no sobre el nominal",
   cerca(flujo[0][1], 5.0 / 2 * 60 / 100 + 60.0, 1e-9), flujo[0][1])

vacio, res0 = bonos.flujos(mitad, date(2030, 1, 1))
ok("un bono ya vencido no tiene flujo", vacio == [] and res0 == 0, (vacio, res0))
nan = bonos.tir(50, vacio, date(2030, 1, 1))
ok("y su TIR es NaN, no un numero cualquiera", nan != nan, nan)

print("\n== los cronogramas: forma ==")
cron = bonos.leer_cronogramas(RAIZ / "bonos_cronograma.csv")
ok("estan los once soberanos", len(cron) == 11, sorted(cron))
ok("todos marcados como verificados",
   all(all(p["verificado"] for p in v) for v in cron.values()),
   [k for k, v in cron.items() if not all(p["verificado"] for p in v)])
for b, pagos in sorted(cron.items()):
    ok(f"{b}: las amortizaciones suman 100",
       cerca(sum(p["amortiza"] for p in pagos), 100.0, 1e-4),
       sum(p["amortiza"] for p in pagos))

HOY = date(2026, 9, 1)
# (bono, precio MEP, TIR%, paridad%, duration, DV01) -- pantalla de referencia
REFERENCIA = [
    ("AL29", 54.14,  7.95, 90.1, 1.43, 0.0077),
    ("AL30", 55.64,  8.65, 86.8, 1.83, 0.0102),
    ("AL35", 75.76, 10.32, 75.5, 4.95, 0.0375),
    ("AE38", 78.54, 10.58, 78.0, 4.18, 0.0328),
    ("AL41", 70.41, 10.44, 70.0, 5.34, 0.0376),
]
print("\n== los cronogramas: contra la pantalla de referencia ==")
for b, mep, rtir, rpar, rdur, rdv in REFERENCIA:
    pagos = cron[b]
    flujo, res = bonos.flujos(pagos, HOY)
    y = bonos.tir(mep, flujo, HOY)
    mac, mod, dv = bonos.duration(mep, flujo, HOY, y)
    vt = bonos.valor_tecnico(pagos, HOY, res)
    parid = mep / vt * 100
    # A la DURATION se le exige mas (dos centesimas) porque es lo que el
    # CRONOGRAMA decide. La TIR y la paridad arrastran el redondeo del precio
    # de referencia, que se reconstruyo de un DV01 de cuatro decimales.
    ok(f"{b}: duration {mod:.2f} (ref {rdur:.2f})", cerca(mod, rdur, 0.02))
    ok(f"{b}: TIR {y*100:.2f}% (ref {rtir:.2f}%)", cerca(y * 100, rtir, 0.06))
    ok(f"{b}: paridad {parid:.1f}% (ref {rpar:.1f}%)", cerca(parid, rpar, 0.3))
    ok(f"{b}: DV01 {dv:.4f} (ref {rdv:.4f})", cerca(dv, rdv, 0.0002))

print("\n== los cronogramas: el importe del proximo cupon, contra bonistas ==")
# `coupon` de bonistas NO es la tasa: es la plata del proximo cupon por cada
# 100 de nominal original. Ata la tasa Y el residual a la vez, y es lo que fijo
# el cronograma del GD46, que no tenia otra referencia.
BONISTAS = {"AL29": 0.30, "AL30": 0.24, "AL35": 2.0625, "AE38": 2.50,
            "AL41": 1.75, "GD29": 0.30, "GD30": 0.24, "GD35": 2.0625,
            "GD38": 2.50, "GD41": 1.75, "GD46": 1.875}
for b, esperado in sorted(BONISTAS.items()):
    d = bonos.desglose(cron[b], HOY)[0]
    ok(f"{b}: proximo cupon {d['renta']:.4f} (bonistas {esperado})",
       cerca(d["renta"], esperado, 0.005), d["renta"])

print("\n== el desglose y el flujo dicen lo mismo ==")
for b, pagos in sorted(cron.items()):
    flujo, res = bonos.flujos(pagos, HOY)
    det = bonos.desglose(pagos, HOY)
    ok(f"{b}: misma cantidad de pagos e importes",
       len(flujo) == len(det) and
       all(cerca(f[1], x["total"], 5e-4) for f, x in zip(flujo, det)))
    ok(f"{b}: el ultimo pago deja el bono en cero",
       cerca(det[-1]["vivo"], 0.0, 1e-4), det[-1]["vivo"])

print("\n== una linea rota del CSV se saltea, no rompe el archivo ==")
with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
    f.write("# comentario\nZZ99,2027-01-09,1.0,10,1\nZZ99,ROTA\n"
            "ZZ99,fecha-mala,1.0,10,1\nZZ99,2027-07-09,1.0,10,1\n")
    ruta = f.name
c = bonos.leer_cronogramas(ruta)
ok("se quedan las lineas buenas", len(c.get("ZZ99", [])) == 2, len(c.get("ZZ99", [])))
ok("un archivo que no existe devuelve vacio, no explota",
   bonos.leer_cronogramas("/no/existe.csv") == {})

print(f"\nFALLAS: {fallas}" if fallas else "\nRENTA FIJA OK")
sys.exit(1 if fallas else 0)
