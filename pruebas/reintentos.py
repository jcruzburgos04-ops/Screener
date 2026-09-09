"""Simula el comportamiento real de Yahoo: los fallos vienen en rachas."""
import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)   # para importar screener.py desde la raiz
import time
import screener as S
from fixtura import series_falsas

S.time.sleep = lambda s: None          # sin pausas, es una prueba
demo = series_falsas([f'T{i}' for i in range(120)] + ['MUERTO1','MUERTO2'], n=300)

llamadas = {'n':0}
def falso_descargar(grupo, periodo, minimo=None):
    llamadas['n'] += 1
    # regla 1: los muertos nunca vuelven
    grupo = [t for t in grupo if not t.startswith('MUERTO')]
    # regla 2: un lote grande falla ENTERO una de cada dos veces (la racha)
    if len(grupo) > 5 and llamadas['n'] % 2 == 0:
        return {}
    # regla 3: en grupos de 5 falla el grupo entero 1 de cada 3
    if len(grupo) == 5 and llamadas['n'] % 3 == 0:
        return {}
    return {t: demo[t] for t in grupo if t in demo}
S._descargar = falso_descargar

t0 = time.time()
d = S.bajar_precios([f'T{i}' for i in range(120)] + ['MUERTO1','MUERTO2'], '3y', lote=50)
vivos = [t for t in d if t.startswith('T')]
print(f'pedidos 122 (120 vivos + 2 muertos)')
print(f'recuperados: {len(vivos)} vivos, {len([t for t in d if t.startswith("MUERTO")])} muertos')
print(f'llamadas a Yahoo: {llamadas["n"]}')
assert len(vivos) == 120, f'faltaron vivos: {sorted(set(f"T{i}" for i in range(120))-set(vivos))}'
assert not any(t.startswith('MUERTO') for t in d)
print('REINTENTOS OK: recupera todos los vivos y deja afuera solo los muertos')

# cuarentena: tres corridas fallando y queda castigado
import json, tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp())/'sin_datos.json'
q = {}
for i in range(3):
    q = S.actualizar_cuarentena(q, ['AAPL','MUERTO1'], {'AAPL'}, path=tmp)
    print(f'  corrida {i+1}: MUERTO1 fallos={q["MUERTO1"]["fallos"]}, '
          f'en cuarentena={"MUERTO1" in S.simbolos_en_cuarentena(q)}')
assert 'AAPL' not in q
assert 'MUERTO1' in S.simbolos_en_cuarentena(q)
# y bajar_precios lo saltea
llamadas['n'] = 0
d = S.bajar_precios(['T1','MUERTO1'], '3y', saltear=S.simbolos_en_cuarentena(q))
assert 'MUERTO1' not in d and 'T1' in d
print('CUARENTENA OK')


# ==============================================================================
# RECIEN LISTADOS: pocas barras porque son nuevos, no porque falte historia
# ==============================================================================
# MIN_BARRAS existe para atajar la serie RECORTADA, que es la forma en que Yahoo
# falla cuando lo apuran: manda menos ruedas de las que hay y los indicadores
# salen mal sin que nada avise. Eso no se afloja.
#
# Pero castigaba tambien al caso opuesto: un papel que cotiza desde hace tres
# meses NO TIENE 220 ruedas y no las va a tener hoy. El SPCX quedaba afuera del
# sitio por eso, con el subyacente y la moneda correctos, y el usuario lo
# reclamo tres veces.
#
# Los dos se ven iguales en la serie -- pocas barras, todas recientes -- asi que
# la unica forma de separarlos es preguntarle a la fuente desde cuando cotiza el
# papel. Aca se le pasa un `consultar` de mentira porque no hay internet.
import pandas as pd

S.CORTOS.clear(); S.CORTOS_DATOS.clear(); S.NUEVOS.clear()

hoy = pd.Timestamp('2026-09-09')
def serie(n):
    idx = pd.bdate_range(end=hoy, periods=n)
    return pd.DataFrame({'Open': 1.0, 'High': 1.0, 'Low': 1.0, 'Close': 1.0,
                         'Volume': 1.0}, index=idx)

# NUEVITO cotiza desde su primera barra: lo que vino es toda su vida.
# RECORTE cotiza desde 2015 y vino con 61 ruedas: le falta historia que existe.
# CHIQUITO es nuevo tambien, pero con 12 barras no hay ni ASH diario.
S.CORTOS_DATOS['NUEVITO']  = serie(61)
S.CORTOS_DATOS['RECORTE']  = serie(61)
S.CORTOS_DATOS['CHIQUITO'] = serie(12)
primeras = {'NUEVITO':  S.CORTOS_DATOS['NUEVITO'].index[0],
            'RECORTE':  pd.Timestamp('2015-03-02'),
            'CHIQUITO': S.CORTOS_DATOS['CHIQUITO'].index[0]}

r = S.rescatar_recien_listados(consultar=lambda t: primeras[t])
assert 'NUEVITO' in r, 'el recien listado no entro: es el caso SPCX otra vez'
assert 'RECORTE' not in r, ('entro una serie RECORTADA: los indicadores de ese '
                            'papel salen mal y nadie se entera')
assert 'CHIQUITO' not in r, f'entro con 12 barras, por debajo del piso {S.MIN_BARRAS_NUEVO}'
assert S.NUEVOS.get('NUEVITO') == 61 and 'RECORTE' not in S.NUEVOS
print(f'recien listado entra con {len(r["NUEVITO"])} barras; serie recortada y '
      f'restos por debajo de {S.MIN_BARRAS_NUEVO} quedan afuera: OK')

# Si la fuente no dice cuando empezo a cotizar, NO se afirma nada: se lo trata
# como recorte. Publicar indicadores de una serie que capaz esta cortada seria
# peor que dejar el papel afuera una noche mas.
S.NUEVOS.clear()
assert not S.rescatar_recien_listados(consultar=lambda t: None), \
    'entro sin saber desde cuando cotiza'
print('sin el dato de la fuente no entra ninguno: OK')

# Y el que despues viene completo sale de las dos listas, para que la pantalla
# no lo siga mostrando como corto una semana despues de que dejo de serlo.
#
# Se recarga el modulo para recuperar el _descargar de verdad: el de mentira de
# mas arriba devuelve un diccionario ya armado y nunca llega a la parte que
# limpia las listas, asi que probarlo contra el falso no probaria nada. Lo que
# se simula ahora es un escalon mas abajo, la respuesta de yfinance.
import importlib
import yfinance as _yf

importlib.reload(S)
S.time.sleep = lambda s: None
S.CORTOS['NUEVITO'] = 61
S.CORTOS_DATOS['NUEVITO'] = serie(61)
S.NUEVOS['NUEVITO'] = 61
entero = serie(300)
_yf.download = lambda *a, **k: entero
S.bajar_precios(['NUEVITO'], '3y')
assert 'NUEVITO' not in S.CORTOS and 'NUEVITO' not in S.CORTOS_DATOS, \
    'quedo anotado como corto despues de venir entero'
assert 'NUEVITO' not in S.NUEVOS, \
    'la tabla lo seguiria marcando como recien listado con 300 barras encima'
print('cuando junta historial sale de la lista de cortos: OK')


# Cortafuegos: si vinieron cortos veinticinco papeles no listaron veinticinco
# empresas hoy, es Yahoo mandando series recortadas en racha. Preguntar uno por
# uno seria pegarle mas a la fuente justo cuando esta cortando. Mismo criterio
# que MAX_INDIVIDUALES.
S.CORTOS_DATOS.clear(); S.NUEVOS.clear()
for i in range(S.MAX_RESCATES + 1):
    S.CORTOS_DATOS[f'RACHA{i}'] = serie(61)
consultas = {'n': 0}
def _contar(t):
    consultas['n'] += 1
    return S.CORTOS_DATOS[t].index[0]
assert not S.rescatar_recien_listados(consultar=_contar), \
    'rescato en medio de una racha de Yahoo'
assert consultas['n'] == 0, f'igual le hizo {consultas["n"]} pedidos a Yahoo'
print(f'con mas de {S.MAX_RESCATES} cortos no pregunta ninguno: OK')
print('RECIEN LISTADOS OK')
