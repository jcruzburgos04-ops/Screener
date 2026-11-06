#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
VALIDAR ESTRATEGIA  ·  el screener contra el backtest del usuario
================================================================================

POR QUE EXISTE
--------------
El usuario quiere que el menu Estrategia reproduzca su backtest "lo mas
exacto posible, para que en vivo obtenga resultados parecidos", y pidio que la
comparacion contra sus archivos "corra en cada publicacion y avise si algo deja
de coincidir". Eso es esto. Corre en actualizar.yml y en intradia.yml, NO frena
la publicacion, y deja el resultado en validacion.json, que la pagina muestra
arriba de la tabla de Estrategia.

DOS VERSIONES, DOS JUEGOS DE ARCHIVOS
-------------------------------------
backtest/v33/  la estrategia vigente (v3.3 «confirmacion», 5/11/2026):
  abiertas_al_2024-12-31.csv            las 10 posiciones abiertas ese dia
  operaciones_v33_completas_2010_2026.csv  todas sus operaciones
  curva_v33.csv                         capital y exposicion dia por dia
  Se arranca la cartera el 31/12/2024 con esas diez y se simula hasta el
  ultimo dia de su curva con las reglas de tamano que dio el usuario
  (estrategia.simular_cartera). Tienen que salir las mismas operaciones
  (entrada, salida, motivo, retorno) y la misma curva.

backtest/v31/  la v3.1, que ahora es la columna «califica v3.1» y la cartera
  en papel contra la que se mide la regla de vuelta (seccion 12):
  spy_ash.csv, senales_jul_oct_2026.csv, operaciones_2025_2026.csv y el caso
  de ETSY del 9 al 16/10/2026. Se comparan con los filtros 1 a 8 y la pausa
  D o W, como antes.

LOS PAPELES QUE SU BACKTEST NO TUVO
-----------------------------------
v3.1: UNH, UPS y UAL (el usuario lo confirmo el 5/11: un corte de descarga
de Yahoo de esa corrida). v3.3: SMSN.IL. Con SMSN.IL adentro, el 10/4/2026
califica holgado (y la v3.1 del usuario SI lo compro ese dia), entra en vez
de AMD y la cartera se corre desde ahi; sin el, salen 91 de 91 operaciones.
En la v3.3 nunca opero desde 2010. Pendiente de que el usuario confirme si
tuvo datos. Por eso hay dos modos:

  modo "backtest"  el universo que de hecho uso cada corrida. Tiene que
                   coincidir: es el que dice si el motor esta bien.
  modo "vivo"      las reglas que corren en la pagina (todos adentro, UPS en
                   los percentiles pero no candidata). Se informa.

LA TOLERANCIA
-------------
La que pidio el usuario: 0,1 % en los valores y +/-1 en el RS. En las
operaciones, el retorno con 0,2 puntos (los precios de Yahoo se reajustan por
dividendos cuando se bajan de nuevo). En la curva, 1 %.

    python validar_estrategia.py --datos sitio/datos.json --salida sitio
================================================================================
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import estrategia as E

CARPETA = Path(__file__).parent / "backtest"
SIN_DATOS_V31 = ("UNH", "UPS", "UAL")
SIN_DATOS_V33 = ("SMSN.IL",)
MOTIVO = {"media de salida": "SMA 40", "SL intradiario": "SL", "SL con gap": "SL con gap",
          "TP": "TP", "TP con gap": "TP con gap", "abierta al final": None}
MOTIVO_V33 = {"media": "SMA 40", "SL": "SL", "SL gap": "SL con gap", "TP": "TP",
              "TP gap": "TP con gap", "abierta al final": None}
FIN_BACKTEST = 20261002
ARRANQUE_V33 = 20241231
TOL_RET, TOL_CURVA = 0.002, 0.01

# El caso de ETSY que mando el usuario (datos de Yahoo del 16/10, redondeados).
# fecha: (cierre, dias de cruce o None, wma21, wma26, adr, rs, regimen,
#         hist3, hist3_ant, ewo ok, pausa, califica)
ETSY = {
    20261009: (76.71, None, 72.31, 72.37, 4.04, 69, False, -1.51, -2.03, True, False, False),
    20261012: (76.93, 0, 72.72, 72.67, 3.95, 65, False, -0.17, -1.51, True, False, False),
    20261013: (79.28, 1, 73.33, 73.16, 3.91, 71, True, -0.17, -1.51, True, False, True),
    20261014: (82.93, 2, 74.25, 73.91, 4.05, 78, True, -0.17, -1.51, True, False, True),
    20261015: (89.18, 3, 75.70, 75.10, 4.19, 85, True, 2.54, -0.17, True, False, True),
    20261016: (87.15, 4, 76.89, 76.08, 4.30, 82, True, 2.54, -0.17, True, True, True),
}


def num(f):
    return int(str(f).replace("-", "")) if f else None


def leer(nombre):
    with open(CARPETA / nombre, encoding="utf-8") as f:
        filas = [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]
    for r in filas:      # en el backtest los sufijos van con guion
        if r.get("ticker") == "SMSN-IL":
            r["ticker"] = "SMSN.IL"
    return filas


class Motor:
    """Las series de todos los papeles y lo que se calcula por dia, con memo."""

    def __init__(self, P, fuera=(), version=33):
        self.v = version
        self.nf = E.FILTROS if version == 33 else E.FILTROS_V31
        self.kp = "pausa" if version == 33 else "pausa31"
        S = {s["t"]: s for s in P["simbolos"]}
        self.spy = E.alinear(S["SPY"], S["SPY"]["d"])
        self.cal = np.asarray(self.spy["d"], np.int64)
        self.cs = np.asarray(self.spy["c"], float)
        mapa = P.get("estr_adr") or E.cargar_adr()
        self.excl = set(P.get("estr_excl") or E.cargar_excluidos())
        uni, _, _ = E.universo_estrategia(P["simbolos"], mapa)
        self.etf = {s["t"] for s in P["simbolos"] if E.es_etf(s.get("g"))}
        self.al, self.se = {}, {}
        for t in uni:
            if t in fuera or t not in S:
                continue
            a = E.alinear(S[t], self.cal)
            if a is None:
                continue
            self.al[t] = a
            self.se[t] = E.serie_papel(a, self.cal, self.cs)
        self._dia, self._pausa = {}, {}

    def otra_version(self, version):
        """El mismo universo y las mismas series, con los filtros y la pausa de otra version."""
        import copy
        m = copy.copy(self)
        m.v = version
        m.nf = E.FILTROS if version == 33 else E.FILTROS_V31
        m.kp = "pausa" if version == 33 else "pausa31"
        m._dia = {}                      # "califica" depende de la version
        return m

    def idx(self, t, d):
        s = self.se[t]["d"]
        k = int(np.searchsorted(s, d))
        return k if k < len(s) and s[k] == d else None

    def pausa(self, d):
        if d not in self._pausa:
            self._pausa[d] = E.ash_spy(self.spy, d)
        return self._pausa[d]

    def pausado(self, d):
        """La pausa de ESTA version: D, W o E en la v3.3; D o W en la v3.1."""
        return self.pausa(d)[self.kp]

    def dia(self, d):
        """RS, prioridad y si califica, para cada papel con dato ese dia."""
        if d in self._dia:
            return self._dia[d]
        ts, js = [], []
        for t in self.se:
            j = self.idx(t, d)
            if j is not None:
                ts.append(t)
                js.append(j)
        g = lambda k: np.array([self.se[t][k][j] for t, j in zip(ts, js)])
        pun = g("rs_puntaje")
        U = np.sort(pun[np.isfinite(pun)])
        pa, pt = E.pct_rank(g("adr")), E.pct_rank(g("atr_pct"))
        out = {}
        for n, (t, j) in enumerate(zip(ts, js)):
            s = self.se[t]
            rs = E.rs_de_puntaje(pun[n], U)
            f = [bool(s["f1"][j]), bool(s["f2"][j]), bool(np.isfinite(rs) and rs > E.RS_MIN),
                 bool(s["f4"][j]), bool(s["f5"][j]), bool(s["f6"][j]),
                 bool(s["f7"][j]), bool(s["f8"][j]), bool(s["f9"][j]), bool(s["f10"][j])]
            out[t] = {"j": j, "rs": rs, "prio": pa[n] + pt[n], "f": f,
                      "califica": all(f[:self.nf]), "califica31": all(f[:E.FILTROS_V31])}
        self._dia[d] = out
        return out

    def senal(self, t, d):
        """Dia de la senal y estado de la operacion del backtest, al dia d."""
        x = self.dia(d).get(t)
        s = self.se[t]
        if x is None or not np.isfinite(s["dias_cruce"][x["j"]]):
            return None
        k = x["j"] - int(s["dias_cruce"][x["j"]])
        for j in range(k, x["j"] + 1):
            dj = int(s["d"][j])
            y = self.dia(dj).get(t)
            if not y or not y["califica"] or self.pausado(dj):
                continue
            g = E.seguir_posicion(self.al[t], dj, s["cierre"][j], s["atr_pct"][j], d)
            return {"fecha": dj, "ruedas": x["j"] - j, "entry": s["cierre"][j],
                    "atr_pct": s["atr_pct"][j], "g": g}
        return {"fecha": None}


def comparar_senales(M, sen, ash):
    dif, info = [], {"filas": len(sen), "dias": 0, "ajuste": {}}
    # pausa del SPY
    pausas = 0
    for r in ash:
        d = num(r["fecha"])
        a = M.pausa(d)
        suyo = (r["D_pausa"] == "True", r["W_pausa"] == "True", r["PAUSA"] == "True")
        if (a["diario"]["pausa"], a["semanal"]["pausa"], a[M.kp]) != suyo:
            dif.append(f"{r['fecha']} pausa: nuestra D/W/total "
                       f"{a['diario']['pausa']}/{a['semanal']['pausa']}/{a[M.kp]} · suya {suyo}")
        for k, x in (("D_SmthBulls", a["diario"]["bulls"]), ("D_SmthBears", a["diario"]["bears"]),
                     ("W_SmthBulls", a["semanal"]["bulls"]), ("W_SmthBears", a["semanal"]["bears"])):
            y = float(r[k])
            if abs(x - y) > 0.01 * abs(y) + 1e-6:     # el SPY tambien se reajusta
                dif.append(f"{r['fecha']} {k}: {x:.4f} contra {y:.4f}")
        pausas += 1
    info["pausas"] = pausas
    # papeles que califican, dia por dia
    porDia = {}
    for r in sen:
        porDia.setdefault(num(r["fecha"]), {})[r["ticker"]] = r
    info["dias"] = len(porDia)
    escala = {}
    for col in ("wma21", "wma26", "adr20", "pct_sobre_min52", "pct_bajo_max52", "macd3d_hist",
                "macd3d_hist_anterior", "ewo1", "ewo2", "ewo_senal", "atr_pct"):
        v = [abs(float(r[col])) for r in sen if r[col] not in ("", None)]
        escala[col] = float(np.median(v)) if v else 0.0
    coincide = 0
    for d, suyos in sorted(porDia.items()):
        dd = M.dia(d)
        nuestros = {t for t, x in dd.items() if x["califica"] and t not in M.excl}
        for t in sorted(nuestros - set(suyos)):
            dif.append(f"{d} {t}: califica para nosotros y no en el backtest")
        for t in sorted(set(suyos) - nuestros):
            x = dd.get(t)
            por = ("sin dato" if x is None else
                   "falla " + ",".join(str(i + 1) for i, f in enumerate(x["f"]) if not f)
                   + f" (RS {x['rs']:.0f})")
            dif.append(f"{d} {t}: califica en el backtest y no para nosotros ({por})")
        for t in sorted(nuestros & set(suyos)):
            coincide += 1
            r, x, s = suyos[t], dd[t], M.se[t]
            j = x["j"]
            k = s["cierre"][j] / float(r["cierre"])
            if abs(k - 1) > 0.001:
                info["ajuste"].setdefault(t, round(float(k), 4))
            if abs(x["rs"] - float(r["rs"])) > 1:
                dif.append(f"{d} {t} RS: {x['rs']:.0f} contra {r['rs']}")
            cmp = [("dias_desde_cruce", s["dias_cruce"][j], 1, 0),
                   ("wma21", s["wma21"][j], k, 0), ("wma26", s["wma26"][j], k, 0),
                   ("adr20", s["adr"][j], 1, 0),
                   ("pct_sobre_min52", s["sobre_min"][j] * 100, 1, 0),
                   ("pct_bajo_max52", s["bajo_max"][j] * 100, 1, 0),
                   ("macd3d_hist", s["hist3"][j], k, 0),
                   ("macd3d_hist_anterior", s["hist3_ant"][j], k, 0),
                   ("ewo1", s["ewo1"][j], k, 0), ("ewo2", s["ewo2"][j], 1, 0),
                   ("ewo_senal", s["ewo_senal"][j], 1, 0),
                   ("atr_pct", s["atr_pct"][j] * 100, 1, 0),
                   # la prioridad es una suma de dos percentiles sobre ~460 papeles:
                   # que dos papeles se crucen por un centavo la mueve ~0,002
                   ("prioridad", x["prio"], 1, 0.01)]
            for col, v, kk, piso in cmp:
                y = float(r[col])
                tol = 0.001 * abs(y) + 0.001 * escala.get(col, 0) + piso + 1e-4
                if col.startswith("pct_"):
                    # una columna que YA es un porcentaje (C/min - 1, C/max - 1):
                    # el 0,1 % es sobre los precios de la cuenta, o sea 0,1
                    # punto. GGB y UGP, que pagan dividendos seguido, se mueven
                    # 0,01-0,02 puntos con cada reajuste de Yahoo.
                    tol = 0.1 * (1 + y / 100)
                if not np.isfinite(v) or abs(v / kk - y) > tol:
                    dif.append(f"{d} {t} {col}: {v / kk:.4f} contra {y:.4f}")
            if (r["regimen_50_200"] == "encendido") != bool(s["regimen"][j]):
                dif.append(f"{d} {t} regimen distinto")
            if (r["pausa_spy"] == "True") != M.pausado(d):
                dif.append(f"{d} {t} pausa del SPY distinta")
            h = M.senal(t, d)
            sd = num(r["dia_senal"])
            if (h["fecha"] if h else None) != sd:
                dif.append(f"{d} {t} dia de la senal: {h and h['fecha']} contra {sd}")
            elif sd:
                ks = M.se[t]["cierre"][M.idx(t, sd)] / float(r["entrada_optima"])
                for col, v in (("entrada_optima", h["entry"]),
                               ("sl_optimo", E.plan(h["entry"], h["atr_pct"])["sl"]),
                               ("tp_optimo", E.plan(h["entry"], h["atr_pct"])["tp"]),
                               ("activacion_optima", E.plan(h["entry"], h["atr_pct"])["activacion"])):
                    y = float(r[col])
                    if abs(v / ks - y) > 0.001 * y:
                        dif.append(f"{d} {t} {col}: {v / ks:.4f} contra {y:.4f}")
                if int(float(r["ruedas_desde_senal"])) != h["ruedas"]:
                    dif.append(f"{d} {t} ruedas desde la senal: {h['ruedas']} contra {r['ruedas_desde_senal']}")
                estado = "cerrada" if h["g"]["salida"] else "abierta"
                if not r["estado"].startswith(estado):
                    dif.append(f"{d} {t} estado: {estado} contra {r['estado']}")
                elif estado == "abierta":
                    neto = E.resultado_neto(h["entry"], s["cierre"][j]) * 100
                    suyo = float(r["estado"].split("(")[1].split("%")[0].replace(",", "."))
                    if abs(neto - suyo) > 0.15:
                        dif.append(f"{d} {t} resultado de la abierta: {neto:+.1f} % contra {suyo:+.1f} %")
    info["coinciden"] = coincide
    return dif, info


def comparar_ops(M, ops):
    dif = []
    for o in ops:
        t = o["ticker"]
        if t not in M.se:
            dif.append(f"{t} {o['entrada']}: sin datos")
            continue
        fe = num(o["entrada"])
        j = M.idx(t, fe)
        if j is None:
            dif.append(f"{t} {o['entrada']}: la entrada cae fuera de las barras publicadas")
            continue
        # nuestra propia entrada (el cierre de ese dia): asi un papel con el
        # precio reajustado por dividendos (HMY) se mide en su propia escala
        s = M.se[t]
        g = E.seguir_posicion(M.al[t], fe, s["cierre"][j], s["atr_pct"][j], FIN_BACKTEST)
        suyo = MOTIVO.get(o["motivo"], o["motivo"])
        if suyo is None:
            if g["salida"]:
                dif.append(f"{t} {o['entrada']}: salimos por {g['salida']} el {g['fecha']}, "
                           "el backtest la tiene abierta al 2/10")
        elif g["salida"] != suyo or g["fecha"] != num(o["salida"]):
            dif.append(f"{t} {o['entrada']}: {g['salida'] or 'abierta'} {g['fecha']} "
                       f"contra {o['motivo']} {o['salida']}")
    return dif


def comparar_orden(M, ops):
    """
    El orden de la tabla tiene que ser el orden en que el backtest compra: en
    cada dia con compras, lo que compro tienen que ser los primeros por
    prioridad entre los candidatos (califican, senal abierta, SPY sin pausa,
    no estaban en cartera). Se mide con NUESTROS numeros, no con los del CSV.
    """
    num_ = lambda f: int(f.replace("-", "")) if f else None
    dif, dias = [], 0
    fechas = sorted({num_(o["entrada"]) for o in ops if num_(o["entrada"]) >= 20260701})
    for d in fechas:
        if d > FIN_BACKTEST or M.pausado(d):
            continue
        compro = [o["ticker"] for o in ops if num_(o["entrada"]) == d and o["reentrada"] != "True"]
        tenia = {o["ticker"] for o in ops
                 if num_(o["entrada"]) < d and (num_(o["salida"]) or 99999999) >= d}
        cand = []
        for t, x in M.dia(d).items():
            if not x["califica"] or t in tenia or t in M.excl:
                continue
            h = M.senal(t, d)
            if h and h["fecha"] and not h["g"]["salida"]:
                cand.append((-x["prio"], t))
        orden = [t for _, t in sorted(cand)]
        dias += 1
        if sorted(compro) != sorted(orden[:len(compro)]):
            dif.append(f"{d} orden: el backtest compro {compro}, "
                       f"los primeros por prioridad son {orden[:len(compro) + 2]}")
    return dif, dias


def comparar_etsy(M):
    dif, filas = [], 0
    if "ETSY" not in M.se:
        return ["ETSY sin datos"], 0
    for d, esp in ETSY.items():
        x = M.dia(d).get("ETSY")
        if x is None:
            continue                     # todavia no hay vela de ese dia
        filas += 1
        s, j = M.se["ETSY"], x["j"]
        c, cr, w1, w2, adr, rs, reg, h3, h3a, ewo, pausa, cal = esp
        dc = s["dias_cruce"][j]
        nuestro = (round(float(s["cierre"][j]), 2), None if not np.isfinite(dc) else int(dc),
                   round(float(s["wma21"][j]), 2), round(float(s["wma26"][j]), 2),
                   round(float(s["adr"][j]), 2), int(x["rs"]), bool(s["regimen"][j]),
                   round(float(s["hist3"][j]), 2), round(float(s["hist3_ant"][j]), 2),
                   bool(s["f8"][j]), M.pausado(d), x["califica"])
        en_vivo = d == 20261016          # el usuario lo midio con la rueda abierta
        for nombre, a, b, tol in (("cierre", nuestro[0], c, 0.0015 * c), ("cruce", nuestro[1], cr, 0),
                                  ("wma21", nuestro[2], w1, 0.0015 * w1),
                                  ("wma26", nuestro[3], w2, 0.0015 * w2), ("adr", nuestro[4], adr, 0.02),
                                  ("rs", nuestro[5], rs, 1), ("regimen", nuestro[6], reg, 0),
                                  ("hist3", nuestro[7], h3, 0.02), ("hist3_ant", nuestro[8], h3a, 0.02),
                                  ("ewo", nuestro[9], ewo, 0), ("pausa", nuestro[10], pausa, 0),
                                  ("califica", nuestro[11], cal, 0)):
            # el 16/10 el usuario lo midio con la rueda abierta: el cierre final
            # movio el precio y, con el de todos, el percentil del RS
            if en_vivo and nombre in ("cierre", "wma21", "wma26", "adr", "rs"):
                continue
            if isinstance(b, bool) or b is None or tol == 0:
                ok = a == b
            else:
                ok = a is not None and abs(a - b) <= tol
            if not ok:
                dif.append(f"ETSY {d} {nombre}: {a} contra {b}")
    return dif, filas


def autocontrol(M, P):
    """serie_papel() y evaluar() tienen que decir lo mismo (son dos caminos)."""
    dif = []
    ts = list(M.se)[:: max(1, len(M.se) // 12)]
    dias = [int(M.cal[-1]), int(M.cal[-40]), int(M.cal[-120])]
    for d in dias:
        dd = M.dia(d)
        U = np.sort([M.se[t]["rs_puntaje"][x["j"]] for t, x in dd.items()
                     if np.isfinite(M.se[t]["rs_puntaje"][x["j"]])])
        for t in ts:
            if t not in dd:
                continue
            e = E.evaluar(M.al[t], M.spy, d, U, M.cal)
            j = dd[t]["j"]
            for k_e, k_s in (("wma21", "wma21"), ("adr", "adr"), ("hist3", "hist3"),
                             ("hist3_ant", "hist3_ant"), ("ewo_senal", "ewo_senal"),
                             ("atr_pct", "atr_pct"), ("sobre_min", "sobre_min"),
                             ("rs_puntaje", "rs_puntaje"), ("ash9_bulls", "ash9_bulls"),
                             ("ash9_bears", "ash9_bears"), ("st_linea", "st_linea"),
                             ("st_dir", "st_dir")):
                a, b = e[k_e], M.se[t][k_s][j]
                if not (np.isnan(a) and np.isnan(b)) and abs(a - b) > 1e-9 * max(1, abs(a)):
                    dif.append(f"autocontrol {d} {t} {k_e}: evaluar {a} contra serie {b}")
            mismo_rs = (np.isnan(e["rs"]) and np.isnan(dd[t]["rs"])) or e["rs"] == dd[t]["rs"]
            if (e["pasa"] != all(dd[t]["f"]) or e["pasa31"] != dd[t]["califica31"]
                    or not mismo_rs):
                dif.append(f"autocontrol {d} {t}: evaluar y serie no califican igual")
    return dif


FECHAS_V33 = (20261104, 20261001, 20260701)     # las tres que pidio comparar
_w = np.exp(-((np.arange(14) - 0.85 * 13) ** 2) / (2 * (14 / 6) ** 2))
PESO_MAX_ALMA14 = float(_w.max() / _w.sum())


def comparar_senales_v33(M, sen, spy):
    """
    senales_v33.csv y spy_v33.csv, dia por dia (jul-nov 2026): la pausa con
    sus tres partes, los papeles que califican (filtros 1 a 10) y cada
    columna con la tolerancia del usuario (0,1 % y RS +/-1), como la v3.1.
    """
    dif, info = [], {"filas": len(sen), "pausas": 0, "coinciden": 0, "ajuste": {},
                     "fechas": {}}
    for r in spy:
        d = num(r["fecha"])
        a = M.pausa(d)
        nuestro = (a["diario"]["pausa"], a["semanal"]["pausa"], a["extendido"]["pausa"], a["pausa"])
        suyo = tuple(r[k] == "True" for k in ("pausa_ash_d", "pausa_ash_w", "extendido", "pausa_total"))
        if nuestro != suyo:
            dif.append(f"{r['fecha']} pausa D/W/E/total: nuestra {nuestro} · suya {suyo}")
        for nom, x, y in (("SPY", a["extendido"]["cierre"], float(r["spy"])),
                          ("SMA 200", a["extendido"]["sma200"], float(r["sma200"]))):
            if abs(x - y) > 0.001 * y:
                dif.append(f"{r['fecha']} {nom}: {x:.4f} contra {y:.4f}")
        info["pausas"] += 1
    porDia = {}
    for r in sen:
        porDia.setdefault(num(r["fecha"]), {})[r["ticker"]] = r
    info["dias"] = len(porDia)
    cols = ("wma21", "wma26", "adr", "sobre_min52_pct", "bajo_max52_pct", "macd3d_hist",
            "macd3d_hist_ant", "ewo1", "ewo2", "ewo_senal", "ash_d_bulls", "ash_d_bears", "atr_pct")
    escala = {c: float(np.median([abs(float(r[c])) for r in sen if r[c] not in ("", None)] or [0]))
              for c in cols}
    for d, suyos in sorted(porDia.items()):
        dd = M.dia(d)
        # aca NO se saca a UPS: calificar y ser candidata son dos cosas; el
        # backtest lo lista calificando 5 dias de jul-nov
        nuestros = {t for t, x in dd.items() if x["califica"]}
        antes = len(dif)
        for t in sorted(nuestros - set(suyos)):
            dif.append(f"{d} {t}: califica para nosotros y no en el backtest")
        for t in sorted(set(suyos) - nuestros):
            x = dd.get(t)
            por = ("sin dato" if x is None else
                   "falla " + ",".join(str(i + 1) for i, f in enumerate(x["f"]) if not f)
                   + f" (RS {x['rs']:.0f})")
            dif.append(f"{d} {t}: califica en el backtest y no para nosotros ({por})")
        for t in sorted(nuestros & set(suyos)):
            r, x, s = suyos[t], dd[t], M.se[t]
            j = x["j"]
            k = s["cierre"][j] / float(r["cierre"])
            if abs(k - 1) > 0.001:
                info["ajuste"].setdefault(t, round(float(k), 4))
            if abs(x["rs"] - float(r["rs"])) > 1:
                dif.append(f"{d} {t} RS: {x['rs']:.0f} contra {float(r['rs']):.0f}")
            if int(s["st_dir"][j]) != int(float(r["supertrend_dir"])):
                dif.append(f"{d} {t} Supertrend: {int(s['st_dir'][j])} contra {r['supertrend_dir']}")
            if (r["regimen"] == "True") != bool(s["regimen"][j]):
                dif.append(f"{d} {t} regimen distinto")
            if (r["pausa"] == "True") != M.pausado(d):
                dif.append(f"{d} {t} pausa distinta")
            if int(float(r["dias_desde_cruce"])) != int(s["dias_cruce"][j]):
                dif.append(f"{d} {t} dias desde el cruce: {s['dias_cruce'][j]} contra {r['dias_desde_cruce']}")
            ok = True
            for col, v, kk, piso in (
                    ("wma21", s["wma21"][j], k, 0), ("wma26", s["wma26"][j], k, 0),
                    ("adr", s["adr"][j], 1, 0),
                    ("sobre_min52_pct", s["sobre_min"][j] * 100, 1, 0),
                    ("bajo_max52_pct", s["bajo_max"][j] * 100, 1, 0),
                    ("macd3d_hist", s["hist3"][j], k, 0), ("macd3d_hist_ant", s["hist3_ant"][j], k, 0),
                    ("ewo1", s["ewo1"][j], k, 0), ("ewo2", s["ewo2"][j], 1, 0),
                    ("ewo_senal", s["ewo_senal"][j], 1, 0),
                    ("ash_d_bulls", s["ash9_bulls"][j], k, 0), ("ash_d_bears", s["ash9_bears"][j], k, 0),
                    ("atr_pct", s["atr_pct"][j] * 100, 1, 0),
                    ("prioridad", x["prio"], 1, 0.01)):
                y = float(r[col])
                tol = 0.001 * abs(y) + 0.001 * escala.get(col, 0) + piso + 1e-4
                if col.endswith("52_pct"):
                    tol = 0.1 * (1 + y / 100)
                if col.startswith("ash_d_"):
                    # Bulls y Bears son RESTAS de dos maximos o minimos seguidos:
                    # un numero chico. Medido el 6/11: cada tramo distinto lo
                    # explica UNA vela con el Low corrido medio centavo o uno
                    # (0,002-0,007 % del precio; redondeo o revision de Yahoo),
                    # que en la columna son 0,2-0,5 %. El piso es lo que mueve un
                    # centavo en una vela: 0,01 USD por el peso maximo de la ALMA.
                    tol += 0.01 * PESO_MAX_ALMA14
                if not np.isfinite(v) or abs(v / kk - y) > tol:
                    dif.append(f"{d} {t} {col}: {v / kk:.4f} contra {y:.4f}")
                    ok = False
            info["coinciden"] += ok
        if d in FECHAS_V33:
            info["fechas"][d] = {"suyos": len(suyos), "nuestros": len(nuestros),
                                 "diferencias": len(dif) - antes}
    return dif, info


def simular_v33(M, ops, curva):
    """La cartera desde el 31/12/2024, con las diez abiertas de ese dia."""
    cur = {num(r["fecha"]): (float(r["capital"]), float(r["expo"])) for r in curva}
    cap0, expo0 = cur[ARRANQUE_V33]
    ab = []
    for r in leer("v33/abiertas_al_2024-12-31.csv"):
        t, fe = r["ticker"], num(r["entrada"])
        j = M.idx(t, fe) if t in M.se else None
        if j is None:
            continue
        # el monto sale del peso y del capital de ese dia; la entrada, de
        # NUESTRO cierre (un reajuste por dividendos no corre el resultado)
        ab.append({"t": t, "fe": fe, "pe": float(M.se[t]["cierre"][j]),
                   "atr_pct": float(r["atr_pct_entrada"]) / 100,
                   "monto": float(r["peso"]) * cur[fe][0]})
    if ab:
        ab[0]["efectivo"] = cap0 * (1 - expo0)
    hist = [{"t": r["ticker"], "fe": num(r["entrada"]), "fs": num(r["salida"])}
            for r in ops if r["salida"] and num(r["salida"]) <= ARRANQUE_V33]
    fin = max(cur)
    dias = [int(d) for d in M.cal if ARRANQUE_V33 < d <= fin]
    return E.simular_cartera(dias, M, 33, capital=cap0, abiertas=ab, historia=hist), cur


def comparar_v33(R, ops, cur):
    suyo = {(r["ticker"], num(r["entrada"])): r for r in ops
            if (num(r["salida"]) or 99999999) > ARRANQUE_V33}
    nos = {(o["t"], o["fe"]): o for o in R["ops"]}
    nos.update({(p["t"], p["fe"]): dict(p, fs=None, motivo=None, ret=None) for p in R["abiertas"]})
    dif, iguales = [], 0
    for k in sorted(set(suyo) | set(nos), key=lambda k: (k[1], k[0])):
        s, n = suyo.get(k), nos.get(k)
        f = f"{k[0]} {k[1]}"
        if s and n:
            sm, sf = MOTIVO_V33.get(s["motivo"], s["motivo"]), num(s["salida"])
            mal = []
            if (sm, sf) != (n["motivo"], n["fs"]):
                mal.append(f"salida {n['motivo'] or 'abierta'} {n['fs'] or ''} contra "
                           f"{s['motivo']} {s['salida']}")
            if n["ret"] is not None and abs(n["ret"] - float(s["ret"])) > TOL_RET:
                mal.append(f"retorno {n['ret'] * 100:+.2f} % contra {float(s['ret']) * 100:+.2f} %")
            if (s["reentrada"] == "True") != bool(n.get("reentrada")):
                mal.append("re-entrada distinta")
            if mal:
                dif.append(f + ": " + "; ".join(mal))
            else:
                iguales += 1
        elif s:
            dif.append(f"{f}: el backtest entro ({s['motivo']} {s['salida']}) y nosotros no")
        else:
            dif.append(f"{f}: entramos y el backtest no")
    desvio, cuando = 0.0, None
    for d, c, _ in R["curva"]:
        if d in cur and abs(c / cur[d][0] - 1) > abs(desvio):
            desvio, cuando = c / cur[d][0] - 1, d
    if abs(desvio) > TOL_CURVA:
        dif.append(f"curva: {desvio * 100:+.2f} % el {cuando}")
    ultimo = R["curva"][-1] if R["curva"] else (None, np.nan, 0)
    return dif, {"iguales": iguales, "total": len(suyo), "desvio_curva": round(desvio * 100, 3),
                 "fecha_desvio": cuando, "capital": round(float(ultimo[1]), 3),
                 "capital_suyo": cur.get(ultimo[0], (np.nan,))[0], "hasta": ultimo[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True)
    ap.add_argument("--salida", default=None, help="carpeta donde dejar validacion.json")
    args = ap.parse_args()
    P = json.loads(Path(args.datos).read_text())

    # ---- v3.3 ----
    ops33 = leer("v33/operaciones_v33_completas_2010_2026.csv")
    curva33 = leer("v33/curva_v33.csv")
    print("== v3.3, modo backtest (sin " + ", ".join(SIN_DATOS_V33) + ")")
    M33 = Motor(P, fuera=SIN_DATOS_V33)
    auto = autocontrol(M33, P)
    R33, cur = simular_v33(M33, ops33, curva33)
    d33, i33 = comparar_v33(R33, ops33, cur)
    print(f"   operaciones desde el 31/12/2024: {i33['iguales']} de {i33['total']} iguales · "
          f"curva: desvio maximo {i33['desvio_curva']:+.2f} % ({i33['fecha_desvio']}) · "
          f"capital {i33['capital']} contra {i33['capital_suyo']}")
    sen33, spy33 = leer("v33/senales_v33.csv"), leer("v33/spy_v33.csv")
    d33s, i33s = comparar_senales_v33(M33, sen33, spy33)
    print(f"   senales jul-nov: pausa {i33s['pausas']} dias · {i33s['coinciden']} de "
          f"{i33s['filas']} papeles-dia identicos · diferencias: {len(d33s)}")
    for d, x in sorted(i33s["fechas"].items(), reverse=True):
        print(f"     {d}: califican {x['suyos']} en el backtest, {x['nuestros']} aca · "
              f"diferencias {x['diferencias']}")
    if i33s["ajuste"]:
        print("   precio reajustado distinto (dividendos): "
              + ", ".join(f"{t} x{k}" for t, k in i33s["ajuste"].items()))
    d33 = d33 + d33s
    print("== v3.3, modo vivo (todos adentro)")
    M33v = Motor(P)
    R33v, _ = simular_v33(M33v, ops33, curva33)
    d33v, i33v = comparar_v33(R33v, ops33, cur)
    print(f"   {i33v['iguales']} de {i33v['total']} iguales · {len(d33v)} diferencias (informativo)")

    # ---- v3.1: la columna «califica v3.1» ----
    sen, ash, ops = (leer("v31/senales_jul_oct_2026.csv"), leer("v31/spy_ash.csv"),
                     leer("v31/operaciones_2025_2026.csv"))
    print("== v3.1 (califica v3.1), modo backtest (sin " + ", ".join(SIN_DATOS_V31) + ")")
    Mb = Motor(P, fuera=SIN_DATOS_V31, version=31)
    d_sen, info = comparar_senales(Mb, sen, ash)
    d_ops = comparar_ops(Mb, ops)
    d_ord, n_ord = comparar_orden(Mb, ops)
    print(f"   pausa del SPY: {info['pausas']} dias · papeles-dia que coinciden: "
          f"{info['coinciden']} de {info['filas']} · diferencias: {len(d_sen)}")
    print(f"   operaciones: {len(ops) - len(d_ops)} de {len(ops)} salen igual · orden de compra: "
          f"{n_ord - len(d_ord)} de {n_ord} dias")
    if info["ajuste"]:
        print("   precio reajustado distinto (dividendos): "
              + ", ".join(f"{t} x{k}" for t, k in info["ajuste"].items()))
    Mv = M33v.otra_version(31)
    d_etsy, n_etsy = comparar_etsy(Mv)
    print(f"== ETSY 9-16/10 (v3.1): {n_etsy} dias comparados · diferencias: {len(d_etsy)}")

    errores = auto + d33 + [f"v3.1 {x}" for x in d_sen + d_ops + d_ord + d_etsy]
    for x in errores[:80]:
        print("   ✘", x)
    for x in d33v[:15]:
        print("   (vivo)", x)
    ok = not errores
    print("\nVALIDACION OK" if ok else f"\nVALIDACION CON {len(errores)} DIFERENCIAS")
    if args.salida:
        out = Path(args.salida)
        out.mkdir(parents=True, exist_ok=True)
        (out / "validacion.json").write_text(json.dumps({
            "version": 33,
            "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "datos": P.get("fecha"), "ok": ok,
            "v33": dict(i33, sin_datos=list(SIN_DATOS_V33),
                        senales={k: i33s[k] for k in ("filas", "coinciden", "dias", "pausas")},
                        fechas={str(k): v for k, v in i33s["fechas"].items()},
                        vivo={"iguales": i33v["iguales"], "diferencias": len(d33v),
                              "ejemplos": d33v[:20]}),
            "v31": {"senales": {"coinciden": info["coinciden"], "filas": info["filas"],
                                "dias": info["dias"], "pausas": info["pausas"]},
                    "operaciones": {"iguales": len(ops) - len(d_ops), "total": len(ops)},
                    "orden": {"iguales": n_ord - len(d_ord), "dias": n_ord},
                    "etsy": {"dias": n_etsy, "ok": not d_etsy},
                    "sin_datos": list(SIN_DATOS_V31)},
            "ajuste": info["ajuste"],
            "diferencias": errores[:200]}, ensure_ascii=False, indent=1, default=float))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
