/* ===========================================================================
   LAS COLUMNAS SON TUYAS, NO DEL FILTRO
   ===========================================================================
   El caso que reporto el usuario, textual: "pasa cuando paso de sin filtros a
   un filtro, y se pierde toda la configuracion de columnas".

   La causa era que la seleccion de columnas viajaba DENTRO de cada perfil
   guardado, asi que elegir un filtro del desplegable te reemplazaba las
   columnas por las que tenia ese perfil el dia que lo guardaste. No habia forma
   de tener una tabla estable: cada filtro mostraba columnas distintas.

   Ahora viven en su propia clave de localStorage y no las toca nadie mas: ni
   los perfiles, ni los presets, ni "sin filtros", ni la vista que llega por
   URL. Si volves a meter las columnas adentro del estado de un perfil, esto se
   pone en rojo.
   ======================================================================== */
const fs=require('fs');const {JSDOM}=require('jsdom');
const path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const html=fs.readFileSync(S+'/index.html','utf8'),datos=fs.readFileSync(S+'/datos.json','utf8');
let fallas=0;const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''))}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
function alm(){const m={};return{getItem:k=>k in m?m[k]:null,setItem:(k,v)=>{m[k]=String(v)},removeItem:k=>{delete m[k]},_m:m};}
function abrir(a){return new Promise(res=>{const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
 beforeParse(w){const noop=()=>{};
  const ctx={measureText:()=>({width:10}),createLinearGradient:()=>({addColorStop:noop}),canvas:{width:300,height:150}};
  w.HTMLCanvasElement.prototype.getContext=()=>new Proxy(ctx,{get:(t,k)=>(k in t?t[k]:noop),set:()=>true});
  w.Element.prototype.scrollIntoView=noop;
  Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
  Object.defineProperty(w,'localStorage',{value:a,configurable:true});
  w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
  w.requestAnimationFrame=f=>setTimeout(f,0);w.navigator.clipboard={writeText:async()=>{}};
  w.fetch=async u=>{const s=String(u);if(s.indexOf('api/')===0)throw new Error('x');
   if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};throw new TypeError('Failed to fetch');};}});
 const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){clearInterval(t);res(dom.window)}},20);});}
const cols=w=>[...w.document.querySelectorAll('#tabla thead th')].map(t=>t.dataset.k);
const chip=(w,k)=>[...w.document.querySelectorAll('#chipsCols .chip')].find(c=>c.dataset.v===k);
async function apagar(w,ks){for(const k of ks){const c=chip(w,k);
  if(c&&c.classList.contains('on'))c.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));}await esperar(600);}
const perfil=(w,v)=>{const s=w.document.querySelector('#selRapido');s.value=v;
  s.dispatchEvent(new w.Event('change',{bubbles:true}));};

(async()=>{
console.log('== EL CASO: de "sin filtros" a un filtro ==');
{const a=alm();const w=await abrir(a);
 await apagar(w,['rsi','adr','adx']);
 const mias=cols(w).join(',');
 ok('apago tres columnas',!cols(w).includes('rsi')&&!cols(w).includes('adr'));

 // guardo un perfil AHORA (lleva estas columnas adentro, como antes)
 w.prompt=()=>'mio';w.document.querySelector('#btnGuardarRapido')
   .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(400);
 // vuelvo a prender una, para que el perfil quede desincronizado a proposito
 chip(w,'rsi').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(600);
 const ahora=cols(w).join(',');
 ok('vuelvo a prender rsi',cols(w).includes('rsi'));

 perfil(w,'m:mio');await esperar(700);
 ok('elegir MI perfil no me cambia las columnas',cols(w).join(',')===ahora,cols(w).join(',').slice(0,70));

 perfil(w,'0');await esperar(700);
 ok('"sin filtros" tampoco',cols(w).join(',')===ahora,cols(w).join(',').slice(0,70));

 /* Un SEGUNDO perfil, guardado con otras columnas encima. Antes esto se
    probaba con los presets de fabrica; se sacaron, y lo que hay que verificar
    sigue siendo lo mismo: saltar de un perfil a otro no me toca las columnas. */
 w.prompt=()=>'otro';w.document.querySelector('#btnGuardarRapido')
   .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(400);
 perfil(w,'m:otro');await esperar(700);
 ok('otro perfil tampoco',cols(w).join(',')===ahora,cols(w).join(',').slice(0,70));

 perfil(w,'0');await esperar(700);
 perfil(w,'m:otro');await esperar(700);
 perfil(w,'m:mio');await esperar(700);
 ok('despues de saltar entre varios, siguen iguales',cols(w).join(',')===ahora,cols(w).join(',').slice(0,70));

 const w2=await abrir(a);await esperar(400);
 ok('y sobreviven a recargar',cols(w2).join(',')===ahora,cols(w2).join(',').slice(0,70));
}
console.log(fallas?'\nFALLAS: '+fallas:'\nTODO PASA');
process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
