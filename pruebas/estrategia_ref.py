"""Referencia en Python para pruebas/estrategia.js: evalua el payload de la
fixtura con estrategia.py en las fechas pedidas y escribe un JSON."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import estrategia as E  # noqa: E402

P = json.load(open(sys.argv[1]))
S0 = {s['t']: s for s in P['simbolos']}
spy = E.alinear(S0['SPY'], S0['SPY']['d'])
S = {t: (spy if t == 'SPY' else E.alinear(s, spy['d'])) for t, s in S0.items()}
S = {t: s for t, s in S.items() if s}
out = {}
for R in map(int, sys.argv[3].split(',')):
    u, _, _ = E.universo_estrategia(P['simbolos'], P.get('estr_adr') or E.cargar_adr())
    u = [t for t in u if t in S]
    fil = [r for r in (E.evaluar(S[t], spy, R) for t in u) if r]
    U = np.sort([f['rs_puntaje'] for f in fil if np.isfinite(f['rs_puntaje'])])
    for f in fil:
        f['rs'] = E.rs_de_puntaje(f['rs_puntaje'], U)
        f['f3'] = bool(np.isfinite(f['rs']) and f['rs'] > E.RS_MIN)
        f['propia'] = bool(f['propia'])
        f['pasa'] = all(f[f'f{k}'] for k in range(1, 9))
    E.prioridad(fil)

    def lim(v):
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if isinstance(v, (float, np.floating)):
            return float(v) if np.isfinite(v) else None
        if isinstance(v, np.integer):
            return int(v)
        return v
    # cuando salto la senal, con el RS de cada dia contra los propios de ese dia
    propios, pausas = {}, {}

    def u_de(x):
        if x not in propios:
            ns = int(np.searchsorted(spy['d'], x, 'right'))
            cs = np.asarray(spy['c'][:ns], float)
            v = []
            for t in u:
                s = S[t]
                n = int(np.searchsorted(s['d'], x, 'right'))
                if n and s['d'][n - 1] == x:
                    v.append(E.puntaje_rs(np.asarray(s['c'][:n], float), cs))
            propios[x] = np.sort([y for y in v if np.isfinite(y)])
        return propios[x]

    def pausa_de(x):
        if x not in pausas:
            pausas[x] = E.ash_spy(spy, x)['pausa']
        return pausas[x]
    hist = {}
    if R == int(sys.argv[3].split(',')[0]):
        for f in fil:
            if f['fecha_cruce'] and sum(not f[f'f{k}'] for k in range(1, 9)) <= 1:
                hist[f['t']] = E.historia_senal(S[f['t']], spy, R, f['fecha_cruce'], u_de, pausa_de)
    out[R] = {'ash': E.ash_spy(spy, R), 'universo': u,
              'historia': {t: ({k: lim(v) for k, v in h.items()} if h else None)
                           for t, h in hist.items()},
              'filas': {f['t']: {k: lim(v) for k, v in f.items()} for f in fil}}
json.dump(out, open(sys.argv[2], 'w'))
