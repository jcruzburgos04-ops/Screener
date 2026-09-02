"""
Sonda: que campos manda cada fuente, de verdad.

No adivina. Baja el panel entero, junta TODAS las claves que aparecen y las
muestra con un ejemplo real, agrupadas por familia. Es lo unico que decide si
se pueden mostrar los pagos de un instrumento o no.
"""
import json, urllib.request, collections

def bajar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

d = bajar("https://bonistas.com/api/bonds")
print(f"bonistas: {len(d)} filas\n")

claves = collections.Counter()
for f in d:
    claves.update(f.keys())
print("=== TODAS LAS CLAVES (cuantas filas la traen no vacia) ===")
llenas = collections.Counter()
for f in d:
    for k, v in f.items():
        if v not in (None, "", 0):
            llenas[k] += 1
for k, n in claves.most_common():
    print(f"  {k:<28} presente {n:>4}   con valor {llenas[k]:>4}")

def muestra(tk):
    for f in d:
        if f.get("ticker") == tk:
            print(f"\n=== {tk} ===")
            for k, v in sorted(f.items()):
                s = str(v)
                print(f"  {k:<28} {s[:150]}")
            return
    print(f"\n=== {tk}: NO ESTA ===")

# Uno de cada tipo: letra capitalizando, bono con cupon, CER amortizable,
# dolar linked, y una ON.
for tk in ("S15S6", "TO26", "TY30P", "TX26", "DICP", "TZV27", "AL30"):
    muestra(tk)

print("\n=== una ON cualquiera ===")
for f in d:
    if str(f.get("bond_family", "")).startswith("ONS"):
        for k, v in sorted(f.items()):
            print(f"  {k:<28} {str(v)[:150]}")
        break

print("\n=== familias ===")
fam = collections.Counter(str(f.get("bond_family")) for f in d)
for k, n in fam.most_common():
    print(f"  {k:<28} {n}")
