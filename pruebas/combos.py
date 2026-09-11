"""
COMBOS DE EMAs  ·  21/34 · 55/115 · 300/600, y el rVWAP por dias calendario

Reemplaza a paragon.py. El Paragon 100/200 se saco por pedido del usuario, y
con el se fueron la conversion multiplicativa de longitudes y el warmup del
ancla de 4h: estos tres combos anclan a 1D, que ES el timeframe de las barras
que baja el screener, asi que no hay nada que convertir.

Lo que queda de aquel archivo es lo que sigue valiendo: que la EMA es la de
Pine y no la de pandas, que un simbolo joven no se rellena con nada, y las
señales derivadas de la nube. Lo que se agrega es el rVWAP, que cambio de
definicion y es el motivo de este archivo.

Lo que NO se prueba aca: que los numeros coincidan con TradingView para un
simbolo y una fecha concretos. Para eso hacen falta valores sacados del
grafico; desde el entorno de desarrollo no hay salida a internet.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

import numpy as np
import pandas as pd

import screener as S

fallas = 0


def ok(nombre, cond, extra=None):
    global fallas
    if cond:
        print(f"  ok     {nombre}")
    else:
        fallas += 1
        print(f"  FALLA  {nombre}" + (f"   -> {extra}" if extra is not None else ""))


print("== la EMA es la de Pine, no la de pandas ==")
x = pd.Series(np.arange(1, 901, dtype=float))
e600 = S.ema_pine(x, 600)
v = e600.to_numpy()
primero = int(np.argmax(np.isfinite(v))) + 1
ok("EMA600 imprime por primera vez en la vela 600", primero == 600, primero)
ok("la vela 599 es NaN", not np.isfinite(v[598]))
ok("la semilla es la SMA de los primeros 600",
   abs(v[599] - x.iloc[:600].mean()) < 1e-12, f"{v[599]:.6f}")
a = 2 / 601
ok("de ahi en adelante sigue la recursion",
   abs(v[600] - (a * x.iloc[600] + (1 - a) * v[599])) < 1e-12)
ok("NO es ewm(adjust=True)",
   abs(v[-1] - x.ewm(span=600, adjust=True).mean().iloc[-1]) > 1e-6)
ok("NO es ewm(adjust=False)",
   abs(v[-1] - x.ewm(span=600, adjust=False).mean().iloc[-1]) > 1e-6)
e5 = S.ema_pine(pd.Series([1.0, 2, 3]), 5)
ok("con menos velas que el largo devuelve todo NaN",
   bool(e5.isna().all()), e5.tolist())

print("\n== los combos van SIN convertir: el ancla es el propio diario ==")
n = 900
df = pd.DataFrame({
    "Open": np.linspace(100, 300, n), "High": np.linspace(101, 303, n),
    "Low": np.linspace(99, 297, n), "Close": np.linspace(100, 300, n),
    "Volume": np.full(n, 1e6)},
    index=pd.bdate_range("2021-01-04", periods=n))
for clave, (rl, ll) in (("c1", (21, 34)), ("c2", (55, 115)), ("c3", (300, 600))):
    rap, len_ = S.combo_emas(df["Close"], rl, ll)
    ok(f"{clave}: la rapida es exactamente ema_pine(close,{rl})",
       bool(np.allclose(rap.dropna(), S.ema_pine(df["Close"], rl).dropna())))
    prim = int(np.argmax(np.isfinite(len_.to_numpy()))) + 1
    ok(f"{clave}: la lenta imprime recien en la vela {ll}", prim == ll, prim)

print("\n== LA EMA 600 ES LA QUE MANDA CUANTAS BARRAS SE PUBLICAN ==")
# El grafico dibuja 220 velas. Para que la linea de la 600 exista en TODO el
# grafico hacen falta 600 de warmup + 220 de vista = 820, y por eso el sitio
# publica 850 y el periodo subio a 5y. Si alguien vuelve a bajar las barras,
# esta prueba lo dice antes de que salga publicado con la columna vacia.
import argparse  # noqa: E402
import generar_sitio  # noqa: E402
import generar_html  # noqa: E402


def _defaults(mod):
    """Los defaults del argparse de un generador, sin correrlo."""
    guardado = argparse.ArgumentParser.parse_args
    capturado = {}

    def espia(self, *a, **k):
        capturado.update({x.dest: x.default for x in self._actions})
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = espia
    try:
        mod.main()
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.parse_args = guardado
    return capturado


for nombre, mod in (("generar_sitio", generar_sitio), ("generar_html", generar_html)):
    d = _defaults(mod)
    ok(f"{nombre}: publica al menos 600+220 barras",
       d.get("barras", 0) >= 600 + 220, d.get("barras"))
    # Y EL PERIODO SALE DEL MODULO, no escrito a mano. Tenerlo repetido ya costo
    # una corrida: el sitio salio con 754 barras en vez de 850 porque
    # generar_sitio.py tenia su propio "3y".
    ok(f"{nombre}: el periodo es el de screener.PERIODO",
       d.get("periodo") == S.PERIODO, f'{d.get("periodo")!r} vs {S.PERIODO!r}')
corto = df.iloc[-500:]
rap, len_ = S.combo_emas(corto["Close"], 300, 600)
ok("con 500 barras la EMA 600 no imprime NADA (y eso es correcto)",
   bool(len_.isna().all()))
s_corto = S.senales_nube(corto, rap, len_, 1.0)
ok("y el combo queda con sesgo None, no con un numero inventado",
   s_corto["sesgo"] is None, s_corto["sesgo"])

print("\n== rVWAP: la ventana son DIAS CALENDARIO, no velas ==")
# ESTE ES EL BUG QUE SE CORRIGIO. Sobre ruedas (lun-vie) 365 velas abarcan
# ~511 dias calendario, o sea medio año de mas. El corte va por fecha.
rv, llena = S.rvwap_dias(df, 365, "hlc3")
t = df.index[-1]
sel = df.loc[df.index >= t - pd.Timedelta(days=365)]
px = (sel["High"] + sel["Low"] + sel["Close"]) / 3
esperado = float((px * sel["Volume"]).sum() / sel["Volume"].sum())
ok("la ultima vela usa exactamente las fechas >= hoy-365d",
   abs(rv.iloc[-1] - esperado) < 1e-9, f"{rv.iloc[-1]:.6f} vs {esperado:.6f}")
ok("y esas son MENOS de 365 velas, porque son ruedas",
   len(sel) < 365, len(sel))
# el metodo viejo, para dejar medido el error que se corrige
pv = ((df["High"] + df["Low"] + df["Close"]) / 3 * df["Volume"]).cumsum()
cv = df["Volume"].cumsum()
viejo = float((pv.iloc[-1] - pv.iloc[-366]) / (cv.iloc[-1] - cv.iloc[-366]))
abarca = (df.index[-1] - df.index[-366]).days
ok("contar 365 VELAS abarcaba mucho mas de 365 dias", abarca > 450, abarca)
ok("y daba un numero distinto", abs(viejo - esperado) / esperado > 1e-4,
   f"viejo={viejo:.4f} correcto={esperado:.4f}")

# borde inclusivo, en las cuatro ventanas
for d in (7, 30, 90, 365):
    r2, _ = S.rvwap_dias(df, d, "hlc3")
    s2 = df.loc[df.index >= t - pd.Timedelta(days=d)]
    p2 = (s2["High"] + s2["Low"] + s2["Close"]) / 3
    e2 = float((p2 * s2["Volume"]).sum() / s2["Volume"].sum())
    ok(f"ventana de {d}d: borde inclusivo ({len(s2)} ruedas)",
       abs(r2.iloc[-1] - e2) < 1e-9)

print("\n== rVWAP: ventana expansiva ==")
hlc3 = (df["High"] + df["Low"] + df["Close"]) / 3
ok("en la vela 1 es el hlc3 de esa vela",
   abs(rv.iloc[0] - hlc3.iloc[0]) < 1e-9, f"{rv.iloc[0]:.6f}")
ok("al principio marca que la ventana NO esta llena", not bool(llena.iloc[0]))
ok("al final marca que SI", bool(llena.iloc[-1]))
ok("y devuelve valor en todas, nunca NaN", bool(rv.notna().all()))
# la transicion tiene que ser continua: el dia que la ventana se llena no salta
i = int(np.argmax(llena.to_numpy()))
salto = abs(rv.iloc[i] - rv.iloc[i - 1])
tipico = float(np.median(np.abs(np.diff(rv.to_numpy()[i:i + 100]))))
ok("la transicion a ventana movil no tiene salto", salto < tipico * 3 + 1e-9,
   f"salto={salto:.6f} tipico={tipico:.6f}")
for fu in ("hl2", "hlc3", "close"):
    r, _ = S.rvwap_dias(df, 365, fu)
    ok(f"la fuente {fu} devuelve valores finitos", bool(r.notna().all()))

print("\n== simbolos jovenes: NaN y marca, nunca un numero inventado ==")
joven = df.iloc[:20]
r3, l3 = S.combo_emas(joven["Close"], 21, 34)
s3 = S.senales_nube(joven, r3, l3, 1.0)
ok("sin warmup el sesgo queda en None", s3["sesgo"] is None, s3["sesgo"])
ok("y el ancho en NaN", not np.isfinite(s3["ancho"]))
ok("y la posicion vacia, no 'adentro'", s3["pos"] == "", repr(s3["pos"]))

print("\n== señales derivadas ==")
rb2, lb2 = S.combo_emas(df["Close"], 55, 115)
s4 = S.senales_nube(df, rb2, lb2, float(S.calc_atr(df, 14).iloc[-1]))
ok("con la serie subiendo, el sesgo es alcista", s4["sesgo"] is True)
ok("y el precio queda arriba de la nube", s4["pos"] == "arriba", s4["pos"])
ok("el ancho es positivo", s4["ancho"] > 0, s4["ancho"])
ok("la distancia en ATR es finita", np.isfinite(s4["dist_atr"]), s4["dist_atr"])
ok("nunca cruzo, asi que el cruce es NaN", not np.isfinite(s4["cruce"]),
   s4["cruce"])

m = 300
zig = np.concatenate([np.linspace(100, 60, m // 2), np.linspace(60, 140, m - m // 2)])
dfz = pd.DataFrame({"Open": zig, "High": zig * 1.01, "Low": zig * .99,
                    "Close": zig, "Volume": np.full(m, 1e6)},
                   index=pd.bdate_range("2023-01-02", periods=m))
rz, lz = S.combo_emas(dfz["Close"], 21, 34)
sz = S.senales_nube(dfz, rz, lz, 1.0)
ok("con una serie que gira, cuenta las velas desde el cruce",
   np.isfinite(sz["cruce"]) and sz["cruce"] > 0, sz["cruce"])
ok("y el sesgo quedo alcista", sz["sesgo"] is True)

print("\n== el regimen cruza el RAPIDO con el MEDIO, no con el de fondo ==")
# El 300/600 quedo afuera del regimen a pedido del usuario: es la tendencia de
# fondo y vive como filtro propio. Si alguien lo mete adentro, el regimen de un
# papel con menos de 600 ruedas se vaciaria, y eso se nota aca.
# 500 ruedas: alcanzan para el 21/34 y el 55/115, NO para la 600.
f = S.metricas("X", df.iloc[:500], {}, 0.0)
ok("el sesgo del combo de fondo queda en None con 500 ruedas",
   f["c3_sesgo"] is None, f["c3_sesgo"])
ok("y aun asi el regimen existe", f["regimen"] != "", f["regimen"])
ok("y la fila NO queda marcada como sin historial",
   f["sin_historial"] is False, f["sin_historial"])
ok("el regimen sale del c1 y el c2",
   f["regimen_ord"] == (2 if f["c2_sesgo"] else 0) + (1 if f["c1_sesgo"] else 0),
   f["regimen_ord"])

print("\nFALLAS: " + str(fallas) if fallas else "\nCOMBOS OK")
sys.exit(1 if fallas else 0)
