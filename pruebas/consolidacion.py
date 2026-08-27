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
k = S.consolidacion(lat, 20)
ok("la detecta", k["estado"] != "", k["estado"])
ok("se movio menos de lo que le corresponde", k["estrechez"] < 1,
   round(k["estrechez"], 3))
ok("el alto es chico", k["rango"] < 0.06, round(k["rango"], 4))
ok("y la llama cajon", k["estado"] == "Cajón", k["estado"])
ok("lleva varias ruedas adentro", k["barras"] >= 12, k["barras"])
ok("la posicion cae entre 0 y 1", 0 <= k["pos"] <= 1, round(k["pos"], 3))

print("\n== una tendencia limpia NO es consolidacion ==")
sube = serie(np.linspace(100, 190, 120))
k2 = S.consolidacion(sube, 20)
ok("no la marca como cajon", k2["estado"] != "Cajón", k2["estado"])
ok("se movio mas de lo que le corresponde", k2["estrechez"] > k["estrechez"],
   f'{round(k2["estrechez"],3)} vs {round(k["estrechez"],3)}')

print("\n== la escala es gradual, no un si/no ==")
grados = [(a, S.consolidacion(serie(zigzag(120, 100, a, 9)), 20))
          for a in (0.004, 0.008, 0.02)]
ok("mas amplitud = mas estrechez, siempre",
   grados[0][1]["estrechez"] < grados[1][1]["estrechez"] < grados[2][1]["estrechez"],
   [round(g[1]["estrechez"], 3) for g in grados])
ok("la mas quieta es cajon", grados[0][1]["estado"] == "Cajón", grados[0][1]["estado"])
ok("la del medio afloja a rango", grados[1][1]["estado"] == "Rango", grados[1][1]["estado"])
ok("la mas movida no es nada", grados[2][1]["estado"] == "", grados[2][1]["estado"])

print("\n== una caja que se angosta da 'Se aprieta' ==")
i = np.arange(120)
# ancha hasta la ventana ANTERIOR (80-100) y angosta en la ULTIMA (100-120)
amp = np.where(i < 100, 0.05, 0.0095)
apr = serie(100 * (1 + amp * np.sin(2 * np.pi * i / 7)))
k3 = S.consolidacion(apr, 20)
ok("la mitad nueva es mas angosta que la vieja", k3["aprieta"] < 0.6,
   round(k3["aprieta"], 3))
ok("lo reporta", k3["estado"] in ("Se aprieta", "Cajón"), k3["estado"])

# El guard contra el falso positivo: angostarse NO alcanza si lo que queda sigue
# siendo volatil para ese papel.
amp2 = np.where(i < 100, 0.05, 0.02)
apr2 = serie(100 * (1 + amp2 * np.sin(2 * np.pi * i / 7)))
k3b = S.consolidacion(apr2, 20)
ok("se angosto igual", k3b["aprieta"] < 0.6, round(k3b["aprieta"], 3))
ok("pero sigue siendo volatil, asi que NO la marca",
   k3b["estado"] == "" and k3b["estrechez"] > 1,
   f'{k3b["estado"]!r} estrechez={round(k3b["estrechez"], 3)}')

print("\n== LO QUE MAS IMPORTA: se mide contra el ADR del propio papel ==")
# dos papeles con EXACTAMENTE el mismo rango en la ventana (4%), pero uno
# tranquilo (llega ahi despacio) y otro volatil (rebota de punta a punta).
tranquilo = serie(zigzag(120, 100, 0.02, 40))    # una vuelta lenta
volatil = serie(zigzag(120, 100, 0.02, 3))       # rebota todos los dias
ka = S.consolidacion(tranquilo, 20)
kb = S.consolidacion(volatil, 20)
ok("los dos tienen un rango parecido",
   abs(ka["rango"] - kb["rango"]) < 0.02,
   f'{round(ka["rango"],4)} vs {round(kb["rango"],4)}')
ok("pero el volatil sale MENOS consolidado que el tranquilo",
   kb["estrechez"] > ka["estrechez"],
   f'tranquilo={round(ka["estrechez"],3)} volatil={round(kb["estrechez"],3)}')

print("\n== la caja no se rompe por una mecha ==")
c = list(zigzag(60, 100, 0.01, 9))
d = serie(c)
d.iloc[-8, d.columns.get_loc("High")] *= 1.005      # una mecha chica que se asoma
k4 = S.consolidacion(d, 20)
ok("sigue contando las ruedas de la caja", k4["barras"] >= 8, k4["barras"])

print("\n== casos limite ==")
corta = serie(np.linspace(100, 101, 10))
k5 = S.consolidacion(corta, 20)
ok("una serie corta no rompe y no inventa",
   k5["estado"] == "" and k5["barras"] != k5["barras"], k5)
plana = serie(np.full(120, 100.0), mecha=0.0)
k6 = S.consolidacion(plana, 20)
ok("una serie sin rango no explota", isinstance(k6["estado"], str), k6["estado"])
ok("con barras=5 (el minimo) tampoco",
   isinstance(S.consolidacion(lat, 5)["estado"], str))

print("\nFALLAS: " + str(fallas) if fallas else "\nCONSOLIDACION OK")
sys.exit(1 if fallas else 0)
