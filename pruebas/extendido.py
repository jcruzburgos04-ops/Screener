"""
Pre-market y after-hours: separar las tres sesiones y comparar contra el cierre
que corresponde. Se prueba con barras armadas a mano porque lo que importa es
la regla, no los numeros de Yahoo.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import pandas as pd

from screener import extendido_de_barras

TZ = "America/New_York"


def barras(horas, cierres):
    """horas: ['08:00','09:30',...] del mismo dia."""
    idx = pd.DatetimeIndex([pd.Timestamp(f"2026-08-13 {h}") for h in horas]).tz_localize(TZ)
    return pd.DataFrame({"Open": cierres, "High": cierres, "Low": cierres,
                         "Close": cierres, "Volume": [1000.0] * len(cierres)},
                        index=idx)


print("== after-hours: se compara contra el cierre de HOY ==")
d = barras(["09:30", "12:00", "15:55", "16:05", "17:30"], [100, 102, 105, 106, 107])
e = extendido_de_barras(d)
assert e and e["tipo"] == "post", e
assert abs(e["px"] - 107) < 1e-9, e
# 107 contra el ultimo cierre regular (105) = +1,90%
assert abs(e["pct"] - (107 / 105 - 1)) < 1e-6, e["pct"]   # pct viaja redondeado a 6
print(f"  tipo={e['tipo']}  px={e['px']}  pct={e['pct']*100:+.2f}%  vol={e['vol']}  OK")

print("\n== pre-market: se compara contra el cierre de AYER ==")
d = barras(["04:30", "07:00", "09:15"], [98, 99, 101])
e = extendido_de_barras(d, cierre_previo=100)
assert e and e["tipo"] == "pre", e
assert abs(e["px"] - 101) < 1e-9
assert abs(e["pct"] - 0.01) < 1e-6, e["pct"]   # pct viaja redondeado a 6
print(f"  tipo={e['tipo']}  px={e['px']}  pct={e['pct']*100:+.2f}%  OK")

print("\n== con la rueda abierta no hay extendido ==")
d = barras(["09:30", "11:00", "14:00"], [100, 101, 102])
assert extendido_de_barras(d) is None
print("  devuelve None: OK")

print("\n== el volumen extendido es solo el de afuera de la rueda ==")
d = barras(["09:30", "15:55", "16:05", "17:00"], [100, 105, 106, 107])
e = extendido_de_barras(d)
assert e["vol"] == 2000, e["vol"]
print(f"  vol={e['vol']} (2 barras fuera de hora): OK")

print("\n== 16:00 en punto ya es after-hours ==")
d = barras(["09:30", "15:55", "16:00"], [100, 105, 106])
e = extendido_de_barras(d)
assert e and e["tipo"] == "post", e
print("  OK")

print("\n== 09:29 todavia es pre-market ==")
d = barras(["09:00", "09:29"], [99, 100])
e = extendido_de_barras(d, cierre_previo=98)
assert e and e["tipo"] == "pre", e
print("  OK")

print("\n== casos que no tienen que romper ==")
assert extendido_de_barras(None) is None
assert extendido_de_barras(pd.DataFrame()) is None
sin_tz = pd.DataFrame({"Close": [1, 2], "Volume": [1, 1]},
                      index=pd.DatetimeIndex(["2026-08-13 08:00", "2026-08-13 09:00"]))
assert extendido_de_barras(sin_tz) is None, "sin zona horaria no se puede decidir"
solo_pre = barras(["05:00", "06:00"], [10, 11])
assert extendido_de_barras(solo_pre) is None, "sin referencia no se inventa un %"
assert extendido_de_barras(solo_pre, cierre_previo=10)["pct"] == 0.1
nan = barras(["16:30"], [float("nan")])
assert extendido_de_barras(nan) is None
print("  None, DataFrame vacio, sin zona, sin referencia y con NaN: OK")


print("\n== solo Estados Unidos ==")
# La ventana 9:30-16:00 es la de Nueva York. Aplicarsela a Tokio da cualquier
# cosa: en la primera corrida real los dos unicos "pre-market" que salieron
# fueron 6701.T y 2317.TW.
import screener
llamados = []
screener.yf = None
orig = screener.bajar_extendido


def _falso_download(grupo, **k):
    llamados.extend(grupo)
    raise RuntimeError("no importa el resultado, solo a quien se le pide")


import types
mod = types.ModuleType("yfinance")
mod.download = _falso_download
sys.modules["yfinance"] = mod
screener.bajar_extendido(["AAPL", "MSFT", "6701.T", "2317.TW", "PBR.SA", "BAS.DE", "BRK-B"])
assert "AAPL" in llamados and "BRK-B" in llamados, llamados
assert not any("." in t and not t.startswith("BRK") for t in llamados), llamados
assert "6701.T" not in llamados and "PBR.SA" not in llamados, llamados
print("  pide:", ", ".join(llamados))
print("  saltea Tokio, Taiwan, Sao Paulo y Frankfurt: OK")

print("\nEXTENDIDO OK")
