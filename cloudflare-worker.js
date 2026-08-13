/* =============================================================================
   PROXY PARA LOS PRECIOS DE YAHOO  ·  Cloudflare Worker, gratis
   =============================================================================

   PARA QUE SIRVE
   --------------
   El navegador sólo puede leer la respuesta de Yahoo si Yahoo manda la cabecera
   CORS que lo permite. Yahoo eso lo cambia cuando quiere y no depende de este
   proyecto. Si el screener te dice "no pude traer precios de hoy", este archivo
   es la solución definitiva: un proxy tuyo, que sí manda la cabecera.

   No guarda nada, no cuesta nada y el plan gratis de Cloudflare da 100.000
   pedidos por día — el screener usa ~465 cada vez que abrís el link.

   CÓMO SE PONE (cinco minutos, sin instalar nada)
   -----------------------------------------------
   1. Entrá a https://dash.cloudflare.com  ->  Workers & Pages  ->  Create
      -> Start with Hello World! -> Deploy.
   2. Tocá "Edit code", borrá lo que haya, pegá TODO este archivo y Deploy.
   3. Copiá la dirección que te queda (algo como
      https://mi-proxy.TU-USUARIO.workers.dev).
   4. En el screener: panel izquierdo -> Datos -> "Si Yahoo no contesta"
      -> pegala en el campo y tocá Probar.

   SEGURIDAD
   ---------
   Sólo deja pasar el endpoint de gráficos de Yahoo, nada más: no se puede usar
   como proxy abierto para cualquier cosa. Si querés cerrarlo del todo a tu
   sitio, poné tu dominio en ORIGENES.
   ========================================================================== */

// Poné acá tu página para que nadie más pueda usar tu proxy. Por ejemplo:
//   const ORIGENES = ['https://tuusuario.github.io'];
// Con la lista vacía, cualquiera que sepa la dirección lo puede usar.
const ORIGENES = [];

// Lo único que se deja pasar. No agregues rutas sin pensarlo.
const PERMITIDO = /^\/v8\/finance\/chart\/[^/]+$/;

export default {
  async fetch(pedido) {
    const url = new URL(pedido.url);
    const origen = pedido.headers.get('Origin') || '';
    const cors = {
      'Access-Control-Allow-Origin': ORIGENES.length
        ? (ORIGENES.includes(origen) ? origen : 'null')
        : '*',
      'Access-Control-Allow-Methods': 'GET,OPTIONS',
      'Access-Control-Max-Age': '86400',
    };

    if (pedido.method === 'OPTIONS') return new Response(null, { headers: cors });
    if (pedido.method !== 'GET') return new Response('sólo GET', { status: 405, headers: cors });
    if (ORIGENES.length && !ORIGENES.includes(origen))
      return new Response('origen no permitido', { status: 403, headers: cors });
    if (!PERMITIDO.test(url.pathname))
      return new Response('ruta no permitida', { status: 403, headers: cors });

    const destino = 'https://query1.finance.yahoo.com' + url.pathname + url.search;
    const r = await fetch(destino, {
      // Yahoo le contesta distinto a un cliente sin User-Agent
      headers: { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' },
      // un minuto de caché en el borde: si abrís el screener dos veces
      // seguidas, la segunda no vuelve a molestar a Yahoo
      cf: { cacheTtl: 60, cacheEverything: true },
    });

    return new Response(r.body, {
      status: r.status,
      headers: {
        ...cors,
        'Content-Type': r.headers.get('Content-Type') || 'application/json',
        'Cache-Control': 'public, max-age=60',
      },
    });
  },
};
