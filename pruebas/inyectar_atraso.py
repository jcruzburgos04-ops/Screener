# Mete atraso artificial en el datos.json de demo para probar la interfaz.
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text())
for i, s in enumerate(d['simbolos']):
    if i % 17 == 0:
        n = 1 + (i % 3)
        for k in ('d','o','h','l','c','v'):
            s[k] = s[k][:-n]
        s['at'] = n
d['atrasados'] = sum(1 for s in d['simbolos'] if s['at'] > 0)
p.write_text(json.dumps(d, separators=(',',':')))
print('atrasados inyectados:', d['atrasados'])
