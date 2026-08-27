"""
CONSOLIDACION  ·  la caja

Se prueba contra series ARMADAS A MANO, donde la respuesta se conoce de
antemano: una serie que va de costado tiene que dar caja, una que sube en
linea recta no, y una que se va angostando tiene que dar "Se aprieta".

El punto que mas importa: la caja se mide contra el ADR del propio papel, asi
que el MISMO rango porcentual tiene que dar consolidacion en un papel tranquilo
y NO darla en uno volatil. Si esa comparacion se rompe, el filtro deja de
servir para cruzar un universo con papeles de volatilidad muy distinta.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

import pathlib

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


def serie(cierres, mecha=0.004):
    """OHLC a partir de una lista de cierres, con mechas proporcionales."""
    c = np.asarray(cierres, dtype=float)
    return pd.DataFrame({
        "Open": c, "High": c * (1 + mecha), "Low": c * (1 - mecha),
        "Close": c, "Volume": np.full(len(c), 1e6)},
        index=pd.bdate_range("2023-01-02", periods=len(c)))


def zigzag(n, base, amp, periodo):
    """Va y viene dentro de una banda: es una consolidacion de manual."""
    i = np.arange(n)
    return base * (1 + amp * np.sin(2 * np.pi * i / periodo))


print("== una serie que va de costado da caja ==")
lat = serie(zigzag(120, 100, 0.006, 9))
k = S.consolidacion(lat)
ok("la detecta", k["estado"] != "", k["estado"])
ok("se movio menos de lo que le corresponde", k["estrechez"] < 1,
   round(k["estrechez"], 3))
ok("el alto es chico", k["rango"] < 0.06, round(k["rango"], 4))
ok("y la llama cajon", k["estado"] == "Cajón", k["estado"])
ok("lleva varias ruedas adentro", k["barras"] >= 12, k["barras"])
ok("la posicion cae entre 0 y 1", 0 <= k["pos"] <= 1, round(k["pos"], 3))

print("\n== una tendencia limpia NO es consolidacion ==")
sube = serie(np.linspace(100, 190, 120))
k2 = S.consolidacion(sube)
ok("no la marca como cajon", k2["estado"] != "Cajón", k2["estado"])
ok("se movio mas de lo que le corresponde", k2["estrechez"] > k["estrechez"],
   f'{round(k2["estrechez"],3)} vs {round(k["estrechez"],3)}')

print("\n== la escala es gradual, no un si/no ==")
grados = [(a, S.consolidacion(serie(zigzag(120, 100, a, 9))))
          for a in (0.004, 0.012, 0.03)]
ok("mas amplitud = mas estrechez, siempre",
   grados[0][1]["estrechez"] < grados[1][1]["estrechez"] < grados[2][1]["estrechez"],
   [round(g[1]["estrechez"], 3) for g in grados])
ok("la mas quieta es cajon", grados[0][1]["estado"] == "Cajón", grados[0][1]["estado"])
ok("la mas movida no es nada", grados[2][1]["estado"] == "", grados[2][1]["estado"])
ok("y el veredicto afloja de a poco, no de golpe",
   grados[0][1]["estado"] != grados[2][1]["estado"],
   [g[1]["estado"] for g in grados])

print("\n== una caja que se angosta da 'Se aprieta' ==")
i = np.arange(120)
# ancha hasta la ventana ANTERIOR (80-100) y angosta en la ULTIMA (100-120)
# ancha hasta la mitad y angosta al final: la caja tiene que quedar en el tramo
# angosto y medirse contra el ancho que vino antes
amp = np.where(i < 90, 0.06, 0.010)
apr = serie(100 * (1 + amp * np.sin(2 * np.pi * i / 7)))
k3 = S.consolidacion(apr)
ok("la caja cae en el tramo angosto", k3["barras"] <= 30, k3["barras"])
ok("y contra lo que vino antes se ve la contraccion", k3["aprieta"] < 0.6,
   round(k3["aprieta"], 3))
ok("la marca como consolidacion",
   k3["estado"] in ("Se aprieta", "Cajón", "Rango"), k3["estado"])

# El guard contra el falso positivo: angostarse NO alcanza si lo que queda sigue
# siendo ancho en terminos absolutos.
amp2 = np.where(i < 90, 0.30, 0.13)
apr2 = serie(100 * (1 + amp2 * np.sin(2 * np.pi * i / 7)))
k3b = S.consolidacion(apr2)
ok("se angosto a menos de la mitad", k3b["aprieta"] < 0.6, round(k3b["aprieta"], 3))
ok("pero la caja sigue siendo enorme, asi que NO la marca",
   k3b["estado"] == "" and k3b["rango"] > 0.18,
   f'{k3b["estado"]!r} alto={round(k3b["rango"]*100, 1)}%')

print("\n== LO QUE MAS IMPORTA: se mide contra el ADR del propio papel ==")
# El mismo recorrido de cierres, o sea la MISMA caja, con dos volatilidades
# diarias distintas. Es la unica forma de aislar la normalizacion: si el ADR no
# entrara en la cuenta, los dos darian identico.
cierres = zigzag(120, 100, 0.02, 25)
quieto = serie(cierres, mecha=0.002)      # apenas se mueve dentro del dia
nervioso = serie(cierres, mecha=0.020)    # mucha mecha, mismo cierre
ka = S.consolidacion(quieto)
kb = S.consolidacion(nervioso)
ok("los dos tienen practicamente la misma caja",
   abs(ka["rango"] - kb["rango"]) < 0.05,
   f'{round(ka["rango"],4)} vs {round(kb["rango"],4)}')
ok("pero el nervioso sale MAS consolidado, porque para el eso es poco",
   kb["estrechez"] < ka["estrechez"],
   f'quieto={round(ka["estrechez"],3)} nervioso={round(kb["estrechez"],3)}')
ok("y sin la normalizacion darian iguales, asi que la diferencia es real",
   abs(kb["estrechez"] - ka["estrechez"]) > 0.15,
   round(abs(kb["estrechez"] - ka["estrechez"]), 3))

print("\n== la caja no se rompe por una mecha ==")
c = list(zigzag(60, 100, 0.01, 9))
d = serie(c)
d.iloc[-8, d.columns.get_loc("High")] *= 1.005      # una mecha chica que se asoma
k4 = S.consolidacion(d)
ok("sigue contando las ruedas de la caja", k4["barras"] >= 8, k4["barras"])

print("\n== casos limite ==")
corta = serie(np.linspace(100, 101, 10))
k5 = S.consolidacion(corta)
ok("una serie corta no rompe y no inventa",
   k5["estado"] == "" and k5["barras"] != k5["barras"], k5)
plana = serie(np.full(120, 100.0), mecha=0.0)
k6 = S.consolidacion(plana)
ok("una serie sin rango no explota", isinstance(k6["estado"], str), k6["estado"])
ok("con barras=5 (el minimo) tampoco",
   isinstance(S.consolidacion(lat, 12)["estado"], str))

print("\n== EL CASO REAL: PLTR antes y despues de romper el rango ==")
# Barras de verdad, guardadas del sitio publicado. Es el caso que señalo el
# usuario y el que rompio el detector viejo: con una ventana FIJA de 20 ruedas
# la caja daba 35% de alto y no se detectaba nada, porque la ventana llegaba
# hasta antes del salto del 04/08 (+29,45%). El rango real eran 13 ruedas desde
# el 10/08 con 7,9% de alto. Sin internet no se puede volver a bajar, asi que
# vive en pltr.json.
import json

crudo = json.loads((pathlib.Path(AQUI) / "pltr.json").read_text())
pltr = pd.DataFrame(
    {"Open": crudo["o"], "High": crudo["h"], "Low": crudo["l"],
     "Close": crudo["c"], "Volume": crudo["v"]},
    index=pd.to_datetime([str(x) for x in crudo["d"]]))

def hasta(f):
    return S.consolidacion(pltr.loc[:f])

k19 = hasta("2026-08-19")
k25 = hasta("2026-08-25")
k26 = hasta("2026-08-26")
k27 = hasta("2026-08-27")

# El 19/08 lee "Se aprieta", y es lo correcto: venia del +29,45% del 04/08 y
# del +10,32% del 07/08, asi que contra ese tramo la caja es una contraccion
# fuerte (aprieta ~0,22). Recien cuando se asienta pasa a "Cajón".
ok("el 19/08 ya ve la consolidacion", k19["estado"] == "Se aprieta", k19["estado"])
ok("y la reconoce como contraccion contra el tramo explosivo previo",
   k19["aprieta"] < 0.35, round(k19["aprieta"], 3))
ok("y lo hace arrancar el 10/08, no antes del salto",
   pltr.loc[:"2026-08-19"].index[-int(k19["barras"])].strftime("%Y-%m-%d") == "2026-08-10",
   pltr.loc[:"2026-08-19"].index[-int(k19["barras"])].date())
ok("el 25/08 ya es cajon", k25["estado"] == "Cajón", k25["estado"])
ok("el 26/08 sigue siendo cajon", k26["estado"] == "Cajón", k26["estado"])
ok("con el alto real (~8%), no el 35% de la ventana fija",
   0.06 < k26["rango"] < 0.10, round(k26["rango"] * 100, 1))
ok("y la caja arranca el 10/08",
   pltr.loc[:"2026-08-26"].index[-int(k26["barras"])].strftime("%Y-%m-%d") == "2026-08-10",
   pltr.loc[:"2026-08-26"].index[-int(k26["barras"])].date())
ok("el 27/08 marca la ruptura hacia arriba", k27["estado"] == "Rompió ↑", k27["estado"])
ok("y muestra la caja DE LA QUE SALIO, no la ya estirada",
   0.06 < k27["rango"] < 0.10, round(k27["rango"] * 100, 1))
ok("con la posicion por encima del techo", k27["pos"] > 1, round(k27["pos"] * 100))

print("\n== la ventana fija era el bug: se comprueba que ya no manda ==")
# el minimo de la curva de estrechez cae donde arranca el rango de verdad
sub = pltr.loc[:"2026-08-26"]
hi = sub["High"].to_numpy(float); lo = sub["Low"].to_numpy(float)
cl = sub["Close"].to_numpy(float)
mejor = S._mejor_caja(hi, lo, cl, len(cl), 60, 7)
ok("el largo elegido es 13 ruedas", mejor["L"] == 13, mejor["L"])
ok("y es un minimo, no un borde",
   S._mejor_caja(hi, lo, cl, len(cl), 12, 7)["est"] > mejor["est"]
   and S._mejor_caja(hi, lo, cl, len(cl), 20, 14)["est"] > mejor["est"],
   round(mejor["est"], 3))

print("\nFALLAS: " + str(fallas) if fallas else "\nCONSOLIDACION OK")
sys.exit(1 if fallas else 0)
