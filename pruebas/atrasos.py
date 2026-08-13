import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)   # para importar screener.py desde la raiz
import numpy as np, pandas as pd
from fixtura import series_falsas
from screener import (atrasos, cargar_mapa_cedears, limpiar_barras,
                      sufijo_mercado)

p = series_falsas(['AAPL','MSFT','NVDA','PBR.SA','VALE3.SA','BAS.DE','SAP.DE','TSM','SONY.T'], n=300)
# atraso simulado: NVDA 3 ruedas, PBR.SA 1 (solo), BAS.DE y SAP.DE juntos (feriado aleman)
p['NVDA'] = p['NVDA'].iloc[:-3]
p['PBR.SA'] = p['PBR.SA'].iloc[:-1]
p['BAS.DE'] = p['BAS.DE'].iloc[:-2]
p['SAP.DE'] = p['SAP.DE'].iloc[:-2]
a = atrasos(p)
print('atrasos:', {k:v for k,v in sorted(a.items()) if v})
assert a['NVDA'] == 3, a['NVDA']
assert a['AAPL'] == 0 and a['MSFT'] == 0
assert a['PBR.SA'] == 1 and a['VALE3.SA'] == 0
# los dos alemanes atrasados juntos son la moda de su mercado: NO se marcan
assert a['BAS.DE'] == 0 and a['SAP.DE'] == 0, (a['BAS.DE'], a['SAP.DE'])
print('sufijos:', [(t,sufijo_mercado(t)) for t in ['AAPL','PBR.SA','BRK-B','BAS.DE']])
assert sufijo_mercado('BRK-B') == '' and sufijo_mercado('PBR.SA') == '.SA'

# limpiar_barras: huecos en OHL, indice desordenado y duplicado
idx = pd.bdate_range('2023-01-02', periods=300)
d = pd.DataFrame({'Open':1.0,'High':1.1,'Low':0.9,'Close':1.0,'Volume':10.0}, index=idx)
d.iloc[5, [0,1,2]] = np.nan          # sin O/H/L
d.iloc[7, 3] = np.nan                # sin Close -> se cae la fila
d = pd.concat([d, d.iloc[[10]]])     # fecha duplicada
d = d.sample(frac=1, random_state=1) # desordenado
lim = limpiar_barras(d)
assert lim is not None and lim.index.is_monotonic_increasing
assert not lim.index.has_duplicates
assert np.isfinite(lim[['Open','High','Low','Close']].to_numpy()).all()
assert len(lim) == 299, len(lim)
print('limpiar_barras OK, filas:', len(lim))

# cedears con lineas rotas: no debe romper ni corromper
import tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp())/'c.csv'
tmp.write_text('local,subyacente\nAAPL.BA,AAPL\nROTA\nOTRA,\nTEN.BA,TS\n')
m = cargar_mapa_cedears(tmp)
print('mapa con lineas rotas:', m)
assert m == {'AAPL':'AAPL','TEN':'TS'}, m
print('\nTODO OK')
