/* ===========================================================================
   PANTALLA ANGOSTA Y PASTILLA DE FRESCURA
   ===========================================================================
   El screener se abre desde un link, asi que tarde o temprano se abre desde el
   telefono. Ahi el panel no puede robarle ancho a la tabla: tiene que ser un
   cajon que se abre encima. jsdom no hace layout, asi que lo comprobable es la
   maquinaria: que las clases cambien, que el velo cierre, que la tecla [ siga
   funcionando y que el estado guardado no abra el cajon solo al entrar.

   Tambien se prueba la pastilla de frescura, que es lo primero que se mira:
   verde si se actualizo recien, ambar si es el cierre de la ultima rueda, rojo
   si el archivo quedo viejo de verdad.
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

function abrir({ancho=1400,payload=null,almacen={}}={}){
  const texto=JSON.stringify(payload||datos);
  return new Promise(res=>{
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
      url:'https://local/',
      beforeParse(w){
        const noop=()=>{};
        w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>noop,set:()=>true});
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return ancho}});
        Object.defineProperty(w,'innerWidth',{value:ancho,configurable:true});
        // jsdom no trae matchMedia: se simula solo la consulta que usa la pagina
        w.matchMedia=q=>({matches:/max-width:\s*860px/.test(q)&&ancho<=860,
                          media:q,addListener:noop,removeListener:noop,
                          addEventListener:noop,removeEventListener:noop});
        Object.defineProperty(w,'localStorage',{value:{_m:{...almacen},
          getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},
          removeItem(k){delete this._m[k]}},configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.fetch=async u=>{
          const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>texto};
          throw new TypeError('Failed to fetch');};
      }});
    const t=setInterval(()=>{
      if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
        clearInterval(t);res(dom.window);}},20);
  });
}

function conFecha(diasAtras){
  const p=JSON.parse(JSON.stringify(datos));
  for(const s of p.simbolos){
    const f=s.d[s.d.length-1];
    const t=Date.UTC(Math.floor(f/10000),Math.floor(f/100)%100-1,f%100)-diasAtras*86400000;
    const d=new Date(t);
    s.d[s.d.length-1]=d.getUTCFullYear()*10000+(d.getUTCMonth()+1)*100+d.getUTCDate();
    s.at=0;
  }
  p.ultimo_cierre=Math.max(...p.simbolos.map(s=>s.d[s.d.length-1]));
  return p;
}

(async()=>{
  console.log('== telefono: el panel es un cajon ==');
  {
    const w=await abrir({ancho:420,almacen:{screener_ash_yahoo_auto:'0'}});
    const d=w.document,$=s=>d.querySelector(s);
    ok('arranca cerrado',!d.body.classList.contains('cajon'));
    ok('la tabla ocupa todo',d.body.classList.contains('compacto'));
    $('#btnAbrir').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(60);
    ok('el boton lo abre',d.body.classList.contains('cajon'));
    ok('aparece el velo',w.getComputedStyle($('#velo')).display!=='none'||
       d.body.classList.contains('cajon'));
    $('#velo').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(60);
    ok('el velo lo cierra',!d.body.classList.contains('cajon'));
    d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'[',bubbles:true}));
    await esperar(60);
    ok('la tecla [ lo abre',d.body.classList.contains('cajon'));
    d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'[',bubbles:true}));
    await esperar(60);
    ok('y lo vuelve a cerrar',!d.body.classList.contains('cajon'));
    ok('la tabla sigue entera',d.querySelectorAll('#tabla tbody tr').length>100,
       d.querySelectorAll('#tabla tbody tr').length);
  }

  console.log('\n== escritorio: el panel sigue siendo panel ==');
  {
    const w=await abrir({ancho:1400,almacen:{screener_ash_yahoo_auto:'0'}});
    const d=w.document;
    ok('arranca abierto',!d.body.classList.contains('compacto'));
    d.querySelector('#btnCerrar').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(60);
    ok('se puede plegar',d.body.classList.contains('compacto'));
    ok('sin cajon ni velo',!d.body.classList.contains('cajon'));
    ok('queda guardado',w.localStorage.getItem('screener_ash_panel')==='0');
  }

  console.log('\n== un panel plegado en el escritorio no abre el cajon en el telefono ==');
  {
    const w=await abrir({ancho:420,almacen:{screener_ash_panel:'1',
      screener_ash_yahoo_auto:'0'}});
    ok('sigue cerrado',!w.document.body.classList.contains('cajon'));
  }

  console.log('\n== la pastilla de frescura ==');
  {
    const recien=JSON.parse(JSON.stringify(datos));
    recien.fecha=new Date().toISOString().slice(0,16).replace('T',' ');
    const w1=await abrir({payload:recien,almacen:{screener_ash_yahoo_auto:'0'}});
    const p1=w1.document.querySelector('#frescura');
    ok('recien actualizado va en verde',p1.classList.contains('fresco'),
       p1.className+' | '+p1.textContent);

    const anoche=JSON.parse(JSON.stringify(datos));
    anoche.fecha='2020-01-01 22:30';
    const w2=await abrir({payload:anoche,almacen:{screener_ash_yahoo_auto:'0'}});
    const p2=w2.document.querySelector('#frescura');
    ok('el cierre de la rueda va en ambar',p2.classList.contains('tibio'),
       p2.className+' | '+p2.textContent);
    ok('y dice de que dia es',/cierre del/.test(p2.textContent),p2.textContent);

    const w3=await abrir({payload:conFecha(9),almacen:{screener_ash_yahoo_auto:'0'}});
    const p3=w3.document.querySelector('#frescura');
    ok('un archivo viejo va en rojo',p3.classList.contains('viejo'),
       p3.className+' | '+p3.textContent);
    ok('y dice cuantas ruedas',/ruedas de atraso/.test(p3.textContent),p3.textContent);
  }

  console.log('\n== el KPI de atrasados marca cuando esta filtrando ==');
  {
    const w=await abrir({almacen:{screener_ash_yahoo_auto:'0'}});
    const d=w.document;
    ok('arranca sin marcar',!d.querySelector('#kpiAtraso').classList.contains('filtrando'));
    d.querySelector('#kpiAtraso').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(120);
    ok('al tocarlo, filtra y se marca',
       d.querySelector('#kpiAtraso').classList.contains('filtrando')&&
       d.querySelector('#fSinAtraso').checked);
    d.querySelector('#kpiAtraso').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(120);
    ok('y al tocarlo de nuevo, vuelve',
       !d.querySelector('#kpiAtraso').classList.contains('filtrando'));
  }

  console.log(fallas?'\nFALLAS: '+fallas:'\nMOVIL Y FRESCURA OK');
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
