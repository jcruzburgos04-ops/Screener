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
    {"ticker": "OTRO", "bond_family": "FAMILIA-NUEVA", "index": "InventadoNuevo",
     "bond_family_label": "Una familia que todavía no existe", "end_date": "2028-01-01",
     "days_to_finish": 480, "last_price": 100, "tir": 0.2, "settlement": "24hs"},
]
c = bonos.armar_pesos(PESOS)
por = {x["clave"]: [f["t"] for f in x["filas"]] for x in c}
# La familia decide QUE ENTRA (filtra las -USD y las patas sinteticas); el
# indice decide EN QUE CURVA VA. Una LECAP y un BONCAP son familias distintas
# y la misma curva de tasa fija.
ok("agrupa por el indice, no por la familia",
   sorted(por) == ["CER", "Fijo", "InventadoNuevo"], sorted(por))
ok("una letra viva entra sola", por.get("Fijo") == ["S30S6"], por.get("Fijo"))
# ESTO es lo que hace que no haya que mantenerlo: una familia que este programa
# no conoce entra igual, con la etiqueta que le pone la fuente, en vez de
# desaparecer en silencio.
ok("un indice desconocido aparece solo y con el nombre que le pone la fuente",
   any(x["clave"] == "InventadoNuevo"
       and x["titulo"] == "Una familia que todavía no existe" for x in c),
   [(x["clave"], x["titulo"]) for x in c])
ok("descarta las patas sinteticas de los duales", "TTS26_CAP" not in str(por))
ok("un papel vencido se cae solo", "VIEJO" not in str(por))
ok("y uno sin precio tampoco entra", "SINPX" not in str(por))
# La misma letra liquidada en dolares es OTRO papel: S30S6 vale 115 y SS6D 0,07.
# En una pestaña que se llama "Pesos" no va, y mezclarlas mete dos puntos al
# mismo plazo con rendimientos muy distintos.
DOLAR = PESOS + [
    {"ticker": "SS6D", "bond_family": "LETRAS-FIJO-USD", "index": "Fijo",
     "end_date": "2026-09-30", "days_to_finish": 27, "last_price": 0.068,
     "tir": 0.35, "tna": 0.30, "mtir": 0.025, "settlement": "24hs"},
]
ok("las familias en dolares no entran a la curva en pesos",
   "SS6D" not in str([f["t"] for x in bonos.armar_pesos(DOLAR) for f in x["filas"]]))
ok("se queda con el plazo que se opera (24hs)",
   c[0]["filas"][0]["precio"] == 115.4, c[0]["filas"][0]["precio"])
ok("pasa la TEM tal cual la publica la fuente",
   cerca(c[0]["filas"][0]["tem"], 0.020, 1e-9), c[0]["filas"][0]["tem"])
ok("las conocidas van en el orden declarado y las nuevas al final",
   [x["clave"] for x in c] == ["Fijo", "CER", "InventadoNuevo"],
   [x["clave"] for x in c])

# LO QUE ESTE CAMBIO ARREGLA: una LECAP (LETRAS-FIJO) y un BONCAP
# (BONO-CAPITALIZABLE) son familias distintas y la MISMA curva de tasa fija.
# Agrupando por familia salian nueve curvas donde el mercado ve cinco.
JUNTAS = [
    {"ticker": "S30S6", "bond_family": "LETRAS-FIJO", "index": "Fijo",
     "end_date": "2026-09-30", "days_to_finish": 27, "last_price": 115.4,
     "tir": 0.27, "tna": 0.24, "mtir": 0.020, "settlement": "24hs"},
    {"ticker": "TO26", "bond_family": "BONO-CAPITALIZABLE", "index": "Fijo",
     "end_date": "2026-10-17", "days_to_finish": 46, "last_price": 104.7,
     "tir": 0.2559, "tna": 0.23, "mtir": 0.0192, "settlement": "24hs"},
]
j = bonos.armar_pesos(JUNTAS)
ok("LECAP y BONCAP caen en la MISMA curva de tasa fija",
   len(j) == 1 and sorted(f["t"] for f in j[0]["filas"]) == ["S30S6", "TO26"],
   [(x["clave"], [f["t"] for f in x["filas"]]) for x in j])

print("\n== fechas: vencimiento habil, plazos y proximo pago ==")
# Contra el informe de cierre del 01/09/2026 nuestros dias daban UNO MENOS en
# los once papeles de tasa fija. NO era un error: ese informe liquida el 02-09
# y nuestro dato liquida el 03-09. Lo que se prueba aca es lo que de verdad
# hay que sostener -- que reproducimos a la fuente exactamente -- para que
# nadie "arregle" un dia que no esta roto.
HOY = bonos._fecha_larga("September 2nd, 2026")
ok("la fecha del panel sale de la fuente, no del reloj", HOY == date(2026, 9, 2), HOY)
ok("y una fecha que no se entiende no rompe",
   bonos._fecha_larga("Septiembre 2, 2026") is None)
ok("con el panel vacio se cae al reloj",
   bonos.fecha_de_la_fuente([]) == date.today())

# ESTO SALIO PUBLICADO Y ESTABA MAL. Tomando la fecha de la PRIMERA fila, una
# sola rancia corria los plazos de los novecientos instrumentos: las ONs
# mostraban su proximo pago el 27/07 estando a 2/9 -- una fecha ya pasada -- y
# el CAC7O daba 412 dias al vencimiento en vez de 369.
PANEL = ([{"estimation_date": "July 21st, 2026"}]
         + [{"estimation_date": "September 2nd, 2026"}] * 40
         + [{"estimation_date": "no se entiende"}, {}])
ok("una fila rancia adelante no corre el panel entero",
   bonos.fecha_de_la_fuente(PANEL) == date(2026, 9, 2),
   bonos.fecha_de_la_fuente(PANEL))
ok("las que no se entienden no cuentan",
   bonos.fecha_de_la_fuente([{"estimation_date": "x"}, {},
                             {"estimation_date": "September 2nd, 2026"}])
   == date(2026, 9, 2))
# Si el panel viene partido en dos dias por mitades, el bueno es el de hoy.
ok("a igual frecuencia gana la mas nueva",
   bonos.fecha_de_la_fuente([{"estimation_date": "September 1st, 2026"},
                             {"estimation_date": "September 2nd, 2026"}])
   == date(2026, 9, 2))

ok("24hs liquida el habil siguiente",
   bonos.liquidacion(date(2026, 9, 2)) == date(2026, 9, 3))
ok("el viernes salta al lunes",
   bonos.liquidacion(date(2026, 9, 4)) == date(2026, 9, 7))
ok("contado inmediato liquida hoy",
   bonos.liquidacion(date(2026, 9, 2), "CI") == date(2026, 9, 2))

# Filas CRUDAS de la fuente, tal como las devolvio el panel del 2/9/2026.
# `days_to_finish` es lo que ELLA publica: si alguna vez dejamos de dar lo
# mismo, es que le cambiamos la convencion sin darnos cuenta.
CRUDAS = [
    # ticker, end_date, days_to_finish, days_to_coupon, plazo, coupon
    ("S15S6", "2026-09-15", 12, 12, "24hs", 7.210377),
    ("TO26",  "2026-10-17", 47, 47, "CI",   7.75),
    ("TY30P", "2030-05-30", 1365, 88, "24hs", 14.75),
    ("DICP",  "2033-12-31", 2678, 123, "24hs", 1575.392582),
]
malos = []
for tk, end, dtf, dtc, sett, cup in CRUDAS:
    f = {"end_date": end, "days_to_finish": dtf, "days_to_coupon": dtc,
         "settlement": sett, "coupon": cup}
    _, dias = bonos.vencimiento_y_dias(f, HOY)
    if dias != dtf:
        malos.append(f"{tk}: {dias} != {dtf}")
ok("los dias dan lo mismo que la fuente, no uno menos", not malos, malos)

# Lo que SI estaba mal: la fecha. El TO26 figura venciendo un sabado.
v26, d26 = bonos.vencimiento_y_dias(
    {"end_date": "2026-10-17", "days_to_finish": 47, "settlement": "CI"}, HOY)
ok("un vencimiento que cae sabado se muestra el lunes", v26 == "2026-10-19", v26)
ok("y son los mismos 47 dias que ya contaba la fuente", d26 == 47, d26)
ok("uno en dia habil no se toca", bonos.vencimiento_y_dias(
   {"end_date": "2026-09-15", "settlement": "24hs"}, HOY)[0] == "2026-09-15")
ok("sin fecha usable se cae a lo que diga la fuente",
   bonos.vencimiento_y_dias({"days_to_finish": 99}, HOY) == (None, 99))
ok("y una fecha ilegible tampoco rompe",
   bonos.vencimiento_y_dias({"end_date": "ayer", "days_to_finish": 5}, HOY) == (None, 5))

# EL PROXIMO PAGO. `coupon` es un IMPORTE, no una tasa: el TO26 paga 15,50%
# anual sobre 100 de residual y el campo trae 7,75, que es el semestre.
p = {tk: bonos.proximo_pago(
        {"end_date": e, "days_to_finish": dtf, "days_to_coupon": dtc,
         "settlement": st, "coupon": c, "coupon_yield": 0.02}, HOY)
     for tk, e, dtf, dtc, st, c in CRUDAS}
ok("una letra que capitaliza paga todo junto al vencimiento",
   p["S15S6"]["fecha"] == "2026-09-15" and p["S15S6"]["ultimo"], p["S15S6"])
ok("y su importe es el que publica la fuente",
   cerca(p["S15S6"]["monto"], 7.2104, 1e-4), p["S15S6"]["monto"])
ok("el TO26 tambien tiene un solo pago por delante", p["TO26"]["ultimo"])
# ESTA es la que separa un cronograma completo de uno que no lo esta.
ok("al TY30P le faltan cupones, y NO se dice que sea el ultimo",
   p["TY30P"]["ultimo"] is False, p["TY30P"])
ok("su proximo pago es el 30/11/2026, no el vencimiento",
   p["TY30P"]["fecha"] == "2026-11-30", p["TY30P"]["fecha"])
ok("y son 88 dias, los que dice la fuente", p["TY30P"]["dias"] == 88)
ok("al DICP tampoco", p["DICP"]["ultimo"] is False)

# Cuando es el ultimo, el pago ES el vencimiento: se toma la MISMA fecha que
# muestra la fila. Derivandola por separado desde los dias, las dos columnas
# podian decir cosas distintas del mismo dia.
ult = {"end_date": "2026-10-17", "days_to_finish": 47, "days_to_coupon": 47,
       "settlement": "CI", "coupon": 7.75}
v_ult, d_ult = bonos.vencimiento_y_dias(ult, HOY)
p_ult = bonos.proximo_pago(ult, HOY)
ok("el ultimo pago cae exactamente en el vencimiento de su fila",
   (p_ult["fecha"], p_ult["dias"]) == (v_ult, d_ult), (p_ult, v_ult, d_ult))
ok("y ese vencimiento es el lunes, no el sabado", p_ult["fecha"] == "2026-10-19")

ok("sin days_to_coupon no hay proximo pago",
   bonos.proximo_pago({"end_date": "2027-01-01", "days_to_finish": 100}, HOY) is None)
# Un days_to_coupon mayor que el plazo al vencimiento es un dato roto, y en
# una columna se leeria como un cobro que no existe.
ok("un proximo pago posterior al vencimiento se descarta",
   bonos.proximo_pago({"end_date": "2027-01-01", "days_to_finish": 100,
                       "days_to_coupon": 500}, HOY) is None)
ok("y uno sin importe sale igual, con el importe vacio",
   bonos.proximo_pago({"end_date": "2027-01-01", "days_to_finish": 100,
                       "days_to_coupon": 10}, HOY)["monto"] is None)

# Y de punta a punta: el panel entero con UNA fila rancia adelante tiene que
# dar los mismos plazos que la fuente. Es el bug que salio publicado.
PANEL_ONS = [
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "RANCIA",
     "emisor": "X", "estimation_date": "July 21st, 2026",
     "end_date": "2027-09-07", "days_to_finish": 369, "last_price": 0,
     "settlement": "24hs", "short_description": "x", "description": "x"},
] + [
    {"bond_family": "ONS", "bond_law": "LA", "ticker": "CAC7O",
     "emisor": "Capex", "estimation_date": "September 2nd, 2026",
     "end_date": "2027-09-07", "days_to_finish": 369, "days_to_coupon": 5,
     "coupon": 3.28, "last_price": 101.0, "tir": 0.06,
     "settlement": "24hs", "short_description": "Bono USD Ley Arg. - 6.00%",
     "description": "x"},
] * 3
o = bonos.armar_ons(PANEL_ONS)[0]
ok("con una fila rancia adelante, los dias siguen dando los de la fuente",
   o["dias"] == 369, (o["t"], o["dias"], o["vto"]))
ok("y el proximo pago NO cae en una fecha ya pasada",
   o["pago"]["fecha"] > "2026-09-02", o["pago"])

print("\n== los que distorsionan el grafico: no operaron ==")
# Los volumenes son los REALES del panel del 2/9/2026, sacados de la corrida
# del workflow. Es el caso que hay que arreglar, no uno inventado: cuatro de
# los seis dolar linked no operaron nada y la curva salia con 0,8% y 10,8%
# mezclados; el TY30P negocio 0,01 contra una mediana de 7,72 y el solo
# estiraba el eje de 300 a 1365 dias.
def _p(t, dias, tem, vol, ind="Fijo", fam="LETRAS-FIJO"):
    return {"ticker": t, "bond_family": fam, "index": ind,
            "end_date": "2027-01-01", "days_to_finish": dias, "last_price": 100.0,
            "tir": tem * 12, "tna": tem * 12, "mtir": tem, "volume": vol,
            "settlement": "24hs"}

FIJA = [_p("S15S6", 12, 0.0201, 69.24), _p("S30S6", 27, 0.0192, 116.28),
        _p("TO26", 46, 0.0185, 1.13),   _p("S30O6", 57, 0.0190, 114.41),
        _p("S13N6", 71, 0.0202, 7.72),  _p("S30N6", 88, 0.0208, 148.60),
        _p("T15E7", 134, 0.0202, 8.94), _p("T30A7", 239, 0.0213, 6.76),
        _p("T31Y7", 270, 0.0216, 7.05), _p("T30J7", 300, 0.0211, 4.90),
        _p("TY30P", 1365, 0.0217, 0.01)]
f = {x["t"]: x for x in bonos.armar_pesos(FIJA)[0]["filas"]}
ok("el que negocio una miga contra su curva queda marcado",
   f["TY30P"]["opero"] is False, f["TY30P"]["volumen"])
ok("y los que operaron de verdad pasan", all(f[t]["opero"] for t in
   ("S15S6", "S30S6", "S30O6", "S13N6", "S30N6")))
# 1,13 contra una mediana de 7,72 es poco, pero es una operacion de verdad:
# el filtro apunta a las puntas rancias, no a los papeles flacos.
ok("un papel poco operado NO es lo mismo que uno sin operar",
   f["TO26"]["opero"] is True, f["TO26"]["volumen"])

USDL = [_p("D30S6", 27, 0.0045, 0.0, "USDL", "DOLAR-LINKED"),
        _p("D31M7", 209, 0.0040, 0.0, "USDL", "DOLAR-LINKED"),
        _p("D10Y7", 249, 0.0007, 0.0, "USDL", "DOLAR-LINKED"),
        _p("TZV27", 300, 0.0020, 0.0, "USDL", "DOLAR-LINKED"),
        _p("TZV28", 666, 0.0085, 1.97, "USDL", "DOLAR-LINKED"),
        _p("TZVD8", 834, 0.0086, 2.79, "USDL", "DOLAR-LINKED")]
u = bonos.armar_pesos(USDL)[0]
ok("de los seis dolar linked reales, quedan los dos que operaron",
   u["operados"] == 2, u["operados"])
ok("pero los seis siguen en la tabla", len(u["filas"]) == 6, len(u["filas"]))
ok("los que quedan son justamente los que tenian volumen",
   sorted(x["t"] for x in u["filas"] if x["opero"]) == ["TZV28", "TZVD8"])

# Si la fuente deja de mandar el volumen, callarse media curva seria peor que
# el problema que esto arregla. Sin dato, pasan todos.
SIN_VOL = [{k: v for k, v in x.items() if k != "volume"} for x in FIJA]
ok("sin el campo volumen no se filtra nada",
   all(x["opero"] for x in bonos.armar_pesos(SIN_VOL)[0]["filas"]))
ok("un cero explicito si filtra",
   bonos.marcar_operados([{"volumen": 0.0}, {"volumen": 5.0}])[0]["opero"] is False)
# Con dos papeles la "mediana" es el mas grande y el chico quedaba afuera por
# nada. Debajo de cinco vale solo la condicion que no necesita muestra.
ok("con pocos papeles no se aplica el piso relativo",
   [x["opero"] for x in bonos.marcar_operados(
       [{"volumen": 157.3}, {"volumen": 33385.4}])] == [True, True])

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

print("\n== los futuros, contra la pantalla de referencia del usuario ==")
# Cuatro contratos de la captura, con su TNA y su TEM publicadas. Fija las dos
# convenciones que se pueden hacer mal: la TNA anualiza en DIAS (x365/d) y la
# TEM CAPITALIZA (no es la directa dividida por los meses). Si alguien las
# cambia por "lo que parece razonable", esto se pone en rojo.
REF_FUT = [  # (contrato, precio, dias, TNA%, TEM%)
    ("DLR092026", 1536.50,  30, 22.58, 1.86),
    ("DLR102026", 1562.50,  60, 21.78, 1.77),
    ("DLR122026", 1619.50, 121, 22.20, 1.78),
    ("DLR072027", 1834.00, 333, 23.65, 1.78),
]
SPOT_REF = 1508.50
for tk, precio, dias, tna_ref, tem_ref in REF_FUT:
    directa = precio / SPOT_REF - 1
    tna = directa * 365.0 / dias
    tem = (1 + directa) ** (30.0 / dias) - 1
    ok(f"{tk}: TNA {tna*100:.2f}% (ref {tna_ref}%)", cerca(tna * 100, tna_ref, 0.01))
    ok(f"{tk}: TEM {tem*100:.2f}% (ref {tem_ref}%)", cerca(tem * 100, tem_ref, 0.01))

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
