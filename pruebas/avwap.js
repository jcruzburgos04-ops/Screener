/* ===========================================================================
   AVWAP ANCLADO AL ULTIMO MAXIMO FRACTAL
   ===========================================================================
   Se verifica contra series armadas a mano, donde el ancla correcta y el valor
   del VWAP se conocen de antemano. Tres cosas que importan:

     1. Que el ancla sea el ultimo maximo TODAVIA NO SUPERADO, que es el techo
        con el que el precio esta peleando, y no cualquier micro-pico.
     2. Que el VWAP sea el de verdad: suma de (precio tipico x volumen) sobre
        suma de volumen, desde el ancla.
     3. Que "Recuperado" signifique que cruzo hace poco y no que esta encima
        desde hace tres meses.
   ======================================================================== */
const M = require('./motor.js');

let fallas = 0;
const ok = (n, c, x) => { if (c) console.log('  ok     ' + n); else { fallas++;
  console.log('  FALLA  ' + n + (x !== undefined ? '   -> ' + x : '')); } };

const cfg = { tlBarras: 120, tlPivote: 3 };

/* serie a partir de una lista de cierres; el rango de cada barra es +-1% */
function serie(cierres, vols) {
  const b = { d: [], o: [], h: [], l: [], c: [], v: [] };
  cierres.forEach((c, i) => {
    b.d.push(20250101 + i); b.o.push(c); b.c.push(c);
    b.h.push(c * 1.01); b.l.push(c * 0.99);
    b.v.push(vols ? vols[i] : 1000);
  });
  return b;
}

console.log('== el VWAP es el de verdad ==');
{
  // dos barras: precios tipicos 100 y 200, volumenes 1 y 3
  // VWAP = (100*1 + 200*3) / 4 = 175
  const b = { d: [1, 2], o: [100, 200], h: [100, 200], l: [100, 200],
              c: [100, 200], v: [1, 3] };
  const v = M.avwapDesde(b, 0);
  ok('pondera por volumen', Math.abs(v[1] - 175) < 1e-9, v[1]);
  ok('la primera barra es su propio precio', Math.abs(v[0] - 100) < 1e-9, v[0]);
  const v2 = M.avwapDesde(b, 1);
  ok('anclado en la segunda, arranca ahi', Math.abs(v2[1] - 200) < 1e-9, v2[1]);
  ok('antes del ancla no hay valor', !isFinite(v2[0]), v2[0]);
  const sinVol = { d: [1, 2], o: [10, 20], h: [10, 20], l: [10, 20], c: [10, 20], v: [0, 0] };
  ok('sin volumen no explota', isFinite(M.avwapDesde(sinVol, 0)[1]),
     M.avwapDesde(sinVol, 0)[1]);
}

console.log('\n== el ancla es el ultimo maximo NO superado ==');
{
  // sube a 120 (pivote), cae, sube a 150 (pivote mas alto), cae y se queda
  const c = [];
  for (let i = 0; i < 12; i++) c.push(100 + i * 1.6);      // hasta ~118
  for (let i = 0; i < 10; i++) c.push(119 - i * 1.5);      // baja
  for (let i = 0; i < 14; i++) c.push(104 + i * 3.3);      // sube a ~147
  for (let i = 0; i < 20; i++) c.push(150 - i * 1.4);      // baja y se queda
  const b = serie(c);
  const i = M.anclaMaximo(b, cfg);
  const maxIdx = b.h.indexOf(Math.max(...b.h));
  ok('ancla en el maximo mas alto sin superar', Math.abs(i - maxIdx) <= 3,
     `ancla=${i} maximo=${maxIdx}`);
  ok('no ancla en el pivote viejo de 118', i > 25, i);
}

console.log('\n== una tendencia alcista con retrocesos: ancla en el ultimo pico ==');
{
  // sube en escalones, con retrocesos, como sube un papel de verdad
  const c = [];
  let p = 100;
  for (let tramo = 0; tramo < 6; tramo++) {
    for (let i = 0; i < 8; i++) { p *= 1.02; c.push(p); }     // impulso
    for (let i = 0; i < 5; i++) { p *= 0.99; c.push(p); }     // retroceso
  }
  const b = serie(c);
  const i = M.anclaMaximo(b, cfg);
  ok('encuentra un ancla', i >= 0, i);
  ok('y es el pico mas reciente', i > c.length - 20, `${i} de ${c.length}`);
  ok('el ancla es un maximo local', b.h[i] >= b.h[i - 1] && b.h[i] >= b.h[i + 1],
     `${b.h[i - 1]} / ${b.h[i]} / ${b.h[i + 1]}`);
}

console.log('\n== sin ningun pivote no se inventa un ancla ==');
{
  // una recta perfecta hacia arriba: ninguna barra domina a las de la derecha,
  // asi que no hay maximo fractal. Que devuelva "no hay" es lo correcto: un
  // papel sin techo reciente no tiene el patron que se esta buscando.
  const c = [];
  for (let i = 0; i < 60; i++) c.push(100 * Math.pow(1.01, i));
  ok('devuelve -1', M.anclaMaximo(serie(c), cfg) === -1, M.anclaMaximo(serie(c), cfg));
  const r = M.avwapAncladp(serie(c), cfg);
  ok('y el resultado queda vacio', !isFinite(r.valor) && r.estado === '', JSON.stringify(r));
}

console.log('\n== el patron que pidio el usuario: vuelta al AVWAP desde el maximo ==');
{
  // maximo, caida larga con volumen, y recuperacion que cruza la linea recien
  const c = [], v = [];
  for (let i = 0; i < 10; i++) { c.push(100 + i); v.push(1000); }      // sube a 109
  c.push(112); v.push(3000);                                          // EL MAXIMO
  for (let i = 0; i < 25; i++) { c.push(111 - i * 1.4); v.push(2000); } // cae a ~77
  for (let i = 0; i < 12; i++) { c.push(77 + i * 3.1); v.push(1500); }  // vuelve rapido
  const b = serie(c, v);
  const r = M.avwapAncladp(b, cfg);
  ok('encontro el ancla', r.ancla > 0, r.ancla);
  ok('el ancla es el maximo', Math.abs(b.h[r.ancla] - Math.max(...b.h)) < 1e-6,
     `${b.h[r.ancla]} vs ${Math.max(...b.h)}`);
  ok('el AVWAP queda entre el minimo y el maximo', r.valor > 77 && r.valor < 113,
     r.valor.toFixed(2));
  ok('cuenta las ruedas desde el ancla', r.barras === b.c.length - 1 - r.ancla,
     r.barras);
  ok('detecta que acaba de recuperarlo', r.estado === 'Recuperado',
     `${r.estado} dist=${(r.dist * 100).toFixed(2)}% cruce=${r.cruce}`);
  ok('el cruce es reciente', r.cruce >= 0 && r.cruce <= 10, r.cruce);
}

console.log('\n== los cuatro estados ==');
{
  // encima desde hace mucho: sube y se queda arriba
  const c = [];
  for (let i = 0; i < 10; i++) c.push(100 + i);
  c.push(112);
  for (let i = 0; i < 6; i++) c.push(111 - i);
  for (let i = 0; i < 40; i++) c.push(106 + i * 1.2);   // muy por encima, hace rato
  const r = M.avwapAncladp(serie(c), cfg);
  ok('encima desde hace rato = "Encima"', r.estado === 'Encima',
     `${r.estado} cruce=${r.cruce}`);
  ok('y la distancia es positiva', r.dist > 0, (r.dist * 100).toFixed(1) + '%');

  // debajo desde hace mucho
  const c2 = [];
  for (let i = 0; i < 10; i++) c2.push(100 + i);
  c2.push(112);
  for (let i = 0; i < 45; i++) c2.push(110 - i * 1.2);
  const r2 = M.avwapAncladp(serie(c2), cfg);
  ok('debajo desde hace rato = "Debajo"', r2.estado === 'Debajo',
     `${r2.estado} cruce=${r2.cruce}`);
  ok('y la distancia es negativa', r2.dist < 0, (r2.dist * 100).toFixed(1) + '%');
}

console.log('\n== casos que no tienen que romper ==');
{
  const corta = serie([1, 2, 3]);
  const r = M.avwapAncladp(corta, cfg);
  ok('serie corta devuelve vacio', r.ancla === -1 && !isFinite(r.valor), JSON.stringify(r));
  const plana = serie(new Array(60).fill(100));
  const r2 = M.avwapAncladp(plana, cfg);
  ok('serie plana no explota', !isFinite(r2.valor) || isFinite(r2.valor), r2.estado);
  ok('anclaMaximo con serie corta devuelve -1', M.anclaMaximo(serie([1, 2]), cfg) === -1);
}

console.log(fallas ? '\nFALLAS: ' + fallas : '\nAVWAP OK');
process.exit(fallas ? 1 : 0);
