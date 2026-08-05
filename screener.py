#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SCREENER LOCAL TIPO FINVIZ  ·  ASH (diario + semanal), EMAs, ADR%, RSI, volumen
================================================================================

Motor: Python calcula -> Excel filtra. Gratis, sobre yfinance.

El ASH es una traduccion linea por linea de
"Absolute Strength Histogram v2 | jh" (Pine v4, original de alexgrover),
con una sola diferencia deliberada: el Pine plotea abs(SmthBulls - SmthBears)
y le pone el signo por color. Aca la columna guarda la DIFERENCIA CON SIGNO:

    ASH = SmthBulls - SmthBears

    > 0  la linea verde (bulls) esta por encima de la roja
    < 0  la verde esta por debajo

USO
---
    pip install yfinance pandas numpy openpyxl
    python screener.py --demo                  # prueba sin internet
    python screener.py                         # corrida real
    python screener.py --sin-fundamentales     # sin float/sector, mas rapido
    python screener.py --universo mi.csv --out salida.xlsx --periodo 3y

DONDE TOCAR
-----------
    CFG_ASH   parametros del indicador (iguales a los del Pine)
    FILTROS   el screen. None desactiva el filtro.
================================================================================
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ==============================================================================
# 1. CONFIGURACION
# ==============================================================================

BENCHMARK = "SPY"
PERIODO = "3y"             # 3y da ~150 barras semanales, comodo para el ASH W
MIN_BARRAS = 220           # barras diarias minimas para aceptar un simbolo
MIN_BARRAS_SEM = 30        # barras semanales minimas para calcular el ASH W

# ---- ASH: mismos nombres y defaults que el Pine ------------------------------
#   modo:    "RSI" | "STOCHASTIC" | "ADX"
#   ma_type: "ALMA" | "EMA" | "WMA" | "SMA" | "SMMA" | "HMA"
CFG_ASH = {
    "length": 16,
    "smooth": 4,
    "modo": "RSI",
    "ma_type": "EMA",
    "alma_offset": 0.85,
    "alma_sigma": 6.0,
}

# ---- Otros indicadores -------------------------------------------------------
EMAS = (20, 50)            # las que pediste. Agregar mas es agregar numeros aca.
ADR_LEN = 20               # ventana del Average Daily Range
RSI_LEN = 14
ATR_LEN = 14
ADX_LEN = 14

# ---- EL SCREEN. None = filtro apagado ----------------------------------------
FILTROS = {
    # --- Volumen y liquidez ---
    "vol20_min":           300_000,      # acciones promedio 20 ruedas
    "dolar_vol20_min":     5_000_000,    # volumen en dolares promedio 20 ruedas
    "rel_vol_min":         None,         # volumen de hoy / promedio 20d

    # --- Movimiento ---
    "adr_pct_min":         None,         # ADR% >= X  (3.0 = se mueve 3% por dia)
    "adr_pct_max":         None,
    "atr_pct_max":         None,

    # --- RSI ---
    "rsi14_min":           None,
    "rsi14_max":           None,

    # --- EMAs ---
    "sobre_ema20":         None,         # True / False / None
    "sobre_ema50":         None,
    "ema20_sobre_ema50":   None,

    # --- ASH diario ---
    "ash_d_min":           None,         # valor de la diferencia
    "ash_d_positivo":      None,         # True = verde por encima de roja
    "ash_d_creciendo":     None,         # True = la diferencia se agranda
    "ash_d_barras_cruce_max": None,      # cruce alcista de hace <= N ruedas

    # --- ASH semanal ---
    "ash_w_min":           None,
    "ash_w_positivo":      None,
    "ash_w_creciendo":     None,

    # --- Precio, float, tendencia ---
    "precio_min":          5.0,
    "precio_max":          None,
    "float_musd_min":      None,
    "float_musd_max":      None,
    "float_shares_max_m":  None,
    "rotacion_float_min":  None,
    "adx14_min":           None,
    "dist_max52s_max":     None,         # % maximo por debajo del maximo de 52s
    "rs_rank_min":         None,         # 1..99
}

# Tabla de reglas: (clave_filtro, columna, operador)
REGLAS = [
    ("vol20_min",          "vol20",           "ge"),
    ("dolar_vol20_min",    "dolar_vol20",     "ge"),
    ("rel_vol_min",        "rel_vol",         "ge"),
    ("adr_pct_min",        "adr_pct",         "ge"),
    ("adr_pct_max",        "adr_pct",         "le"),
    ("atr_pct_max",        "atr_pct",         "le"),
    ("rsi14_min",          "rsi14",           "ge"),
    ("rsi14_max",          "rsi14",           "le"),
    ("sobre_ema20",        "sobre_ema20",     "bool"),
    ("sobre_ema50",        "sobre_ema50",     "bool"),
    ("ema20_sobre_ema50",  "ema20_sobre_ema50", "bool"),
    ("ash_d_min",          "ash_d",           "ge"),
    ("ash_d_positivo",     "ash_d_positivo",  "bool"),
    ("ash_d_creciendo",    "ash_d_creciendo", "bool"),
    ("ash_w_min",          "ash_w",           "ge"),
    ("ash_w_positivo",     "ash_w_positivo",  "bool"),
    ("ash_w_creciendo",    "ash_w_creciendo", "bool"),
    ("precio_min",         "precio",          "ge"),
    ("precio_max",         "precio",          "le"),
    ("float_musd_min",     "float_musd",      "ge"),
    ("float_musd_max",     "float_musd",      "le"),
    ("float_shares_max_m", "float_shares_m",  "le"),
    ("rotacion_float_min", "rotacion_float",  "ge"),
    ("adx14_min",          "adx14",           "ge"),
    ("rs_rank_min",        "rs_rank",         "ge"),
]

# Columnas del Excel: (clave, titulo, formato)
COLUMNAS = [
    ("ticker",            "Ticker",          "@"),
    ("local",             "Local/CEDEAR",    "@"),
    ("grupo",             "Grupo",           "@"),
    ("nombre",            "Nombre",          "@"),
    ("sector",            "Sector",          "@"),
    ("industria",         "Industria",       "@"),
    ("pais",              "Pais",            "@"),
    ("precio",            "Precio",          "#,##0.00"),
    ("chg_pct",           "Chg %",           "0.0%"),
    # --- ASH ---
    ("ash_d",             "ASH D",           "#,##0.0000"),
    ("ash_d_pend",        "ASH D pend",      "#,##0.0000"),
    ("ash_d_norm",        "ASH D norm",      "0.000"),
    ("ash_d_barras_cruce", "ASH D barras",   "0"),
    ("ash_w",             "ASH W",           "#,##0.0000"),
    ("ash_w_pend",        "ASH W pend",      "#,##0.0000"),
    ("ash_w_norm",        "ASH W norm",      "0.000"),
    ("ash_bulls_d",       "Bulls D",         "#,##0.0000"),
    ("ash_bears_d",       "Bears D",         "#,##0.0000"),
    # --- Momentum / volatilidad ---
    ("rsi14",             "RSI 14",          "0.0"),
    ("adr_pct",           "ADR %",           "0.00"),
    ("atr_pct",           "ATR %",           "0.00"),
    ("adx14",             "ADX 14",          "0.0"),
    # --- EMAs ---
    ("vs_ema20",          "vs EMA20 %",      "0.0%"),
    ("vs_ema50",          "vs EMA50 %",      "0.0%"),
    ("sobre_ema20",       "Sobre EMA20",     "@"),
    ("sobre_ema50",       "Sobre EMA50",     "@"),
    ("ema20_sobre_ema50", "EMA20>EMA50",     "@"),
    # --- Performance ---
    ("perf_1s",           "1 sem",           "0.0%"),
    ("perf_1m",           "1 mes",           "0.0%"),
    ("perf_3m",           "3 meses",         "0.0%"),
    ("perf_6m",           "6 meses",         "0.0%"),
    ("perf_12m",          "12 meses",        "0.0%"),
    ("rs_3m",             "RS 3m vs bench",  "0.0%"),
    ("rs_rank",           "RS rank",         "0"),
    ("dist_max52s",       "Desde max 52s %", "0.0%"),
    ("dist_min52s",       "Sobre min 52s %", "0.0%"),
    # --- Volumen y float ---
    ("volumen",           "Volumen",         "#,##0"),
    ("vol20",             "Vol prom 20d",    "#,##0"),
    ("rel_vol",           "Rel volumen",     "0.00"),
    ("dolar_vol20",       "$ Vol 20d",       "#,##0"),
    ("float_shares_m",    "Float (M acc)",   "#,##0.0"),
    ("float_musd",        "Float ($M)",      "#,##0"),
    ("rotacion_float",    "Rotacion float",  "0.000"),
    ("mcap_musd",         "Market cap ($M)", "#,##0"),
]

MAPA_CEDEARS = Path("cedears.csv")   # local -> subyacente que cotiza afuera

CACHE_PRECIOS = Path("cache_precios.pkl")   # lo reusa la app web
CACHE_META = Path("cache_fundamentales.json")
CACHE_DIAS = 7


# ==============================================================================
# 2. MEDIAS MOVILES (las seis del Pine)
# ==============================================================================

def sma(s, n):
    return s.rolling(int(n), min_periods=int(n)).mean()


def ema(s, n):
    return s.ewm(span=int(n), adjust=False).mean()


def _conv(s, pesos):
    """Media movil por convolucion: mismo resultado que un rolling, mas rapido."""
    n = len(pesos)
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = np.convolve(x, pesos[::-1], mode="valid")
    return pd.Series(out, index=s.index)


def wma(s, n):
    n = int(n)
    w = np.arange(1.0, n + 1.0)
    return _conv(s, w / w.sum())


def alma(s, n, offset=0.85, sigma=6.0):
    n = int(n)
    m = offset * (n - 1)
    d = n / float(sigma)
    i = np.arange(n, dtype=float)
    w = np.exp(-((i - m) ** 2) / (2 * d * d))
    return _conv(s, w / w.sum())


def hma(s, n):
    n = int(n)
    return wma(2 * wma(s, n // 2) - wma(s, n), int(round(np.sqrt(n))))


def smma(s, n):
    """
    Replica literal del SMMA del Pine de referencia:

        w = wma(src, len)
        result := na(w[1]) ? sma(src, len) : (w[1]*(len-1) + src) / len

    Ojo: NO es la SMMA recursiva clasica (Wilder). El `result` del Pine no se
    referencia a si mismo, usa la WMA de la barra anterior. Lo dejo igual para
    que los numeros coincidan con el indicador del grafico.
    """
    n = int(n)
    w = wma(s, n)
    r = (w.shift(1) * (n - 1) + s) / n
    return r.fillna(sma(s, n))


def rma(s, n):
    """Media de Wilder. No esta en el Pine del ASH, pero RSI/ADX/ATR la usan."""
    return s.ewm(alpha=1.0 / int(n), adjust=False).mean()


def ma(tipo, s, n, alma_offset=0.85, alma_sigma=6.0):
    t = tipo.upper()
    if t == "SMA":
        return sma(s, n)
    if t == "EMA":
        return ema(s, n)
    if t == "WMA":
        return wma(s, n)
    if t == "SMMA":
        return smma(s, n)
    if t == "HMA":
        return hma(s, n)
    if t == "ALMA":
        return alma(s, n, alma_offset, alma_sigma)
    raise ValueError(f"MA desconocida: {tipo}")


# ==============================================================================
# 3. ASH
# ==============================================================================

def calc_ash(df, length=9, smooth=3, modo="RSI", ma_type="WMA",
             alma_offset=0.85, alma_sigma=6.0, src="Close"):
    """
    Absolute Strength Histogram v2 (jh / alexgrover), traducido de Pine v4.

    Devuelve (SmthBulls, SmthBears, SmthBulls - SmthBears).
    El tercer elemento es la diferencia CON SIGNO: positiva = verde arriba.
    """
    price = df[src]
    modo = modo.upper()
    kw = dict(alma_offset=alma_offset, alma_sigma=alma_sigma)

    # Price1 = sma(src,1) = src   ·   Price2 = sma(src[1],1) = src[1]
    p1, p2 = price, price.shift(1)

    if modo == "RSI":
        d = p1 - p2
        bulls = 0.5 * (d.abs() + d)
        bears = 0.5 * (d.abs() - d)
    elif modo in ("STOCHASTIC", "STOCH"):
        # El Pine usa Price1 (el cierre) para el lowest y el highest,
        # no el minimo y el maximo de la barra.
        bulls = p1 - p1.rolling(int(length), min_periods=int(length)).min()
        bears = p1.rolling(int(length), min_periods=int(length)).max() - p1
    elif modo == "ADX":
        h, l = df["High"], df["Low"]
        dh = h - h.shift(1)
        dl = l.shift(1) - l
        bulls = 0.5 * (dh.abs() + dh)
        bears = 0.5 * (dl.abs() + dl)
    else:
        raise ValueError(f"modo ASH desconocido: {modo}")

    avg_bulls = ma(ma_type, bulls, length, **kw)
    avg_bears = ma(ma_type, bears, length, **kw)
    smth_bulls = ma(ma_type, avg_bulls, smooth, **kw)
    smth_bears = ma(ma_type, avg_bears, smooth, **kw)
    return smth_bulls, smth_bears, smth_bulls - smth_bears


def ash_norm(bulls, bears):
    """
    (bulls - bears) / (bulls + bears), acotado a [-1, 1].

    El ASH crudo esta en unidades de precio: un papel de USD 500 muestra
    numeros mas grandes que uno de USD 20 aunque la fuerza sea la misma.
    El signo del crudo si sirve (es lo que pediste); esta version ademas
    permite ORDENAR el universo de mayor a menor fuerza. Las dos estan en
    el Excel.
    """
    b, s = float(bulls), float(bears)
    t = b + s
    if not np.isfinite(t) or t == 0:
        return np.nan
    return (b - s) / t


# ==============================================================================
# 4. RESTO DE INDICADORES
# ==============================================================================

def calc_rsi(c, n=14):
    d = c.diff()
    gan = rma(d.clip(lower=0), n)
    per = rma(-d.clip(upper=0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100 - 100 / (1 + gan / per)
    return r.mask((gan == 0) & (per == 0), 50.0)


def calc_atr(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def calc_adx(df, n=14):
    h, l = df["High"], df["Low"]
    up, dn = h.diff(), -l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr = calc_atr(df, n)
    pdi = 100 * rma(plus, n) / atr
    mdi = 100 * rma(minus, n) / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return rma(dx, n)


def calc_adr_pct(df, n=20):
    """
    ADR% = 100 * (promedio de High/Low de las ultimas n ruedas - 1).

    Es el "cuanto se mueve por dia" en porcentaje, la version que usan los
    swing traders. Distinto del ATR%: el ADR ignora los gaps.
    """
    return 100 * (sma(df["High"] / df["Low"], n) - 1)


def barras_desde_cruce(hist):
    """Barras transcurridas desde el ultimo cambio de signo del histograma."""
    h = hist.dropna()
    if len(h) < 2:
        return np.nan
    signo = np.sign(h.to_numpy())
    idx = np.where(signo[1:] != signo[:-1])[0]
    if len(idx) == 0:
        return np.nan
    return int(len(signo) - 1 - (idx[-1] + 1))


def perf(c, barras):
    if len(c) <= barras:
        return np.nan
    return float(c.iloc[-1] / c.iloc[-1 - barras] - 1)


def a_semanal(df):
    """Arma barras semanales (cierre viernes) a partir de las diarias."""
    w = df.resample("W-FRI").agg({"Open": "first", "High": "max", "Low": "min",
                                  "Close": "last", "Volume": "sum"})
    return w.dropna(subset=["Close"])


# ==============================================================================
# 5. DATOS
# ==============================================================================

def cargar_mapa_cedears(path=MAPA_CEDEARS):
    """
    Mapa   ticker local  ->  simbolo del subyacente donde realmente cotiza.

    Los indicadores NUNCA se calculan sobre el CEDEAR: su precio mezcla el
    movimiento del papel con el tipo de cambio implicito, asi que el ASH, el
    RSI y el ADR saldrian contaminados. Se baja el subyacente y listo.
    """
    mapa = {}
    p = Path(path)
    if not p.exists():
        return mapa
    for linea in p.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = [x.strip().upper() for x in linea.split(",")]
        if partes[0] in ("LOCAL", "CEDEAR", "TICKER"):
            continue
        if len(partes) >= 2 and partes[1]:
            clave = partes[0]
        if clave.endswith(".BA"):
            clave = clave[:-3]
        mapa[clave] = partes[1]
    return mapa


def leer_universo(path, mapa=None):
    """
    universo.csv:   ticker , grupo , [subyacente]

    - Si el ticker termina en .BA se reemplaza por su subyacente, buscandolo
      primero en la tercera columna y despues en cedears.csv.
    - Si no hay forma de resolverlo, se avisa y se descarta: bajar el CEDEAR
      daria indicadores equivocados, que es peor que no tenerlos.
    """
    mapa = mapa if mapa is not None else cargar_mapa_cedears()
    p = Path(path)
    if not p.exists():
        sys.exit(f"[X] No encuentro el archivo de universo: {p}")

    filas, sin_resolver = [], []
    for linea in p.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = [x.strip() for x in linea.split(",")]
        if partes[0].lower() in ("ticker", "simbolo", "symbol"):
            continue
        crudo = partes[0].upper()
        grupo = partes[1] if len(partes) > 1 else ""
        explicito = partes[2].upper() if len(partes) > 2 and partes[2] else ""

        local, descarga = "", crudo
        if explicito:
            local, descarga = (crudo, explicito) if explicito != crudo else ("", crudo)
        elif crudo.endswith(".BA"):
            base = crudo[:-3]
            if base in mapa:
                local, descarga = crudo, mapa[base]
            else:
                sin_resolver.append(crudo)
                continue
        filas.append({"ticker": descarga, "grupo": grupo, "local": local})

    if sin_resolver:
        print(f"    [!] sin subyacente conocido, los salteo: {', '.join(sin_resolver)}")
        print("        agregalos a cedears.csv o poné el subyacente en la 3a columna")

    df = pd.DataFrame(filas).drop_duplicates("ticker")
    if df.empty:
        sys.exit("[X] El universo quedo vacio.")
    return df


def bajar_precios(tickers, periodo, lote=100):
    import yfinance as yf
    datos = {}
    for i in range(0, len(tickers), lote):
        grupo = tickers[i:i + lote]
        print(f"    lote {i // lote + 1}: {len(grupo)} simbolos...", flush=True)
        try:
            raw = yf.download(grupo, period=periodo, interval="1d",
                              auto_adjust=True, group_by="ticker",
                              threads=True, progress=False)
        except Exception as e:
            print(f"    [!] fallo el lote: {e}")
            continue
        for t in grupo:
            try:
                d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                d = d.dropna(subset=["Close"])
                if len(d) >= MIN_BARRAS:
                    datos[t] = d
            except Exception:
                pass
        time.sleep(0.6)
    return datos


def bajar_fundamentales(tickers, usar_cache=True):
    import yfinance as yf
    cache = {}
    if usar_cache and CACHE_META.exists():
        try:
            cache = json.loads(CACHE_META.read_text())
        except Exception:
            cache = {}
    ahora = datetime.now(timezone.utc).timestamp()
    faltan = [t for t in tickers
              if t not in cache or ahora - cache[t].get("_ts", 0) > CACHE_DIAS * 86400]
    print(f"    {len(tickers) - len(faltan)} en cache, {len(faltan)} a descargar")

    def uno(t):
        try:
            i = yf.Ticker(t).get_info()
            return t, {"nombre": i.get("shortName") or i.get("longName") or "",
                       "sector": i.get("sector") or "",
                       "industria": i.get("industry") or "",
                       "pais": i.get("country") or "",
                       "float_shares": i.get("floatShares"),
                       "shares_out": i.get("sharesOutstanding"),
                       "mcap": i.get("marketCap"), "_ts": ahora}
        except Exception:
            return t, {"nombre": "", "sector": "", "industria": "", "pais": "",
                       "float_shares": None, "shares_out": None, "mcap": None,
                       "_ts": ahora}

    if faltan:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for n, (t, d) in enumerate(ex.map(uno, faltan), 1):
                cache[t] = d
                if n % 50 == 0:
                    print(f"      {n}/{len(faltan)}", flush=True)
        try:
            CACHE_META.write_text(json.dumps(cache))
        except Exception as e:
            print(f"    [!] no pude guardar el cache: {e}")
    return cache


def guardar_precios(datos, meta=None, path=CACHE_PRECIOS):
    """Deja los precios en disco para que la app web no vuelva a bajarlos."""
    import pickle
    with open(path, "wb") as fh:
        pickle.dump({"precios": datos, "meta": meta or {},
                     "fecha": datetime.now().isoformat(timespec="minutes")}, fh)


def cargar_precios(path=CACHE_PRECIOS):
    """Devuelve (precios, meta, fecha) o (None, None, None) si no hay cache."""
    import pickle
    p = Path(path)
    if not p.exists():
        return None, None, None
    try:
        with open(p, "rb") as fh:
            d = pickle.load(fh)
        return d["precios"], d.get("meta", {}), d.get("fecha", "")
    except Exception:
        return None, None, None


def datos_demo(tickers, n=760, semilla=7):
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


# ==============================================================================
# 6. METRICAS
# ==============================================================================

def metricas(t, df, meta, bench_perf, cfg_ash=None, emas=None, adr_len=None,
             rsi_len=None, atr_len=None, adx_len=None, historial=0):
    """
    Calcula todas las metricas de un simbolo.

    Los parametros vienen por argumento (no de las constantes) para que la app
    web pueda recalcular con la configuracion que el usuario elija sin tocar
    el modulo. Si no se pasan, se usan los defaults de arriba.

    historial: si es > 0, agrega las ultimas N barras del ASH como lista, para
    dibujar el sparkline en la tabla.
    """
    cfg = dict(cfg_ash or CFG_ASH)
    emas = tuple(emas or EMAS)
    adr_len = adr_len or ADR_LEN
    rsi_len = rsi_len or RSI_LEN
    atr_len = atr_len or ATR_LEN
    adx_len = adx_len or ADX_LEN

    c, v = df["Close"], df["Volume"]
    px = float(c.iloc[-1])

    # --- ASH diario ---
    bu, be, ash_d = calc_ash(df, **cfg)

    # --- ASH semanal (barras armadas desde las diarias) ---
    sem = a_semanal(df)
    if len(sem) >= MIN_BARRAS_SEM:
        buw, bew, ash_w = calc_ash(sem, **cfg)
        w_val = float(ash_w.iloc[-1])
        w_prev = float(ash_w.iloc[-2])
        w_norm = ash_norm(buw.iloc[-1], bew.iloc[-1])
    else:
        w_val = w_prev = w_norm = np.nan

    e = {n: ema(c, n) for n in emas}
    vol20 = float(v.rolling(20).mean().iloc[-1])
    vent = min(len(c), 252)
    max52, min52 = float(c.iloc[-vent:].max()), float(c.iloc[-vent:].min())

    fs = meta.get("float_shares") or meta.get("shares_out")
    fs = float(fs) if fs else np.nan
    mcap = meta.get("mcap")
    mcap = float(mcap) if mcap else np.nan

    d_val, d_prev = float(ash_d.iloc[-1]), float(ash_d.iloc[-2])
    p3m = perf(c, 63)

    f = {
        "ticker": t,
        "nombre": meta.get("nombre", ""),
        "sector": meta.get("sector", ""),
        "industria": meta.get("industria", ""),
        "pais": meta.get("pais", ""),
        "precio": px,
        "chg_pct": perf(c, 1),

        "ash_d": d_val,
        "ash_d_pend": d_val - d_prev,
        "ash_d_norm": ash_norm(bu.iloc[-1], be.iloc[-1]),
        "ash_d_positivo": bool(d_val > 0),
        "ash_d_creciendo": bool(d_val > d_prev),
        "ash_d_barras_cruce": barras_desde_cruce(ash_d),
        "ash_bulls_d": float(bu.iloc[-1]),
        "ash_bears_d": float(be.iloc[-1]),

        "ash_w": w_val,
        "ash_w_pend": w_val - w_prev,
        "ash_w_norm": w_norm,
        "ash_w_positivo": bool(w_val > 0) if w_val == w_val else False,
        "ash_w_creciendo": bool(w_val > w_prev) if w_val == w_val else False,

        "rsi14": float(calc_rsi(c, rsi_len).iloc[-1]),
        "adr_pct": float(calc_adr_pct(df, adr_len).iloc[-1]),
        "atr_pct": float(calc_atr(df, atr_len).iloc[-1] / px * 100),
        "adx14": float(calc_adx(df, adx_len).iloc[-1]),

        "perf_1s": perf(c, 5), "perf_1m": perf(c, 21), "perf_3m": p3m,
        "perf_6m": perf(c, 126), "perf_12m": perf(c, 252),
        "rs_3m": (p3m - bench_perf) if (p3m == p3m and bench_perf == bench_perf) else np.nan,
        "dist_max52s": px / max52 - 1,
        "dist_min52s": px / min52 - 1,

        "volumen": float(v.iloc[-1]),
        "vol20": vol20,
        "rel_vol": float(v.iloc[-1] / vol20) if vol20 else np.nan,
        "dolar_vol20": float((c * v).rolling(20).mean().iloc[-1]),
        "float_shares_m": fs / 1e6 if fs == fs else np.nan,
        "float_musd": fs * px / 1e6 if fs == fs else np.nan,
        "rotacion_float": vol20 / fs if (fs == fs and fs) else np.nan,
        "mcap_musd": mcap / 1e6 if mcap == mcap else np.nan,
    }
    for n in emas:
        f[f"vs_ema{n}"] = px / float(e[n].iloc[-1]) - 1
        f[f"sobre_ema{n}"] = bool(px > float(e[n].iloc[-1]))
    if 20 in emas and 50 in emas:
        f["ema20_sobre_ema50"] = bool(e[20].iloc[-1] > e[50].iloc[-1])
    if historial:
        f["serie_d"] = [float(x) for x in ash_d.dropna().iloc[-historial:]]
        f["serie_w"] = ([float(x) for x in ash_w.dropna().iloc[-historial:]]
                        if w_val == w_val else [])
    return f


def aplicar_filtros(df, filtros):
    m = pd.Series(True, index=df.index)
    for clave, col, op in REGLAS:
        val = filtros.get(clave)
        if val is None or col not in df.columns:
            continue
        if op == "ge":
            m &= df[col] >= val
        elif op == "le":
            m &= df[col] <= val
        elif op == "bool":
            m &= df[col].astype(bool) == bool(val)

    v = filtros.get("ash_d_barras_cruce_max")
    if v is not None:
        m &= (df["ash_d_barras_cruce"] <= v) & (df["ash_d"] > 0)
    v = filtros.get("dist_max52s_max")
    if v is not None:
        m &= df["dist_max52s"] >= -abs(v) / 100
    return m.fillna(False)


# ==============================================================================
# 7. EXCEL
# ==============================================================================

def asegurar_columnas_emas(emas):
    """Agrega al Excel las columnas de las EMAs que se hayan configurado."""
    claves = {k for k, _, _ in COLUMNAS}
    pos = next(i for i, (k, _, _) in enumerate(COLUMNAS) if k == "vs_ema20")
    for n in emas:
        for clave, titulo, fmt in ((f"vs_ema{n}", f"vs EMA{n} %", "0.0%"),
                                   (f"sobre_ema{n}", f"Sobre EMA{n}", "@")):
            if clave not in claves:
                COLUMNAS.insert(pos, (clave, titulo, fmt))
                pos += 1


def exportar(df_todo, df_filtrado, salida, notas):
    from openpyxl import Workbook
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    fuente = "Arial"
    head_fill = PatternFill("solid", fgColor="1F3864")
    head_font = Font(name=fuente, bold=True, color="FFFFFF", size=10)
    body_font = Font(name=fuente, size=10)
    borde = Border(bottom=Side(style="thin", color="D9D9D9"))
    verde = Font(name=fuente, size=10, color="1E7B34", bold=True)
    rojo = Font(name=fuente, size=10, color="B02418", bold=True)

    def hoja(nombre, datos):
        ws = wb.create_sheet(nombre)
        claves = [k for k, _, _ in COLUMNAS if k in datos.columns]
        titulos = {k: h for k, h, _ in COLUMNAS}
        formatos = {k: f for k, _, f in COLUMNAS}
        for j, k in enumerate(claves, 1):
            cl = ws.cell(row=1, column=j, value=titulos[k])
            cl.fill, cl.font = head_fill, head_font
            cl.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for i, (_, r) in enumerate(datos.iterrows(), 2):
            for j, k in enumerate(claves, 1):
                v = r[k]
                if isinstance(v, (bool, np.bool_)):
                    v = "SI" if v else "NO"
                elif isinstance(v, (float, np.floating)):
                    v = None if pd.isna(v) else float(v)
                elif isinstance(v, (int, np.integer)):
                    v = int(v)
                cel = ws.cell(row=i, column=j, value=v)
                cel.border = borde
                cel.number_format = formatos[k]
                if k in ("ash_d", "ash_w") and isinstance(v, float):
                    cel.font = verde if v > 0 else rojo
                else:
                    cel.font = body_font
        n = len(datos) + 1
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(claves))}{n}"
        ws.row_dimensions[1].height = 32
        anchos = {"nombre": 26, "industria": 26, "sector": 20, "pais": 14,
                  "ticker": 10, "grupo": 14}
        for j, k in enumerate(claves, 1):
            ws.column_dimensions[get_column_letter(j)].width = anchos.get(k, 12)
        for k in ("ash_d_norm", "ash_w_norm", "rs_rank", "adr_pct"):
            if k in claves and n > 1:
                col = get_column_letter(claves.index(k) + 1)
                ws.conditional_formatting.add(
                    f"{col}2:{col}{n}",
                    ColorScaleRule(start_type="min", start_color="F8696B",
                                   mid_type="percentile", mid_value=50, mid_color="FFEB84",
                                   end_type="max", end_color="63BE7B"))
        return ws

    hoja("Filtrado", df_filtrado)
    hoja("Universo", df_todo)
    ws = wb.create_sheet("Config")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 50
    for i, (a, b) in enumerate(notas, 1):
        ws.cell(row=i, column=1, value=a).font = Font(name=fuente, bold=True, size=10)
        ws.cell(row=i, column=2, value=str(b)).font = Font(name=fuente, size=10)
    wb.save(salida)


# ==============================================================================
# 8. MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser(description="Screener local con ASH diario y semanal")
    ap.add_argument("--universo", default="universo.csv")
    ap.add_argument("--out", default="screener.xlsx")
    ap.add_argument("--periodo", default=PERIODO)
    ap.add_argument("--sin-fundamentales", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--usar-cache", action="store_true",
                    help="usa los precios ya bajados (cache_precios.pkl)")
    args = ap.parse_args()

    t0 = time.time()
    uni = leer_universo(args.universo)
    tickers = uni["ticker"].tolist()
    grupos = dict(zip(uni["ticker"], uni["grupo"]))
    locales = dict(zip(uni["ticker"], uni["local"]))
    print(f"[1/5] Universo: {len(tickers)} simbolos")

    print("[2/5] Precios diarios...")
    pedir = tickers if BENCHMARK in tickers else tickers + [BENCHMARK]
    if args.demo:
        precios = datos_demo(pedir)
    elif args.usar_cache:
        precios, _, fecha = cargar_precios()
        if precios is None:
            sys.exit("[X] No hay cache de precios. Corré sin --usar-cache primero.")
        print(f"      cache del {fecha}")
    else:
        precios = bajar_precios(pedir, args.periodo)
    bench = precios.get(BENCHMARK)
    if BENCHMARK not in tickers:
        precios.pop(BENCHMARK, None)
    bench_perf = perf(bench["Close"], 63) if bench is not None else np.nan
    faltantes = [t for t in tickers if t not in precios]
    print(f"      {len(precios)} con datos, {len(faltantes)} descartados")

    if not args.demo and not args.usar_cache:
        guardar_precios(precios)

    print("[3/5] Fundamentales...")
    meta = ({t: {} for t in precios} if (args.sin_fundamentales or args.demo)
            else bajar_fundamentales(list(precios.keys())))

    print("[4/5] Indicadores (ASH D + ASH W, EMAs, ADR, RSI)...")
    filas = []
    for t, d in precios.items():
        try:
            f = metricas(t, d, meta.get(t, {}), bench_perf)
            f["grupo"] = grupos.get(t, "")
            f["local"] = locales.get(t, "")
            filas.append(f)
        except Exception as e:
            print(f"      [!] {t}: {e}")
    df = pd.DataFrame(filas)
    if df.empty:
        sys.exit("[X] Ningun simbolo con datos. Revisa conexion, tickers o MIN_BARRAS.")

    df["rs_rank"] = (df["perf_3m"].rank(pct=True) * 98 + 1).round()
    mask = aplicar_filtros(df, FILTROS)
    df = df.sort_values("ash_d_norm", ascending=False)
    df_f = df[mask.reindex(df.index, fill_value=False)]
    print(f"      {len(df_f)} de {len(df)} pasan el filtro")

    print("[5/5] Excel...")
    asegurar_columnas_emas(EMAS)
    notas = [("Generado", datetime.now().strftime("%Y-%m-%d %H:%M")),
             ("Universo", f"{len(tickers)} simbolos ({args.universo})"),
             ("Con datos", len(df)), ("Pasan el filtro", len(df_f)),
             ("Descartados", ", ".join(faltantes) if faltantes else "ninguno"),
             ("Periodo", args.periodo), ("Benchmark", BENCHMARK), ("", ""),
             ("--- ASH ---", "Absolute Strength Histogram v2 | jh"),
             ("columna ASH", "SmthBulls - SmthBears (con signo)"),
             ("modo", CFG_ASH["modo"]), ("length", CFG_ASH["length"]),
             ("smooth", CFG_ASH["smooth"]), ("ma_type", CFG_ASH["ma_type"]),
             ("semanal", "barras W-FRI armadas desde las diarias"), ("", ""),
             ("--- Otros ---", ""),
             ("EMAs", ", ".join(str(x) for x in EMAS)),
             ("ADR", f"{ADR_LEN} ruedas"), ("RSI", RSI_LEN), ("", ""),
             ("--- Filtros activos ---", "")] + \
            [(k, v) for k, v in FILTROS.items() if v is not None]
    exportar(df, df_f, args.out, notas)
    print(f"\nListo -> {args.out}   ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
