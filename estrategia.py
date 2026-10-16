#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ESTRATEGIA (base v3.1)  ·  la referencia en Python de lo que calcula la pagina
================================================================================

POR QUE EXISTE SI LA PAGINA YA LO CALCULA
-----------------------------------------
Por lo mismo que el ASH esta dos veces: el usuario compara estos numeros contra
su backtest en Python, y la unica forma de saber que el JS de `plantilla.html`
dice lo mismo es tener una segunda implementacion y compararlas
(`pruebas/estrategia_paridad.js`). Ademas la usan:

  - `rs_amplio.py`, que arma de noche el universo amplio del RS con el mismo
    `puntaje_rs` que usa la pagina;
  - la sonda de Actions, que corre todo contra el historial COMPLETO de Yahoo
    (desde 1997) y lo compara con las 850 barras que se publican.

LAS REGLAS SON DEL USUARIO, NO NUESTRAS
---------------------------------------
Cada numero de aca viene de su especificacion (prompt_screener_v31.md) y de sus
respuestas. No se "simplifica" nada sin preguntarle. Lo que la especificacion
no decia y hubo que elegir esta marcado con ELEGIDO, para que sepa donde mirar
si un valor no le cierra contra el backtest.

LAS MEDIAS SON LAS DE PINE, NO LAS DEL SCREENER
-----------------------------------------------
El screener siembra la RMA (y por eso el ATR) con el primer valor, y su ema()
con el primer precio: eso sostiene la paridad del ASH y no se toca. Aca va lo
que pidio el usuario: `ta.ema` y `ta.rma` sembradas con la SMA de los primeros
n valores VALIDOS, y `ta.atr` con el true range de Pine (la primera vela usa
H-L). Son funciones aparte a proposito.
================================================================================
"""

from datetime import date, timedelta

import numpy as np

from screener import alma, calc_ash  # noqa: F401  (alma: la misma del ASH)

# ------------------------------------------------------------------------------
# Constantes de la estrategia. Las mismas que ESTR en plantilla.html.
# ------------------------------------------------------------------------------
WMA_RAP, WMA_LEN, CRUCE_MAX = 21, 26, 20
ADR_N, ADR_MIN = 20, 2.0
RS_MIN = 70.0
RUEDAS_52 = 252
SOBRE_MIN, BAJO_MAX = 1.30, 0.75
SMA_REG_C, SMA_REG_L = 50, 200
MACD_R, MACD_L, MACD_S = 5, 13, 13
EWO_R, EWO_L, EWO_S = 3, 21, 5
ATR_N = 14
SL_K, SL_MIN, SL_MAX = 3.5, 0.005, 0.95
TP_K, ACT_K = 3.00, 1.20
SMA_SAL, EMA_REENT = 40, 34
LUGARES = 10
COMISION = 0.0035
# Una vela de 3 dias CERRO el viernes 2/10/2026 (dato del usuario). Las
# siguientes son 5-6-7/10, 8-9-12/10... Se cuenta sobre el calendario de NYSE,
# que en la practica es el de las fechas del SPY.
ANCLA_3D = 20261002


# ==============================================================================
# 1. MEDIAS DE PINE
# ==============================================================================

def sma(x, n):
    """ta.sma: NaN si falta algun valor de la ventana."""
    x = np.asarray(x, float)
    o = np.full(len(x), np.nan)
    if len(x) < n:
        return o
    c = np.convolve(np.nan_to_num(x), np.ones(n), "valid") / n
    malos = np.convolve(~np.isfinite(x), np.ones(n), "valid") > 0
    c[malos] = np.nan
    o[n - 1:] = c
    return o


def _recursiva(x, n, a):
    """
    Lo que tienen en comun ta.ema y ta.rma en el codigo de referencia de Pine:

        sum := na(sum[1]) ? ta.sma(src, length) : a*src + (1-a)*nz(sum[1])

    La semilla es la SMA de los primeros n valores VALIDOS seguidos: en el
    MACD, la senal arranca 13 velas despues de que el MACD tiene valor, no en
    la vela 13 de la serie. Un hueco en el medio corta la media y vuelve a
    sembrar (asi se comporta Pine con un na en src).
    """
    x = np.asarray(x, float)
    o = np.full(len(x), np.nan)
    s = sma(x, n)
    p = np.nan
    for i in range(len(x)):
        if not np.isfinite(p):
            p = s[i]
        elif np.isfinite(x[i]):
            p = a * x[i] + (1 - a) * p
        else:
            p = np.nan
        o[i] = p
    return o


def ema_p(x, n):
    return _recursiva(x, n, 2.0 / (n + 1))


def rma_p(x, n):
    return _recursiva(x, n, 1.0 / n)


def wma(x, n):
    """ta.wma: el peso mas grande a la vela mas nueva."""
    x = np.asarray(x, float)
    o = np.full(len(x), np.nan)
    if len(x) < n:
        return o
    w = np.arange(1.0, n + 1.0)
    for i in range(n - 1, len(x)):
        v = x[i - n + 1:i + 1]
        o[i] = (v * w).sum() / w.sum() if np.isfinite(v).all() else np.nan
    return o


def atr_p(h, l, c, n):
    """ta.atr: rma del true range; la primera vela (sin cierre previo) es H-L."""
    h, l, c = (np.asarray(v, float) for v in (h, l, c))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isfinite(pc),
                  np.fmax(np.fmax(h - l, np.abs(h - pc)), np.abs(l - pc)),
                  h - l)
    return rma_p(tr, n)


def pct_rank(valores):
    """
    Percentil 0-1 de cada valor dentro de la lista, con empates promediados.
    Es `pandas.Series.rank(pct=True)`: el mas chico da 1/N y el mas grande 1.
    """
    v = np.asarray(valores, float)
    o = np.full(len(v), np.nan)
    ok = np.isfinite(v)
    w = v[ok]
    if not len(w):
        return o
    srt = np.sort(w)
    menos = np.searchsorted(srt, w, "left")
    hasta = np.searchsorted(srt, w, "right")
    o[ok] = (menos + 1 + hasta) / 2.0 / len(w)
    return o


def rs_de_puntaje(x, universo_ordenado):
    """
    ELEGIDO: el percentil de `x` dentro del universo amplio (ya ordenado), como
    rank(pct=True) de pandas, por 100 y acotado a 1-99. El filtro compara ESTE
    numero (sin redondear) contra 70; en pantalla va redondeado.
    """
    u = universo_ordenado
    if not np.isfinite(x) or not len(u):
        return np.nan
    menos = np.searchsorted(u, x, "left")
    hasta = np.searchsorted(u, x, "right")
    if hasta == menos:      # no esta en el universo: cuenta como uno mas
        pct = (menos + 1) / (len(u) + 1)
    else:
        pct = (menos + 1 + hasta) / 2.0 / len(u)
    return min(99.0, max(1.0, pct * 100))


# ==============================================================================
# 2. CALENDARIO: feriados de NYSE, velas de 3 dias, semanas cerradas
# ==============================================================================

def _pascua(y):
    """Domingo de Pascua (algoritmo anonimo gregoriano)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(y, mes, dia)


def _nesimo(y, m, wd, k):
    """k-esimo dia `wd` (0=lunes) del mes; k=-1 es el ultimo."""
    if k > 0:
        d = date(y, m, 1)
        d += timedelta((wd - d.weekday()) % 7)
        return d + timedelta(7 * (k - 1))
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(1)
    return d - timedelta((d.weekday() - wd) % 7)


def _observado(d):
    """Sabado se corre al viernes, domingo al lunes."""
    if d.weekday() == 5:
        return d - timedelta(1)
    if d.weekday() == 6:
        return d + timedelta(1)
    return d


def feriados_nyse(y):
    """
    Los cierres completos de NYSE por REGLA, no por lista: asi no vence. Solo
    hace falta para una pregunta -- si la semana del SPY ya cerro --, y ahi lo
    que importa son los viernes (Viernes Santo, y 4 de julio, 19 de junio o
    Navidad cuando caen sabado). Los cierres extraordinarios (duelos
    nacionales, el 11-S) no estan: son imprevisibles.
    """
    f = {_nesimo(y, 1, 0, 3), _nesimo(y, 2, 0, 3), _pascua(y) - timedelta(2),
         _nesimo(y, 5, 0, -1), _observado(date(y, 7, 4)), _nesimo(y, 9, 0, 1),
         _nesimo(y, 11, 3, 4), _observado(date(y, 12, 25))}
    ano_nuevo = date(y, 1, 1)
    # NYSE no corre el 1 de enero al viernes 31 de diciembre si cae sabado.
    if ano_nuevo.weekday() != 5:
        f.add(_observado(ano_nuevo))
    if y >= 2022:
        f.add(_observado(date(y, 6, 19)))
    return f


def a_date(n):
    n = int(n)
    return date(n // 10000, n // 100 % 100, n % 100)


def semana_cerrada(fecha):
    """
    La semana (W-FRI) de `fecha` ya cerro si despues de `fecha` no queda
    ninguna rueda de NYSE hasta el viernes. Es lo que pidio el usuario: "la
    semana cierra con su ultima rueda; si el viernes es feriado, cierra el
    jueves".
    """
    d = a_date(fecha)
    fer = feriados_nyse(d.year)
    k = d + timedelta(1)
    while k.weekday() <= 4:
        if k not in fer:
            return False
        k += timedelta(1)
    return True


def clave_semana(f):
    """Numero de semana W-FRI (la semana termina el viernes)."""
    # toordinal() da 1 al lunes 1/1/0001: (o-1)//7 cambia de numero cada
    # lunes, asi que lunes..domingo es una semana, que para ruedas es W-FRI.
    return (a_date(f).toordinal() - 1) // 7


def semanal_cerrado(d, c):
    """Cierres semanales W-FRI; la semana en curso sale si no cerro."""
    fechas, cierres, k = [], [], None
    for f, v in zip(d, c):
        kk = clave_semana(f)
        if kk != k:
            fechas.append(f)
            cierres.append(v)
            k = kk
        else:
            fechas[-1], cierres[-1] = f, v
    if fechas and not semana_cerrada(fechas[-1]):
        fechas, cierres = fechas[:-1], cierres[:-1]
    return fechas, np.asarray(cierres, float)


def velas_3d(d, o, h, l, c, calendario, hasta):
    """
    Velas de 3 ruedas consecutivas del calendario de NYSE, contadas de forma
    que una vela termina en ANCLA_3D. Devuelve solo las CERRADAS a `hasta`.

    `calendario` son las fechas del SPY (ordenadas). Una fecha del papel que
    no esta en el calendario (un dia que Londres opero y Nueva York no) cae en
    la vela de la ultima rueda de NYSE anterior.
    """
    cal = np.asarray(calendario, np.int64)
    pa = int(np.searchsorted(cal, ANCLA_3D))
    if pa >= len(cal) or cal[pa] != ANCLA_3D:
        raise ValueError("el ancla de las velas de 3 dias no esta en el calendario")
    ph = int(np.searchsorted(cal, hasta, "right")) - 1
    inicio = pa + 1                      # primera rueda de una vela
    g_cerrada = (ph - inicio - 2) // 3   # la ultima vela cuyo 3er dia ya paso
    velas = {}
    for i, f in enumerate(d):
        if f > hasta:
            break
        p = int(np.searchsorted(cal, f, "right")) - 1
        if p < 0:
            continue
        g = (p - inicio) // 3
        # la primera vela puede venir cortada (la serie arranca a mitad de
        # una): se tira, porque no es una vela de 3 ruedas
        if g > g_cerrada or inicio + 3 * g < 0:
            continue
        v = velas.get(g)
        if v is None:
            velas[g] = [f, o[i], h[i], l[i], c[i]]
        else:
            v[0] = f
            v[2] = max(v[2], h[i])
            v[3] = min(v[3], l[i])
            v[4] = c[i]
    gs = sorted(velas)
    fin = [int(cal[inicio + 3 * g + 2]) for g in gs]
    return {"g": gs, "fin": fin,
            "o": np.array([velas[g][1] for g in gs], float),
            "h": np.array([velas[g][2] for g in gs], float),
            "l": np.array([velas[g][3] for g in gs], float),
            "c": np.array([velas[g][4] for g in gs], float)}


# ==============================================================================
# 3. LOS INDICADORES DE UN PAPEL, A LA FECHA `hasta`
# ==============================================================================

def automata_regimen(c, s50, s200):
    """
    Encendido se apaga con C < linea; apagado se prende con C > linea; igual a
    la linea, queda como estaba. Linea = max(SMA 50, SMA 200). Sin datos para
    las SMA: encendido (y vuelve a encendido si falta un dato en el medio).
    """
    on = True
    for j in range(len(c)):
        if not (np.isfinite(s50[j]) and np.isfinite(s200[j])):
            on = True
            continue
        linea = max(s50[j], s200[j])
        if on and c[j] < linea:
            on = False
        elif not on and c[j] > linea:
            on = True
    return on


def puntaje_rs(c, c_spy):
    """
    RS estilo IBD contra el SPY, con los retornos a 63/126/189/252 ruedas.
    `c` y `c_spy` terminan en la MISMA fecha. NaN si falta historia.
    """
    if len(c) < 253 or len(c_spy) < 253:
        return np.nan
    s = 0.0
    for n, w in ((63, .4), (126, .2), (189, .2), (252, .2)):
        a, b = c[-1] / c[-1 - n], c_spy[-1] / c_spy[-1 - n]
        if not (np.isfinite(a) and np.isfinite(b)) or b <= 0:
            return np.nan
        s += w * a / b
    return s


def evaluar(s, spy, hasta, universo_rs=None, calendario=None):
    """
    Todas las columnas de la tabla para el papel `s` al cierre de `hasta`.
    `s` y `spy` son dicts con listas d/o/h/l/c (el formato del payload).
    Devuelve None si el papel no tiene la vela de `hasta`: un indicador
    calculado con la vela de otro dia seria un dato equivocado.
    """
    d = np.asarray(s["d"], np.int64)
    n = int(np.searchsorted(d, hasta, "right"))
    if n == 0 or d[n - 1] != hasta:
        return None
    o, h, l, c = (np.asarray(s[k][:n], float) for k in "ohlc")
    d = d[:n]
    i = n - 1
    r = {"t": s["t"], "fecha": int(hasta), "cierre": c[i]}

    # 1 · cruce WMA 21/26
    w1, w2 = wma(c, WMA_RAP), wma(c, WMA_LEN)
    r["wma21"], r["wma26"] = w1[i], w2[i]
    arriba = np.isfinite(w1[i]) and np.isfinite(w2[i]) and w1[i] >= w2[i]
    ini = i
    if arriba:
        while ini - 1 >= 0 and np.isfinite(w1[ini - 1]) and np.isfinite(w2[ini - 1]) \
                and w1[ini - 1] >= w2[ini - 1]:
            ini -= 1
    con_cruce = arriba and ini - 1 >= 0 and np.isfinite(w1[ini - 1]) \
        and np.isfinite(w2[ini - 1]) and w1[ini - 1] < w2[ini - 1]
    r["dias_cruce"] = (i - ini) if con_cruce else None
    r["fecha_cruce"] = int(d[ini]) if con_cruce else None
    r["f1"] = bool(con_cruce and i - ini <= CRUCE_MAX)

    # 2 · ADR%(20)
    adr = (sma(h / l, ADR_N) - 1) * 100
    r["adr"] = adr[i]
    r["f2"] = bool(np.isfinite(adr[i]) and adr[i] > ADR_MIN)

    # 3 · RS
    cs = np.asarray(spy["c"], float)[:int(np.searchsorted(spy["d"], hasta, "right"))]
    r["rs_puntaje"] = puntaje_rs(c, cs)
    r["rs"] = (rs_de_puntaje(r["rs_puntaje"], universo_rs)
               if universo_rs is not None else np.nan)
    r["f3"] = bool(np.isfinite(r["rs"]) and r["rs"] > RS_MIN)

    # 4 y 5 · minimo y maximo de 52 semanas (252 velas, hoy incluida)
    if n >= RUEDAS_52:
        lo, hi = l[-RUEDAS_52:].min(), h[-RUEDAS_52:].max()
    else:
        lo = hi = np.nan                 # ELEGIDO: sin 252 velas no pasa
    r["min52"], r["max52"] = lo, hi
    r["sobre_min"] = c[i] / lo - 1
    r["bajo_max"] = c[i] / hi - 1
    r["f4"] = bool(np.isfinite(lo) and c[i] >= SOBRE_MIN * lo)
    r["f5"] = bool(np.isfinite(hi) and c[i] >= BAJO_MAX * hi)

    # 6 · regimen SMA 50/200, autómata con histeresis sobre TODA la serie
    s50, s200 = sma(c, SMA_REG_C), sma(c, SMA_REG_L)
    on = automata_regimen(c, s50, s200)
    r["sma50"], r["sma200"] = s50[i], s200[i]
    r["regimen"] = on
    r["f6"] = on

    # 7 · MACD 5/13/13 sobre velas de 3 dias cerradas
    cal = calendario if calendario is not None else spy["d"]
    v3 = velas_3d(d, o, h, l, c, cal, hasta)
    m = ema_p(v3["c"], MACD_R) - ema_p(v3["c"], MACD_L)
    sg = ema_p(m, MACD_S)
    hist = m - sg
    r["v3_fin"] = int(v3["fin"][-1]) if len(v3["fin"]) else None
    r["v3_ant"] = int(v3["fin"][-2]) if len(v3["fin"]) > 1 else None
    r["macd3"] = m[-1] if len(m) else np.nan
    r["macd3_senal"] = sg[-1] if len(sg) else np.nan
    r["hist3"] = hist[-1] if len(hist) else np.nan
    r["hist3_ant"] = hist[-2] if len(hist) > 1 else np.nan
    r["f7"] = bool(np.isfinite(r["hist3"]) and np.isfinite(r["hist3_ant"])
                   and r["hist3"] > r["hist3_ant"])

    # 8 · EWO diario
    e3, e21 = ema_p(c, EWO_R), ema_p(c, EWO_L)
    ewo1 = e3 - e21
    ewo2 = (e3 / e21 - 1) * 100
    sew = ema_p(ewo2, EWO_S)
    r["ewo1"], r["ewo2"], r["ewo_senal"] = ewo1[i], ewo2[i], sew[i]
    r["f8"] = bool(np.isfinite(ewo1[i]) and np.isfinite(sew[i])
                   and ewo1[i] > 0 and ewo2[i] > sew[i])

    # Para el orden y el plan
    a = atr_p(h, l, c, ATR_N)
    r["atr"] = a[i]
    r["atr_pct"] = a[i] / c[i]
    s40 = sma(c, SMA_SAL)
    r["sma40"] = s40[i]
    r["ema34"] = ema_p(c, EMA_REENT)[i]
    dist = min(max(SL_K * r["atr_pct"], SL_MIN), SL_MAX) if np.isfinite(r["atr_pct"]) else np.nan
    r["sl_pct"] = dist
    r["sl"] = c[i] * (1 - dist)
    r["tp"] = c[i] * TP_K
    r["activacion"] = c[i] * ACT_K
    r["pasa"] = all(r[f"f{k}"] for k in range(1, 9))
    return r


def ash_spy(spy, hasta):
    """
    El estado del mercado: ASH diario (STOCHASTIC 9/1, ALMA) y semanal de
    semanas CERRADAS (RSI 21/4, ALMA). Usa calc_ash del screener, que es el
    que tiene la paridad de 6,7e-14 con el JS.
    """
    import pandas as pd
    n = int(np.searchsorted(spy["d"], hasta, "right"))
    c = np.asarray(spy["c"][:n], float)
    b, r, _ = calc_ash(pd.DataFrame({"Close": c}), 9, 1, "STOCHASTIC", "ALMA")
    fs, cs = semanal_cerrado(spy["d"][:n], c)
    bw, rw, _ = calc_ash(pd.DataFrame({"Close": cs}), 21, 4, "RSI", "ALMA")
    dia = {"bulls": float(b.iloc[-1]), "bears": float(r.iloc[-1])}
    dia["pausa"] = dia["bears"] > dia["bulls"]
    sem = {"bulls": float(bw.iloc[-1]), "bears": float(rw.iloc[-1]),
           "semana": int(fs[-1]) if fs else None}
    sem["pausa"] = sem["bears"] > 2 * sem["bulls"]
    return {"fecha": int(hasta), "diario": dia, "semanal": sem,
            "pausa": dia["pausa"] or sem["pausa"]}


def prioridad(filas):
    """Percentil del ADR%(20) + percentil del ATR%(14), sobre TODOS los papeles."""
    pa = pct_rank([f["adr"] for f in filas])
    pt = pct_rank([f["atr_pct"] for f in filas])
    for f, a, t in zip(filas, pa, pt):
        f["prio"] = (a + t) * 100 if np.isfinite(a) and np.isfinite(t) else np.nan
    return filas


# ==============================================================================
# 4. EL UNIVERSO DE LA ESTRATEGIA
# ==============================================================================

def cargar_adr(path="estrategia_adr.csv"):
    """local -> ADR ('' = afuera). Una linea rota se saltea, como cedears.csv."""
    from pathlib import Path
    mapa = {}
    p = Path(path)
    if not p.exists():
        return mapa
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.lower().startswith("local,"):
            continue
        partes = [x.strip() for x in ln.split(",")]
        if len(partes) < 2 or not partes[0]:
            continue
        mapa[partes[0]] = partes[1]
    return mapa


def es_etf(grupo):
    return str(grupo or "").startswith("ETF")


def universo_estrategia(simbolos, mapa_adr):
    """
    Los papeles del usuario que entran a la estrategia, en el orden del
    payload: sin ETFs (decision del usuario: en el backtest eran 14 de 608
    operaciones, con -3,3% de promedio), y cada cotizacion local reemplazada
    por su ADR. Si el ADR ya estaba en la lista no se duplica. Devuelve
    (tickers, reemplazos {local: adr}, afuera [locales sin ADR]).
    """
    hay = {s["t"] for s in simbolos}
    vistos, salida, reemp, afuera = set(), [], {}, []
    for s in simbolos:
        t = s["t"]
        if es_etf(s.get("g")):
            continue
        if t in mapa_adr:
            adr = mapa_adr[t]
            if not adr:
                afuera.append(t)
                continue
            reemp[t] = adr
            if adr not in hay:
                afuera.append(t)        # el ADR no vino en los datos
                continue
            t = adr
        elif s.get("mon", "USD") != "USD":
            afuera.append(t)            # otra moneda y sin ADR cargado
            continue
        if t not in vistos:
            vistos.add(t)
            salida.append(t)
    return salida, reemp, afuera
