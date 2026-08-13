/* ===========================================================================
   PRECIOS DE YAHOO PEDIDOS DESDE EL NAVEGADOR
   ===========================================================================
   Acá se prueba lo único que se puede probar sin internet: que la respuesta de
   Yahoo se interprete bien, que las barras nuevas se peguen sobre las viejas
   sin escalones, que el ajuste por dividendos se aplique, que las fechas caigan
   en el día correcto en un mercado con otro huso, y que cuando Yahoo NO deja
   (que es lo que pasa cuando bloquea CORS) la página lo diga en vez de mostrar
   precios viejos como si fueran de hoy.

   Lo que NO se puede probar acá: si Yahoo permite CORS hoy. Eso depende de
   Yahoo y hay que verlo en el navegador de verdad.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const SITIO=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
const datos=JSON.parse(fs.readFileSync(path.join(SITIO,'datos.json'),'utf8'));

let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'   -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));

/* Una respuesta de Yahoo igual a la de verdad: epoch en segundos, arrays
   paralelos, adjclose aparte, y el huso del mercado en meta.gmtoffset. */
function respuestaYahoo(fechas,cierres,{gmtoffset=-14400,dividendo=1}={}){
  return {chart:{result:[{
    meta:{gmtoffset,exchangeTimezoneName:'America/New_York'},
    timestamp:fechas.map(f=>{
      const a=Math.floor(f/10000),m=Math.floor(f/100)%100,d=f%100;
      // 13:30 UTC = apertura de Nueva York; menos el offset para que al
      // sumarlo de nuevo caiga en el mismo dia
      return Date.UTC(a,m-1,d,13,30)/1000-gmtoffset;}),
    indicators:{
      quote:[{open:cierres.map(c=>c*0.99),high:cierres.map(c=>c*1.02),
              low:cierres.map(c=>c*0.98),close:cierres.slice(),
              volume:cierres.map(()=>1000000)}],
      adjclose:[{adjclose:cierres.map(c=>c*dividendo)}]}}]}};
}

function abrir(respondedor){
  return new Promise(res=>{
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
      url:'https://local/',
      beforeParse(w){
        const noop=()=>{};
        w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>noop,set:()=>true});
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
        Object.defineProperty(w,'localStorage',{value:{_m:{},
          getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},
          removeItem(k){delete this._m[k]}},configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.__pedidos=[];
        w.fetch=async(u)=>{
          const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)
            return {ok:true,body:null,text:async()=>JSON.stringify(datos)};
          w.__pedidos.push(s);
          return respondedor(s,w);
        };
      }});
    const w=dom.window;
    const t=setInterval(()=>{
      if(w.document.querySelectorAll('#tabla tbody tr').length){clearInterval(t);
        res({w,$:s=>w.document.querySelector(s),
             $$:s=>[...w.document.querySelectorAll(s)]});}
    },20);
  });
}

/* Abre la pagina con un datos.json cualquiera. Se usa para simular "abri el
   link un lunes a la mañana con los datos del viernes". */
function abrirCon(datosTexto,respondedor,almacenInicial){
  return new Promise(res=>{
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
      url:'https://local/',
      beforeParse(w){
        const noop=()=>{};
        w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>noop,set:()=>true});
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
        Object.defineProperty(w,'localStorage',{value:{_m:{...(almacenInicial||{})},
          getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},
          removeItem(k){delete this._m[k]}},configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.__pedidos=[];
        w.fetch=async u=>{
          const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>datosTexto};
          w.__pedidos.push(s);return respondedor(s,w);};
      }});
    const t=setInterval(()=>{
      if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
        clearInterval(t);res(dom.window);}},20);
  });
}

(async()=>{
  console.log('== interpretar la respuesta de Yahoo ==');
  {
    const {w,$}=await abrir(async()=>({ok:false,status:403}));
    const r=respuestaYahoo([20260810,20260811],[100,110],{dividendo:0.5});
    const b=w.eval('barrasDeYahoo('+JSON.stringify(r)+')');
    ok('saca las fechas en el dia correcto',b.d[0]===20260810&&b.d[1]===20260811,b.d.join(','));
    ok('aplica el ajuste por dividendos al cierre',Math.abs(b.c[1]-55)<1e-9,b.c[1]);
    ok('y el mismo factor a la apertura',Math.abs(b.o[1]-110*0.99*0.5)<1e-9,b.o[1]);
    ok('el maximo nunca queda por debajo del cierre',b.h[1]>=b.c[1]&&b.l[1]<=b.c[1]);
    ok('el volumen no se ajusta',b.v[1]===1000000,b.v[1]);

    // Tokio: +9 h. Si no se usara gmtoffset, la barra caeria un dia antes.
    const rt=respuestaYahoo([20260811],[100],{gmtoffset:32400});
    const bt=w.eval('barrasDeYahoo('+JSON.stringify(rt)+')');
    ok('un mercado con otro huso cae en su propio dia',bt.d[0]===20260811,bt.d[0]);

    ok('una respuesta vacia devuelve null',
       w.eval('barrasDeYahoo({chart:{result:[]}})')===null);
    ok('una respuesta con nulls no rompe',
       w.eval('barrasDeYahoo({chart:{result:[{meta:{gmtoffset:0},timestamp:[1,2],'+
              'indicators:{quote:[{close:[null,null]}]}}]}})')===null);
  }

  console.log('\n== pegar las barras nuevas sobre el historial ==');
  {
    const {w}=await abrir(async()=>({ok:false,status:403}));
    const res=w.eval(`(function(){
      const s=DATOS.simbolos[0];
      const antes={n:s.d.length,ultima:s.d[s.d.length-1],anteultima:s.d[s.d.length-2],
                   cierreAnterior:s.c[s.c.length-2]};
      // Yahoo devuelve la ultima barra guardada (quiza parcial) mas dos nuevas
      const nuevo={d:[antes.ultima,antes.ultima+1,antes.ultima+2],
                   o:[1,2,3],h:[1,2,3],l:[1,2,3],c:[11,22,33],v:[9,9,9]};
      fusionarBarras(s,nuevo);
      return {antes,despues:{n:s.d.length,ultima:s.d[s.d.length-1],
              c1:s.c[s.c.length-1],c3:s.c[s.c.length-3],
              anteultimaSigueIgual:s.c[s.c.length-4]===antes.cierreAnterior}};
    })()`);
    ok('agrega las barras nuevas',res.despues.ultima===res.antes.ultima+2,
       res.despues.ultima+' vs '+res.antes.ultima);
    ok('reemplaza la ultima (podia ser parcial)',res.despues.c3===11,res.despues.c3);
    ok('no toca el historial viejo',res.despues.anteultimaSigueIgual);
    ok('no duplica fechas',w.eval('new Set(DATOS.simbolos[0].d).size===DATOS.simbolos[0].d.length'));
    ok('no crece sin limite',res.despues.n<=(datos.barras||600),res.despues.n);
  }

  console.log('\n== Yahoo bloqueado: tiene que avisar, no mentir ==');
  {
    // esto es exactamente lo que hace el navegador cuando falta la cabecera CORS
    const {w,$}=await abrir(async()=>{throw new TypeError('Failed to fetch');});
    // se dispara explicitamente: si dependiera del refresco automatico, la
    // prueba pasaria o fallaria segun la fecha con la que se armo la fixtura
    w.eval('traerDeYahoo(false)');
    for(let i=0;i<200&&w.eval('bajandoYahoo');i++)await esperar(50);
    await esperar(300);
    ok('muestra la banda de aviso',$('#avisoYahoo').style.display==='block',
       $('#avisoYahoo').style.display);
    ok('el aviso dice que son del ultimo cierre',
       /último cierre publicado/.test($('#avisoYahoo').textContent),
       $('#avisoYahoo').textContent.slice(0,80));
    ok('abre solo la ayuda del proxy',$('#detProxy').open);
    ok('la tabla sigue mostrando el historial',$$0(w)>100,$$0(w));
    ok('no se inventa ningun precio',
       w.eval('DATOS.simbolos[0].c.length')===datos.simbolos[0].c.length);
    ok('no intento 465 pedidos al pedo',w.__pedidos.length<=2,w.__pedidos.length);
  }

  console.log('\n== Yahoo contesta: actualiza y limpia el atraso ==');
  {
    const hoy=new Date();
    const f=hoy.getUTCFullYear()*10000+(hoy.getUTCMonth()+1)*100+hoy.getUTCDate();
    const {w,$}=await abrir(async(u)=>{
      const sym=decodeURIComponent(u.split('/chart/')[1].split('?')[0]);
      const base=100+sym.length;
      return {ok:true,status:200,json:async()=>respuestaYahoo([f],[base])};
    });
    // el archivo publicado trae atrasados; el refresco automatico al abrir ya
    // corrio para cuando llegamos aca, asi que la referencia es el archivo
    const atrasadosAntes=datos.simbolos.filter(s=>+s.at>0).length;
    for(let i=0;i<300&&w.eval('bajandoYahoo');i++)await esperar(50);
    await esperar(200);
    w.eval('traerDeYahoo(false)');
    for(let i=0;i<300&&w.eval('bajandoYahoo');i++)await esperar(50);
    await esperar(300);
    ok('pidio todos los simbolos',w.__pedidos.length>=datos.simbolos.length,
       w.__pedidos.length+' de '+datos.simbolos.length);
    ok('la url es la del endpoint de graficos',
       /\/v8\/finance\/chart\/[^/?]+\?range=/.test(w.__pedidos[1]||''),w.__pedidos[1]);
    ok('el archivo publicado traia atrasados',atrasadosAntes>0,atrasadosAntes);
    ok('despues no queda ninguno',w.eval('DATOS.simbolos.filter(s=>s.at>0).length')===0,
       w.eval('DATOS.simbolos.filter(s=>s.at>0).length'));
    ok('el ultimo cierre es el de hoy',w.eval('DATOS.ultimo_cierre')===f,
       w.eval('DATOS.ultimo_cierre'));
    ok('la tabla se repinto',$$0(w)>100,$$0(w));
    ok('el panel cuenta cuantos actualizo',/actualizados/.test($('#infoYahoo').textContent),
       $('#infoYahoo').textContent);
    ok('no quedo la banda roja',$('#avisoYahoo').style.display!=='block');
    ok('el precio de la tabla salio de Yahoo',
       w.eval('filas.find(f=>f.t===DATOS.simbolos[0].t).precio')===100+datos.simbolos[0].t.length,
       w.eval('filas.find(f=>f.t===DATOS.simbolos[0].t).precio'));
  }

  console.log('\n== el proxy propio ==');
  {
    const {w,$}=await abrir(async(u)=>{
      if(u.indexOf('https://mi-proxy.workers.dev')!==0)throw new TypeError('Failed to fetch');
      return {ok:true,status:200,json:async()=>respuestaYahoo([20260811],[123])};
    });
    w.eval('traerDeYahoo(false)');
    for(let i=0;i<200&&w.eval('bajandoYahoo');i++)await esperar(50);
    await esperar(300);
    ok('sin proxy configurado, falla',$('#avisoYahoo').style.display==='block',
       $('#avisoYahoo').style.display);
    $('#yaProxy').value='https://mi-proxy.workers.dev/';
    $('#btnProbarProxy').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(600);
    ok('con el proxy puesto, anda',/Anda/.test($('#infoYahoo').textContent),
       $('#infoYahoo').textContent);
    ok('la barra final del proxy no duplica la /',
       (w.__pedidos.find(u=>u.indexOf('mi-proxy')>=0)||'').indexOf('.dev//')<0,
       w.__pedidos.find(u=>u.indexOf('mi-proxy')>=0));
    ok('el proxy queda guardado',w.localStorage.getItem('screener_ash_proxy')
       ==='https://mi-proxy.workers.dev/');
  }

  console.log('\n== Yahoo frena por exceso de pedidos (429) ==');
  {
    let n=0;
    const {w,$}=await abrir(async()=>{
      n++;
      if(n<=1)return {ok:true,status:200,json:async()=>respuestaYahoo([20260811],[100])};
      return {ok:false,status:429};
    });
    await esperar(200);
    w.eval('traerDeYahoo(false)');
    for(let i=0;i<200&&w.eval('bajandoYahoo');i++)await esperar(50);
    await esperar(200);
    ok('corta en vez de insistir 465 veces',w.__pedidos.length<60,w.__pedidos.length);
    ok('y lo explica',/429|exceso/.test($('#infoYahoo').textContent),
       $('#infoYahoo').textContent);
  }

  console.log('\n== al abrir el link con datos viejos, pide solo ==');
  {
    const viejo=JSON.parse(JSON.stringify(datos));
    // una semana atras: es el caso de abrir el link un lunes a la mañana
    for(const s of viejo.simbolos){
      const f=s.d[s.d.length-1];
      const t0=Date.UTC(Math.floor(f/10000),Math.floor(f/100)%100-1,f%100)-7*86400000;
      const dd=new Date(t0);
      s.d[s.d.length-1]=dd.getUTCFullYear()*10000+(dd.getUTCMonth()+1)*100+dd.getUTCDate();
      s.at=0;
    }
    viejo.ultimo_cierre=Math.max(...viejo.simbolos.map(s=>s.d[s.d.length-1]));
    const w=await abrirCon(JSON.stringify(viejo),async()=>{
      throw new TypeError('Failed to fetch');});
    await esperar(1500);
    ok('sin que toques nada, sale a buscar precios',w.__pedidos.length>0,w.__pedidos.length);
    ok('y avisa si no pudo',
       w.document.querySelector('#avisoYahoo').style.display==='block');
  }

  console.log('\n== recargar enseguida no dispara otra vuelta ==');
  {
    // sin marca previa: sale a buscar aunque el archivo diga que esta al dia
    const hoy=new Date();
    const f=hoy.getUTCFullYear()*10000+(hoy.getUTCMonth()+1)*100+hoy.getUTCDate();
    const alDia=JSON.parse(JSON.stringify(datos));
    for(const s of alDia.simbolos){s.d[s.d.length-1]=f;s.at=0;}
    alDia.ultimo_cierre=f;
    const w1=await abrirCon(JSON.stringify(alDia),async()=>{
      throw new TypeError('Failed to fetch');});
    await esperar(1200);
    ok('aunque el archivo diga que esta al dia, igual busca',w1.__pedidos.length>0,
       w1.__pedidos.length);

    // con una marca de hace un minuto: no repite
    const w2=await abrirCon(JSON.stringify(alDia),async()=>{
      throw new TypeError('Failed to fetch');},
      {screener_ash_yahoo_ultimo:String(Date.now()-60*1000)});
    await esperar(1200);
    ok('si recargaste hace un minuto, no repite',w2.__pedidos.length===0,w2.__pedidos.length);

    // con una marca de hace media hora: vuelve a buscar
    const w3=await abrirCon(JSON.stringify(alDia),async()=>{
      throw new TypeError('Failed to fetch');},
      {screener_ash_yahoo_ultimo:String(Date.now()-30*60*1000)});
    await esperar(1200);
    ok('media hora despues, vuelve a buscar',w3.__pedidos.length>0,w3.__pedidos.length);

    // y con el tilde apagado, nunca
    const w4=await abrirCon(JSON.stringify(alDia),async()=>{
      throw new TypeError('Failed to fetch');},
      {screener_ash_yahoo_auto:'0'});
    await esperar(1200);
    ok('con el tilde apagado, no pide nada',w4.__pedidos.length===0,w4.__pedidos.length);
  }

  console.log('\n== la fecha de la mayoria, no la maxima ==');
  {
    // el caso real: 430 papeles de Nueva York en el cierre de ayer y uno de
    // Tokio que ya opera hoy. El maximo dice "al dia" y es mentira.
    const mezcla=JSON.parse(JSON.stringify(datos));
    const ayer=20260812, hoy=20260813;
    mezcla.simbolos.forEach((s,i)=>{s.d[s.d.length-1]=(i===0?hoy:ayer);s.at=0;});
    mezcla.ultimo_cierre=hoy;
    const w=await abrirCon(JSON.stringify(mezcla),async()=>{
      throw new TypeError('Failed to fetch');},{screener_ash_yahoo_auto:'0'});
    await esperar(600);
    ok('la mayoria manda',w.eval('fechaMayoritaria()')===ayer,w.eval('fechaMayoritaria()'));
    ok('y no es la maxima',w.eval('DATOS.ultimo_cierre')===hoy);
  }

  console.log(fallas?'\nFALLAS: '+fallas:'\nYAHOO OK');
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});

function $$0(w){return w.document.querySelectorAll('#tabla tbody tr').length;}
