/* ===========================================================================
   PRECIOS EN VIVO DESDE data912
   ===========================================================================
   La pagina abierta le pide a data912 el ultimo precio cada minuto y parchea
   la vela del dia. Lo que se verifica es lo que NO puede pasar, porque son los
   errores que no se ven en pantalla:
     - que se toque la apertura o el volumen (data912 no trae ni una cosa ni la
       otra que sirva);
     - que se parchee un papel de otro mercado, uno cuya ultima vela no es la de
       hoy, o fuera de la rueda regular (el after-hours pisaria el cierre);
     - que un precio roto (+30%) entre como si fuera un movimiento.
   Y despues el circuito entero: pedido, parche, recalculo, tabla y pastilla.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const SITIO=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
const texto=fs.readFileSync(path.join(SITIO,'datos.json'),'utf8');

let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'   -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));

function abrir(d912){
  return new Promise(res=>{
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
      url:'https://local/',
      beforeParse(w){
        const noop=()=>{};
        w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>noop,set:()=>true});
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
        Object.defineProperty(w,'localStorage',{value:{_m:{},getItem(k){return this._m[k]??null},
          setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}},configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.__pedidos=[];
        w.fetch=async u=>{
          const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>texto};
          if(s.indexOf('data912.com/live/')>=0){
            w.__pedidos.push(s);
            if(!d912)throw new TypeError('Failed to fetch');
            const cual=s.endsWith('usa_adrs')?'adrs':'stocks';
            return {ok:true,json:async()=>d912[cual]||[]};}
          throw new TypeError('Failed to fetch');};
      }});
    const t=setInterval(()=>{
      if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
        clearInterval(t);res(dom.window);}},20);
  });
}

(async()=>{
  const PL=JSON.parse(texto);
  const cuenta=new Map();
  for(const s of PL.simbolos){const f=s.d[s.d.length-1];cuenta.set(f,(cuenta.get(f)||0)+1);}
  const HOY=[...cuenta.entries()].sort((a,b)=>b[1]-a[1])[0][0];
  const hoyStr=String(HOY);
  // 15:00 UTC es rueda en Nueva York en verano (11:00) y en invierno (10:00)
  const EN_RUEDA=new Date(Date.UTC(+hoyStr.slice(0,4),+hoyStr.slice(4,6)-1,+hoyStr.slice(6,8),15,0));
  const FUERA=new Date(Date.UTC(+hoyStr.slice(0,4),+hoyStr.slice(4,6)-1,+hoyStr.slice(6,8),22,0));
  const por=t=>PL.simbolos.find(s=>s.t===t);
  const ultimo=s=>s.c[s.c.length-1];
  // un papel de EE.UU. al dia, otro atrasado (la fixtura atrasa uno de cada 17)
  const usa=PL.simbolos.filter(s=>s.t.slice(1).indexOf('.')<0&&s.t!=='BRK-B');
  const alDia=usa.filter(s=>s.d[s.d.length-1]===HOY);
  const atrasado=usa.find(s=>s.d[s.d.length-1]<HOY);
  const A=alDia[0], B=alDia[1], C=alDia[2];
  const brk=por('BRK-B'), ext=PL.simbolos.find(s=>s.t.endsWith('.SA'));
  console.log(`hoy ${HOY} · al dia ${A.t}, ${B.t}, ${C.t} · atrasado ${atrasado&&atrasado.t}`+
    ` · ${brk?'BRK-B':'sin BRK-B'} · extranjero ${ext&&ext.t}`);

  console.log('\n== las reglas del parche ==');
  {
    const w=await abrir(null);
    const S=t=>w.eval(`DATOS.simbolos.find(s=>s.t===${JSON.stringify(t)})`);
    const a0={o:S(A.t).o.at(-1),h:S(A.t).h.at(-1),l:S(A.t).l.at(-1),c:ultimo(S(A.t)),v:S(A.t).v.at(-1)};
    const arriba=+(Math.max(a0.h,a0.c)*1.03).toFixed(4);     // pasa el maximo
    const abajo=+(Math.min(ultimo(S(B.t)),S(B.t).l.at(-1))*0.97).toFixed(4);
    const lista=[
      {symbol:A.t,c:arriba},{symbol:B.t,c:abajo},
      {symbol:C.t,c:+(ultimo(S(C.t))*1.30).toFixed(4)},        // dato roto
      {symbol:atrasado.t,c:ultimo(atrasado)*1.01}];
    if(brk)lista.push({symbol:'BRK.B',c:+(ultimo(S('BRK-B'))*1.01).toFixed(4)});
    if(ext)lista.push({symbol:ext.t,c:ultimo(ext)*1.01});
    const cAtr=ultimo(S(atrasado.t)), cC=ultimo(S(C.t)), cExt=ext&&ultimo(S(ext.t));

    // fuera de la rueda: nada
    w.__lista=lista;w.__fuera=FUERA;w.__en=EN_RUEDA;
    const R0=w.eval('aplicarVivo(__lista,__fuera)');
    ok('fuera de la rueda no toca nada',R0.cambiados.length===0&&ultimo(S(A.t))===a0.c,
       JSON.stringify(R0.cambiados));

    const R=w.eval('aplicarVivo(__lista,__en)');
    const a1=S(A.t);
    ok('pisa el cierre de la vela de hoy',ultimo(a1)===arriba,`${ultimo(a1)} vs ${arriba}`);
    ok('y estira el máximo si el precio lo pasa',a1.h.at(-1)===arriba,a1.h.at(-1));
    ok('NO toca la apertura',a1.o.at(-1)===a0.o,`${a1.o.at(-1)} vs ${a0.o}`);
    ok('NO toca el volumen (el de data912 no es el del día)',a1.v.at(-1)===a0.v);
    ok('ni agrega una vela: sigue la misma cantidad',a1.d.length===A.d.length,a1.d.length);
    ok('del otro lado, estira el mínimo',S(B.t).l.at(-1)===abajo,S(B.t).l.at(-1));
    ok('un precio 30% lejos se descarta como dato roto',
       ultimo(S(C.t))===cC&&R.descartados.includes(C.t),JSON.stringify(R.descartados));
    ok('el que no tiene la vela de hoy no se parchea',ultimo(S(atrasado.t))===cAtr,
       `${ultimo(S(atrasado.t))} vs ${cAtr}`);
    if(ext)ok('uno de otro mercado no se parchea aunque el símbolo venga',
       ultimo(S(ext.t))===cExt);
    if(brk)ok('BRK.B de data912 llega a BRK-B',R.cambiados.includes('BRK-B'),
       JSON.stringify(R.cambiados));
    ok('devuelve exactamente los que cambió',
       R.cambiados.length===(brk?3:2),JSON.stringify(R.cambiados));
  }

  console.log('\n== el circuito entero: pedido, parche, tabla y pastilla ==');
  {
    const PRECIO=+(ultimo(A)*1.04).toFixed(2);
    const w=await abrir({stocks:[{symbol:A.t,c:PRECIO,pct_change:4}],adrs:[]});
    // el reloj de la prueba: rueda abierta en la fecha de la fixtura
    w.eval(`relojNY=()=>({fecha:${HOY},min:11*60,dia:'Wed'})`);
    /* La pagina arranca su propio ciclo al abrir, con el reloj de verdad: si
       la prueba corre con la rueda abierta, ese primer pedido tambien sale.
       Se lo deja terminar antes de contar, o se cuentan los dos. */
    await esperar(300);
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    await esperar(50);
    ok('pide los dos paneles de data912',w.__pedidos.length===2,JSON.stringify(w.__pedidos));
    const fila=[...w.document.querySelectorAll('#tabla tbody tr')].find(tr=>
      (tr.querySelector('.tk')||{}).textContent===A.t);
    const col=[...w.document.querySelectorAll('#tabla thead th')].findIndex(th=>/^Precio/.test(th.textContent.trim()));
    ok('la tabla muestra el precio nuevo',!!fila&&col>=0&&
       parseFloat(fila.children[col].textContent.replace(',','.'))===PRECIO,
       fila&&fila.children[col].textContent);
    const f=w.eval(`filas.find(f=>f.t===${JSON.stringify(A.t)})`);
    ok('y la variación del día se recalculó sobre ese precio',
       Math.abs(f.chg-(PRECIO/A.c[A.c.length-2]-1))<1e-9,f.chg);
    const pas=w.document.querySelector('#frescura');
    ok('la pastilla dice "en vivo"',pas.textContent==='en vivo'&&pas.classList.contains('vivo'),
       pas.textContent);
    ok('y el título aclara que los ETF no van en vivo',/ETF/.test(pas.title),pas.title);

    // si data912 deja de contestar, la pastilla vuelve sola a lo publicado
    w.fetch=async()=>{throw new TypeError('Failed to fetch');};
    await w.eval('pedirVivo()');
    ok('si data912 se cae, deja de decir "en vivo"',pas.textContent!=='en vivo',pas.textContent);
    ok('y no muestra ninguna alarma',!/error|falló|rojo/i.test(pas.textContent),pas.textContent);
  }

  console.log('\n== con la pestaña escondida no se pide nada ==');
  {
    const w=await abrir({stocks:[],adrs:[]});
    w.eval(`relojNY=()=>({fecha:${HOY},min:11*60,dia:'Wed'})`);
    Object.defineProperty(w.document,'hidden',{get:()=>true,configurable:true});
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    ok('pestaña escondida: cero pedidos',w.__pedidos.length===0,w.__pedidos.length);
  }

  console.log(fallas?'\nFALLAS: '+fallas:'\nVIVO OK');
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
