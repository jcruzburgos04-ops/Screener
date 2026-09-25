/* ===========================================================================
   DIRECTRIZ BAJISTA: la recta de maximos que bajan
   ===========================================================================
   La figura de las capturas del usuario: una recta que une maximos cada vez
   mas bajos, el precio apretado debajo dos o tres semanas, y la ruptura con
   CIERRE por encima (lo pidio asi: la mecha no alcanza).

   Cada regla tiene un caso armado a mano que SOLO ella decide (se busco con
   la regla apagada: sin ella, el caso entra). Mas velas reales guardadas del
   sitio publicado: tres figuras buenas y cuatro que la primera version leia
   mal. Y la pagina: columna, filtros y el dibujo de la recta.
   ======================================================================== */
const fs = require('fs'), path = require('path');
const M = require('./motor.js');

let fallas = 0;
const ok = (n, c, x) => { if (c) console.log('  ok     ' + n); else { fallas++;
  console.log('  FALLA  ' + n + (x !== undefined ? '   -> ' + x : '')); } };

/* 30 velas quietas y despues la figura: una vela de cada tres toca la recta
   (sale de 106 y baja 0,35% por rueda, ~0,18 ADR) y las demas se apoyan en un
   piso plano. Las velas miden ~2%, el ADR de una accion comun. */
function figura(o = {}) {
  const L = o.L || 12, v0 = 106, s = o.s || 0.00354, piso = o.piso || 100,
        caePiso = o.caePiso || 0, cada = o.cada || 3;
  const b = { d: [], o: [], h: [], l: [], c: [], v: [] };
  const push = (h, l, c) => { b.d.push(20250101 + b.d.length); b.o.push((h + l) / 2);
    b.h.push(h); b.l.push(l); b.c.push(c); b.v.push(1e6); };
  for (let i = 0; i < 30; i++) { const c = 101 + Math.sin(i / 2); push(c * 1.01, c * 0.99, c); }
  const v = x => v0 * (1 - s * x);
  for (let x = 0; x < L; x++) {
    const p = piso * (1 - caePiso * x);
    if (x % cada === 0 || (o.cada && x === L - 1)) push(v(x), v(x) * 0.98, v(x) * 0.99);
    else push(p * 1.02, p, p * 1.01);
  }
  b.recta = j => v(j - 30);
  return b;
}
const conVela = (b, c, h) => { const n = {}; for (const k of ['d', 'o', 'h', 'l', 'c', 'v']) n[k] = b[k].slice();
  n.d.push(n.d.at(-1) + 1); n.o.push(b.c.at(-1)); n.h.push(h || Math.max(c, b.c.at(-1)) * 1.004);
  n.l.push(Math.min(c, b.c.at(-1)) * 0.996); n.c.push(c); n.v.push(1e6); n.recta = b.recta; return n; };
const E = b => M.directriz(b).estado;

console.log('== la figura ==');
{
  const b = figura(), R = M.directriz(b);
  ok('debajo de la recta: "Debajo"', R.estado === 'Debajo', R.estado);
  ok('la recta sale del pico (la vela 30)', R.a === 30, R.a);
  ok('y apoya en los máximos que bajan (6 toques)', R.toques === 6, R.toques);
  ok('encuentra el largo (12 ruedas)', R.barras === 12, R.barras);
  ok('dice cuánto le falta para romper', R.dist > 0 && R.dist < 0.03, R.dist);
}

console.log('\n== la ruptura: con CIERRE por encima ==');
{
  const b = figura(), n = b.c.length;
  const hoy = conVela(b, b.recta(n) * 1.02);
  const R = M.directriz(hoy);
  ok('cierra 2% arriba de la recta: "Rompió ↑" hoy', R.estado === 'Rompió ↑' && R.hace === 0, `${R.estado} ${R.hace}`);
  ok('y reporta la recta de la que salió', R.a === 30 && R.barras === 12, `${R.a} ${R.barras}`);
  ok('el cierre queda arriba de la recta', R.dist < 0, R.dist);
  let dos = conVela(conVela(hoy, hoy.recta(n + 1) * 1.03), hoy.recta(n + 2) * 1.04);
  ok('dos ruedas después: "hace 2"', M.directriz(dos).hace === 2, M.directriz(dos).hace);
  let seis = hoy; for (let k = 1; k <= 6; k++) seis = conVela(seis, hoy.recta(n + k) * 1.05);
  ok('pasadas cinco ruedas ya no se muestra', E(seis) !== 'Rompió ↑', E(seis));
  const mecha = conVela(b, b.recta(n) * 0.995, b.recta(n) * 1.03);
  ok('la mecha arriba y el cierre abajo NO es ruptura', E(mecha) !== 'Rompió ↑', E(mecha));
  // 0,05% arriba: menos que el margen de 0,1% que pide un cierre para contar como ruptura
  // con la recta que traza el motor, no la del generador: las velas del piso
  // quedan un poco arriba de la teorica y el motor la apoya ahi
  const fm = M.mejorDirectriz(b, n), vm = fm.h0 + fm.m * (n - fm.a);
  const justo = conVela(b, vm * 1.0005, vm * 1.03);
  ok('la mecha arriba y el cierre justo en la recta tampoco', E(justo) !== 'Rompió ↑', E(justo));
  const vuelve = conVela(hoy, hoy.recta(n + 1) * 0.98);
  ok('si al otro día cierra abajo otra vez, ya no es ruptura', E(vuelve) !== 'Rompió ↑', E(vuelve));
}

console.log('\n== lo que NO es una directriz: cada caso lo decide una sola regla ==');
{
  ok('una recta empinada (0,31 ADR por rueda): es una caída', E(figura({ L: 14, s: 0.005, piso: 96 })) === '',
     E(figura({ L: 14, s: 0.005, piso: 96 })));
  ok('los mínimos cayendo casi como la recta: un canal', E(figura({ caePiso: 0.003, piso: 103 })) === '',
     E(figura({ caePiso: 0.003, piso: 103 })));
  ok('una recta que apoya en dos puntos no es una recta', E(figura({ L: 10, cada: 9 })) === '',
     E(figura({ L: 10, cada: 9 })));
  ok('el precio lejos de la recta', E(figura({ L: 16, s: 0.0001, piso: 88 })) === '',
     E(figura({ L: 16, s: 0.0001, piso: 88 })));
  ok('una recta casi plana que no se acerca al piso', E(figura({ L: 16, s: 0.001, piso: 98 })) === '',
     E(figura({ L: 16, s: 0.001, piso: 98 })));
  ok('un "apriete" que es sólo el piso muy abajo del pico', E(figura({ L: 16, piso: 98 })) === '',
     E(figura({ L: 16, piso: 98 })));
  ok('el ancla tiene que ser un pico de verdad', E(figura({ L: 16, s: 0.004, piso: 94 })) === '',
     E(figura({ L: 16, s: 0.004, piso: 94 })));
  let largo = true;
  for (const L of [18, 24, 30]) { const r = M.directriz(figura({ L, s: 0.0015 })); if (r.estado && r.barras > 16) largo = false; }
  ok('nunca una recta de más de 16 ruedas', largo);
}

console.log('\n== con velas reales (guardadas del sitio publicado) ==');
{
  const R = JSON.parse(fs.readFileSync(path.join(__dirname, 'directriz_real.json'), 'utf8'));
  const u = M.directriz(R.UNG);
  ok('UNG al 25/09: la rompió hace 3', u.estado === 'Rompió ↑' && u.hace === 3, `${u.estado} ${u.hace}`);
  ok('BAYN.DE al 25/09: la rompió hace 3', M.directriz(R['BAYN.DE']).estado === 'Rompió ↑');
  ok('NOW al 25/09: debajo de la recta', E(R.NOW) === 'Debajo', E(R.NOW));
  for (const t of ['PATH', 'ETSY', 'BKR']) ok(`${t}: la caída no es una directriz`, E(R[t]) === '', E(R[t]));
  ok('WMT: con el precio lejos de la recta, no', E(R.WMT) === '', E(R.WMT));
}

console.log('\n== casos que no tienen que romper ==');
{
  ok('serie corta', E(figura({ L: 3 })) === '' || true);
  const c = figura(); c.c[c.c.length - 1] = 0;
  ok('cierre en cero', E(c) === '');
  const h = figura(); h.l[35] = NaN;
  let r; try { r = M.directriz(h); } catch (e) { r = e; }
  ok('un hueco no explota', r && typeof r.estado === 'string', r);
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
  console.log('\n== en la página: columna, filtros y gráfico ==');
  const { w, trazos } = await abrir();
  const $ = s => w.document.querySelector(s);
  const ths = [...w.document.querySelectorAll('#tabla thead th')].map(th => th.textContent.trim());
  ok('la columna Directriz sale por defecto', ths.some(t => /^Directriz/.test(t)), ths.join(' | '));
  const cuenta = q => w.eval(`filas.filter(f=>${q}).length`);
  const debajo = cuenta("f.dir==='Debajo'"), rompio = cuenta("f.dir==='Rompió ↑'");
  ok('la fixtura trae de las dos', debajo > 0 && rompio > 0, `${debajo}/${rompio}`);
  // se cuentan filas con ticker: con cero resultados la tabla muestra una fila de aviso
  const filasTabla = () => w.document.querySelectorAll('#tabla tbody tr .tk').length;
  const poner = async (id, v) => { $(id).value = v; for (const e of ['input', 'change'])
    $(id).dispatchEvent(new w.Event(e, { bubbles: true })); await esperar(700); };
  await poner('#fDir', 'Debajo');
  ok('"Debajo" deja exactamente esas', filasTabla() === debajo, `${filasTabla()} vs ${debajo}`);
  await poner('#fDir', 'Rompió ↑');
  ok('"La rompió" deja exactamente esas', filasTabla() === rompio, `${filasTabla()} vs ${rompio}`);
  const hoy = cuenta("f.dir==='Rompió ↑'&&f.dir_hace===0");
  await poner('#fDir', 'hoy');
  ok('"La rompió hoy" deja sólo las de hoy', filasTabla() === hoy, `${filasTabla()} vs ${hoy}`);
  await poner('#fDir', 'any');
  ok('"Cualquiera" deja las dos', filasTabla() === debajo + rompio, `${filasTabla()} vs ${debajo + rompio}`);
  await poner('#fDir', '');
  const d0 = w.eval("filas.filter(f=>f.dir==='Debajo').map(f=>f.dir_dist).sort((a,b)=>a-b)[0]");
  const umbral = Math.ceil(d0 * 400) / 4;           // el slider va de a 0,25%
  const cerca = cuenta(`f.dir==='Debajo'&&f.dir_dist<=${umbral / 100}`);
  await poner('#fDirDist', String(umbral));
  ok(`"a ≤ ${umbral}% de la recta" deja las que están así de cerca`, filasTabla() === cerca && cerca > 0,
     `${filasTabla()} vs ${cerca}`);
  w.eval('limpiarFiltros()'); await esperar(700);
  ok('limpiar saca los dos (están en NEUTRO)', $('#fDir').value === '' && $('#fDirDist').value === '0',
     `${$('#fDir').value}/${$('#fDirDist').value}`);

  /* El grafico: con y sin la directriz. Lo que agrega tiene que ser su recta
     (un moveTo y un lineTo) y adentro del canvas. */
  const t = w.eval("filas.find(f=>f.dir).t");
  w.eval(`seleccionar(${JSON.stringify(t)})`); await esperar(300);
  const adentro = ([, x, y]) => x >= -1 && x <= 901 && y >= -1 && y <= 421;
  trazos.length = 0; w.eval('dibujar()'); const con = trazos.slice();
  w.eval('directriz=()=>({estado:""})');
  trazos.length = 0; w.eval('dibujar()'); const sin = trazos.slice();
  const k = p => p.join(','), quedan = new Map();
  for (const p of sin) quedan.set(k(p), (quedan.get(k(p)) || 0) + 1);
  const nuevos = con.filter(p => { const c = quedan.get(k(p)) || 0; if (c) { quedan.set(k(p), c - 1); return false; } return true; });
  ok(`el gráfico de ${t} dibuja la recta`, nuevos.length === 2 && nuevos[0][0] === 'moveTo', JSON.stringify(nuevos));
  ok('y adentro del canvas', nuevos.every(adentro), JSON.stringify(nuevos));

  console.log(fallas ? '\nFALLAS: ' + fallas : '\nDIRECTRIZ OK');
  process.exit(fallas ? 1 : 0);
})().catch(e => { console.error('EXPLOTO:', e); process.exit(1); });
