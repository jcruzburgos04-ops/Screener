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

print("\n== obligaciones negociables ==")
CRUDO = [
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "AAA1D", "emisor": "Uno",
     "end_date": "2030-01-01", "last_price": 100.0, "tir": 0.08,
     "modified_duration": 3.0, "parity": 1.0, "settlement": "24hs",
     "description": "**Cupón:**\\n- Tasa nominal anual (TNA): 8.75%"},
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "AAA1D", "emisor": "Uno",
     "end_date": "2030-01-01", "last_price": 99.0, "tir": 0.09,
     "modified_duration": 3.0, "parity": 1.0, "settlement": "CI",
     "description": "x"},
    {"bond_family": "ONS-CABLE", "bond_law": "LNY", "ticker": "BBB1C", "emisor": "Uno",
     "end_date": "2029-01-01", "last_price": 90.0, "tir": 0.10,
     "modified_duration": 2.0, "parity": 0.9, "settlement": "24hs",
     "short_description": "Bono USD Ley NY - 6.25% - vto. 01/2029"},
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "CCC1D", "emisor": "Dos",
     "end_date": "2028-01-01", "last_price": 101.0, "tir": 0.05,
     "modified_duration": 1.0, "parity": 1.0, "settlement": "24hs",
     "description": "sin tasa en ningun lado"},
    {"bond_family": "ONS", "ticker": "SINPX", "emisor": "Tres", "last_price": None},
    {"bond_family": "BONO-USD-LPA", "ticker": "AL30", "emisor": "Argentino",
     "last_price": 55.0, "settlement": "24hs"},
]
o = bonos.armar_ons(CRUDO)
tk = [x["t"] for x in o]
ok("se queda con una fila por especie", tk == ["AAA1D", "BBB1C", "CCC1D"], tk)
ok("y con el plazo que se opera (24hs), no el contado inmediato",
   o[0]["precio"] == 100.0, o[0]["precio"])
ok("saltea las que no tienen precio", "SINPX" not in tk)
ok("y lo que no es una ON", "AL30" not in tk)
ok("lee la tasa del texto de las condiciones", o[0]["cupon"] == 8.75, o[0]["cupon"])
ok("o del resumen cuando no esta en el texto", o[1]["cupon"] == 6.25, o[1]["cupon"])
# Una ON step-up no tiene UNA tasa. Poner un numero ahi seria inventarlo.
ok("y deja el cupon vacio si no lo dice en ningun lado, en vez de inventarlo",
   o[2]["cupon"] is None, o[2]["cupon"])
ok("marca las que liquidan afuera", o[1]["cable"] is True and o[0]["cable"] is False)
ok("traduce la ley", o[1]["ley"] == "Nueva York" and o[0]["ley"] == "Argentina")

e = bonos.emisores(o)
ok("agrupa por emisor", [x["emisor"] for x in e] == ["Uno", "Dos"],
   [x["emisor"] for x in e])
ok("cuenta los papeles", e[0]["papeles"] == 2, e[0]["papeles"])
ok("la mediana de un emisor con dos papeles es el promedio de los dos",
   cerca(e[0]["tir_med"], 0.09, 1e-9), e[0]["tir_med"])
ok("y los ordena por lo que el mercado les cobra",
   e[0]["tir_med"] > e[1]["tir_med"])

print("\n== curvas en pesos: se arman solas, sin lista de tickers ==")
# Lo que se prueba aca es que la seleccion sea por REGLA y no por lista: es lo
# que hace que una letra nueva aparezca sola y una vencida desaparezca sola.
PESOS = [
    {"ticker": "S30S6", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2026-09-30", "days_to_finish": 27,
     "last_price": 115.4, "tir": 0.27, "tna": 0.24, "mtir": 0.020,
     "modified_duration": 0.06, "parity": 1.003, "settlement": "24hs"},
    # el mismo papel en contado inmediato: gana el de 24hs
    {"ticker": "S30S6", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2026-09-30", "days_to_finish": 27,
     "last_price": 99.9, "tir": 0.99, "tna": 0.9, "mtir": 0.06, "settlement": "CI"},
    {"ticker": "TZXM9", "bond_family": "LETRAS-CER", "index": "CER", "end_date": "2029-03-28", "days_to_finish": 937,
     "last_price": 89.9, "tir": 0.098, "tna": 0.094, "mtir": 0.0078,
     "modified_duration": 2.34, "parity": 0.787, "settlement": "24hs"},
    # pata sintetica de un dual: TIR de -95%, no es comprable
    {"ticker": "TTS26_CAP", "bond_family": "TAMAR-FIJA", "index": "Fijo", "end_date": "2026-09-15", "days_to_finish": 12,
     "last_price": 168.8, "tir": -0.958, "tna": -2.78, "mtir": -0.232, "settlement": "CI"},
    # ya vencido
    {"ticker": "VIEJO", "bond_family": "LETRAS-FIJO", "index": "Fijo", "end_date": "2026-08-01", "days_to_finish": -30,
     "last_price": 100.0, "tir": 0.3, "tna": 0.28, "mtir": 0.022, "settlement": "24hs"},
    # sin precio
    {"ticker": "SINPX", "bond_family": "LETRAS-CER", "index": "CER", "end_date": "2028-01-01", "days_to_finish": 480,
     "last_price": 0, "tir": 0, "settlement": "24hs"},
    # familia que no esta en CURVAS_PESOS: se ignora en vez de romper
    {"ticker": "OTRO", "bond_family": "FAMILIA-NUEVA",
     "bond_family_label": "Una familia que todavía no existe", "end_date": "2028-01-01",
     "days_to_finish": 480, "last_price": 100, "tir": 0.2, "settlement": "24hs"},
]
c = bonos.armar_pesos(PESOS)
por = {x["clave"]: [f["t"] for f in x["filas"]] for x in c}
ok("agrupa por la familia que declara la fuente",
   sorted(por) == ["FAMILIA-NUEVA", "LETRAS-CER", "LETRAS-FIJO"], sorted(por))
ok("una letra viva entra sola", por.get("LETRAS-FIJO") == ["S30S6"], por.get("LETRAS-FIJO"))
# ESTO es lo que hace que no haya que mantenerlo: una familia que este programa
# no conoce entra igual, con la etiqueta que le pone la fuente, en vez de
# desaparecer en silencio.
ok("una familia desconocida aparece sola y con su nombre",
   any(x["clave"] == "FAMILIA-NUEVA"
       and x["titulo"] == "Una familia que todavía no existe" for x in c),
   [(x["clave"], x["titulo"]) for x in c])
ok("descarta las patas sinteticas de los duales", "TTS26_CAP" not in str(por))
ok("un papel vencido se cae solo", "VIEJO" not in str(por))
ok("y uno sin precio tampoco entra", "SINPX" not in str(por))
ok("se queda con el plazo que se opera (24hs)",
   c[0]["filas"][0]["precio"] == 115.4, c[0]["filas"][0]["precio"])
ok("pasa la TEM tal cual la publica la fuente",
   cerca(c[0]["filas"][0]["tem"], 0.020, 1e-9), c[0]["filas"][0]["tem"])
ok("las conocidas van en el orden declarado y las nuevas al final",
   [x["clave"] for x in c] == ["LETRAS-FIJO", "LETRAS-CER", "FAMILIA-NUEVA"],
   [x["clave"] for x in c])

print("\n== futuros: el vencimiento sale del simbolo, no de una lista ==")
import futuros  # noqa: E402
ok("DLR092026 vence el ultimo dia habil de septiembre",
   futuros.vencimiento("DLR092026") == date(2026, 9, 30), futuros.vencimiento("DLR092026"))
# 31/1/2027 cae domingo: tiene que retroceder al viernes 29
ok("y si el ultimo dia cae fin de semana, retrocede al habil",
   futuros.vencimiento("DLR012027") == date(2027, 1, 29), futuros.vencimiento("DLR012027"))
ok("diciembre no se pasa de año",
   futuros.vencimiento("DLR122026") == date(2026, 12, 31), futuros.vencimiento("DLR122026"))
ok("un simbolo raro devuelve None en vez de romper",
   futuros.vencimiento("RARO") is None and futuros.vencimiento(None) is None)
ok("un mes imposible tambien", futuros.vencimiento("DLR992026") is None)
ok("la etiqueta es la del mercado",
   futuros.etiqueta("DLR092026", date(2026, 9, 30)) == "DLR/SEP26",
   futuros.etiqueta("DLR092026", date(2026, 9, 30)))

RUEDAS = [
    {"symbol": "DLR092026", "dateTime": "2026-09-01T00:00:00Z", "close": 1500.0,
     "settlement": 1500.0, "volume": 100, "openInterest": 900000},
    {"symbol": "DLR092026", "dateTime": "2026-09-02T00:00:00Z", "close": 1509.0,
     "settlement": 1509.5, "volume": 390944, "openInterest": 997504,
     "changePercent": -0.17, "impliedRate": 22.5},
    {"symbol": "DLR122026", "dateTime": "2026-09-02T00:00:00Z", "close": 1619.5,
     "settlement": 1619.5, "volume": 6462, "openInterest": 318356},
    # vencido hace rato: se cae solo
    {"symbol": "DLR012026", "dateTime": "2026-09-02T00:00:00Z", "close": 1200.0},
    {"symbol": "RARO", "dateTime": "2026-09-02T00:00:00Z", "close": 1.0},
]
f, spot, fuente = futuros.armar(RUEDAS, date(2026, 9, 2), 1508.5, "A3500")
tk = [x["t"] for x in f]
ok("solo quedan los contratos vivos", tk == ["DLR/SEP26", "DLR/DIC26"], tk)
ok("usa la rueda MAS NUEVA de cada contrato", f[0]["precio"] == 1509.0, f[0]["precio"])
ok("y van ordenados por plazo", f[0]["dias"] < f[1]["dias"])
# tasa directa = 1619.5/1508.5 - 1 = 7.36% en 120 dias
# Tolerancia 1e-6 y no 1e-9: el payload redondea a seis decimales a proposito,
# para que el JSON no lleve dieciseis digitos de ruido por cada numero.
ok("la tasa directa se calcula contra el spot",
   cerca(f[1]["directa"], 1619.5 / 1508.5 - 1, 1e-6), f[1]["directa"])
ok("la TNA anualiza en dias, no en meses",
   cerca(f[1]["tna"], f[1]["directa"] * 365.0 / f[1]["dias"], 1e-6), f[1]["tna"])
# La TEM capitaliza: NO es directa/meses. Con 7.36% en 120 dias, directa/4 daria
# 1.84% y la capitalizada da menos.
ok("la TEM capitaliza en vez de dividir",
   cerca(f[1]["tem"], (1 + f[1]["directa"]) ** (30.0 / f[1]["dias"]) - 1, 1e-6)
   and f[1]["tem"] < f[1]["directa"] / (f[1]["dias"] / 30.0), f[1]["tem"])
ok("la implicita que publica A3 viaja aparte de la propia",
   f[0]["implicita"] == 22.5, f[0]["implicita"])

# Sin spot: se usa el contrato mas corto, y el payload lo DICE.
f2, spot2, fuente2 = futuros.armar(RUEDAS, date(2026, 9, 2))
ok("sin spot usa el contrato mas corto", spot2 == 1509.0, spot2)
ok("y avisa que es una aproximacion", "corto" in str(fuente2), fuente2)
ok("ese contrato queda con tasa cero contra si mismo",
   cerca(f2[0]["directa"], 0.0, 1e-12), f2[0]["directa"])

# Con tres contratos o mas que traigan la implicita de A3, el spot se DEDUCE de
# ellas en vez de usar el contrato mas corto. Es la correccion que importa: en
# datos reales el mas corto quedo en 1534,5 contra un A3500 de 1509,5, y ese
# 1,7% se le sumaba a la tasa de TODOS los contratos.
CON_IMPL = [
    {"symbol": "DLR092026", "dateTime": "2026-09-02", "close": 1534.5, "impliedRate": 22.5},
    {"symbol": "DLR102026", "dateTime": "2026-09-02", "close": 1562.5, "impliedRate": 21.78},
    {"symbol": "DLR122026", "dateTime": "2026-09-02", "close": 1619.5, "impliedRate": 22.20},
    {"symbol": "DLR062027", "dateTime": "2026-09-02", "close": 1805.0, "impliedRate": 23.68},
]
f3, spot3, fuente3 = futuros.armar(CON_IMPL, date(2026, 9, 2))
ok("con las implicitas de A3, el spot se deduce", "deducido" in str(fuente3), fuente3)
# El A3500 real de esa rueda era 1509,47: la deduccion tiene que caer cerca, y
# MUY lejos del contrato mas corto (1534,5).
ok(f"y cae en {spot3:.2f}, cerca del A3500 real (1509,47)",
   cerca(spot3, 1509.47, 5.0), spot3)
ok("mucho mejor que el contrato mas corto",
   abs(spot3 - 1509.47) < abs(1534.5 - 1509.47), spot3)

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
