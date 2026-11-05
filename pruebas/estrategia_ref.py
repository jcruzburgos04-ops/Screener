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
        f['pasa'] = all(f[f'f{k}'] for k in range(1, E.FILTROS + 1))
        f['pasa31'] = all(f[f'f{k}'] for k in range(1, E.FILTROS_V31 + 1))
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
            if f['fecha_cruce'] and sum(not f[f'f{k}'] for k in range(1, E.FILTROS + 1)) <= 1:
                hist[f['t']] = E.historia_senal(S[f['t']], spy, R, f['fecha_cruce'], u_de, pausa_de)
    out[R] = {'ash': E.ash_spy(spy, R), 'universo': u,
              'historia': {t: ({k: lim(v) for k, v in h.items()} if h else None)
                           for t, h in hist.items()},
              'filas': {f['t']: {k: lim(v) for k, v in f.items()} for f in fil}}

# ---- las dos carteras simuladas, sin pausa (en la fixtura el SPY esta en
# pausa casi siempre y no entraria nada), con el Motor del validador ----
import validar_estrategia as V  # noqa: E402


class SinPausa(V.Motor):
    def pausa(self, d):
        a = dict(super().pausa(d))
        a["pausa"] = a["pausa31"] = False
        return a


Mo = SinPausa(P)
dias = [int(d) for d in Mo.cal[-250:]]
sims = {}
for v in (33, 31):
    R_ = E.simular_cartera(dias, Mo, v, capital=1.0)
    sims[v] = {"ops": [[o["t"], o["fe"], o["fs"], o["motivo"], float(o["ret"]), bool(o["reentrada"]),
                        float(o["monto"])] for o in R_["ops"]],
               "abiertas": [[p["t"], p["fe"]] for p in R_["abiertas"]],
               "curva": [[d, float(c), float(e)] for d, c, e in R_["curva"]]}
serie = {}
for t in list(Mo.se)[::7]:
    s = Mo.se[t]
    serie[t] = {k: [None if (isinstance(x, float) and not np.isfinite(x)) else
                    (bool(x) if isinstance(x, (bool, np.bool_)) else float(x)) for x in s[k]]
                for k in ("dias_cruce", "adr", "rs_puntaje", "sobre_min", "hist3", "hist3_ant",
                          "ewo_senal", "ash9_bulls", "ash9_bears", "st_dir", "st_linea",
                          "atr_pct", "f4", "f6", "f7", "f8", "f9", "f10", "bajo40", "toco34")}
    serie[t]["d"] = [int(x) for x in s["d"]]
out["sim"] = {"dias": dias, "v33": sims[33], "v31": sims[31]}
out["serie"] = serie
json.dump(out, open(sys.argv[2], 'w'))
