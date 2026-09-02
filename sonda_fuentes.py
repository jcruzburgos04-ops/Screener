#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SONDA TEMPORAL -- se borra cuando conteste.

Busca tres cosas, en orden de importancia:

  1. UNA FUENTE CON LOS CRONOGRAMAS de los soberanos. Es lo unico que falta
     para que los 11 bonos tengan TIR. Ni data912 ni BYMA los publican en los
     endpoints que ya se probaron, asi que aca se prueban los oficiales
     (Ministerio de Economia, datos.gob.ar) y los del mercado (IAMC, Rava,
     Bolsar, bonistas).

  2. LA FORMA DE LOS DATOS de data912 que todavia no se uso: arg_corp (las
     obligaciones negociables), arg_notes (las letras) y el historico de bonos.
     Hace falta saber que campos trae antes de escribir el parser.

  3. BYMA CON MAS VARIANTES. Con POST y cuerpo {excludeZeroPxAndQty,T2} el
     endpoint `cedears` contesto 1,19 MB pero `government-bonds` dio 401 y
     `public-bonds` un sobre paginado vacio. Eso no huele a "no se puede":
     huele a que cada endpoint quiere otro cuerpo. Se prueban varios.
"""
import json
import ssl
import urllib.request
import urllib.error

SIN_VERIFICAR = ssl.create_default_context()
SIN_VERIFICAR.check_hostname = False
SIN_VERIFICAR.verify_mode = ssl.CERT_NONE

NAVEGADOR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
}


def pedir(url, cuerpo=None, cabeceras=None, metodo=None, tiempo=25):
    """Devuelve (estado, bytes) o (0, mensaje de error). Nunca lanza."""
    h = dict(NAVEGADOR)
    if cabeceras:
        h.update(cabeceras)
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode()
        h["Content-Type"] = "application/json"
    try:
        req = urllib.request.Request(url, headers=h, data=datos, method=metodo)
        with urllib.request.urlopen(req, timeout=tiempo, context=SIN_VERIFICAR) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        cuerpo_err = b""
        try:
            cuerpo_err = e.read()[:200]
        except Exception:
            pass
        return e.code, cuerpo_err
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}".encode()[:200]


def titulo(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def linea(estado, cuerpo, etiqueta, muestra=200):
    marca = "OK " if estado == 200 else "   "
    n = len(cuerpo) if isinstance(cuerpo, bytes) else 0
    print(f"  {marca}{estado:<4} {n:>9}  {etiqueta}")
    if cuerpo:
        txt = cuerpo[:muestra].decode("utf-8", "replace").replace("\n", " ")
        print(f"        {txt}")


# ---------------------------------------------------------------------------
# 1. CRONOGRAMAS
# ---------------------------------------------------------------------------
def cronogramas():
    titulo("1. FUENTES CON EL CRONOGRAMA DE PAGOS")

    print("\n-- Ministerio de Economia / datos abiertos --")
    for u in (
        "https://apis.datos.gob.ar/series/api/search?q=deuda&limit=20",
        "https://apis.datos.gob.ar/series/api/search?q=bonar&limit=20",
        "https://www.argentina.gob.ar/economia/finanzas/deuda",
        "https://www.argentina.gob.ar/economia/finanzas/graficos-deuda",
    ):
        e, c = pedir(u)
        linea(e, c, u, 260)

    print("\n-- IAMC (publica el flujo de fondos de cada bono) --")
    for u in (
        "https://www.iamc.com.ar/",
        "https://www.iamc.com.ar/EstadisticasDiarias/",
        "https://api.iamc.com.ar/api/instrumentos",
    ):
        e, c = pedir(u)
        linea(e, c, u, 160)

    print("\n-- Rava (tiene pestaña de flujo de fondos por especie) --")
    for u in (
        "https://clasico.rava.com/lib/restapi/v3/publico/perfil/AL30",
        "https://clasico.rava.com/empresas/perfil.php?e=AL30",
        "https://www.rava.com/perfil/AL30",
    ):
        e, c = pedir(u)
        linea(e, c, u, 200)

    print("\n-- Bolsar / bonistas / otros --")
    for u in (
        "https://bolsar.info/api/Titulos/GetTitulo?simbolo=AL30",
        "https://bonistas.com/api/bonds",
        "https://bonistas.com/api/flujos/AL30",
        "https://api.bonistas.com/bonds",
    ):
        e, c = pedir(u)
        linea(e, c, u, 200)


# ---------------------------------------------------------------------------
# 2. data912: lo que todavia no se leyo
# ---------------------------------------------------------------------------
def campos(url, cuantos=2):
    e, c = pedir(url)
    print(f"\n  [{e}] {url}   {len(c) if isinstance(c, bytes) else 0} bytes")
    if e != 200:
        print(f"      {c[:200].decode('utf-8','replace')}")
        return
    try:
        d = json.loads(c)
    except Exception as ex:
        print(f"      no es JSON: {ex}")
        return
    if isinstance(d, dict):
        print(f"      dict con claves: {sorted(d)[:25]}")
        return
    print(f"      {len(d)} filas")
    if d:
        print(f"      campos: {sorted(d[0])}")
        for f in d[:cuantos]:
            print(f"      {json.dumps(f, ensure_ascii=False)[:400]}")
        # los simbolos, que es lo que hace falta para armar el universo
        simbolos = sorted({str(x.get('symbol') or x.get('ticker') or '') for x in d})
        print(f"      simbolos ({len(simbolos)}): {' '.join(s for s in simbolos if s)[:900]}")


def data912():
    titulo("2. data912: LOS ENDPOINTS QUE FALTABA MIRAR")
    for u in (
        "https://data912.com/live/arg_corp",       # obligaciones negociables
        "https://data912.com/live/arg_notes",      # letras
        "https://data912.com/live/arg_bonds",      # soberanos (para ver campos)
        "https://data912.com/live/mep",
        "https://data912.com/historical/bonds/AL30",
    ):
        campos(u)


# ---------------------------------------------------------------------------
# 3. BYMA con mas variantes
# ---------------------------------------------------------------------------
def byma():
    titulo("3. BYMA: MISMO ENDPOINT, DISTINTO CUERPO")
    base = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/"
    cuerpos = [
        ("T2", {"excludeZeroPxAndQty": True, "T2": True}),
        ("T1", {"excludeZeroPxAndQty": True, "T1": True, "T0": False}),
        ("T0", {"excludeZeroPxAndQty": False, "T0": True}),
        ("vacio", {}),
    ]
    endpoints = [
        "government-bonds", "public-bonds", "negotiable-obligations",
        "corporate-bonds", "short-term-government-bonds", "leading-equity",
        "general-equity", "bluechips", "galpones", "index", "indices",
    ]
    for ep in endpoints:
        for nombre, cuerpo in cuerpos:
            e, c = pedir(base + ep, cuerpo=cuerpo)
            # solo se imprime lo que aporta: un 200 con contenido, o un error nuevo
            interesante = (e == 200 and len(c) > 200) or e not in (200, 401, 404)
            if interesante:
                linea(e, c, f"{ep}  [{nombre}]", 200)
                break
        else:
            print(f"     {e:<4}         -  {ep}  (ningun cuerpo sirvio)")

    print("\n-- ¿hay documentacion de la API? --")
    for u in (
        "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/swagger.json",
        "https://open.bymadata.com.ar/v3/api-docs",
        "https://open.bymadata.com.ar/swagger-ui/index.html",
        "https://open.bymadata.com.ar/assets/config/config.json",
    ):
        e, c = pedir(u)
        linea(e, c, u, 300)


if __name__ == "__main__":
    cronogramas()
    data912()
    byma()
    print("\n[fin]")
