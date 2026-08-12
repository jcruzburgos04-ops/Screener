import numpy as np, json, os, sys
rng = np.random.default_rng(11)
n = 500
out = {}
for k,(base,vol) in {'A':(50,.02),'B':(500,.012),'C':(3.5,.04)}.items():
    r = rng.normal(.0003, vol, n)
    c = base*np.exp(np.cumsum(r))
    rango = c*rng.uniform(.004,.025,n)
    out[k] = {"o":list(c+rng.normal(0,rango/3)),"h":list(c+rango),
              "l":list(c-rango),"c":list(c),
              "v":[float(x) for x in rng.lognormal(13.5,.8,n).round()]}
salida = sys.argv[1] if len(sys.argv)>1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'series.json')
json.dump(out, open(salida,'w'))
print('series ->', salida)
