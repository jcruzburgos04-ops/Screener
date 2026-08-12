#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SERVIDOR LOCAL  ·  el screener con boton de "actualizar ahora"
================================================================================

    python servidor.py                 # abre http://127.0.0.1:8765
    python servidor.py --puerto 9000
    python servidor.py --sin-abrir     # no abre el navegador solo

POR QUE HACE FALTA UN SERVIDOR
------------------------------
El navegador no puede pedirle los precios a Yahoo por su cuenta: la respuesta
viene sin cabeceras CORS y la bloquea. Alguien tiene que bajarlos del lado de
afuera del navegador, y ese alguien es este proceso.

QUE HACE
--------
Sirve plantilla.html y tres endpoints:

    GET  /api/estado                       progreso, para la barra de arriba
    GET  /api/datos                        el payload, ya comprimido
    POST /api/actualizar?periodo=&fund=&completo=   dispara la descarga

La descarga corre en un hilo aparte, asi que la pagina sigue respondiendo y
puede mostrar cuanto lleva hecho.

DECISIONES QUE PARECEN RARAS Y NO LO SON
----------------------------------------
· El payload se guarda YA COMPRIMIDO en cache_datos.json.gz. Antes se
  recomprimian 14 MB en cada pedido; asi son cuatro milisegundos.
· Solo se escucha en 127.0.0.1. Es tu maquina, no un servicio.
· De la biblioteca estandar: pandas y yfinance los usa screener.py, pero el
  servidor en si no agrega ninguna dependencia mas.
================================================================================
"""

import argparse
import gzip
import json
import threading
import traceback
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PLANTILLA = Path("plantilla.html")
CACHE_WEB = Path("cache_datos.json.gz")

# Estado compartido entre el hilo de la descarga y el de las respuestas.
# Un lock alcanza: son cuatro campos y se escriben de a poco.
CANDADO = threading.Lock()
ESTADO = {"corriendo": False, "paso": "", "hecho": 0, "total": 0,
          "error": "", "fecha": "", "hay_datos": False}


def marcar(**kw):
    with CANDADO:
        ESTADO.update(kw)


def leer_estado():
    with CANDADO:
        return dict(ESTADO)


def guardar_payload(payload):
    """Deja el JSON comprimido en disco: es lo que se manda tal cual."""
    crudo = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    CACHE_WEB.write_bytes(gzip.compress(crudo.encode("utf-8"), 6))


def descargar(periodo, fund, completo):
    """El trabajo pesado. Corre en su propio hilo."""
    from generar_html import armar_payload
    from screener import (BENCHMARK, actualizar_cuarentena, atrasos,
                          bajar_fundamentales, bajar_precios,
                          cargar_cuarentena, cargar_precios, guardar_precios,
                          leer_universo, repescar_atrasados,
                          simbolos_en_cuarentena)
    try:
        marcar(corriendo=True, error="", paso="leyendo el universo", hecho=0, total=0)
        uni = leer_universo("universo.csv")
        tickers = uni["ticker"].tolist()
        pedir = tickers if BENCHMARK in tickers else tickers + [BENCHMARK]

        cuarentena = cargar_cuarentena()
        # "Rehacer todo el historial" tambien perdona la cuarentena: si el
        # usuario aprieta ese boton es justamente porque sospecha de los datos.
        castigados = set() if completo else simbolos_en_cuarentena(cuarentena)

        def paso(hecho, total, texto):
            marcar(paso=texto, hecho=hecho, total=total)

        marcar(paso="bajando precios", total=len(pedir))
        precios = bajar_precios(pedir, periodo, saltear=castigados, progreso=paso)
        if not precios:
            raise RuntimeError("Yahoo no devolvio ningun precio")
        precios, _ = repescar_atrasados(precios, periodo, progreso=paso)
        actualizar_cuarentena(cuarentena,
                              [t for t in pedir if t not in castigados],
                              set(precios))

        meta = {}
        if fund:
            marcar(paso="sector, industria y float", hecho=0, total=len(precios))
            meta = bajar_fundamentales(list(precios.keys()), usar_cache=not completo)
        guardar_precios(precios, meta)

        marcar(paso="armando la tabla", hecho=len(precios), total=len(precios))
        payload = armar_payload(precios, meta, uni, 600)
        payload["faltantes"] = sorted(
            set(t for t in tickers if t not in precios)
            | set(t for t in tickers if t not in {s["t"] for s in payload["simbolos"]}))
        guardar_payload(payload)

        tarde = sum(1 for t, n in atrasos(precios).items() if n > 0)
        marcar(corriendo=False, hay_datos=True, fecha=payload["fecha"],
               paso=f"listo: {len(payload['simbolos'])} simbolos"
                    + (f", {tarde} atrasados" if tarde else ""))
    except Exception as e:
        traceback.print_exc()
        marcar(corriendo=False, error=str(e), paso="fallo la actualizacion")


def lanzar(periodo, fund, completo):
    """Arranca la descarga si no hay otra en curso. Devuelve si la lanzo."""
    with CANDADO:
        if ESTADO["corriendo"]:
            return False
        ESTADO["corriendo"] = True
        ESTADO["error"] = ""
        ESTADO["paso"] = "arrancando"
    threading.Thread(target=descargar, args=(periodo, fund, completo),
                     daemon=True).start()
    return True


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        pass                      # sin ruido en la consola

    def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8",
                   gzipeado=False):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        if gzipeado:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj, codigo=200):
        self._responder(codigo, json.dumps(obj).encode("utf-8"))

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html"):
            if not PLANTILLA.exists():
                self._responder(500, b"Falta plantilla.html", "text/plain; charset=utf-8")
                return
            # La pagina va SIN datos: los pide por api/datos y muestra la barra.
            html = PLANTILLA.read_text(encoding="utf-8").replace(
                '/*__DATOS__*/ {fecha:"", simbolos:[]}', '{fecha:"",simbolos:[]}')
            self._responder(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if ruta == "/api/estado":
            e = leer_estado()
            e["hay_datos"] = CACHE_WEB.exists()
            self._json(e)
            return

        if ruta == "/api/datos":
            if not CACHE_WEB.exists():
                self._json({"simbolos": []}, 404)
                return
            acepta = self.headers.get("Accept-Encoding", "")
            crudo = CACHE_WEB.read_bytes()
            if "gzip" in acepta:
                self._responder(200, crudo, gzipeado=True)
            else:
                self._responder(200, gzip.decompress(crudo))
            return

        self._responder(404, b"no existe", "text/plain; charset=utf-8")

    def do_POST(self):
        p = urlparse(self.path)
        if p.path != "/api/actualizar":
            self._responder(404, b"no existe", "text/plain; charset=utf-8")
            return
        q = parse_qs(p.query)
        periodo = (q.get("periodo") or ["3y"])[0]
        fund = (q.get("fund") or ["1"])[0] != "0"
        completo = (q.get("completo") or ["0"])[0] == "1"
        if periodo not in ("1y", "2y", "3y", "5y", "10y", "max"):
            periodo = "3y"
        arranco = lanzar(periodo, fund, completo)
        self._json({"lanzado": arranco, **leer_estado()})


def main():
    ap = argparse.ArgumentParser(description="Screener con servidor local")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-abrir", action="store_true")
    ap.add_argument("--actualizar", action="store_true",
                    help="empieza a bajar los precios apenas arranca")
    args = ap.parse_args()

    if CACHE_WEB.exists():
        marcar(hay_datos=True,
               fecha=datetime.fromtimestamp(CACHE_WEB.stat().st_mtime)
               .strftime("%Y-%m-%d %H:%M"))

    url = f"http://127.0.0.1:{args.puerto}/"
    srv = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
    print(f"Screener ASH en {url}")
    print("Ctrl+C para cortar.")
    if args.actualizar or not CACHE_WEB.exists():
        print("No hay datos todavia: los empiezo a bajar.")
        lanzar("3y", True, False)
    if not args.sin_abrir:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nChau.")
        srv.shutdown()


if __name__ == "__main__":
    main()
