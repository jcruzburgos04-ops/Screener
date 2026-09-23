/* ===========================================================================
   PRECIOS EN VIVO: data912 primero, CNBC para el resto y de respaldo
   ===========================================================================
   La pagina abierta pide el ultimo precio cada minuto y parchea la vela del
   dia. Lo que se verifica es lo que NO puede pasar, porque son los errores que
   no se ven en pantalla:
     - que se toque la apertura, o el volumen desde data912 (no trae el del dia);
     - que se parchee un papel cuya ultima vela no es de la misma rueda que la
       cotizacion, uno de EE.UU. fuera de la rueda regular (el after-hours
       pisaria el cierre), o uno de otra bolsa con el precio de data912;
     - que entre un precio roto (+30%) o en otra moneda (euro contra dolar
       difiere menos de 15% y la regla del salto sola no lo ataja);
     - que CNBC no respalde cuando data912 se cae, o que se le pida lo que
       data912 ya trajo.
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

/* fuentes = {d912:{stocks,adrs}|null, cnbc:{SIMBOLO:{last,...}}|null}; null =
   esa fuente no contesta. Se puede cambiar despues con w.__fuentes. */
function abrir(fuentes){
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
        w.__pedidos=[];w.__fuentes=fuentes;
        w.fetch=async u=>{
          const s=String(u), F=w.__fuentes||{};
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>texto};
          if(s.indexOf('data912.com/live/')>=0){
            w.__pedidos.push(s);
            if(!F.d912)throw new TypeError('Failed to fetch');
            const cual=s.endsWith('usa_adrs')?'adrs':'stocks';
            return {ok:true,json:async()=>F.d912[cual]||[]};}
          if(s.indexOf('quote.cnbc.com/')>=0){
            w.__pedidos.push(s);
            if(!F.cnbc)throw new TypeError('Failed to fetch');
            const pedidos=decodeURIComponent(s.split('symbols=')[1]||'').split('|');
            // como la de verdad: devuelve uno por simbolo pedido, y los que no
            // conoce vienen sin precio
            const q=pedidos.map(p=>F.cnbc[p]?{symbol:p,...F.cnbc[p]}:{symbol:p,code:1});
            return {ok:true,json:async()=>({FormattedQuoteResult:{FormattedQuote:q.length===1?q[0]:q}})};}
          throw new TypeError('Failed to fetch');};
      }});
    const t=setInterval(()=>{
      if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
        clearInterval(t);res(dom.window);}},20);
  });
}
const simbolosCnbc=pedidos=>pedidos.filter(u=>u.indexOf('cnbc')>=0)
  .flatMap(u=>decodeURIComponent(u.split('symbols=')[1]||'').split('|'));
// CNBC escribe los miles con coma: se prueba el parseo con eso
const txt=x=>x.toLocaleString('en-US',{maximumFractionDigits:4});

(async()=>{
  const PL=JSON.parse(texto);
  const cuenta=new Map();
  for(const s of PL.simbolos){const f=s.d[s.d.length-1];cuenta.set(f,(cuenta.get(f)||0)+1);}
  const HOY=[...cuenta.entries()].sort((a,b)=>b[1]-a[1])[0][0];
  const hoyStr=String(HOY), fISO=f=>`${String(f).slice(0,4)}-${String(f).slice(4,6)}-${String(f).slice(6,8)}`;
  const HOY_ISO=fISO(HOY);
  // 15:00 UTC es rueda en Nueva York en verano (11:00) y en invierno (10:00)
  const EN_RUEDA=new Date(Date.UTC(+hoyStr.slice(0,4),+hoyStr.slice(4,6)-1,+hoyStr.slice(6,8),15,0));
  const FUERA=new Date(Date.UTC(+hoyStr.slice(0,4),+hoyStr.slice(4,6)-1,+hoyStr.slice(6,8),22,0));
  const por=t=>PL.simbolos.find(s=>s.t===t);
  const ultimo=s=>s.c[s.c.length-1];
  const afuera=t=>t.slice(1).indexOf('.')>=0;
  const alDiaS=s=>s.d[s.d.length-1]===HOY;
  const usa=PL.simbolos.filter(s=>!afuera(s.t)&&s.t!=='BRK-B'&&s.t!=='SPY');
  const alDia=usa.filter(alDiaS);
  const atrasado=usa.find(s=>!alDiaS(s));
  const [A,B,C,D]=alDia;
  const brk=por('BRK-B'), spy=por('SPY');
  const deBolsa=suf=>PL.simbolos.filter(s=>s.t.endsWith(suf));
  const alemanes=deBolsa('.DE'), brasil=deBolsa('.SA');
  const DE1=alemanes.find(alDiaS), DE2=alemanes.find(s=>alDiaS(s)&&s!==DE1);
  const DEviejo=alemanes.find(s=>!alDiaS(s));
  const BR1=brasil.find(alDiaS);
  const KS=por('000660.KS');
  console.log(`hoy ${HOY} · al dia ${A.t}, ${B.t}, ${C.t}, ${D.t} · atrasado ${atrasado&&atrasado.t}`+
    ` · ETF ${spy&&spy.t} · Alemania ${DE1&&DE1.t}/${DE2&&DE2.t} (viejo ${DEviejo&&DEviejo.t})`+
    ` · Brasil ${BR1&&BR1.t} · Corea ${KS&&KS.t}`);
  if(!(spy&&DE1&&DE2&&DEviejo&&BR1&&KS&&atrasado)){console.log('la fixtura no trae los casos');process.exit(1);}

  console.log('\n== las reglas del parche: data912 ==');
  {
    const w=await abrir(null);
    const S=t=>w.eval(`DATOS.simbolos.find(s=>s.t===${JSON.stringify(t)})`);
    const a0={o:S(A.t).o.at(-1),h:S(A.t).h.at(-1),c:ultimo(S(A.t)),v:S(A.t).v.at(-1)};
    const arriba=+(Math.max(a0.h,a0.c)*1.03).toFixed(4);     // pasa el maximo
    const abajo=+(Math.min(ultimo(S(B.t)),S(B.t).l.at(-1))*0.97).toFixed(4);
    const lista=[
      {symbol:A.t,c:arriba},{symbol:B.t,c:abajo},
      {symbol:C.t,c:+(ultimo(S(C.t))*1.30).toFixed(4)},        // dato roto
      {symbol:atrasado.t,c:ultimo(atrasado)*1.01},
      {symbol:BR1.t,c:ultimo(BR1)*1.01}];                     // otra bolsa
    if(brk)lista.push({symbol:'BRK.B',c:+(ultimo(S('BRK-B'))*1.01).toFixed(4)});
    const cAtr=ultimo(S(atrasado.t)), cC=ultimo(S(C.t)), cBR=ultimo(S(BR1.t));

    w.__lista=lista;w.__fuera=FUERA;w.__en=EN_RUEDA;
    const R0=w.eval('aplicarVivo(__lista,null,__fuera)');
    ok('fuera de la rueda no toca nada',R0.cambiados.length===0&&ultimo(S(A.t))===a0.c,
       JSON.stringify(R0.cambiados));

    const R=w.eval('aplicarVivo(__lista,null,__en)');
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
    ok('uno de otra bolsa no toma el precio de data912 aunque el símbolo venga',
       ultimo(S(BR1.t))===cBR);
    if(brk)ok('BRK.B de data912 llega a BRK-B',R.cambiados.includes('BRK-B'),
       JSON.stringify(R.cambiados));
    ok('devuelve exactamente los que cambió',
       R.cambiados.length===(brk?3:2),JSON.stringify(R.cambiados));
    ok('y los cuenta como de data912',R.porFuente.d912===R.cubiertos&&R.porFuente.cnbc===0,
       JSON.stringify(R.porFuente));
  }

  console.log('\n== las reglas del parche: CNBC ==');
  {
    const w=await abrir(null);
    const S=t=>w.eval(`DATOS.simbolos.find(s=>s.t===${JSON.stringify(t)})`);
    const q=(s,f,extra)=>{const c=ultimo(S(s.t));
      return {last:txt(+(c*f).toFixed(4)),currencyCode:s.mon||'USD',last_time:HOY_ISO+'T11:28:00.254-0400',...extra};};
    const s0={o:S(spy.t).o.at(-1),h:S(spy.t).h.at(-1),l:S(spy.t).l.at(-1),v:S(spy.t).v.at(-1),c:ultimo(S(spy.t))};
    const hiSpy=+(Math.max(s0.h,s0.c)*1.05).toFixed(4), loSpy=+(Math.min(s0.l,s0.c)*0.96).toFixed(4);
    const cD=ultimo(S(D.t)), vD=S(D.t).v.at(-1);
    const cnbc={
      [spy.t]:q(spy,1.01,{high:txt(hiSpy),low:txt(loSpy),volume:txt(s0.v*2+1234)}),
      [D.t]:q(D,1.02,{volume:txt(Math.floor(vD/2))}),           // volumen MENOR: no baja
      [DE1.t.replace('.DE','-DE')]:q(DE1,1.01,{last_time:HOY_ISO+'T17:13:18.000+0200'}),
      [DE2.t.replace('.DE','-DE')]:q(DE2,1.01,{currencyCode:'USD'}),   // otra moneda
      [DEviejo.t.replace('.DE','-DE')]:q(DEviejo,1.01),         // su vela no es de hoy
      [BR1.t]:q(BR1,1.01,{last_time:HOY_ISO+'T12:13:33.000-0300'}), // solo con el simbolo de Yahoo
      [C.t]:q(C,1.01),                                         // data912 lo trae roto
    };
    const lista=[{symbol:C.t,c:+(ultimo(S(C.t))*1.30).toFixed(4)}];
    w.__cnbc=cnbc;w.__lista=lista;w.__en=EN_RUEDA;w.__fuera=FUERA;
    const cDE2=ultimo(S(DE2.t)), cViejo=ultimo(S(DEviejo.t)), cSpy=s0.c;

    // Nueva York cerrado: los de EE.UU. no, los de afuera si
    const R0=w.eval('aplicarVivo(null,leerCnbc({FormattedQuoteResult:{FormattedQuote:'+
      'Object.entries(__cnbc).map(([k,v])=>({symbol:k,...v}))}}),__fuera)');
    ok('con Nueva York cerrado no toca los de EE.UU.',ultimo(S(spy.t))===cSpy&&!R0.cambiados.includes(D.t),
       JSON.stringify(R0.cambiados));
    ok('pero sí los de afuera, que tienen su propia rueda',
       R0.cambiados.includes(DE1.t)&&R0.cambiados.includes(BR1.t),JSON.stringify(R0.cambiados));

    const R=w.eval('aplicarVivo(__lista,leerCnbc({FormattedQuoteResult:{FormattedQuote:'+
      'Object.entries(__cnbc).map(([k,v])=>({symbol:k,...v}))}}),__en)');
    const sp=S(spy.t);
    ok('un ETF (que data912 no tiene) toma el precio de CNBC',
       Math.abs(ultimo(sp)-cSpy*1.01)<1e-3,`${ultimo(sp)} vs ${cSpy*1.01}`);
    ok('lee los miles con coma ("1,234.5")',R.cambiados.includes(spy.t));
    ok('toma el máximo y el mínimo del día de CNBC',sp.h.at(-1)===hiSpy&&sp.l.at(-1)===loSpy,
       `${sp.h.at(-1)}/${sp.l.at(-1)} vs ${hiSpy}/${loSpy}`);
    ok('y el volumen del día, que sube',sp.v.at(-1)===s0.v*2+1234,sp.v.at(-1));
    ok('pero el volumen nunca baja',S(D.t).v.at(-1)===vD,`${S(D.t).v.at(-1)} vs ${vD}`);
    ok('la apertura sigue sin tocarse',sp.o.at(-1)===s0.o);
    // ya los parcheo la vuelta de Nueva York cerrado: se mira el precio, no si cambio
    ok('Alemania con el código de CNBC (BAS-DE)',Math.abs(ultimo(S(DE1.t))-ultimo(DE1)*1.01)<1e-3,
       `${ultimo(S(DE1.t))} vs ${ultimo(DE1)*1.01}`);
    ok('Brasil con el símbolo de Yahoo cuando CNBC no conoce el otro',
       Math.abs(ultimo(S(BR1.t))-ultimo(BR1)*1.01)<1e-3,`${ultimo(S(BR1.t))} vs ${ultimo(BR1)*1.01}`);
    ok('otra moneda se descarta aunque el precio cierre',
       ultimo(S(DE2.t))===cDE2&&R.descartados.includes(DE2.t),JSON.stringify(R.descartados));
    ok('una cotización de otra rueda que la última vela no se aplica',ultimo(S(DEviejo.t))===cViejo);
    ok('si data912 trae un dato roto, se prueba con CNBC',
       Math.abs(ultimo(S(C.t))-ultimo(C)*1.01)<1e-3&&!R.descartados.includes(C.t),
       `${ultimo(S(C.t))} vs ${ultimo(C)*1.01}`);
    ok('el que no tiene fuente queda anotado',R.sinFuente.includes(KS.t),R.sinFuente.slice(0,5).join(' '));
    ok('y cuenta los de CNBC aparte',R.porFuente.cnbc>=5,JSON.stringify(R.porFuente));
  }

  console.log('\n== el circuito entero: pedido, parche, tabla y pastilla ==');
  {
    const PA=+(ultimo(A)*1.04).toFixed(2), PS=+(ultimo(spy)*1.02).toFixed(2), PA2=+(ultimo(A)*1.05).toFixed(2);
    const cnbcDe=(s,p)=>({last:txt(p),currencyCode:s.mon||'USD',last_time:HOY_ISO+'T11:28:00.000-0400'});
    const w=await abrir({d912:{stocks:[{symbol:A.t,c:PA,pct_change:4}],adrs:[]},
      cnbc:{[spy.t]:cnbcDe(spy,PS),[A.t]:cnbcDe(A,PA2)}});
    // el reloj de la prueba: rueda abierta en la fecha de la fixtura
    w.eval(`relojNY=()=>({fecha:${HOY},min:11*60,dia:'Wed'})`);
    /* La pagina arranca su propio ciclo al abrir, con el reloj de verdad: si
       la prueba corre con la rueda abierta, ese primer pedido tambien sale.
       Se lo deja terminar antes de contar, o se cuentan los dos. */
    await esperar(300);
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    await esperar(50);
    const d9=w.__pedidos.filter(u=>u.indexOf('data912')>=0), cn=simbolosCnbc(w.__pedidos);
    ok('pide los dos paneles de data912',d9.length===2,JSON.stringify(d9));
    ok('a CNBC le pide el ETF y los de afuera',cn.includes(spy.t)&&cn.includes(BR1.t)&&
       cn.includes(DE1.t.replace('.DE','-DE')),cn.length);
    ok('y NO lo que data912 ya trajo',!cn.includes(A.t),A.t);
    ok('en lotes de hasta 200',w.__pedidos.filter(u=>u.indexOf('cnbc')>=0).every(u=>
      decodeURIComponent(u.split('symbols=')[1]).split('|').length<=200));
    const precioEnTabla=t=>{
      const fila=[...w.document.querySelectorAll('#tabla tbody tr')].find(tr=>
        (tr.querySelector('.tk')||{}).textContent===t);
      const col=[...w.document.querySelectorAll('#tabla thead th')].findIndex(th=>/^Precio/.test(th.textContent.trim()));
      return fila&&col>=0?parseFloat(fila.children[col].textContent.replace(',','.')):NaN;};
    ok('la tabla muestra el precio de data912',precioEnTabla(A.t)===PA,precioEnTabla(A.t));
    ok('y el del ETF, de CNBC',precioEnTabla(spy.t)===PS,precioEnTabla(spy.t));
    const f=w.eval(`filas.find(f=>f.t===${JSON.stringify(A.t)})`);
    ok('la variación del día se recalculó sobre ese precio',
       Math.abs(f.chg-(PA/A.c[A.c.length-2]-1))<1e-9,f.chg);
    const pas=w.document.querySelector('#frescura');
    ok('la pastilla dice "en vivo"',pas.textContent==='en vivo'&&pas.classList.contains('vivo'),
       pas.textContent);
    ok('y el título dice cuántos de cada fuente',/desde data912/.test(pas.title)&&/desde CNBC/.test(pas.title),
       pas.title);
    ok('y cuáles quedaron sin precio en vivo',/Sin precio en vivo/.test(pas.title)&&
       w.eval('VIVO.sinFuente').includes(KS.t),pas.title);

    // data912 se cae: CNBC respalda, tambien a los que eran de data912
    w.__fuentes={d912:null,cnbc:w.__fuentes.cnbc};
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    await esperar(50);
    ok('si data912 se cae, a CNBC le pide también las acciones',simbolosCnbc(w.__pedidos).includes(A.t));
    ok('y el precio sale de CNBC',precioEnTabla(A.t)===PA2,precioEnTabla(A.t));
    ok('la pastilla sigue "en vivo"',pas.textContent==='en vivo',pas.textContent);
    ok('y avisa que CNBC está de respaldo',/respaldo/.test(pas.title),pas.title);

    // se caen las dos: la pastilla vuelve sola a lo publicado
    w.__fuentes={d912:null,cnbc:null};
    await w.eval('pedirVivo()');
    ok('si se caen las dos, deja de decir "en vivo"',pas.textContent!=='en vivo',pas.textContent);
    ok('y no muestra ninguna alarma',!/error|falló|rojo/i.test(pas.textContent),pas.textContent);
  }

  console.log('\n== Nueva York cerrado, fin de semana y pestaña escondida ==');
  {
    // un papel de afuera SI se actualiza: la pastilla igual no puede decir "en vivo"
    const w=await abrir({d912:{stocks:[],adrs:[]},cnbc:{[DE1.t.replace('.DE','-DE')]:
      {last:txt(+(ultimo(DE1)*1.01).toFixed(4)),currencyCode:'EUR',last_time:HOY_ISO+'T17:13:18.000+0200'}}});
    await esperar(300);
    w.eval(`relojNY=()=>({fecha:${HOY},min:18*60,dia:'Wed'})`);
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    const cn=simbolosCnbc(w.__pedidos);
    ok('con Nueva York cerrado no se le pide nada a data912',
       !w.__pedidos.some(u=>u.indexOf('data912')>=0),JSON.stringify(w.__pedidos));
    ok('y a CNBC solo los de afuera',cn.length>0&&cn.every(s=>/[.-]/.test(s.slice(1))&&!/^BRK/.test(s)),
       cn.filter(s=>!/[.-]/.test(s.slice(1))).slice(0,5).join(' '));
    ok('el de afuera sí se actualizó',w.eval('VIVO.cubiertos')>0,w.eval('VIVO.cubiertos'));
    ok('la pastilla no dice "en vivo" con Nueva York cerrado',
       w.document.querySelector('#frescura').textContent!=='en vivo');

    w.eval(`relojNY=()=>({fecha:${HOY},min:11*60,dia:'Sat'})`);
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    ok('el fin de semana: cero pedidos',w.__pedidos.length===0,w.__pedidos.length);

    w.eval(`relojNY=()=>({fecha:${HOY},min:11*60,dia:'Wed'})`);
    Object.defineProperty(w.document,'hidden',{get:()=>true,configurable:true});
    w.__pedidos.length=0;
    await w.eval('pedirVivo()');
    ok('pestaña escondida: cero pedidos',w.__pedidos.length===0,w.__pedidos.length);
  }

  console.log(fallas?'\nFALLAS: '+fallas:'\nVIVO OK');
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
