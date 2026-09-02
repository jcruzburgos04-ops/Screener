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
# Los precios de las pruebas son SINTETICOS y viven en fixtura.py, dentro de
# esta carpeta. El proyecto ya NO tiene modo demo: se saco justamente para que
# no se pueda publicar sin querer un sitio con precios inventados, que parecen
# de verdad y confunden. Lo que se prueba aca es la maquinaria, no los numeros
# de mercado; para eso estan verificar.py y diagnostico.py, que si necesitan
# internet.
# =============================================================================
set -e
cd "$(dirname "$0")"
RAIZ=$(cd .. && pwd)
export SCREENER_SITIO="$PWD/tmp/sitio"

echo "== armando la fixtura (series sinteticas, solo para las pruebas) =="
python3 fixtura.py

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

echo; echo "== Paragon: EMA de Pine, conversion y rVWAP =="
python3 paragon.py
echo; echo "== consolidacion: la caja =="
python3 consolidacion.py
echo; echo "== lineas de tendencia =="
node tendencias.js
echo; echo "== AVWAP anclado al ultimo maximo =="
node avwap.js
echo; echo "== interfaz (jsdom) =="
node interfaz.js
echo; echo "== grafico y escapado =="
node grafico.js
echo; echo "== estres =="
node estres.js
echo; echo "== precios de Yahoo desde el navegador =="
node yahoo.js
echo; echo "== teclado =="
node teclado.js
echo; echo "== la vista de bonos =="
node bonos.js
echo; echo "== el desplegable de filtros dibujado a mano =="
node selector.js
echo; echo "== las columnas no dependen del filtro =="
node columnas_globales.js
echo; echo "== persistencia de la seleccion de columnas =="
node persistencia.js
echo; echo "== frescura: la pastilla no puede mentir (en UTC-3) =="
TZ=America/Argentina/Buenos_Aires node frescura.js
echo; echo "== pantalla angosta y pastilla de frescura =="
node movil.js
echo; echo "== vista panorama (indices y sectores) =="
node panorama.js
echo; echo "== orden de columnas, letra y densidad =="
node columnas.js
echo; echo "== Python: pre-market y after-hours =="
python3 extendido.py
echo; echo "== Python: actualizacion rapida (intradia) =="
python3 rapido.py

echo; echo "TODO OK"
