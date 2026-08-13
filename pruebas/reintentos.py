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
def falso_descargar(grupo, periodo):
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
