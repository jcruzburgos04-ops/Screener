import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)   # para importar screener.py desde la raiz
import json, numpy as np, pandas as pd
import screener as S
series = json.load(open(os.path.join(AQUI,'series.json')))
js = json.load(open(os.path.join(AQUI,'salida_js.json')))

def cmp(a, b, nombre, peor):
    a = np.array([np.nan if x is None else x for x in a], dtype=float)
    b = np.array([np.nan if x is None else x for x in b], dtype=float)
    if len(a) != len(b):
        print(f'  LARGO DISTINTO {nombre}: {len(a)} vs {len(b)}'); return peor, 1
    na, nb = np.isnan(a), np.isnan(b)
    if (na != nb).any():
        i = np.where(na != nb)[0]
        print(f'  NaN DISTINTOS {nombre} en {i[:5]}'); return peor, 1
    m = ~na
    if not m.any(): return peor, 0
    # El error se mide contra la ESCALA de la serie, no punto a punto: el
    # histograma es una resta de dos numeros casi iguales, asi que donde cruza
    # el cero el error relativo puntual explota aunque el absoluto sea 1e-16.
    escala = max(float(np.nanmedian(np.abs(b[m]))), 1e-9)
    err = float(np.max(np.abs(a[m]-b[m]))) / escala
    if err > peor[0]: peor = (err, nombre)
    return peor, (1 if err > 1e-12 else 0)

peor = (0.0, '')
malos = 0
for k, b in series.items():
    df = pd.DataFrame({'Open':b['o'],'High':b['h'],'Low':b['l'],
                       'Close':b['c'],'Volume':b['v']},
                      index=pd.bdate_range('2023-01-02', periods=len(b['c'])))
    for modo in ('RSI','STOCHASTIC','ADX'):
        for ma in ('EMA','WMA','SMA','SMMA','HMA','ALMA'):
            bu, be, h = S.calc_ash(df, length=16, smooth=4, modo=modo, ma_type=ma,
                                   alma_offset=0.85, alma_sigma=6.0)
            r = js[k][f'{modo}|{ma}']
            for nom, py, j in (('bulls',bu,r['bulls']),('bears',be,r['bears']),
                               ('hist',h,r['hist'])):
                peor, bad = cmp(py.tolist(), j, f'{k} {modo}/{ma} {nom}', peor)
                malos += bad
    for nom, py, j in (('rsi', S.calc_rsi(df['Close'],14), js[k]['rsi']),
                       ('atr', S.calc_atr(df,14), js[k]['atr']),
                       ('adx', S.calc_adx(df,14), js[k]['adx']),
                       ('adr', S.calc_adr_pct(df,20), js[k]['adr'])):
        peor, bad = cmp(py.tolist(), j, f'{k} {nom}', peor)
        malos += bad
    # --- Paragon ---
    # La EMA de Pine (semilla = SMA de los primeros n, NaN antes), la conversion
    # de longitudes y el rVWAP expansivo, en las tres fuentes.
    for nom, py, j in (('emaPine100', S.ema_pine(df['Close'],100), js[k]['emaPine100']),
                       ('emaPine200', S.ema_pine(df['Close'],200), js[k]['emaPine200'])):
        peor, bad = cmp(py.tolist(), j, f'{k} {nom}', peor)
        malos += bad
    for kk in (1,2,6,12):
        py_l = [S.largo_equivalente(100,kk), S.largo_equivalente(200,kk)]
        js_l = js[k]['largos'][str(kk)]
        if py_l != js_l:
            print(f'  LARGO DISTINTO {k} k={kk}: py={py_l} js={js_l}'); malos += 1
    for kk in (1,2,6):
        rap, len_, _, _ = S.paragon_conjunto(df['Close'],100,200,kk)
        for nom, py, j in ((f'parA{kk} rapida', rap, js[k][f'parA{kk}'][0]),
                           (f'parA{kk} lenta',  len_, js[k][f'parA{kk}'][1])):
            peor, bad = cmp(py.tolist(), j, f'{k} {nom}', peor)
            malos += bad
    for fu in ('hl2','hlc3','close'):
        rv, _ = S.rvwap_expansivo(df, 365, fu)
        peor, bad = cmp(rv.tolist(), js[k]['rvwap_'+fu], f'{k} rvwap {fu}', peor)
        malos += bad

    bu,be,h = S.calc_ash(df, **S.CFG_ASH)
    cr_py = S.barras_desde_cruce(h)
    cr_js = js[k]['cruce']
    if cr_py != cr_js:
        print(f'  CRUCE DISTINTO {k}: py={cr_py} js={cr_js}'); malos += 1

print(f'\nseries comparadas: {len(series)}  ·  18 combinaciones modo x media + RSI/ATR/ADX/ADR')
print('mas Paragon: EMA de Pine, conversion de longitudes y rVWAP en tres fuentes')
print(f'error relativo maximo: {peor[0]:.3e}   ({peor[1]})')
print('RESULTADO:', 'PARIDAD OK' if malos == 0 else f'{malos} DESVIOS')
sys.exit(1 if malos else 0)

