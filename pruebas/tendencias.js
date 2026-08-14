/* ===========================================================================
   LINEAS DE TENDENCIA
   ===========================================================================
   Se verifican contra figuras armadas a mano, donde la respuesta se conoce de
   antemano: un canal alcista tiene que dar "Canal alcista", un triangulo
   ascendente tiene que dar la resistencia plana y el soporte subiendo, y una
   serie sin forma no tiene que inventar un patron.

   Lo que NO se puede probar aca: si las lineas se ven bien. Eso lo tiene que
   mirar el usuario en el navegador.
   ======================================================================== */
const M = require('./motor.js');

let fallas = 0;
const ok = (n, c, x) => { if (c) console.log('  ok     ' + n); else { fallas++;
  console.log('  FALLA  ' + n + (x !== undefined ? '   -> ' + x : '')); } };

/* Arma una serie OHLC a partir de dos rectas (techo y piso) y una onda que va
   rebotando entre las dos. Asi la figura es exactamente la que se busca. */
function figura(n, techo0, techoM, piso0, pisoM, ondas) {
  const b = { d: [], o: [], h: [], l: [], c: [], v: [] };
  for (let i = 0; i < n; i++) {
    const techo = techo0 + techoM * i, piso = piso0 + pisoM * i;
    // una onda que toca los dos extremos varias veces
    const u = (Math.cos(2 * Math.PI * ondas * i / n) + 1) / 2;   // 0..1
    const c = piso + (techo - piso) * u;
    const cuerpo = (techo - piso) * 0.02;
    b.d.push(20250101 + i);
    b.c.push(c); b.o.push(c - cuerpo);
    b.h.push(c + cuerpo * 0.5); b.l.push(c - cuerpo * 1.5);
    b.v.push(1e6);
  }
  return b;
}

const cfg = { tlBarras: 120, tlPivote: 5 };

console.log('== los pivotes ==');
{
  const s = [1, 2, 5, 2, 1, 0, 1, 4, 1, 0, 1, 2, 1];
  const altos = M.pivotes(s, 2, true);
  const bajos = M.pivotes(s, 2, false);
  ok('encuentra los maximos locales', altos.includes(2) && altos.includes(7),
     altos.join(','));
  ok('encuentra los minimos locales', bajos.includes(5) && bajos.includes(9),
     bajos.join(','));
  ok('no marca las puntas', !altos.includes(0) && !altos.includes(s.length - 1),
     altos.join(','));
}

console.log('\n== la recta envolvente apoya, no parte al medio ==');
{
  // puntos sobre una recta y=2x+10, con algunos hundidos hacia abajo
  const xs = [0, 10, 20, 30, 40, 50], ys = [10, 30, 20, 70, 45, 110];
  const r = M.envolvente(xs, ys, true, 3);
  const debajo = xs.filter((x, i) => ys[i] > r.m * x + r.b + 1e-6);
  ok('ningun punto queda por encima de la recta de arriba', debajo.length === 0,
     debajo.join(','));
  const rb = M.envolvente(xs, ys, false, 3);
  const encima = xs.filter((x, i) => ys[i] < rb.m * x + rb.b - 1e-6);
  ok('ninguno queda por debajo de la de abajo', encima.length === 0, encima.join(','));
  ok('la de arriba va por arriba de la de abajo',
     r.m * 25 + r.b > rb.m * 25 + rb.b);
}

console.log('\n== canal alcista ==');
{
  const b = figura(140, 120, 0.5, 100, 0.5, 4);
  const t = M.tendencias(b, cfg);
  ok('lo clasifica bien', t.patron === 'Canal alcista', t.patron);
  ok('las dos pendientes son positivas', t.pendRes > 0 && t.pendSop > 0,
     t.pendRes.toFixed(4) + ' / ' + t.pendSop.toFixed(4));
  ok('la resistencia toca varias veces', t.tocRes >= 3, t.tocRes);
  ok('el soporte tambien', t.tocSop >= 3, t.tocSop);
}

console.log('\n== canal bajista ==');
{
  const b = figura(140, 220, -0.5, 200, -0.5, 4);
  const t = M.tendencias(b, cfg);
  ok('lo clasifica bien', t.patron === 'Canal bajista', t.patron);
  ok('las dos pendientes son negativas', t.pendRes < 0 && t.pendSop < 0,
     t.pendRes.toFixed(4) + ' / ' + t.pendSop.toFixed(4));
}

console.log('\n== triangulo ascendente: techo plano, piso subiendo ==');
{
  const b = figura(140, 200, 0, 120, 0.5, 5);
  const t = M.tendencias(b, cfg);
  ok('lo clasifica bien', t.patron === 'Triángulo asc.', t.patron);
  ok('la resistencia es casi plana', Math.abs(t.pendRes) < 0.015,
     t.pendRes.toFixed(4));
  ok('el soporte sube', t.pendSop > 0.015, t.pendSop.toFixed(4));
}

console.log('\n== triangulo descendente: techo bajando, piso plano ==');
{
  const b = figura(140, 220, -0.5, 120, 0, 5);
  const t = M.tendencias(b, cfg);
  ok('lo clasifica bien', t.patron === 'Triángulo desc.', t.patron);
}

console.log('\n== cuña: se cierra ==');
{
  const b = figura(140, 230, -0.4, 120, 0.4, 5);
  const t = M.tendencias(b, cfg);
  ok('lo clasifica bien', t.patron === 'Cuña / triángulo', t.patron);
  ok('las lineas convergen', t.pendRes < 0 && t.pendSop > 0,
     t.pendRes.toFixed(4) + ' / ' + t.pendSop.toFixed(4));
}

console.log('\n== rango lateral ==');
{
  const b = figura(140, 200, 0, 160, 0, 6);
  const t = M.tendencias(b, cfg);
  ok('lo clasifica bien', t.patron === 'Rango', t.patron);
}

console.log('\n== la distancia a las lineas ==');
{
  // rango 160-200; la onda arranca y termina en el techo (cos(0)=1)
  const b = figura(140, 200, 0, 160, 0, 6);
  const t = M.tendencias(b, cfg);
  ok('pegado al techo, la resistencia esta a menos de 2%',
     Math.abs(t.distRes) < 0.02, (t.distRes * 100).toFixed(2) + '%');
  ok('y el soporte quedo bien abajo', t.distSop > 0.15,
     (t.distSop * 100).toFixed(2) + '%');
}

console.log('\n== ruido sin forma: no inventa nada ==');
{
  let semilla = 42;
  const rnd = () => (semilla = (semilla * 1103515245 + 12345) % 2147483648) / 2147483648;
  const b = { d: [], o: [], h: [], l: [], c: [], v: [] };
  let p = 100;
  for (let i = 0; i < 140; i++) {
    p *= 1 + (rnd() - 0.5) * 0.05;
    b.d.push(20250101 + i); b.c.push(p); b.o.push(p);
    b.h.push(p * 1.01); b.l.push(p * 0.99); b.v.push(1e6);
  }
  const t = M.tendencias(b, cfg);
  ok('no explota con ruido', isFinite(t.distRes) || t.patron === '', t.patron);
  ok('el techo sigue por encima del piso en la ultima barra',
     !t.res || !t.sop || (t.res.m * (t.N - 1) + t.res.b) >= (t.sop.m * (t.N - 1) + t.sop.b),
     t.patron);
}

console.log('\n== casos limite ==');
{
  const corta = { d: [1, 2, 3], o: [1, 1, 1], h: [1, 1, 1], l: [1, 1, 1], c: [1, 1, 1], v: [0, 0, 0] };
  const t = M.tendencias(corta, cfg);
  ok('una serie corta no rompe', t.patron === '' && t.tocRes === 0, JSON.stringify(t.patron));
  const plana = figura(140, 100, 0, 100, 0, 3);
  const t2 = M.tendencias(plana, cfg);
  ok('una serie sin rango no rompe', isFinite(t2.pendRes) || t2.patron === '', t2.patron);
  ok('regresion con un solo punto devuelve null', M.regresion([1], [1]) === null);
}

console.log(fallas ? '\nFALLAS: ' + fallas : '\nTENDENCIAS OK');
process.exit(fallas ? 1 : 0);
