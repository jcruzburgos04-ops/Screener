/* ===========================================================================
   PERSISTENCIA DE LA SELECCION DE COLUMNAS
   ===========================================================================
   Nueve flujos reales, porque "el guardado de columnas falla" fue la queja mas
   repetida del proyecto y tuvo DOS causas distintas, las dos introducidas por
   arreglos anteriores:

     1. copiarVista() dejaba el #v= pegado en la barra y al abrir pisaba la
        sesion guardada  (lo cubre columnas.js)
     2. con dos pestañas abiertas, la vieja grababa SU estado al pasar a segundo
        plano y revertia lo que acababas de configurar en la otra. Como
        visibilitychange dispara en cada cambio de pestaña, alcanzaba con ir y
        venir.  (es el caso I de aca abajo)

   Si alguna vez volves a hacer que una pestaña grabe sin que el usuario haya
   tocado nada en ella, el caso I se pone en rojo.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(S,'index.html'),'utf8');
const datos=fs.readFileSync(path.join(S,'datos.json'),'utf8');
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''));}};
function nuevoAlmacen(ini){const m={...(ini||{})};return{
  getItem:k=>k in m?m[k]:null,setItem:(k,v)=>{m[k]=String(v)},removeItem:k=>{delete m[k]},_m:m};}
function abrir(alm,url){return new Promise(res=>{
  const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:url||'https://local/',
    beforeParse(w){const noop=()=>{};
      const ctx={measureText:()=>({width:10}),createLinearGradient:()=>({addColorStop:noop}),
        getImageData:()=>({data:[0,0,0,0]}),canvas:{width:300,height:150}};
      w.HTMLCanvasElement.prototype.getContext=()=>new Proxy(ctx,{
        get:(t,k)=>(k in t?t[k]:noop),set:()=>true});
      w.Element.prototype.scrollIntoView=noop;
      Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
      Object.defineProperty(w,'localStorage',{value:alm,configurable:true});
      w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
      w.requestAnimationFrame=f=>setTimeout(f,0);
      w.navigator.clipboard={writeText:async()=>{}};
      w.fetch=async u=>{const s=String(u);
        if(s.indexOf('api/')===0)throw new Error('sin servidor');
        if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>datos};
        throw new TypeError('Failed to fetch');};}});
  const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
    clearInterval(t);res(dom.window);}},20);});}
const cols=w=>[...w.document.querySelectorAll('#tabla thead th')].map(t=>t.dataset.k);
const clic=(w,sel)=>{const e=w.document.querySelector(sel);
  if(!e)throw new Error('no existe '+sel);e.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));};
const chipCol=(w,k)=>[...w.document.querySelectorAll('#chipsCols .chip')].find(c=>c.dataset.v===k);
async function apagar(w,ks){for(const k of ks){const c=chipCol(w,k);
  if(c&&c.classList.contains('on'))c.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));}
  await esperar(600);}

(async()=>{
console.log('== A · apagar columnas y recargar ==');
{const a=nuevoAlmacen();let w=await abrir(a);await apagar(w,['rsi','adr']);
 const w2=await abrir(a);await esperar(300);
 ok('siguen apagadas',!cols(w2).includes('rsi')&&!cols(w2).includes('adr'),cols(w2).join(','));}

console.log('\n== B · apagar, reordenar arrastrando, recargar ==');
{const a=nuevoAlmacen();let w=await abrir(a);await apagar(w,['rsi']);
 const filas=[...w.document.querySelectorAll('#ordenCols .fila-ord')];
 if(filas.length>2){const b=w.document.querySelector('#ordenCols .fila-ord:nth-child(3) .ord-b[data-mover="-1"]');
   if(b)b.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));}
 await esperar(600);
 const orden1=cols(w).join(',');
 const w2=await abrir(a);await esperar(300);
 ok('el orden sobrevive',cols(w2).join(',')===orden1,cols(w2).join(',').slice(0,60));
 ok('y la columna apagada sigue apagada',!cols(w2).includes('rsi'));}

console.log('\n== C · apagar y despues elegir un perfil del desplegable ==');
/* Con presets de fabrica esto se probaba eligiendo uno; se sacaron, asi que se
   guarda un perfil ANTES de apagar las columnas -- lleva rsi y adr prendidas
   adentro -- y recien despues se apagan y se elige. Que el perfil las tenga
   guardadas es justamente lo que hace que la prueba valga: elegirlo NO las
   tiene que devolver. */
{const a=nuevoAlmacen();let w=await abrir(a);
 w.prompt=()=>'mio';
 w.document.querySelector('#btnGuardarRapido').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(400);
 await apagar(w,['rsi','adr']);
 const sel=w.document.querySelector('#selRapido');
 sel.value='m:mio';sel.dispatchEvent(new w.Event('change',{bubbles:true}));
 await esperar(700);
 ok('el perfil NO deberia devolver las columnas',
    !cols(w).includes('rsi')&&!cols(w).includes('adr'),cols(w).join(','));
 const w2=await abrir(a);await esperar(300);
 ok('y despues de recargar tampoco',!cols(w2).includes('rsi'),cols(w2).join(','));}

console.log('\n== D · apagar TODAS las columnas apagables ==');
{const a=nuevoAlmacen();let w=await abrir(a);
 const todas=[...w.document.querySelectorAll('#chipsCols .chip.on')].map(c=>c.dataset.v);
 await apagar(w,todas);
 const q=cols(w).length;
 const w2=await abrir(a);await esperar(300);
 ok('no vuelven solas al recargar',cols(w2).length===q,'antes '+q+' despues '+cols(w2).length);}

console.log('\n== E · apagar todas las EMAs ==');
{const a=nuevoAlmacen();let w=await abrir(a);
 const on=[...w.document.querySelectorAll('#chipsEma .chip.on')].map(c=>c.dataset.v);
 for(const v of on){const c=[...w.document.querySelectorAll('#chipsEma .chip')].find(x=>x.dataset.v===v);
   c.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));}
 await esperar(700);
 const w2=await abrir(a);await esperar(400);
 const emas=[...w2.document.querySelectorAll('#chipsEma .chip.on')].map(c=>c.dataset.v);
 ok('siguen apagadas al recargar',emas.length===0,'volvieron '+emas.join(','));}

console.log('\n== F · apagar y cerrar la pestaña enseguida (antes del debounce) ==');
{const a=nuevoAlmacen();let w=await abrir(a);
 const c=chipCol(w,'rsi');c.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 w.dispatchEvent(new w.Event('pagehide'));           // sin esperar los 400ms
 await esperar(100);
 const w2=await abrir(a);await esperar(300);
 ok('el cambio se guardo igual',!cols(w2).includes('rsi'),cols(w2).join(','));}

console.log('\n== G · apagar, ir a Panorama, recargar ==');
{const a=nuevoAlmacen();let w=await abrir(a);await apagar(w,['rsi','adr']);
 clic(w,'#chipVista');await esperar(500);
 const w2=await abrir(a);await esperar(400);
 ok('siguen apagadas',!cols(w2).includes('rsi')&&!cols(w2).includes('adr'),cols(w2).join(','));}

console.log('\n== H · guardar un perfil, apagar mas, recargar ==');
{const a=nuevoAlmacen();let w=await abrir(a);await apagar(w,['rsi']);
 w.prompt=()=>'mio';clic(w,'#btnGuardarRapido');await esperar(400);
 await apagar(w,['adr']);
 const w2=await abrir(a);await esperar(400);
 ok('las dos siguen apagadas',!cols(w2).includes('rsi')&&!cols(w2).includes('adr'),cols(w2).join(','));}


console.log('== I · dos pestañas: la vieja pisa a la nueva ==');
{
  const a=nuevoAlmacen();
  const vieja=await abrir(a);            // pestaña abierta desde ayer
  await esperar(300);
  const nueva=await abrir(a);            // abro otra y configuro aca
  await apagar(nueva,['rsi','adr']);
  ok('la nueva las apago',!cols(nueva).includes('rsi'));

  // vuelvo a la pestaña vieja y despues la cierro / cambio de pestaña
  vieja.dispatchEvent(new vieja.Event('pagehide'));
  await esperar(200);

  const w3=await abrir(a);await esperar(300);
  ok('lo que configure en la nueva sobrevive',
     !cols(w3).includes('rsi')&&!cols(w3).includes('adr'),
     'volvieron: '+['rsi','adr'].filter(k=>cols(w3).includes(k)).join(','));
}

console.log(fallas?'\nFALLAS: '+fallas:'\nPERSISTENCIA DE COLUMNAS OK');
process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
