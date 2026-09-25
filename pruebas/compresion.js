/* ===========================================================================
   COMPRESION: dos rectas que se juntan
   ===========================================================================
   Como las lineas de tendencia, se verifica contra figuras armadas a mano,
   donde la respuesta se conoce de antemano: un triangulo tiene que dar su
   nombre, y lo que NO es una compresion -- una caja plana, una V, una caida
   con las rectas casi paralelas -- no tiene que dar nada. Esos tres casos son
   los que la primera version marcaba sobre los papeles reales.

   Despues la pagina: que la columna salga por defecto, que el filtro deje
   exactamente las filas que tienen figura, y que el grafico dibuje las rectas
   sin salirse del canvas.

   Lo que NO se prueba aca: si las rectas se ven como las traza un trader. Eso
   se miro dibujado sobre los 480 papeles reales (ver CLAUDE.md, seccion 4d).
   ======================================================================== */
const fs = require('fs'), path = require('path');
const M = require('./motor.js');

let fallas = 0;
const ok = (n, c, x) => { if (c) console.log('  ok     ' + n); else { fallas++;
  console.log('  FALLA  ' + n + (x !== undefined ? '   -> ' + x : '')); } };

/* Un tramo previo quieto y despues la figura: el precio va y viene entre un
   techo y un piso que son rectas, tocando los dos varias veces. Las velas
   miden ~2% de punta a punta, que es el ADR de una accion comun. */
function serie(previo, L, techo0, techoM, piso0, pisoM, ondas) {
  const b = { d: [], o: [], h: [], l: [], c: [], v: [] };
  const push = c => { b.d.push(20250101 + b.d.length); b.c.push(c); b.o.push(c * 0.999);
    b.h.push(c * 1.01); b.l.push(c * 0.99); b.v.push(1e6); };
  for (let i = 0; i < previo; i++) push(techo0 * (1 + 0.02 * Math.sin(i / 3)));
  for (let i = 0; i < L; i++) {
    const t = techo0 * (1 + techoM * i), p = piso0 * (1 + pisoM * i);
    const u = (Math.cos(2 * Math.PI * ondas * i / (L - 1)) + 1) / 2;
    push(p + (t - p) * u);
  }
  return b;
}
const conBarra = (b, c) => { const n = { d: [...b.d, b.d.at(-1) + 1], o: [...b.o, b.c.at(-1)],
  h: [...b.h, Math.max(c, b.c.at(-1)) * 1.002], l: [...b.l, Math.min(c, b.c.at(-1)) * 0.998],
  c: [...b.c, c], v: [...b.v, 1e6] }; return n; };

console.log('== las figuras, con su nombre ==');
{
  // techo baja 0,24%/rueda (0,12 ADR), piso plano: triangulo descendente
  const desc = serie(80, 40, 110, -0.0022, 100, 0, 4);
  const R = M.compresion(desc);
  ok('techo que baja contra piso plano: Triáng. desc.', R.estado === 'Triáng. desc.', R.estado);
  ok('encuentra el largo de la figura (30-60 ruedas)', R.barras >= 30 && R.barras <= 60, R.barras);
  ok('y cuánto se angostó (menos de la mitad)', R.apriete > 0 && R.apriete <= 0.55, R.apriete);
  ok('la resistencia queda arriba del precio', R.distRes >= 0, R.distRes);

  const sim = serie(80, 40, 110, -0.0011, 100, 0.0011, 4);
  ok('techo baja y piso sube: Triángulo', M.compresion(sim).estado === 'Triángulo', M.compresion(sim).estado);

  const asc = serie(80, 40, 110, 0, 100, 0.0022, 4);
  ok('techo plano y piso que sube: Triáng. asc.', M.compresion(asc).estado === 'Triáng. asc.', M.compresion(asc).estado);

  const P = M.CMP.plana * 2;
  ok('las dos bajando: Cuña bajista', M.tipoCompresion({ pendRes: -P * 2, pendSop: -P }) === 'Cuña bajista');
  ok('las dos subiendo: Cuña alcista', M.tipoCompresion({ pendRes: P, pendSop: P * 2 }) === 'Cuña alcista');
}

console.log('\n== lo que NO es una compresión ==');
{
  const caja = serie(80, 40, 110, 0, 100, 0, 4);
  ok('una caja plana (eso lo ve la caja, no esto)', M.compresion(caja).estado === '', M.compresion(caja).estado);

  // una V: cae 16% en 20 ruedas y vuelve. Las rectas salen de UN piso
  const v = { d: [], o: [], h: [], l: [], c: [], v: [] };
  const pushV = c => { v.d.push(20250101 + v.d.length); v.c.push(c); v.o.push(c); v.h.push(c * 1.01);
    v.l.push(c * 0.99); v.v.push(1e6); };
  for (let i = 0; i < 80; i++) pushV(100 * (1 + 0.02 * Math.sin(i / 3)));
  for (let i = 0; i < 20; i++) pushV(100 * (1 - 0.008 * i) * (1 + 0.004 * Math.sin(i)));
  for (let i = 0; i < 20; i++) pushV(84 * (1 + 0.009 * i) * (1 + 0.004 * Math.sin(i)));
  ok('una V (NVDA, HON: la recta sale de un solo piso)', M.compresion(v).estado === '', M.compresion(v).estado);

  /* una caida que se angosta: techo -0,25%/rueda (0,14 ADR, pasa el tope de
     pendiente), piso -0,10%/rueda. Se angosta al 20% y termina en menos de un
     rango diario: lo UNICO que la saca es que la linea media se corrio 0,9
     anchos. Si se afloja la deriva, entra como cuña. */
  const cae = serie(80, 40, 106, -0.0025, 100, -0.001, 4);
  ok('una caída con las rectas casi paralelas (SPGI, GM, SLB)', M.compresion(cae).estado === '', M.compresion(cae).estado);

  /* una caja angosta (1,5 rangos diarios): pasa todo menos el apriete, porque
     no se angosta nada. Eso es un rango, y lo ve la caja. */
  const angosta = { d: [], o: [], h: [], l: [], c: [], v: [] };
  for (let i = 0; i < 120; i++) { const c = 100 + (Math.cos(2 * Math.PI * i / 10) + 1) / 2;
    angosta.d.push(20250101 + i); angosta.c.push(c); angosta.o.push(c); angosta.h.push(c * 1.01);
    angosta.l.push(c * 0.99); angosta.v.push(1e6); }
  ok('una caja angosta que no se angosta', M.compresion(angosta).estado === '', M.compresion(angosta).estado);

  /* un triangulo corto y EMPINADO: 14 ruedas, cada recta 0,35%/rueda contra
     un ADR de 2% (~0,17 ADR por rueda). Llena el arranque, no se corre y se
     angosta: lo unico que lo saca es el tope de pendiente. Es la forma de una
     V suavizada, y en los papeles reales eran NVDA y HON. */
  const empinado = serie(80, 14, 110, -0.0035, 100, 0.0035, 3);
  ok('un triángulo con las rectas demasiado empinadas', M.compresion(empinado).estado === '',
     M.compresion(empinado).estado);

  // un solo toque arriba: el techo es UN pico al principio y despues nada lo toca
  const pico = serie(80, 40, 104, 0, 100, 0, 5);
  pico.h[80] = 118; pico.c[80] = 112;
  ok('una recta que no apoya al final no es una recta', M.compresion(pico).estado === '', M.compresion(pico).estado);
}

console.log('\n== con velas reales (guardadas del sitio publicado) ==');
{
  const R = JSON.parse(fs.readFileSync(path.join(__dirname, 'compresion_real.json'), 'utf8'));
  /* PG al 26/08: el techo sale de UN pico y el piso del fondo de una V. La
     primera version lo marcaba "Triángulo". Lo saca la regla de que el precio
     llene el arranque: estiradas hacia atras, las rectas no abrazan nada. */
  ok('PG al 26/08, una V: no es una compresión', M.compresion(R.PG).estado === '', M.compresion(R.PG).estado);
  ok('TGT al 25/09: Triáng. desc.', M.compresion(R.TGT).estado === 'Triáng. desc.', M.compresion(R.TGT).estado);
  ok('KO al 25/09: Triángulo', M.compresion(R.KO).estado === 'Triángulo', M.compresion(R.KO).estado);
}

console.log('\n== la ruptura ==');
{
  const desc = serie(80, 40, 110, -0.0022, 100, 0, 4);
  const antes = M.mejorCompresion(desc, desc.c.length);
  const n = desc.c.length, techoHoy = antes.res.m * n + antes.res.b, pisoHoy = antes.sop.m * n + antes.sop.b;
  const sube = conBarra(desc, techoHoy * 1.03);
  const R = M.compresion(sube);
  ok('cierra 3% arriba de la resistencia: Rompió ↑', R.estado === 'Rompió ↑', R.estado);
  ok('y reporta la figura de la que SALIÓ (la de ayer)', R.barras === antes.L && R.i0 === antes.i0,
     `${R.barras}/${R.i0} vs ${antes.L}/${antes.i0}`);
  ok('el precio queda arriba de la resistencia', R.distRes < 0, R.distRes);
  ok('abajo del piso: Rompió ↓', M.compresion(conBarra(desc, pisoHoy * 0.97)).estado === 'Rompió ↓');
  ok('adentro: sigue siendo la figura', M.compresion(conBarra(desc, (techoHoy + pisoHoy) / 2)).estado !== '' &&
     M.compresion(conBarra(desc, (techoHoy + pisoHoy) / 2)).estado.indexOf('Rompió') < 0);
}

console.log('\n== casos que no tienen que romper ==');
{
  const corta = serie(0, 8, 110, 0, 100, 0, 2);
  ok('serie más corta que la figura mínima', M.compresion(corta).estado === '');
  const hueco = serie(80, 40, 110, -0.0022, 100, 0, 4);
  hueco.l[100] = NaN;
  let r; try { r = M.compresion(hueco); } catch (e) { r = e; }
  ok('un hueco en los mínimos no explota', r && typeof r.estado === 'string', r);
  const cero = serie(80, 40, 110, -0.0022, 100, 0, 4); cero.c[cero.c.length - 1] = 0;
  ok('precio cero no explota', M.compresion(cero).estado === '');
}

/* ----------------------- la pagina ----------------------- */
const SITIO = process.env.SCREENER_SITIO || path.join(__dirname, 'tmp', 'sitio');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync(path.join(SITIO, 'index.html'), 'utf8');
const texto = fs.readFileSync(path.join(SITIO, 'datos.json'), 'utf8');
function abrir() {
  return new Promise(res => {
    const trazos = [];
    const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, url: 'https://local/',
      beforeParse(w) {
        const noop = () => {};
        let x = 0, y = 0;
        const ctx = new Proxy({}, { get: (_, k) => k === 'moveTo' || k === 'lineTo'
          ? (a, b) => { trazos.push([k, a, b]); } : k === 'measureText' ? () => ({ width: 10 }) : noop,
          set: () => true });
        w.HTMLCanvasElement.prototype.getContext = () => ctx;
        Object.defineProperty(w.HTMLCanvasElement.prototype, 'clientWidth', { get() { return 900; } });
        Object.defineProperty(w.HTMLCanvasElement.prototype, 'clientHeight', { get() { return 420; } });
        w.Element.prototype.scrollIntoView = noop;
        Object.defineProperty(w.HTMLElement.prototype, 'clientWidth', { get() { return 1200; } });
        Object.defineProperty(w, 'localStorage', { value: { _m: {}, getItem(k) { return this._m[k] ?? null; },
          setItem(k, v) { this._m[k] = String(v); }, removeItem(k) { delete this._m[k]; } }, configurable: true });
        w.TextEncoder = require('util').TextEncoder; w.TextDecoder = require('util').TextDecoder;
        w.fetch = async u => { const s = String(u);
          if (s.indexOf('datos.json') >= 0) return { ok: true, body: null, text: async () => texto };
          throw new TypeError('Failed to fetch'); };
      } });
    const w = dom.window;
    const t = setInterval(() => { if (w.document.querySelectorAll('#tabla tbody tr').length) {
      clearInterval(t); res({ w, trazos }); } }, 20);
  });
}
const esperar = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  console.log('\n== en la página: columna, filtro y gráfico ==');
  const { w, trazos } = await abrir();
  const $ = s => w.document.querySelector(s);
  const ths = [...w.document.querySelectorAll('#tabla thead th')].map(th => th.textContent.trim());
  ok('la columna Compresión sale por defecto', ths.some(t => /^Compresión/.test(t)), ths.join(' | '));
  const conFigura = w.eval('filas.filter(f=>f.compr).length');
  const quietas = w.eval("filas.filter(f=>f.compr&&f.compr.indexOf('Rompió')<0).length");
  ok('la fixtura trae figuras para probar', conFigura > 0 && quietas > 0 && quietas < conFigura, `${quietas}/${conFigura}`);
  const filasTabla = () => w.document.querySelectorAll('#tabla tbody tr').length;
  const elegir = async v => { $('#fCompr').value = v; $('#fCompr').dispatchEvent(new w.Event('change', { bubbles: true }));
    $('#fCompr').dispatchEvent(new w.Event('input', { bubbles: true })); await esperar(700); };
  await elegir('todo');
  ok('"Cualquiera, con rupturas" deja exactamente las que tienen figura', filasTabla() === conFigura,
     `${filasTabla()} vs ${conFigura}`);
  await elegir('any');
  ok('"Cualquier figura" saca las rupturas', filasTabla() === quietas, `${filasTabla()} vs ${quietas}`);
  const ru = w.eval("filas.filter(f=>f.compr==='Rompió ↑').length");
  await elegir('Rompió ↑');
  ok('"Rompió ↑" deja sólo esas', filasTabla() === ru && ru > 0, `${filasTabla()} vs ${ru}`);
  ok('el filtro se cuenta como puesto', /1/.test(($('#nFiltros') || { textContent: '1' }).textContent));
  w.eval('limpiarFiltros()'); await esperar(700);
  ok('limpiar lo saca (está en NEUTRO)', $('#fCompr').value === '', $('#fCompr').value);

  /* El grafico de un papel con figura. Se dibuja dos veces, con y sin la
     compresion, y se compara: lo que agrega tienen que ser exactamente sus
     dos rectas (dos moveTo y dos lineTo), y ninguna fuera del canvas. Se
     compara contra si mismo porque otras capas (la linea de tendencia larga)
     arrancan fuera del canvas y las recorta el clip: eso no es de aca. */
  const t = w.eval("filas.find(f=>f.compr).t");
  w.eval(`seleccionar(${JSON.stringify(t)})`);
  await esperar(300);
  const adentro = ([, x, y]) => x >= -1 && x <= 901 && y >= -1 && y <= 421;
  trazos.length = 0; w.eval('dibujar()'); const con = trazos.slice();
  w.eval('compresion=()=>({estado:""})');
  trazos.length = 0; w.eval('dibujar()'); const sin = trazos.slice();
  const clave = p => p.join(',');
  const quedan = new Map(); for (const p of sin) quedan.set(clave(p), (quedan.get(clave(p)) || 0) + 1);
  const nuevos = con.filter(p => { const k = clave(p), c = quedan.get(k) || 0; if (c) { quedan.set(k, c - 1); return false; } return true; });
  ok(`el gráfico de ${t} dibuja las dos rectas`, nuevos.length === 4 &&
     nuevos.filter(p => p[0] === 'moveTo').length === 2, JSON.stringify(nuevos));
  ok('y ninguna se sale del canvas', nuevos.every(adentro), JSON.stringify(nuevos.filter(p => !adentro(p))));

  console.log(fallas ? '\nFALLAS: ' + fallas : '\nCOMPRESION OK');
  process.exit(fallas ? 1 : 0);
})().catch(e => { console.error('EXPLOTO:', e); process.exit(1); });
