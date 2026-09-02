/* ===========================================================================
   LA VISTA DE BONOS
   ===========================================================================
   Lo que importa verificar acá no es que se vea lindo -- eso no se puede desde
   jsdom -- sino tres cosas que sí se rompen solas:

     1. que el interruptor de vistas no pueda quedar en dos posiciones a la vez
        (es el mismo error que ya hubo con los chips de Panorama y favoritos);
     2. que la tarjeta diga en la cara que NO hay TIR ni duration, porque una
        tabla de bonos incompleta que no lo avisa se lee como completa;
     3. que si bonos.json no existe todavia, la pantalla explique qué pasó en
        vez de quedarse en blanco o tirar un error.

   Los numeros de bonos_fixtura.json tienen la FORMA verificada contra la
   fuente real, pero son datos de prueba como todo lo de esta carpeta.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(S,'index.html'),'utf8');
const datos=fs.readFileSync(path.join(S,'datos.json'),'utf8');
const bonos=fs.readFileSync(path.join(__dirname,'bonos_fixtura.json'),'utf8');
let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
function abrir(hayBonos){return new Promise(res=>{
 const alm={_m:{},getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}};
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
  beforeParse(w){const noop=()=>{};
   const ctx={measureText:()=>({width:10}),createLinearGradient:()=>({addColorStop:noop}),canvas:{width:300,height:150}};
   w.HTMLCanvasElement.prototype.getContext=()=>new Proxy(ctx,{get:(t,k)=>(k in t?t[k]:noop),set:()=>true});
   w.Element.prototype.scrollIntoView=noop;
   Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1400}});
   Object.defineProperty(w,'localStorage',{value:alm,configurable:true});
   w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
   w.requestAnimationFrame=f=>setTimeout(f,0);w.navigator.clipboard={writeText:async()=>{}};
   w.fetch=async u=>{const s=String(u);
    if(s.indexOf('api/')===0)throw new Error('sin servidor');
    if(s.indexOf('bonos.json')>=0){
      if(!hayBonos)return{ok:false,status:404};
      return{ok:true,json:async()=>JSON.parse(bonos)};}
    if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};
    throw new TypeError('Failed to fetch');};}});
 const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
   clearInterval(t);res(dom.window);}},20);});}

(async()=>{
console.log('== el interruptor de tres posiciones ==');
{const w=await abrir(true), d=w.document;
 const clic=s=>d.querySelector(s).dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 const prendidos=()=>['#chipTabla','#chipVista','#chipBonos']
   .filter(s=>d.querySelector(s).classList.contains('on'));
 ok('arranca en Tabla',prendidos().join()==='#chipTabla',prendidos().join());
 clic('#chipBonos');await esperar(300);
 ok('al ir a Bonos queda SOLO Bonos prendido',prendidos().join()==='#chipBonos',prendidos().join());
 ok('y el body lo refleja',d.body.classList.contains('bonos')&&!d.body.classList.contains('panorama'));
 ok('la tabla del screener se esconde',
    w.getComputedStyle(d.querySelector('.tabla-wrap')).display==='none');
 ok('las tres vistas viven en la navegacion del panel',
    ['#chipTabla','#chipVista','#chipBonos'].every(s=>d.querySelector(s).closest('#navVistas')));
 clic('#chipVista');await esperar(300);
 ok('al ir a Panorama queda SOLO Panorama',prendidos().join()==='#chipVista',prendidos().join());
 ok('y sale de bonos',!d.body.classList.contains('bonos'));
 clic('#chipTabla');await esperar(200);
 ok('y se vuelve a la tabla',prendidos().join()==='#chipTabla'&&!d.body.classList.contains('bonos'));

 console.log('\n== lo que muestra ==');
 clic('#chipBonos');await esperar(400);
 const txt=d.querySelector('#bonosCuerpo').textContent;
 ok('separa por ley',/Ley Argentina/.test(txt)&&/Ley Nueva York/.test(txt));
 ok('muestra los tickers',/AL30/.test(txt)&&/GD30/.test(txt));
 ok('trae el tipo de cambio por bono',/Tipo de cambio por bono/.test(txt));
 ok('y el canje de leyes',/Canje de leyes/.test(txt));
 ok('con la mediana calculada',/1,0413/.test(txt)||/1\.0413/.test(txt),
    (txt.match(/mediana es[^,]{0,20}/)||[''])[0]);
 ok('AVISA que no hay TIR ni duration',/sin TIR/i.test(txt),
    (txt.match(/Todav.a sin[^.]{0,40}/)||[''])[0]);
 const filas=d.querySelectorAll('#bonosCuerpo .bo-tabla tbody tr');
 ok('dibuja filas de verdad',filas.length>=10,filas.length);

 console.log('\n== la vista se recuerda ==');
 const alm2=w.localStorage;
 ok('queda guardada como "b"',alm2.getItem('screener_ash_vista')==='b',
    alm2.getItem('screener_ash_vista'));

 console.log('\n== elegir un filtro te saca de bonos ==');
 const sel=d.querySelector('#selRapido');
 sel.value='p:Tendencia limpia';sel.dispatchEvent(new w.Event('change',{bubbles:true}));
 await esperar(700);
 ok('vuelve a la tabla sola',!d.body.classList.contains('bonos')&&
    d.querySelector('#chipTabla').classList.contains('on'));
}

console.log('\n== si todavia no hay bonos publicados ==');
{const w=await abrir(false), d=w.document;
 d.querySelector('#chipBonos').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(400);
 const txt=d.querySelector('#bonosCuerpo').textContent;
 ok('lo explica en vez de quedarse en blanco',/Todavía no hay datos/.test(txt),txt.slice(0,70));
 ok('y no dice "error"',!/error/i.test(txt));
}
console.log(fallas?'\nFALLAS: '+fallas:'\nBONOS OK');
process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
