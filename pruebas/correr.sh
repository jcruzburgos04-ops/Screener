#!/usr/bin/env bash
# =============================================================================
# Todas las pruebas del screener, de una.
#
#   cd pruebas && ./correr.sh
#
# No hay navegador en el entorno de desarrollo, asi que la interfaz se prueba
# con jsdom desde Node. Eso alcanza para contar filas y columnas, leer los KPI,
# disparar clics y teclas, verificar la persistencia y medir el recalculo.
# NO alcanza para nada visual: del grafico solo se puede comprobar que no lance
# excepciones y que lo que dibuja caiga dentro del canvas.
#
# Los precios son SINTETICOS (--demo). Lo que se prueba es la maquinaria, no los
# numeros de mercado; para eso estan verificar.py y diagnostico.py, que si
# necesitan internet.
# =============================================================================
set -e
cd "$(dirname "$0")"
RAIZ=$(cd .. && pwd)
export SCREENER_SITIO="$PWD/tmp/sitio"

echo "== armando un sitio de prueba con datos sinteticos =="
mkdir -p tmp
(cd "$RAIZ" && python3 generar_sitio.py --demo --barras 400 --salida "$PWD/pruebas/tmp/sitio" >/dev/null)
python3 inyectar_atraso.py tmp/sitio/datos.json
python3 - <<'PY'
# Yahoo sin fundamentales no trae sector ni industria; se inventan para poder
# probar el ranking de industrias y el escapado de nombres raros.
import json, pathlib
p = pathlib.Path('tmp/sitio/datos.json'); d = json.loads(p.read_text())
secs = ['Technology','Financial Services','Energy','Healthcare','Basic Materials','Utilities']
inds = ['Semiconductors','Software','Banks','Oil & Gas','Drug Manufacturers','Steel',
        'Gold','Utilities - Regulated','Auto Manufacturers','Aerospace','REIT','Airlines']
for i, s in enumerate(d['simbolos']):
    s['sec'] = secs[i % len(secs)]; s['ind'] = inds[i % len(inds)]
    s['n'] = f"Empresa {s['t']} S.A."; s['fl'] = 1e8 + i*1e6; s['mc'] = 5e9 + i*1e7
p.write_text(json.dumps(d, separators=(',', ':')))
print('sectores e industrias de prueba puestos')
PY

echo; echo "== Python: atrasos, limpieza y mapeo de CEDEARs =="
python3 atrasos.py
echo; echo "== Python: reintentos y cuarentena =="
python3 reintentos.py
echo; echo "== Python: repesca de atrasados =="
python3 repesca.py

echo; echo "== paridad Python <-> JavaScript del ASH =="
python3 - <<'PY'
import re, pathlib
h = pathlib.Path('../plantilla.html').read_text(encoding='utf-8')
m = re.search(r'<script id="motor">(.*?)</script>', h, re.S)
pathlib.Path('motor.js').write_text(m.group(1), encoding='utf-8')
print('motor.js extraido de plantilla.html')
PY
python3 series.py
node paridad_js.js
python3 paridad.py

echo; echo "== interfaz (jsdom) =="
node interfaz.js
echo; echo "== grafico y escapado =="
node grafico.js
echo; echo "== estres =="
node estres.js

echo; echo "TODO OK"
