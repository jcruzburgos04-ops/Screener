"""Referencia en Python para pruebas/estrategia.js: evalua el payload de la
fixtura con estrategia.py en las fechas pedidas y escribe un JSON."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import estrategia as E  # noqa: E402

P = json.load(open(sys.argv[1]))
S = {s['t']: s for s in P['simbolos']}
spy = S['SPY']
out = {}
for R in map(int, sys.argv[3].split(',')):
    u, _, _ = E.universo_estrategia(P['simbolos'], P.get('estr_adr') or E.cargar_adr())
    fil = [r for r in (E.evaluar(S[t], spy, R) for t in u) if r]
    U = np.sort([f['rs_puntaje'] for f in fil if np.isfinite(f['rs_puntaje'])])
    for f in fil:
        f['rs'] = E.rs_de_puntaje(f['rs_puntaje'], U)
        f['f3'] = bool(np.isfinite(f['rs']) and f['rs'] > E.RS_MIN)
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
    out[R] = {'ash': E.ash_spy(spy, R), 'universo': u,
              'filas': {f['t']: {k: lim(v) for k, v in f.items()} for f in fil}}
json.dump(out, open(sys.argv[2], 'w'))
