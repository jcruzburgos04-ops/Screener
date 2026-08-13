"""
La actualizacion rapida: el camino que mantiene el sitio fresco durante la
rueda sin rehacer el historial. Se prueba con Yahoo simulado, porque lo que
importa verificar es la fusion: que no se pierda historial, que no se dupliquen
fechas y que la barra provisoria de la corrida anterior se pise.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)

import json
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from fixtura import armar

tmp = Path(tempfile.mkdtemp())
previo_dir = tmp / "previo"
previo_dir.mkdir()
armar(str(previo_dir), barras=400)
previo = json.loads((previo_dir / "datos.json").read_text())
antes = {s["t"]: (len(s["d"]), s["d"][-1], s["c"][-1]) for s in previo["simbolos"]}
print(f"payload previo: {len(previo['simbolos'])} simbolos, "
      f"ultimo cierre {previo['ultimo_cierre']}, {previo['atrasados']} atrasados")

# Yahoo simulado: devuelve el ultimo mes, con la ultima barra corrida un dia
# y un cierre distinto (que es lo que pasa a mitad de rueda).
ultima = max(s["d"][-1] for s in previo["simbolos"])
sig = pd.Timestamp(f"{str(ultima)[:4]}-{str(ultima)[4:6]}-{str(ultima)[6:8]}") \
    + pd.tseries.offsets.BDay(1)

falso = {}
for s in previo["simbolos"]:
    idx = pd.bdate_range(end=sig, periods=22)
    base = float(s["c"][-1])
    falso[s["t"]] = pd.DataFrame(
        {"Open": base, "High": base * 1.01, "Low": base * 0.99,
         "Close": [base] * 21 + [base * 1.05], "Volume": 1000.0}, index=idx)

guion = f"""
import json, sys, pickle
sys.path.insert(0, {RAIZ!r})
import screener
with open({str(tmp / 'falso.pkl')!r}, 'rb') as fh:
    falso = pickle.load(fh)
screener.bajar_precios = lambda t, p, **k: {{x: falso[x] for x in t if x in falso}}
sys.argv = ['actualizar_rapido.py', '--previo', {str(previo_dir / 'datos.json')!r},
            '--salida', {str(tmp / 'sitio')!r}]
exec(open({str(Path(RAIZ) / 'actualizar_rapido.py')!r}).read())
"""
import pickle
with open(tmp / "falso.pkl", "wb") as fh:
    pickle.dump(falso, fh)

r = subprocess.run([sys.executable, "-c", guion], cwd=RAIZ,
                   capture_output=True, text=True)
print(r.stdout.strip()[-500:])
if r.returncode:
    print(r.stderr[-2000:])
    sys.exit("[X] actualizar_rapido.py fallo")

nuevo = json.loads((tmp / "sitio" / "datos.json").read_text())
d = {s["t"]: s for s in nuevo["simbolos"]}

assert len(nuevo["simbolos"]) == len(previo["simbolos"]), "se perdieron simbolos"
sig_i = int(sig.strftime("%Y%m%d"))

sin_dup = all(len(set(s["d"])) == len(s["d"]) for s in nuevo["simbolos"])
assert sin_dup, "quedaron fechas duplicadas"
print("sin fechas duplicadas: OK")

largos = {len(s["d"]) for s in nuevo["simbolos"]}
assert max(largos) <= 400, f"el historial crecio: {max(largos)}"
assert min(largos) >= 380, f"se perdio historial: {min(largos)}"
print(f"historial acotado a 400 barras: OK (entre {min(largos)} y {max(largos)})")

for s in nuevo["simbolos"]:
    assert len(s["d"]) == len(s["c"]) == len(s["o"]) == len(s["h"]) == len(s["l"]) == len(s["v"]), \
        f"{s['t']}: arrays de largo distinto"
print("todos los arrays quedaron parejos: OK")

avanzo = sum(1 for s in nuevo["simbolos"] if s["d"][-1] == sig_i)
assert avanzo == len(nuevo["simbolos"]), f"solo {avanzo} avanzaron de fecha"
print(f"todos avanzaron a la rueda nueva ({sig_i}): OK")

# la barra provisoria de la corrida anterior tiene que quedar pisada
uno = nuevo["simbolos"][0]
assert abs(uno["c"][-1] - round(float(previo["simbolos"][0]["c"][-1]) * 1.05, 4)) < 0.02, \
    f"no se piso el cierre provisorio: {uno['c'][-1]}"
print("la barra provisoria se piso con el precio nuevo: OK")

assert nuevo["atrasados"] == 0, f"quedaron {nuevo['atrasados']} atrasados"
assert nuevo["ultimo_cierre"] == sig_i
assert nuevo.get("parcial") is True, "no quedo marcado como armado durante la rueda"
print("atrasos recalculados y payload marcado como parcial: OK")

# y el historial viejo no se toco
viejo0 = previo["simbolos"][0]["c"][-40:-1]
nuevo0 = d[previo["simbolos"][0]["t"]]["c"]
assert any(abs(a - b) < 1e-9 for a in viejo0 for b in nuevo0), "se perdio el historial viejo"
print("el historial anterior sigue ahi: OK")

# El caso que se escapo en la primera corrida real: Yahoo devuelve la ventana
# del mes con menos ruedas de las que ya habia guardadas. Antes eso borraba
# barras buenas; ahora, indexando por fecha, no puede pasar.
falso_ralo = {t: d.iloc[::2] for t, d in falso.items()}   # una rueda si, una no
with open(tmp / "falso.pkl", "wb") as fh:
    pickle.dump(falso_ralo, fh)
r3 = subprocess.run([sys.executable, "-c", guion], cwd=RAIZ, capture_output=True, text=True)
assert r3.returncode == 0, r3.stderr[-1500:]
ralo = json.loads((tmp / "sitio" / "datos.json").read_text())
perdidas = [(s["t"], antes[s["t"]][0], len(s["d"]))
            for s in ralo["simbolos"] if len(s["d"]) < antes[s["t"]][0]]
assert not perdidas, f"se perdieron barras: {perdidas[:5]}"
assert all(len(set(s["d"])) == len(s["d"]) for s in ralo["simbolos"])
assert all(s["d"] == sorted(s["d"]) for s in ralo["simbolos"]), "quedaron desordenadas"
print(f"con Yahoo devolviendo la mitad de las ruedas, no se pierde ni una barra: OK")
with open(tmp / "falso.pkl", "wb") as fh:
    pickle.dump(falso, fh)

# si Yahoo casi no contesta, NO se publica
guion2 = guion.replace("{x: falso[x] for x in t if x in falso}",
                       "{x: falso[x] for x in t[:10] if x in falso}")
r2 = subprocess.run([sys.executable, "-c", guion2], cwd=RAIZ,
                    capture_output=True, text=True)
assert r2.returncode != 0, "publico con una descarga incompleta"
assert "vino incompleto" in (r2.stdout + r2.stderr), r2.stdout[-300:]
print("con una descarga incompleta corta y no publica: OK")

print("\nACTUALIZACION RAPIDA OK")
