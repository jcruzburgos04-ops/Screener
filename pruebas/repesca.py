"""El caso que motiva todo: Yahoo devuelve series recortadas y nadie avisa."""
import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)   # para importar screener.py desde la raiz
import sys
import screener as S
from fixtura import series_falsas
S.time.sleep = lambda s: None

completo = series_falsas([f'T{i}' for i in range(20)], n=300)
recortado = {t: (d.iloc[:-3] if i % 4 == 0 else d)
             for i, (t, d) in enumerate(completo.items())}

print('antes de repescar:', {t:n for t,n in S.atrasos(recortado).items() if n})
# pedir de a uno devuelve la serie entera, que es lo que pasa de verdad
S._descargar = lambda grupo, per, minimo=None: {t: completo[t] for t in grupo if t in completo}
rec, quedan = S.repescar_atrasados(recortado, '3y')
print('despues de repescar:', {t:n for t,n in S.atrasos(rec).items() if n}, '| quedan:', quedan)
assert not quedan and not any(S.atrasos(rec).values())
print('REPESCA OK')

# y si el simbolo esta genuinamente muerto, no se inventa nada
muerto = {t: (d.iloc[:-5] if t=='T0' else d) for t,d in completo.items()}
S._descargar = lambda grupo, per, minimo=None: {}
rec2, quedan2 = S.repescar_atrasados(muerto, '3y')
assert quedan2 == ['T0'], quedan2
assert len(rec2['T0']) == 295
print('MUERTO OK: no lo inventa, lo reporta ->', quedan2)
