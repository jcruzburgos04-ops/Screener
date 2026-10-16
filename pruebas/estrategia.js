/* ===========================================================================
   ESTRATEGIA (base v3.1)
   ===========================================================================
   1. PARIDAD con estrategia.py, la referencia en Python: todas las columnas,
      todos los filtros y el ASH del SPY, en varias fechas de la fixtura. Es el
      mismo invariante que el del ASH: si tocas una, toca la otra.
   2. LAS REGLAS UNA POR UNA, con series armadas a mano para cada borde: el
      dia 20 del cruce entra y el 21 no, el empate con la linea del regimen no
      cambia el estado, la vela de 3 dias, la semana del Viernes Santo, la vela
      de hoy antes de las 16:30, SL y TP en la misma vela...
   3. LA PANTALLA en jsdom: cartel, casi-senales, RS en rojo sin universo
      amplio, registro de operaciones, re-entrada y respaldo.
   Los precios son SINTETICOS: se prueba la maquinaria. Los numeros contra
   Yahoo de verdad los da la sonda de Actions (ver CLAUDE.md, seccion 4f).
   ======================================================================== */
const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const SITIO=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const M=require('./motor.js');
let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'   -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
const P=JSON.parse(fs.readFileSync(path.join(SITIO,'datos.json'),'utf8'));
// todo sobre el calendario del SPY, como la pagina y como el backtest
const S0=new Map(P.simbolos.map(s=>[s.t,s])),spy=M.alinearEstr(S0.get('SPY'),S0.get('SPY').d);
const S=new Map([...S0].map(([t,s])=>[t,t==='SPY'?spy:M.alinearEstr(s,spy.d)]).filter(x=>x[1]));

console.log('== 1. paridad con estrategia.py ==');
{
  const n=spy.d.length,fechas=[spy.d[n-1],spy.d[n-120],spy.d[n-300]];
  if(spy.d.includes(20261002))fechas.push(20261002);
  const tmp=path.join(__dirname,'tmp','estr_ref.json');
  execFileSync('python3',[path.join(__dirname,'estrategia_ref.py'),path.join(SITIO,'datos.json'),tmp,fechas.join(',')]);
  const ref=JSON.parse(fs.readFileSync(tmp,'utf8'));
  let peor=0,donde='',dec=0,ejemplo='',filas=0,pasan=0,ashPeor=0,ashDec=0;
  for(const R of fechas){
    const u=M.universoEstr(P.simbolos,P.estr_adr).tickers.filter(t=>S.has(t));
    ok(`mismo universo el ${R}`,JSON.stringify(u)===JSON.stringify(ref[R].universo),
      u.length+' vs '+ref[R].universo.length);
    const fil=u.map(t=>M.evaluarEstr(S.get(t),spy,R,null,spy.d)).filter(Boolean);
    const U=fil.map(f=>f.rs_puntaje).filter(isFinite).sort((a,b)=>a-b);
    fil.forEach(f=>{f.rs=M.rsDePuntaje(f.rs_puntaje,U);f.f3=f.rs>70;
      f.pasa=[1,2,3,4,5,6,7,8].every(k=>f['f'+k]);});
    M.prioridadEstr(fil);
    ok(`mismas filas el ${R}`,fil.length===Object.keys(ref[R].filas).length);
    for(const f of fil){const r=ref[R].filas[f.t];filas++;pasan+=f.pasa;
      for(const k of Object.keys(r)){const x=f[k],y=r[k];
        if(typeof y==='boolean'){if(x!==y){dec++;ejemplo=`${R} ${f.t} ${k}`;}continue;}
        if(typeof y==='number'){const e=isFinite(x)?Math.abs(x-y)/Math.max(1e-9,Math.abs(y)):Infinity;
          if(e>peor){peor=e;donde=`${R} ${f.t} ${k}`;}}
        else if(y===null&&x!=null&&isFinite(x)){dec++;ejemplo=`${R} ${f.t} ${k} (null en Python)`;}}}
    if(R===fechas[0]){
      // cuando salto la senal: mismo dia, misma entrada, mismo destino
      const prop=new Map(),pau=new Map();
      const uDe=d=>{if(!prop.has(d)){const ns=M.cuantos?0:0;const cs=spy.c.slice(0,spy.d.filter(x=>x<=d).length);
        prop.set(d,u.map(t=>{const s=S.get(t),n=s.d.filter(x=>x<=d).length;
          return n&&s.d[n-1]===d?M.puntajeRs(s.c.slice(0,n),cs):NaN;}).filter(isFinite).sort((a,b)=>a-b));}
        return prop.get(d);};
      const pDe=d=>{if(!pau.has(d))pau.set(d,M.ashSpy(spy,d).pausa);return pau.get(d);};
      let hn=0,hpeor=0,hdec=0,hej='',viejas=0,salieron=0;
      for(const [t,h] of Object.entries(ref[R].historia)){
        const f=fil.find(x=>x.t===t),j=M.historiaSenal(S.get(t),spy,R,f.fecha_cruce,uDe,pDe,spy.d);hn++;
        if(!h){if(j){hdec++;hej=t;}continue;}
        for(const [k,y] of [['fecha',h.fecha],['ruedas',h.ruedas],['salida',h.salida],
            ['salida_fecha',h.salida_fecha],['activa',h.activa],['enPausa',h.en_pausa]])
          if((j[k]??null)!==(y??null)){hdec++;hej=`${t} ${k}: ${j[k]} vs ${y}`;}
        for(const [k,y] of [['entry',h.entry],['atr_pct',h.atr_pct],['rs',h.rs],['salida_precio',h.salida_precio]]){
          if(y==null)continue;hpeor=Math.max(hpeor,Math.abs(j[k]-y)/Math.abs(y));}
        if(h.fecha){viejas+=h.ruedas>0;salieron+=!!h.salida;
          // el dia de la senal: pasa todo y el SPY no esta en pausa; entra a ese cierre
          const e=M.evaluarEstr(S.get(t),spy,h.fecha,uDe(h.fecha),spy.d);
          if(!e.pasa||pDe(h.fecha)||e.cierre!==j.entry){hdec++;hej=t+' el dia de la senal no cierra';}
          // y antes, ninguno sin pausa que pasara: es el PRIMERO
          const s=S.get(t);for(let k=s.d.indexOf(f.fecha_cruce);s.d[k]<h.fecha;k++){
            const e2=M.evaluarEstr(s,spy,s.d[k],uDe(s.d[k]),spy.d);
            if(e2&&e2.pasa&&!pDe(s.d[k])){hdec++;hej=t+' habia una senal antes';}}}}
      ok('cuándo saltó la señal: Python y JS dicen el mismo día, entrada y salida',
        hdec===0&&hpeor<1e-10,hdec+' · '+hej+' · '+hpeor);
      ok('es el PRIMER día sin pausa con todo cumplido, y entra a ese cierre',hdec===0);
      ok('y la prueba compara algo: hay señales viejas',hn>5&&viejas>0,`${hn} historias, ${viejas} viejas, ${salieron} ya salieron`);
    }
    const a=M.ashSpy(spy,R),b=ref[R].ash;
    for(const q of ['diario','semanal'])for(const z of ['bulls','bears'])
      ashPeor=Math.max(ashPeor,Math.abs(a[q][z]-b[q][z])/Math.abs(b[q][z]));
    if(a.pausa!==b.pausa||a.diario.pausa!==b.diario.pausa||a.semanal.pausa!==b.semanal.pausa||
       a.semanal.semana!==b.semanal.semana)ashDec++;}
  ok('todas las columnas coinciden (desvío relativo < 1e-10)',peor<1e-10,peor.toExponential(2)+' en '+donde);
  ok('ninguna decisión distinta (filtros 1-8 y pasa)',dec===0,dec+' · '+ejemplo);
  ok('el ASH del SPY coincide, diario y semanal',ashPeor<1e-10&&ashDec===0,ashPeor+' / '+ashDec);
  ok('y la prueba compara algo: filas y señales',filas>500&&pasan>0,filas+' filas, '+pasan+' señales');
  console.log(`         (${filas} filas en ${fechas.length} fechas, desvío máximo ${peor.toExponential(1)})`);
}

console.log('\n== 2. las reglas, una por una ==');
// calendario de ruedas reales alrededor del ancla
const dias=(a,b)=>{const o=[];for(let d=M.__aDia?0:0,t=Date.UTC(+String(a).slice(0,4),+String(a).slice(4,6)-1,+String(a).slice(6));;t+=86400000){
  const x=new Date(t),f=x.getUTCFullYear()*10000+(x.getUTCMonth()+1)*100+x.getUTCDate();if(f>b)break;
  const w=x.getUTCDay();if(w&&w<6&&!M.feriadosNYSE(x.getUTCFullYear()).has(t/86400000))o.push(f);}return o;};
{
  const cal=dias(20250101,20261231);
  ok('feriados 2026 por regla: Viernes Santo 3/4, 3/7 por el 4 de julio sábado, Juneteenth 19/6',
    !cal.includes(20260403)&&!cal.includes(20260703)&&!cal.includes(20260619)&&cal.includes(20260702));
  ok('el 1/1 que cae sábado NO se corre al 31/12 (regla de NYSE)',dias(20211230,20211231).includes(20211231));
  ok('semana del Viernes Santo: cierra el jueves 2/4/2026',M.semanaCerrada(20260402));
  ok('un jueves cualquiera no cierra la semana',!M.semanaCerrada(20261015));
  ok('el viernes la cierra',M.semanaCerrada(20261016));
  // velas de 3 dias: "las siguientes son 5-6-7 de octubre, 8-9-12 de octubre"
  const b={d:cal,o:cal.map((_,i)=>100+i),h:cal.map((_,i)=>101+i),l:cal.map((_,i)=>99+i),c:cal.map((_,i)=>100.5+i)};
  const n=M.velas3d(b,cal.indexOf(20261015)+1,cal,20261015);
  const fin=n.fin.slice(-4);
  ok('las velas de 3 días cierran 2/10, 7/10, 12/10 y 15/10',
    JSON.stringify(fin)==='[20261002,20261007,20261012,20261015]',JSON.stringify(fin));
  const m=M.velas3d(b,cal.indexOf(20261014)+1,cal,20261014);
  ok('el 14/10 la última CERRADA es la del 12/10 (la de 13-14-15 está abierta)',
    m.fin[m.fin.length-1]===20261012,m.fin[m.fin.length-1]);
  const i5=cal.indexOf(20261005),v=n.c.length-3;
  ok('O = open del 1er día, H = máximo, L = mínimo, C = cierre del 3ro',
    n.o[v]===b.o[i5]&&n.h[v]===b.h[i5+2]&&n.l[v]===b.l[i5]&&n.c[v]===b.c[i5+2]);
  ok('sin el ancla en el calendario, no inventa velas',M.velas3d(b,10,cal.filter(f=>f!==20261002),20261015)===null);
}
{
  // la vela de hoy, recien a las 16:30 de Nueva York
  const s={d:[20261014,20261015,20261016]};
  ok('16:29 en NY: la vela de hoy todavía no',M.velaEstrategia(s,{fecha:20261016,min:16*60+29})===20261015);
  ok('16:30 en NY: ya sí',M.velaEstrategia(s,{fecha:20261016,min:16*60+30})===20261016);
  ok('si la última vela es de ayer, se usa a cualquier hora',
    M.velaEstrategia({d:[20261014,20261015]},{fecha:20261016,min:600})===20261015);
}
{
  // EMA de Pine: semilla SMA de los primeros n VALIDOS
  const x=[NaN,NaN,1,2,3,4,5],e=M.emaP(x,3);
  ok('emaP siembra con la SMA de los 3 primeros válidos',isNaN(e[3])&&e[4]===2&&Math.abs(e[5]-3)<1e-15);
  const tr=M.atrP([2,3],[1,1],[1.5,2],1);
  ok('atrP: la primera vela usa H-L',tr[0]===1&&tr[1]===2);
}
// una serie armada para el cruce, el regimen y la entrada
function serie(c,extra){const n=c.length,d=dias(20230101,20291231).slice(0,n);
  return Object.assign({t:'X',d,o:c.slice(),h:c.map(v=>v*1.03),l:c.map(v=>v*0.97),c},extra||{});}
{
  // baja 300 ruedas y despues sube: el cruce WMA 21/26 cae en una rueda concreta
  const c=[];for(let i=0;i<300;i++)c.push(200-i*0.3);for(let i=0;i<60;i++)c.push(110+i*1.2);
  const s=serie(c),cal=s.d,w1=M.wma(c,21),w2=M.wma(c,26);
  let k=300;while(!(w1[k]>=w2[k]))k++;
  const r20=M.evaluarEstr(s,s,s.d[k+20],null,cal),r21=M.evaluarEstr(s,s,s.d[k+21],null,cal);
  ok('día del cruce = 0 y el día 20 entra',r20.dias_cruce===20&&r20.f1&&r20.fecha_cruce===s.d[k]);
  ok('el día 21 ya no',r21.dias_cruce===21&&!r21.f1);
  ok('la racha que arranca con la serie (sin cruce previo) no pasa',
    !M.evaluarEstr(serie(c.slice(k)),serie(c.slice(k)),serie(c.slice(k)).d[20],null,serie(c.slice(k)).d).f1);
}
{
  // regimen: empate con la linea no cambia el estado; sin datos, encendido
  const c=new Array(260).fill(100);
  const s=serie(c),r=M.evaluarEstr(s,s,s.d[259],null,s.d);
  ok('C igual a la línea todo el tiempo: queda como arrancó (encendido)',r.regimen===true);
  // el autómata solo, con la linea a mano: [sin dato, 10, 10, 10, 10]
  const L=[NaN,10,10,10,10],A=(c,l2)=>M.automataRegimen(c,L,l2||L);
  ok('cae debajo: se apaga',A([5,9])===false);
  ok('cae debajo y vuelve a IGUALAR la línea: sigue apagado',A([5,9,10,10])===false);
  ok('cierra POR ENCIMA: se prende',A([5,9,10,10,11])===true);
  ok('encendido e igual a la línea: sigue encendido',A([5,11,10,10])===true);
  ok('la línea es el MÁXIMO de las dos medias',M.automataRegimen([5,10.5],[NaN,10],[NaN,11])===false);
  ok('un dato que falta en el medio lo vuelve a encender',
    M.automataRegimen([5,9,10],[NaN,10,NaN],[NaN,10,10])===true);
  const s4=serie(c.slice(0,150)),r4=M.evaluarEstr(s4,s4,s4.d[149],null,s4.d);
  ok('sin 200 ruedas para la SMA 200: encendido',r4.regimen===true&&isNaN(r4.sma200));
  ok('sin 252 velas no pasa ni el mínimo ni el máximo de 52 s',!r4.f4&&!r4.f5);
}
{
  // el plan
  const p=M.planEstr(100,0.02);
  ok('SL = 1 - 3,5 x ATR%, TP x3, activación x1,2',Math.abs(p.sl-93)<1e-12&&p.tp===300&&Math.abs(p.activacion-120)<1e-12);
  ok('distancia del SL con piso 0,5 % y techo 95 %',M.planEstr(100,0.0001).sl_pct===0.005&&M.planEstr(100,1).sl_pct===0.95);
  // seguimiento: SL y TP en la misma vela cuenta el SL; abre debajo del SL sale al open
  const base=new Array(80).fill(100);
  const mk=(f)=>{const s=serie(base.slice());f(s);return s;};
  const op={t:'X',fe:null,pe:100,atr_pct:0.02};
  let s=mk(s=>{s.h[60]=310;s.l[60]=90;});op.fe=s.d[50];
  let g=M.seguirPosicion(s,op,s.d[79]);
  ok('TP y SL en la misma vela: cuenta el SL',g.salida==='SL'&&g.precio===93&&g.fecha===s.d[60],JSON.stringify(g));
  s=mk(s=>{s.o[61]=90;s.l[61]=89;});g=M.seguirPosicion(s,op,s.d[79]);
  ok('abre debajo del SL: sale al open, como «SL con gap»',g.salida==='SL con gap'&&g.precio===90);
  s=mk(s=>{s.o[61]=320;s.h[61]=330;});g=M.seguirPosicion(s,op,s.d[79]);
  ok('abre arriba del TP: sale al open, como «TP con gap»',g.salida==='TP con gap'&&g.precio===320);
  s=mk(s=>{for(let j=55;j<80;j++){s.c[j]=125;s.o[j]=s.h[j]=s.l[j]=125;} s.c[70]=100;s.l[70]=99;});
  g=M.seguirPosicion(s,op,s.d[79]);
  ok('cierre >= +20 % activa y la salida por SMA 40 es al cierre',g.salida==='SMA 40'&&g.fecha===s.d[70]&&g.desde===s.d[55],JSON.stringify(g));
  s=mk(s=>{s.c[55]=121;s.h[55]=121;s.c[56]=99;s.o[56]=s.l[56]=99;});
  g=M.seguirPosicion(s,op,s.d[57]);
  ok('la media cuenta recién DESDE EL DÍA SIGUIENTE a la activación',g.salida==='SMA 40'&&g.fecha===s.d[56]);
  s=mk(s=>{s.c[60]=119.9;s.h[60]=125;s.c[61]=99;});
  g=M.seguirPosicion(s,op,s.d[70]);
  ok('un MÁXIMO por encima de +20 % no activa: hace falta el cierre',g.salida===null&&!g.activa);
}
{
  // re-entrada: desde la salida cerro <= SMA 40, el low toco la EMA 34 y hoy cierra > SMA 40
  const c=[];for(let i=0;i<120;i++)c.push(100+i*0.5);c.push(150,140,138,150,160);
  const s=serie(c),n=c.length;
  const r=M.reentrada(s,s.d[n-1],s.d[119]);
  ok('re-entrada: bajó a la SMA 40, tocó la EMA 34 y hoy cierra arriba',r.ok,JSON.stringify(r));
  const r2=M.reentrada(s,s.d[n-1],s.d[n-1]);
  ok('si desde la salida no volvió a la SMA 40, no hay re-entrada',!r2.ok&&!r2.bajo);
}

{
  // la serie alineada al calendario del SPY, como la arma el backtest
  const cal=[20261005,20261006,20261007,20261008,20261009,20261012];
  const s={t:'X',d:[20261005,20261007,20261010,20261012],o:[10,11,12,13],h:[10.5,11.5,12.5,12.9],
    l:[9.5,10.5,11.5,12.5],c:[10,11,12,13.2],v:[5,5,5,5]};
  const a=M.alinearEstr(s,cal);
  ok('un día que Nueva York no operó (sábado 10/10) se descarta',!a.d.includes(20261010)&&a.d.length===6);
  ok('un hueco: O = H = L = C = cierre anterior, volumen 0, sin vela propia',
    a.c[1]===10&&a.o[1]===10&&a.h[1]===10&&a.l[1]===10&&a.v[1]===0&&a.propia[1]===false&&a.propia[2]===true);
  ok('después del último dato no hay vela (no se inventa)',a.d[a.d.length-1]===20261012);
  ok('una vela mal formada se arregla: H = máx(H, O, C)',a.h[5]===13.2&&a.l[5]===12.5);
  ok('antes del primer dato tampoco',M.alinearEstr({t:'Y',d:[20261008],o:[1],h:[1],l:[1],c:[1]},cal).d[0]===20261008);
  ok('redondeo del RS al par, como numpy: 74,5 → 74 y 75,5 → 76',M.redondeoPar(74.5)===74&&M.redondeoPar(75.5)===76&&M.redondeoPar(70.4999999999)===70);
  ok('RS = redondeo(percentil × 98 + 1)',M.rsDePuntaje(3,[1,2,3,4])===M.redondeoPar(3/4*98+1));
}

console.log('\n== 3. la pantalla ==');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
function abrir(almacen,valid){
  return new Promise(res=>{
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
      beforeParse(w){const noop=()=>{};
        w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:(o,k)=>k==='measureText'?()=>({width:8}):noop,set:()=>true});
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w,'localStorage',{value:almacen,configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.requestAnimationFrame=f=>setTimeout(f,0);
        w.fetch=async u=>{const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>JSON.stringify(P)};
          if(s.indexOf('validacion.json')>=0)return valid?{ok:true,json:async()=>valid}:{ok:false,status:404};
          throw new TypeError('Failed to fetch');};}});
    const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
      clearInterval(t);res(dom.window);}},20);});}
function almacen(ini){return {_m:Object.assign({screener_ash_yahoo_auto:'0'},ini||{}),
  getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}};}
(async()=>{
  const A=almacen();
  const VAL={generado:'2026-10-16 22:00 UTC',ok:false,senales:{coinciden:960,filas:961,dias:66,pausas:66},
    operaciones:{iguales:94,total:94},etsy:{ok:true},diferencias:['20260701 IFF: algo']};
  let w=await abrir(A,VAL);const $=s=>w.document.querySelector(s),$$=s=>[...w.document.querySelectorAll(s)];
  $('#chipEstr').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(120);
  ok('entra a la vista',w.document.body.classList.contains('estrategia')&&$('#chipEstr').classList.contains('on'));
  const res=w.eval('calcularEstrategia()');
  const cartel=$('.es-cartel').textContent;
  ok('el cartel dice lo que dice el ASH del SPY',res.mercado.pausa?cartel.startsWith('PAUSA'):cartel==='SE PUEDE ENTRAR',cartel);
  ok('muestra SmthBulls y SmthBears de los dos',$$('.es-asd').length===2&&$$('.es-asd-v b').length===4);
  ok('la validación contra el backtest se ve, y avisa si no coincide',
    !!$('.es-valid.mal')&&$('.es-valid').textContent.includes('960 de 961'),$('.es-valid')&&$('.es-valid').textContent);
  ok('los ETFs son candidatos y llevan su etiqueta',res.filas.some(f=>f.t==='SPY'&&f.etf));
  ok('UPS cuenta en los percentiles…',res.filas.some(f=>f.t==='UPS')||!P.simbolos.some(s=>s.t==='UPS'));
  const filas=()=>[...$$('#estrCuerpo .es-tabla')[0].querySelectorAll('tbody tr[data-t]')];
  /* En la fixtura el SPY esta en pausa todos los dias, asi que ninguna senal
     es valida y no habria nada que ordenar ni que comprar: sin esto los
     sabotajes de la pantalla pasaban en verde. Se apaga la pausa de los dias
     anteriores (la de hoy se maneja aparte, mas abajo). */
  w.eval("pausaDeEstr=()=>false;memoEstr.clave='';renderEstrategia()");
  const res2=w.eval('calcularEstrategia()');Object.assign(res,res2);
  ok('…pero nunca aparece como candidata',!filas().some(tr=>tr.dataset.t==='UPS'));
  const th=[...$$('.es-tabla')[0].querySelectorAll('th')].map(x=>x.textContent);
  ok('las columnas en el orden pedido',th.slice(0,24).join('|')===['Ticker','Cierre','Días desde el cruce',
    'WMA 21 / WMA 26','ADR%(20)','RS','% sobre mín. 52 s','% bajo máx. 52 s','Régimen SMA 50/200',
    'MACD 3D hist (valor · anterior)','EWO D (ewo1 · ewo2 · señal)','ATR%(14)','Prioridad',
    'Señal','Nueva hoy','Entrada óptima','SL · TP · Activ. óptimos','Precio vs óptima','Estado de la señal',
    'Entry (si entro hoy)','SL (precio · %)','TP','Activación +20 %','SMA 40'].join('|'),th.join('|'));
  // grupos: primero las validas (califican + senal abierta), por prioridad y despues ticker
  const cl=f=>w.eval(`clasificarEstr(calcularEstrategia(),calcularEstrategia().filas.find(x=>x.t===${JSON.stringify(f.t)}))`);
  const validas=res.filas.filter(f=>f.pasa&&f.t!=='UPS'&&cl(f).valida);
  const trs=filas(),primeras=trs.slice(0,validas.length).map(tr=>tr.dataset.t);
  ok('arriba van las que califican con la señal abierta',
    validas.every(f=>primeras.includes(f.t)),primeras.join(' ')+' / '+validas.map(f=>f.t).join(' '));
  const pr=primeras.map(t=>res.filas.find(f=>f.t===t));
  ok('ordenadas por prioridad, y a igualdad por ticker',
    pr.every((f,i)=>!i||pr[i-1].prio>f.prio||(pr[i-1].prio===f.prio&&pr[i-1].t<f.t)));
  ok('el resto va atenuado',trs.slice(validas.length).every(tr=>tr.classList.contains('es-at')));
  ok('una señal que pasó sólo en pausa dice «sin señal válida»',
    trs.every(tr=>tr.children[18].textContent.trim()!==''));
  ok('la prueba tiene señales válidas con que trabajar',validas.length>=2,validas.length);
  w.eval('memoEstr.res.mercado=Object.assign({},memoEstr.res.mercado,{pausa:true});renderEstrategia()');
  ok('en pausa ninguna es COMPRA',$$('.es-et.comprar').length===0);
  // un papel que no puede ser candidato (como UPS) desaparece aunque califique
  const vt=validas[0].t;
  w.eval(`DATOS.estr_excl=Object.assign({},DATOS.estr_excl,{${JSON.stringify(vt)}:'prueba'});memoEstr.clave='';renderEstrategia()`);
  ok('un excluido no aparece como candidato aunque califique',!filas().some(tr=>tr.dataset.t===vt));
  const r3=w.eval('calcularEstrategia()');
  ok('pero sigue en los percentiles',r3.filas.some(f=>f.t===vt));
  w.eval(`delete DATOS.estr_excl[${JSON.stringify(vt)}];memoEstr.clave='';renderEstrategia()`);
  // sin pausa: COMPRA en las primeras N del grupo 1
  w.eval('memoEstr.res.mercado=Object.assign({},memoEstr.res.mercado,{pausa:false});renderEstrategia()');
  const nv=validas.length;
  ok('sin pausa, COMPRA en las primeras según los lugares libres',
    $$('.es-et.comprar').length===Math.min(10,nv)&&(nv===0||filas()[0].querySelector('.es-et.comprar')),
    $$('.es-et.comprar').length+' vs '+Math.min(10,nv));
  $('#esLugares').value='1';$('#esLugares').dispatchEvent(new w.Event('change',{bubbles:true}));await esperar(30);
  w.eval('memoEstr.res.mercado=Object.assign({},memoEstr.res.mercado,{pausa:false});renderEstrategia()');
  ok('lugares libres editable: con 1, una sola COMPRA',$$('.es-et.comprar').length===Math.min(1,nv));
  $('#esLugares').value='';$('#esLugares').dispatchEvent(new w.Event('change',{bubbles:true}));await esperar(30);
  // casi-senales y cerradas
  const antes=filas().length;
  $('#esCasi').checked=true;$('#esCasi').dispatchEvent(new w.Event('change',{bubbles:true}));await esperar(30);
  const casi=res.filas.filter(f=>f.fallan.length===1&&f.t!=='UPS').length;
  ok('ver casi-señales agrega las que fallan UN filtro, con ese filtro en rojo',
    filas().length>=antes+Math.min(1,casi)&&(casi===0||filas().some(tr=>tr.querySelector('.es-falla'))));
  // una senal que el backtest ya cerro: no es entrada valida, se esconde
  const vc=validas[1].t;
  w.eval(`(()=>{const E=calcularEstrategia(),h=Object.assign({},historiaEstr(E,E.filas.find(x=>x.t===${JSON.stringify(vc)})),
    {salida:'SL',salida_fecha:E.R,salida_precio:1});E.historias.set(${JSON.stringify(vc)},h);renderEstrategia();})()`);
  ok('una señal cerrada en el backtest desaparece de las entradas',!filas().some(tr=>tr.dataset.t===vc));
  const nCerr=res.filas.filter(f=>f.pasa&&f.t!=='UPS'&&cl(f).estado==='cerrada').length;
  const sinCerr=filas().length;
  $('#esCerradas').checked=true;$('#esCerradas').dispatchEvent(new w.Event('change',{bubbles:true}));await esperar(30);
  ok('la prueba tiene señales cerradas',nCerr>0,nCerr);
  w.eval(`(()=>{const E=calcularEstrategia(),h=Object.assign({},historiaEstr(E,E.filas.find(x=>x.t===${JSON.stringify(vc)})),
    {salida:'SL',salida_fecha:E.R,salida_precio:1});E.historias.set(${JSON.stringify(vc)},h);renderEstrategia();})()`);
  const trc=filas().find(tr=>tr.dataset.t===vc);
  ok('y vuelve atenuada, con su salida, con «ver señales cerradas»',!!trc&&trc.classList.contains('es-at')&&trc.children[18].textContent.startsWith('cerrada por SL'));
  ok('ver señales cerradas las agrega, atenuadas y con su salida',filas().length===sinCerr+nCerr,
    `${filas().length} vs ${sinCerr}+${nCerr}`);
  ok('los interruptores quedan guardados',JSON.parse(A._m.screener_ash_estrategia).casi===true&&
    JSON.parse(A._m.screener_ash_estrategia).cerradas===true);
  // celdas de la senal
  {const h={fecha:20261009,ruedas:4,entry:100,atr_pct:0.02,enPausa:20261008,salida:'SL con gap',salida_fecha:20261014,salida_precio:93,activa:false};
   const tb=w.document.createElement('tbody');
   tb.innerHTML='<tr>'+w.eval(`celdasSenal(${JSON.stringify(h)},{cierre:110,pasa:true})`)+'</tr>';
   const c=[...tb.querySelectorAll('td')].map(x=>x.textContent.trim());
   ok('Señal: fecha y hace cuánto',c[0]==='09/10/2026 · hace 4 ruedas',c[0]);
   ok('Nueva hoy: no',c[1]==='no');
   ok('Entrada óptima y SL/TP/activación con el ATR% de ese día',c[2]==='100,00'&&c[3]==='93,00 · 300,00 · 120,00',c[2]+' | '+c[3]);
   ok('Precio vs óptima, sin colores',c[4]==='+10,0 %'&&!tb.children[0].children[4].className);
   ok('Estado: cerrada por SL con gap, con fecha y resultado neto',c[5]==='cerrada por SL con gap el 14/10/2026 (-7,6 %)',c[5]);
   const h2=Object.assign({},h,{ruedas:0,salida:null,activa:false});
   tb.innerHTML='<tr>'+w.eval(`celdasSenal(${JSON.stringify(h2)},{cierre:100,pasa:true})`)+'</tr>';
   const c2=[...tb.querySelectorAll('td')].map(x=>x.textContent.trim());
   ok('la de hoy: nueva hoy = sí, abierta en el backtest con la comisión (−0,7 %)',
     c2[0].endsWith('hoy')&&c2[1]==='sí'&&c2[5]==='abierta en el backtest (-0,7 %)',c2.join(' | '));
   tb.innerHTML='<tr>'+w.eval(`celdasSenal({fecha:null,enPausa:20261008},{cierre:100,pasa:true})`)+'</tr>';
   ok('si sólo calificó en pausa: sin señal válida',tb.textContent.includes('sin señal válida (pausa del SPY en todos los días)'));}
  // registro: Entre / posiciones / Sali
  const tr0=filas()[0];
  if(tr0){const inp=tr0.querySelector('.es-pe');inp.value='100';inp.dispatchEvent(new w.Event('input'));
    ok('cargar el precio de entrada recalcula el plan de hoy',tr0.querySelector('.es-tp').textContent==='300,00');
    const t=tr0.dataset.t;tr0.querySelector('.es-entre').click();await esperar(30);
    const reg=JSON.parse(A._m.screener_ash_estrategia);
    ok('Entré anota ticker, cruce, fecha, precio y ATR% del día',reg.ops.length===1&&reg.ops[0].t===t&&reg.ops[0].pe===100&&reg.ops[0].cruce&&reg.ops[0].atr_pct>0);
    ok('deja de ser entrada nueva',!filas().some(tr=>tr.dataset.t===t));
    const pos=$$('#estrCuerpo tr[data-id]')[0];
    ok('aparece en posiciones abiertas con días, activada y la acción del día',
      !!pos&&/mantener|VENDER|salió por/.test(pos.children[9].textContent)&&/sí|no/.test(pos.children[7].textContent),
      pos&&pos.textContent);
    ok('los lugares libres bajan a 9',$('#esLugares').placeholder==='9');
    pos.querySelector('.es-ps').value='110';pos.querySelector('.es-sali').click();await esperar(30);
    const reg2=JSON.parse(A._m.screener_ash_estrategia);
    ok('Salí la cierra con fecha, precio y motivo',reg2.ops[0].fs>0&&reg2.ops[0].ps===110&&!!reg2.ops[0].ms);
    const c=cl({t});
    ok('cerrada en este cruce: sólo vuelve como re-entrada',c.tipo==='reentrada'||c.tipo==='operada',c.tipo);
    let blob=null;w.URL.createObjectURL=b=>{blob=b;return 'blob:x';};w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=()=>{};
    w.eval('exportarConfig()');const txt=await blob.text();
    ok('el respaldo .json lleva el registro',JSON.parse(txt).estrategia.ops.length===1);
    const B=almacen({screener_ash_estrategia:JSON.stringify({ops:[{id:'otra',t:'ZZZ',cruce:1,fe:1,pe:1,fs:null}]})});
    const w2=await abrir(B);w2.eval(`importarConfig(${JSON.stringify(txt)})`);
    ok('restaurar FUSIONA: queda la que había y entra la del respaldo',JSON.parse(B._m.screener_ash_estrategia).ops.length===2);
  }
  // la vela sin vela propia
  const hueco=P.simbolos.find(s=>{const ds=new Set(s.d);return spy.d.some(d=>d>s.d[0]&&d<s.d[s.d.length-1]&&!ds.has(d));});
  if(hueco){const r=w.eval('calcularEstrategia()');const a=r.AL.get(hueco.t);
    ok('el papel con huecos se alinea al calendario del SPY',a&&a.propia.includes(false),hueco.t);}
  else ok('la fixtura trae un papel con huecos',false);
  // la tabla del screener no muestra los ADRs de Estrategia
  w.eval("verVista('t')");await esperar(50);
  const enTabla=[...w.document.querySelectorAll('#tabla tbody tr .tk')].map(x=>x.textContent);
  ok('la tabla del screener no muestra los ADRs de Estrategia',!enTabla.includes('BASFY')&&!enTabla.includes('HNHPF'));
  ok('y Estrategia sí, en lugar de la cotización local',res.filas.some(f=>f.t==='BASFY')&&!res.filas.some(f=>f.t==='BAS.DE'));
  console.log(fallas?`\nFALLAS: ${fallas}`:'\nestrategia: todo OK');
  process.exit(fallas?1:0);
})();
