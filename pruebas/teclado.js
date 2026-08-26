/* ===========================================================================
   TECLADO
   ===========================================================================
   Con 465 filas, moverse de a una con la flecha no alcanza, y unos atajos que
   solo figuran al fondo de un panel plegable no los encuentra nadie. Se
   verifica que los saltos caigan donde tienen que caer, que ? abra la hoja de
   atajos, y -lo que mas se rompe solo- que ninguna tecla se dispare mientras
   se esta escribiendo en el buscador.
   ======================================================================== */
const fs=require('fs');const {JSDOM}=require('jsdom');
const path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const html=fs.readFileSync(S+'/index.html','utf8'),datos=fs.readFileSync(S+'/datos.json','utf8');
const alm={_m:{},getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}};
let fallas=0;const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''))}};
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
 beforeParse(w){const noop=()=>{};
  const ctx={measureText:()=>({width:10}),createLinearGradient:()=>({addColorStop:noop}),canvas:{width:300,height:150}};
  w.HTMLCanvasElement.prototype.getContext=()=>new Proxy(ctx,{get:(t,k)=>(k in t?t[k]:noop),set:()=>true});
  w.Element.prototype.scrollIntoView=noop;
  Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
  Object.defineProperty(w,'localStorage',{value:alm,configurable:true});
  w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
  w.requestAnimationFrame=f=>setTimeout(f,0);w.navigator.clipboard={writeText:async()=>{}};
  w.fetch=async u=>{const s=String(u);if(s.indexOf('api/')===0)throw new Error('x');
   if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};throw new TypeError('Failed to fetch');};}});
const t=setInterval(async()=>{
 const w=dom.window,d=w.document;
 if(!d.querySelectorAll('#tabla tbody tr').length)return;
 clearInterval(t);
 const tecla=(k,extra)=>d.dispatchEvent(new w.KeyboardEvent('keydown',{key:k,bubbles:true,...(extra||{})}));
 const sel=()=>d.querySelector('#tabla tbody tr.sel')?.dataset.i;
 tecla('Home');await new Promise(r=>setTimeout(r,120));
 ok('Inicio va a la primera fila',sel()==='0',sel());
 tecla('PageDown');await new Promise(r=>setTimeout(r,120));
 ok('PageDown salta doce',sel()==='12',sel());
 tecla('PageUp');await new Promise(r=>setTimeout(r,120));
 ok('PageUp vuelve',sel()==='0',sel());
 tecla('End');await new Promise(r=>setTimeout(r,150));
 const n=d.querySelectorAll('#tabla tbody tr').length;
 ok('Fin va a la ultima',+sel()===n-1,sel()+' de '+n);
 tecla('?');await new Promise(r=>setTimeout(r,120));
 ok('la tecla ? abre los atajos',d.querySelector('#ayuda').classList.contains('abierto'));
 ok('y lista las teclas',d.querySelectorAll('#ayuda kbd').length>=12,d.querySelectorAll('#ayuda kbd').length);
 tecla('Escape');await new Promise(r=>setTimeout(r,120));
 ok('Escape la cierra',!d.querySelector('#ayuda').classList.contains('abierto'));
 // y no se dispara escribiendo en el buscador
 const b=d.querySelector('#buscar');b.focus();
 b.dispatchEvent(new w.KeyboardEvent('keydown',{key:'?',bubbles:true}));
 await new Promise(r=>setTimeout(r,120));
 ok('escribiendo en el buscador no se abre',!d.querySelector('#ayuda').classList.contains('abierto'));
 console.log(fallas?'\nFALLAS: '+fallas:'\nATAJOS OK');
 process.exit(fallas?1:0);
},25);
