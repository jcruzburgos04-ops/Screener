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
const S=new Map(P.simbolos.map(s=>[s.t,s])),spy=S.get('SPY');

console.log('== 1. paridad con estrategia.py ==');
{
  const n=spy.d.length,fechas=[spy.d[n-1],spy.d[n-120],spy.d[n-300]];
  if(spy.d.includes(20261002))fechas.push(20261002);
  const tmp=path.join(__dirname,'tmp','estr_ref.json');
  execFileSync('python3',[path.join(__dirname,'estrategia_ref.py'),path.join(SITIO,'datos.json'),tmp,fechas.join(',')]);
  const ref=JSON.parse(fs.readFileSync(tmp,'utf8'));
  let peor=0,donde='',dec=0,ejemplo='',filas=0,pasan=0,ashPeor=0,ashDec=0;
  for(const R of fechas){
    const u=M.universoEstr(P.simbolos,P.estr_adr).tickers;
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
  ok('abre debajo del SL: sale al open',g.salida==='SL'&&g.precio===90);
  s=mk(s=>{s.o[61]=320;s.h[61]=330;});g=M.seguirPosicion(s,op,s.d[79]);
  ok('abre arriba del TP: sale al open',g.salida==='TP'&&g.precio===320);
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

console.log('\n== 3. la pantalla ==');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
function abrir(almacen,conRsu){
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
          if(s.indexOf('rs_universo.json')>=0&&conRsu)return {ok:true,json:async()=>conRsu};
          if(s.indexOf('rs_universo.json')>=0)return {ok:false,status:404};
          throw new TypeError('Failed to fetch');};}});
    const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
      clearInterval(t);res(dom.window);}},20);});}
function almacen(ini){return {_m:Object.assign({screener_ash_yahoo_auto:'0'},ini||{}),
  getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}};}
(async()=>{
  const A=almacen();
  let w=await abrir(A);const $=s=>w.document.querySelector(s),$$=s=>[...w.document.querySelectorAll(s)];
  $('#chipEstr').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(80);
  ok('entra a la vista',w.document.body.classList.contains('estrategia')&&$('#chipEstr').classList.contains('on'));
  const res=w.eval('calcularEstrategia()');
  const cartel=$('.es-cartel').textContent;
  ok('el cartel dice lo que dice el ASH del SPY',res.mercado.pausa?cartel.startsWith('PAUSA'):cartel==='SE PUEDE ENTRAR',cartel);
  ok('muestra SmthBulls y SmthBears de los dos',$$('.es-asd').length===2&&$$('.es-asd-v b').length===4);
  ok('la tabla se atenúa en pausa y sólo en pausa',!!$('.es-tabla-wrap.atenuada')===res.mercado.pausa);
  ok('sin rs_universo.json el RS sale contra los propios y EN ROJO',res.fuente==='propio'&&!!$('.es-info .es-mal'));
  const senales=res.filas.filter(f=>f.pasa).length;
  const filas=()=>$$('#estrCuerpo .es-tabla')[0].querySelectorAll('tbody tr[data-t]');
  ok('una fila por señal',filas().length===senales,filas().length+' vs '+senales);
  const th=[...$$('.es-tabla')[0].querySelectorAll('th')].map(x=>x.textContent.replace(' ⚠',''));
  ok('las columnas en el orden pedido',th.slice(0,21).join('|')===['Ticker','Cierre','Días desde el cruce',
    'WMA 21 / WMA 26','ADR%(20)','RS','% sobre mín. 52 s','% bajo máx. 52 s','Régimen SMA 50/200',
    'MACD 3D hist (valor · anterior)','EWO D (ewo1 · ewo2 · señal)','ATR%(14)','Prioridad','Señal','Entry óptima','Backtest','Entry',
    'SL (precio · %)','TP','Activación +20 %','SMA 40'].join('|'),th.join('|'));
  const conHist=[...filas()].filter(tr=>/hoy|hace \d+ rueda|con el SPY en pausa/.test(tr.children[13].textContent));
  ok('cada señal dice hace cuánto fue',filas().length===0||conHist.length===filas().length,
    conHist.length+' de '+filas().length);
  const hEj=res.filas.filter(f=>f.pasa).map(f=>w.eval(`historiaEstr(calcularEstrategia(),calcularEstrategia().filas.find(x=>x.t===${JSON.stringify(f.t)}))`)).find(h=>h&&h.fecha);
  if(hEj){const tr=[...filas()].find(tr=>tr.dataset.t===res.filas.find(f=>f.pasa&&w.eval(`historiaEstr(calcularEstrategia(),calcularEstrategia().filas.find(x=>x.t===${JSON.stringify(f.t)}))`).fecha===hEj.fecha).t);
    ok('la entrada óptima es el cierre del día de la señal',!!tr&&tr.children[14].textContent.startsWith(new Intl.NumberFormat('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(hEj.entry)),tr&&tr.children[14].textContent);}
  {const h={fecha:20261009,ruedas:4,entry:100,atr_pct:0.02,enPausa:20261008,salida:'SL',salida_fecha:20261014,salida_precio:93,activa:false};
   const tb=w.document.createElement('tbody');
   tb.innerHTML='<tr>'+w.eval(`celdasSenal(${JSON.stringify(h)},{cierre:110})`)+'</tr>';
   const c=[...tb.querySelectorAll('td')].map(x=>x.textContent.trim());
   ok('la celda de la señal: hace cuánto y qué día',c[0].startsWith('hace 4 ruedas · 09/10/2026'),c[0]);
   ok('la entrada óptima y cuánto subió desde ahí',c[1]==='100,00 · hoy +10,0 %',c[1]);
   ok('si el backtest ya salió, lo dice con fecha y resultado',c[2]==='salió por SL el 14/10/2026 (-7,0 %)',c[2]);
   ok('y avisa que antes pasó con el SPY en pausa',tb.querySelector('td').title.includes('08/10/2026'));
   const h2=Object.assign({},h,{ruedas:0,salida:null,activa:true});
   tb.innerHTML='<tr>'+w.eval(`celdasSenal(${JSON.stringify(h2)},{cierre:100})`)+'</tr>';
   const c2=[...tb.querySelectorAll('td')].map(x=>x.textContent.trim());
   ok('la de hoy dice hoy, y la abierta su resultado',c2[0].startsWith('hoy')&&c2[2]==='abierta 0,0 % · activada',c2.join(' | '));}
  const pr=[...filas()].map(tr=>res.filas.find(f=>f.t===tr.dataset.t).prio);
  ok('ordenadas por prioridad',pr.every((v,i)=>!i||v<=pr[i-1]));
  if(!res.mercado.pausa)ok('marca las primeras según los lugares libres',
    $$('.es-et.comprar').length===Math.min(10,senales));
  else ok('en pausa no marca ninguna para comprar',$$('.es-et.comprar').length===0);
  // casi-senales
  $('#esCasi').checked=true;$('#esCasi').dispatchEvent(new w.Event('change',{bubbles:true}));await esperar(30);
  const casi=res.filas.filter(f=>f.fallan.length===1).length;
  ok('ver casi-señales agrega las que fallan UN filtro',filas().length===senales+casi,filas().length+' vs '+(senales+casi));
  const roja=[...filas()].find(tr=>tr.querySelector('.es-falla'));
  ok('y el filtro que falla va en rojo',casi===0||!!roja);
  ok('el interruptor queda guardado',JSON.parse(A._m.screener_ash_estrategia).casi===true);
  // el precio real de entrada recalcula el plan
  const tr0=filas()[0];
  if(tr0){const inp=tr0.querySelector('.es-pe');inp.value='100';inp.dispatchEvent(new w.Event('input'));
    ok('cargar el precio de entrada recalcula el TP',tr0.querySelector('.es-tp').textContent==='300,00',tr0.querySelector('.es-tp').textContent);
    // Entré: pasa a la cartera y deja de ser señal
    const t=tr0.dataset.t;tr0.querySelector('.es-entre').click();await esperar(30);
    const reg=JSON.parse(A._m.screener_ash_estrategia);
    ok('Entré anota la operación con su cruce y su precio',reg.ops.length===1&&reg.ops[0].t===t&&reg.ops[0].pe===100&&reg.ops[0].cruce);
    ok('y deja de mostrarse como entrada nueva',![...filas()].some(tr=>tr.dataset.t===t));
    ok('aparece en la cartera',$$('#estrCuerpo tr[data-id]').length===1);
    ok('los lugares libres bajan a 9',$('#esLugares').placeholder==='9');
    // cerrarla: sigue sin poder entrar en el mismo cruce (no hay re-entrada armada)
    const fila=$$('#estrCuerpo tr[data-id]')[0];fila.querySelector('.es-ps').value='110';
    fila.querySelector('.es-sali').click();await esperar(30);
    const reg2=JSON.parse(A._m.screener_ash_estrategia);
    ok('Salí la cierra con fecha y precio',reg2.ops[0].fs>0&&reg2.ops[0].ps===110);
    const c=w.eval(`clasificarEstr(calcularEstrategia().filas.find(f=>f.t===${JSON.stringify(t)}),calcularEstrategia().porT,calcularEstrategia().R)`);
    ok('cerrada en este cruce: sólo vuelve como re-entrada',c.tipo==='reentrada'||c.tipo==='operada',c.tipo);
    // respaldo: la exportacion lleva el registro y la importacion fusiona
    let blob=null;w.URL.createObjectURL=b=>{blob=b;return 'blob:x';};w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=()=>{};
    w.eval('exportarConfig()');const txt=await blob.text();const resp=JSON.parse(txt);
    ok('el respaldo .json lleva el registro',resp.estrategia&&resp.estrategia.ops.length===1);
    const B=almacen({screener_ash_estrategia:JSON.stringify({ops:[{id:'otra',t:'ZZZ',cruce:1,fe:1,pe:1,fs:null}]})});
    const w2=await abrir(B);w2.eval(`importarConfig(${JSON.stringify(txt)})`);
    const regB=JSON.parse(B._m.screener_ash_estrategia);
    ok('restaurar FUSIONA: queda la que había y entra la del respaldo',regB.ops.length===2,regB.ops.length);
  }
  // con el universo amplio publicado
  const U=res.filas.map(f=>f.rs_puntaje).filter(isFinite);
  const amplio={fecha:res.R-1,n:U.length*3,p:[...U,...U.map(x=>x*0.7),...U.map(x=>x*0.8)].sort((a,b)=>a-b)};
  const w3=await abrir(almacen(),amplio);
  w3.document.querySelector('#chipEstr').dispatchEvent(new w3.MouseEvent('click',{bubbles:true}));await esperar(80);
  const r3=w3.eval('calcularEstrategia()');
  ok('con rs_universo.json el RS sale contra el universo amplio, sin rojo',r3.fuente==='amplio'&&!w3.document.querySelector('.es-info .es-mal'));
  ok('y si los cortes no son de la vela usada, lo dice con su fecha',
    w3.document.querySelector('.es-info .es-ojo:last-child').textContent.indexOf('no son de la vela usada')>=0);
  const t3=r3.filas.find(f=>isFinite(f.rs_puntaje));
  ok('el RS amplio es el percentil contra la lista publicada',
    Math.abs(t3.rs-M.rsDePuntaje(t3.rs_puntaje,amplio.p))<1e-12);
  // la tabla del screener no muestra los ADRs de la estrategia
  w3.eval("verVista('t')");await esperar(50);
  const enTabla=[...w3.document.querySelectorAll('#tabla tbody tr .tk')].map(x=>x.textContent);
  ok('la tabla del screener no muestra los ADRs de Estrategia',!enTabla.includes('BASFY')&&!enTabla.includes('HNHPF'));
  ok('pero Estrategia sí los usa',r3.filas.some(f=>f.t==='BASFY')&&!r3.filas.some(f=>f.t==='BAS.DE'));
  ok('y los ETFs quedan afuera de Estrategia',!r3.filas.some(f=>f.t==='SPY'||f.t==='QQQ'));
  console.log(fallas?`\nFALLAS: ${fallas}`:'\nestrategia: todo OK');
  process.exit(fallas?1:0);
})();
