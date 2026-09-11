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
    # --- combos de EMAs ---
    # La EMA de Pine (semilla = SMA de los primeros n, NaN antes) y los tres
    # combos. Ya no hay conversion de longitudes que verificar: estan anclados
    # a 1D, que es el timeframe de estas mismas barras.
    for nom, py, j in (('emaPine21',  S.ema_pine(df['Close'],21),  js[k]['emaPine21']),
                       ('emaPine115', S.ema_pine(df['Close'],115), js[k]['emaPine115']),
                       ('emaPine300', S.ema_pine(df['Close'],300), js[k]['emaPine300'])):
        peor, bad = cmp(py.tolist(), j, f'{k} {nom}', peor)
        malos += bad
    for nom, par in (('c1',(21,34)), ('c2',(55,115)), ('c3',(300,600))):
        rap, len_ = S.combo_emas(df['Close'], *par)
        for etq, py, j in ((f'{nom} rapida', rap, js[k][nom][0]),
                           (f'{nom} lenta',  len_, js[k][nom][1])):
            peor, bad = cmp(py.tolist(), j, f'{k} {etq}', peor)
            malos += bad
    # El rVWAP en las tres fuentes y en las CUATRO ventanas. Como la ventana va
    # por dias calendario, esto verifica ademas que las dos implementaciones
    # cuenten los dias igual, que es justo donde estaba el error.
    for fu in ('hl2','hlc3','close'):
        for d in (7,30,90,365):
            rv, llena = S.rvwap_dias(df, d, fu)
            peor, bad = cmp(rv.tolist(), js[k][f'rvwap_{fu}_{d}'],
                            f'{k} rvwap {fu} {d}d', peor)
            malos += bad
            py_ll = [1 if x else 0 for x in llena.tolist()]
            if py_ll != js[k][f'rvllena_{fu}_{d}']:
                i = next(n for n, (a, bb) in enumerate(
                    zip(py_ll, js[k][f'rvllena_{fu}_{d}'])) if a != bb)
                print(f'  VENTANA LLENA DISTINTA {k} {fu} {d}d en la barra {i}')
                malos += 1

    # --- consolidacion (la caja) ---
    for N in (20, 40, 60):
        K = S.consolidacion(df, N)
        jk = js[k]['consol'][str(N)]
        if K['estado'] != jk[0]:
            print(f'  ESTADO DISTINTO {k} N={N}: py={K["estado"]!r} js={jk[0]!r}')
            malos += 1
        if not (K['barras'] != K['barras'] and jk[2] is None) and K['barras'] != jk[2]:
            print(f'  BARRAS DISTINTAS {k} N={N}: py={K["barras"]} js={jk[2]}')
            malos += 1
        for nom, py, j in (('rango', K['rango'], jk[1]), ('pos', K['pos'], jk[3]),
                           ('aprieta', K['aprieta'], jk[4]),
                           ('estrechez', K['estrechez'], jk[5])):
            peor, bad = cmp([py], [j], f'{k} caja{N} {nom}', peor)
            malos += bad

    bu,be,h = S.calc_ash(df, **S.CFG_ASH)
    cr_py = S.barras_desde_cruce(h)
    cr_js = js[k]['cruce']
    if cr_py != cr_js:
        print(f'  CRUCE DISTINTO {k}: py={cr_py} js={cr_js}'); malos += 1

print(f'\nseries comparadas: {len(series)}  ·  18 combinaciones modo x media + RSI/ATR/ADX/ADR')
print('mas los combos de EMAs, el rVWAP por dias calendario y la caja')
print(f'error relativo maximo: {peor[0]:.3e}   ({peor[1]})')
print('RESULTADO:', 'PARIDAD OK' if malos == 0 else f'{malos} DESVIOS')
sys.exit(1 if malos else 0)

