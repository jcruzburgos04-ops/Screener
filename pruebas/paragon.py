"""
PARAGON  ·  EMA 100/200 ancladas y rVWAP 365d

Los cuatro puntos que el usuario pidio verificar antes de dar la parte por
cerrada, mas la comprobacion que cierra la identificacion del indicador.

Lo que NO se prueba aca: que los numeros coincidan con TradingView para un
simbolo y una fecha concretos. Para eso hacen falta valores sacados del
grafico, que el usuario tiene que pasar; desde el entorno de desarrollo no
hay salida a Yahoo ni a TradingView.
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
x = pd.Series(np.arange(1, 501, dtype=float))
e200 = S.ema_pine(x, 200)
v = e200.to_numpy()
primero = int(np.argmax(np.isfinite(v))) + 1
ok("EMA200 imprime por primera vez en la vela 200", primero == 200, primero)
ok("la vela 199 es NaN", not np.isfinite(v[198]))
ok("la semilla es la SMA de los primeros 200",
   abs(v[199] - x.iloc[:200].mean()) < 1e-12, f"{v[199]:.6f}")
a = 2 / 201
ok("de ahi en adelante sigue la recursion",
   abs(v[200] - (a * x.iloc[200] + (1 - a) * v[199])) < 1e-12)
ok("NO es ewm(adjust=True)",
   abs(v[-1] - x.ewm(span=200, adjust=True).mean().iloc[-1]) > 1e-6)
ok("NO es ewm(adjust=False)",
   abs(v[-1] - x.ewm(span=200, adjust=False).mean().iloc[-1]) > 1e-6)
e5 = S.ema_pine(pd.Series([1.0, 2, 3]), 5)
ok("con menos velas que el largo devuelve todo NaN",
   bool(e5.isna().all()), e5.tolist())

print("\n== la conversion de longitudes es multiplicativa, no lineal ==")
# La comprobacion que cierra la identificacion: el Pine original documenta que
# 200 velas de 4h son 33 velas diarias y 100 son 17 (16,67 redondea a 17).
ok("k=6 (cripto): 100 -> 17", S.largo_equivalente(100, 6) == 17,
   S.largo_equivalente(100, 6))
ok("k=6 (cripto): 200 -> 33", S.largo_equivalente(200, 6) == 33,
   S.largo_equivalente(200, 6))
ok("k=2 (rueda de EEUU): 100/200 -> 50/100",
   (S.largo_equivalente(100, 2), S.largo_equivalente(200, 2)) == (50, 100),
   (S.largo_equivalente(100, 2), S.largo_equivalente(200, 2)))
ok("k=1 no cambia nada",
   (S.largo_equivalente(100, 1), S.largo_equivalente(200, 1)) == (100, 200))
# donde la lineal se equivoca: en semanal (k=42 velas de 4h por semana)
lineal = round(100 / 42)
ok("con k grande la lineal y la correcta difieren",
   S.largo_equivalente(100, 42) != lineal,
   f"correcta={S.largo_equivalente(100,42)} lineal={lineal}")
ok("nunca baja de 2", S.largo_equivalente(100, 10000) >= 2)

print("\n== warmup del conjunto A sobre un grafico diario ==")
# 200 velas de 4h son 33,33 dias, asi que la 34a vela diaria es la primera que
# las completa. Es el test que confirma que la reconstruccion esta bien.
n = 120
df = pd.DataFrame({
    "Open": np.linspace(100, 200, n), "High": np.linspace(101, 202, n),
    "Low": np.linspace(99, 198, n), "Close": np.linspace(100, 200, n),
    "Volume": np.full(n, 1e6)},
    index=pd.bdate_range("2024-01-01", periods=n))
rap, len_, lr, ll = S.paragon_conjunto(df["Close"], 100, 200, 6)
ok("con k=6 los largos son 17 y 33", (lr, ll) == (17, 33), (lr, ll))
prim = int(np.argmax(np.isfinite(len_.to_numpy()))) + 1
ok("la nube diaria imprime por primera vez en la vela 34", prim == 34, prim)
ok("en la vela 33 todavia es NaN", not np.isfinite(len_.iloc[32]))

print("\n== conjunto B: exacto sobre diarias ==")
rb, lb, lrb, llb = S.paragon_conjunto(df["Close"], 100, 200, 1)
ok("las longitudes van tal cual", (lrb, llb) == (100, 200), (lrb, llb))
ok("la EMA 100 es identica a ema_pine(close,100)",
   bool(np.allclose(rb.dropna(), S.ema_pine(df["Close"], 100).dropna())))

print("\n== rVWAP: ventana expansiva ==")
rv, llena = S.rvwap_expansivo(df, 365)
hl2 = (df["High"] + df["Low"]) / 2
ok("en la vela 1 es el hl2 de esa vela",
   abs(rv.iloc[0] - hl2.iloc[0]) < 1e-9, f"{rv.iloc[0]:.6f} vs {hl2.iloc[0]:.6f}")
ok("con menos velas que la ventana, marca que no esta llena", llena is False)
ok("y aun asi devuelve valor en todas", bool(rv.notna().all()))

n2 = 400
df2 = pd.DataFrame({
    "High": np.arange(1, n2 + 1) * 1.01, "Low": np.arange(1, n2 + 1) * 0.99,
    "Close": np.arange(1, n2 + 1, dtype=float),
    "Volume": np.full(n2, 1000.0)},
    index=pd.bdate_range("2023-01-02", periods=n2))
rv2, llena2 = S.rvwap_expansivo(df2, 365)
h2 = (df2["High"] + df2["Low"]) / 2
manual = ((h2.iloc[-365:] * df2["Volume"].iloc[-365:]).sum()
          / df2["Volume"].iloc[-365:].sum())
ok("en la vela 400 usa exactamente las ultimas 365",
   abs(rv2.iloc[-1] - manual) < 1e-9, f"{rv2.iloc[-1]:.6f} vs {manual:.6f}")
ok("con 400 velas la ventana ya esta llena", llena2 is True)
# la transicion tiene que ser continua: sin salto entre la vela 365 y la 366
salto = abs(rv2.iloc[365] - rv2.iloc[364])
tipico = float(np.median(np.abs(np.diff(rv2.to_numpy()[300:400]))))
ok("la transicion a ventana movil no tiene salto", salto < tipico * 3,
   f"salto={salto:.6f} tipico={tipico:.6f}")
for fu in ("hl2", "hlc3", "close"):
    r, _ = S.rvwap_expansivo(df2, 365, fu)
    ok(f"la fuente {fu} devuelve valores finitos", bool(r.notna().all()))

print("\n== reindexar a otra grilla ==")
# El equivalente de request.security(..., lookahead_off): para cada vela del
# destino, el ultimo valor del ancla cerrado en o antes de su cierre.
diario = S.ema_pine(df["Close"], 33)
sem = diario.resample("W-FRI").last()
comunes = sem.index.intersection(diario.index)
ok("en las fechas donde las dos grillas coinciden, el valor es el mismo",
   bool(np.allclose(sem.reindex(comunes).dropna(),
                    diario.reindex(comunes).dropna())),
   len(comunes))
ok("el forward fill no mira al futuro",
   bool((diario.reindex(df.index, method="ffill").dropna()
         <= diario.dropna().max() + 1e-9).all()))

print("\n== simbolos jovenes: NaN y marca, nunca un numero inventado ==")
corto = df.iloc[:20]
r3, l3, _, _ = S.paragon_conjunto(corto["Close"], 100, 200, 1)
s3 = S.senales_paragon(corto, r3, l3, 1.0)
ok("sin warmup el sesgo queda en None", s3["sesgo"] is None, s3["sesgo"])
ok("y el ancho en NaN", not np.isfinite(s3["ancho"]))
ok("y la posicion vacia, no 'adentro'", s3["pos"] == "", repr(s3["pos"]))

print("\n== señales derivadas ==")
# hace falta una serie mas larga que el warmup: con 120 velas y largo 200 el
# conjunto todavia no imprimio, que es justo lo que prueba el bloque anterior
nl = 400
dfl = pd.DataFrame({
    "Open": np.linspace(100, 300, nl), "High": np.linspace(101, 303, nl),
    "Low": np.linspace(99, 297, nl), "Close": np.linspace(100, 300, nl),
    "Volume": np.full(nl, 1e6)},
    index=pd.bdate_range("2023-01-02", periods=nl))
rb2, lb2, _, _ = S.paragon_conjunto(dfl["Close"], 100, 200, 1)
s4 = S.senales_paragon(dfl, rb2, lb2, float(S.calc_atr(dfl, 14).iloc[-1]))
ok("con la serie subiendo, el sesgo es alcista", s4["sesgo"] is True)
ok("y el precio queda arriba de la nube", s4["pos"] == "arriba", s4["pos"])
ok("el ancho es positivo", s4["ancho"] > 0, s4["ancho"])
ok("la distancia en ATR es finita", np.isfinite(s4["dist_atr"]), s4["dist_atr"])
ok("nunca cruzo, asi que el cruce es NaN", not np.isfinite(s4["cruce"]),
   s4["cruce"])

# una serie que si cruza
m = 300
zig = np.concatenate([np.linspace(100, 60, m // 2), np.linspace(60, 140, m - m // 2)])
dfz = pd.DataFrame({"Open": zig, "High": zig * 1.01, "Low": zig * .99,
                    "Close": zig, "Volume": np.full(m, 1e6)},
                   index=pd.bdate_range("2023-01-02", periods=m))
rz, lz, _, _ = S.paragon_conjunto(dfz["Close"], 20, 50, 1)
sz = S.senales_paragon(dfz, rz, lz, 1.0)
ok("con una serie que gira, cuenta las velas desde el cruce",
   np.isfinite(sz["cruce"]) and sz["cruce"] > 0, sz["cruce"])
ok("y el sesgo quedo alcista", sz["sesgo"] is True)

print("\nFALLAS: " + str(fallas) if fallas else "\nPARAGON OK")
sys.exit(1 if fallas else 0)
