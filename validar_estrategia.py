#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
VALIDAR ESTRATEGIA  ·  el screener contra el backtest del usuario
================================================================================

POR QUE EXISTE
--------------
El usuario quiere que el menu Estrategia reproduzca su backtest (v3.1) "lo mas
exacto posible, para que en vivo obtenga resultados parecidos", y pidio que la
comparacion contra sus archivos "corra en cada publicacion y avise si algo deja
de coincidir". Eso es esto. Corre en actualizar.yml y en intradia.yml, NO frena
la publicacion, y deja el resultado en validacion.json, que la pagina muestra
arriba de la tabla de Estrategia.

CONTRA QUE
----------
Los archivos que genero su backtest, en backtest/:
  spy_ash.csv                 la pausa del SPY dia por dia (jul-oct 2026)
  senales_jul_oct_2026.csv    cada dia, cada papel que calificaba, todas las
                              columnas, el dia de la senal y el estado
  operaciones_2025_2026.csv   sus operaciones: entrada, salida y motivo
y el caso de ETSY del 9 al 16/10/2026 que mando en el mensaje.

LO QUE SE DESCUBRIO COMPARANDO (16/10/2026), y por eso hay dos modos
--------------------------------------------------------------------
El CSV de senales coincide EXACTO (961 de 961 papeles-dia, 960 RS) si UNH, UPS
y UAL no estan en el universo, y con ellos adentro el RS sale bien en 830 de
961. El usuario dice que los tres estan en su lista; los datos dicen que en
jul-oct su backtest no los tuvo. Asi que:

  modo "backtest"  el universo que de hecho uso el CSV (sin esos tres). Tiene
                   que coincidir: es el que dice si el motor esta bien.
  modo "vivo"      las reglas que corren en la pagina (UNH y UAL como todos,
                   UPS en los percentiles pero no candidata). Se informa
                   cuanto se aparta; no es una falla.

LA TOLERANCIA
-------------
La que pidio el usuario: 0,1 % en los valores y +/-1 en el RS. Dos detalles:
  - Los precios de Yahoo se reajustan por dividendos cuando se bajan de nuevo,
    asi que un papel puede venir entero corrido (HMY: 2,7 %). Se mide el
    factor k = nuestro cierre / su cierre y los campos en precios se comparan
    divididos por k; el factor se informa aparte.
  - En los osciladores que pasan por cero (MACD, EWO) el 0,1 % relativo no
    sirve: se suma un piso de 0,1 % de la escala de la columna (la mediana de
    su valor absoluto). Es lo mismo que se hace con el ASH (seccion 4).

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
SIN_DATOS_EN_EL_CSV = ("UNH", "UPS", "UAL")
MOTIVO = {"media de salida": "SMA 40", "SL intradiario": "SL", "SL con gap": "SL con gap",
          "TP": "TP", "TP con gap": "TP con gap", "abierta al final": None}
FIN_BACKTEST = 20261002

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
        filas = list(csv.DictReader(f))
    for r in filas:      # en el backtest los sufijos van con guion
        if r.get("ticker") == "SMSN-IL":
            r["ticker"] = "SMSN.IL"
    return filas


class Motor:
    """Las series de todos los papeles y lo que se calcula por dia, con memo."""

    def __init__(self, P, fuera=()):
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

    def idx(self, t, d):
        s = self.se[t]["d"]
        k = int(np.searchsorted(s, d))
        return k if k < len(s) and s[k] == d else None

    def pausa(self, d):
        if d not in self._pausa:
            self._pausa[d] = E.ash_spy(self.spy, d)
        return self._pausa[d]

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
                 bool(s["f7"][j]), bool(s["f8"][j])]
            out[t] = {"j": j, "rs": rs, "prio": pa[n] + pt[n], "f": f, "califica": all(f)}
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
            if not y or not y["califica"] or self.pausa(dj)["pausa"]:
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
        if (a["diario"]["pausa"], a["semanal"]["pausa"], a["pausa"]) != suyo:
            dif.append(f"{r['fecha']} pausa: nuestra D/W/total "
                       f"{a['diario']['pausa']}/{a['semanal']['pausa']}/{a['pausa']} · suya {suyo}")
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
            if (r["pausa_spy"] == "True") != M.pausa(d)["pausa"]:
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
        if d > FIN_BACKTEST or M.pausa(d)["pausa"]:
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
                   bool(s["f8"][j]), M.pausa(d)["pausa"], x["califica"])
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
                             ("rs_puntaje", "rs_puntaje")):
                a, b = e[k_e], M.se[t][k_s][j]
                if not (np.isnan(a) and np.isnan(b)) and abs(a - b) > 1e-9 * max(1, abs(a)):
                    dif.append(f"autocontrol {d} {t} {k_e}: evaluar {a} contra serie {b}")
            mismo_rs = (np.isnan(e["rs"]) and np.isnan(dd[t]["rs"])) or e["rs"] == dd[t]["rs"]
            if e["pasa"] != dd[t]["califica"] or not mismo_rs:
                dif.append(f"autocontrol {d} {t}: evaluar y serie no califican igual")
    return dif


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True)
    ap.add_argument("--salida", default=None, help="carpeta donde dejar validacion.json")
    args = ap.parse_args()
    P = json.loads(Path(args.datos).read_text())
    sen, ash, ops = leer("senales_jul_oct_2026.csv"), leer("spy_ash.csv"), leer("operaciones_2025_2026.csv")

    print("== modo backtest: el universo que uso el CSV (sin " + ", ".join(SIN_DATOS_EN_EL_CSV) + ")")
    Mb = Motor(P, fuera=SIN_DATOS_EN_EL_CSV)
    auto = autocontrol(Mb, P)
    d_sen, info = comparar_senales(Mb, sen, ash)
    d_ops = comparar_ops(Mb, ops)
    d_ord, n_ord = comparar_orden(Mb, ops)
    print(f"   orden de compra: {n_ord - len(d_ord)} de {n_ord} dias con compras salen "
          "de los primeros por prioridad")
    print(f"   pausa del SPY: {info['pausas']} dias · papeles-dia que coinciden: "
          f"{info['coinciden']} de {info['filas']} · diferencias: {len(d_sen)}")
    print(f"   operaciones: {len(ops) - len(d_ops)} de {len(ops)} salen igual")
    if info["ajuste"]:
        print("   precio reajustado distinto (dividendos): "
              + ", ".join(f"{t} x{k}" for t, k in info["ajuste"].items()))
    print("== modo vivo: las reglas de la pagina")
    Mv = Motor(P)
    d_viv, info_v = comparar_senales(Mv, sen, ash)
    print(f"   papeles-dia que coinciden: {info_v['coinciden']} de {info_v['filas']} · "
          f"diferencias: {len(d_viv)} (informativo)")
    d_etsy, n_etsy = comparar_etsy(Mv)
    print(f"== ETSY 9-16/10: {n_etsy} dias comparados · diferencias: {len(d_etsy)}")
    errores = auto + d_sen + d_ops + d_ord + d_etsy
    for x in errores[:80]:
        print("   ✘", x)
    for x in d_viv[:15]:
        print("   (vivo)", x)
    ok = not errores
    print("\nVALIDACION OK" if ok else f"\nVALIDACION CON {len(errores)} DIFERENCIAS")
    if args.salida:
        out = Path(args.salida)
        out.mkdir(parents=True, exist_ok=True)
        (out / "validacion.json").write_text(json.dumps({
            "generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "datos": P.get("fecha"), "ok": ok,
            "senales": {"coinciden": info["coinciden"], "filas": info["filas"],
                        "dias": info["dias"], "pausas": info["pausas"]},
            "operaciones": {"iguales": len(ops) - len(d_ops), "total": len(ops)},
            "orden": {"iguales": n_ord - len(d_ord), "dias": n_ord},
            "etsy": {"dias": n_etsy, "ok": not d_etsy},
            "ajuste": info["ajuste"],
            "vivo": {"coinciden": info_v["coinciden"], "diferencias": len(d_viv),
                     "ejemplos": d_viv[:20]},
            "sin_datos_en_el_csv": list(SIN_DATOS_EN_EL_CSV),
            "diferencias": errores[:200]}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
