/* ===========================================================================
   LA PASTILLA DE FRESCURA TIENE QUE DECIR LA VERDAD
   ===========================================================================
   Se corre con TZ=America/Argentina/Buenos_Aires a proposito: el bug solo
   aparecia fuera de UTC.

   El runner escribe la hora en UTC pero el texto va sin zona ("2026-08-28
   14:53"), y Date.parse de un texto sin zona lo lee como hora LOCAL. En UTC-3
   eso corria todo 3 horas hacia adelante, asi que CUALQUIER archivo de menos
   de 3 horas se mostraba como "precios de recien" -- aunque fuera del cierre
   anterior. El 28/08 el cron no corrio en todo el dia, el usuario vio los
   precios de ayer, y la pastilla seguia en verde diciendole que estaban al dia.

   Si alguna vez volves a parsear DATOS.fecha sin forzar la Z, o sacas el campo
   `ts` del payload, esto se pone en rojo.
   ======================================================================== */
/* Que la pastilla diga la verdad en la zona del usuario (UTC-3). */
const fs=require('fs');const {JSDOM}=require('jsdom');
const path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const html=fs.readFileSync(S+'/index.html','utf8');
const base=JSON.parse(fs.readFileSync(S+'/datos.json','utf8'));
let fallas=0;const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''))}};
function abrir(datos){return new Promise(res=>{
 const alm={_m:{},getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}};
 const pedidas=[];
 const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
  beforeParse(w){const noop=()=>{};
   const ctx={measureText:()=>({width:10}),createLinearGradient:()=>({addColorStop:noop}),canvas:{width:300,height:150}};
   w.HTMLCanvasElement.prototype.getContext=()=>new Proxy(ctx,{get:(t,k)=>(k in t?t[k]:noop),set:()=>true});
   w.Element.prototype.scrollIntoView=noop;
   Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
   Object.defineProperty(w,'localStorage',{value:alm,configurable:true});
   w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
   w.requestAnimationFrame=f=>setTimeout(f,0);w.navigator.clipboard={writeText:async()=>{}};
   w.fetch=async u=>{const s=String(u);pedidas.push(s);
    if(s.indexOf('api/')===0)throw new Error('x');
    if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>JSON.stringify(datos)};
    throw new TypeError('Failed to fetch');};}});
 const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
   clearInterval(t);setTimeout(()=>res({w:dom.window,pedidas}),300);}},20);});}
(async()=>{
 const ahora=Date.now();
 // A) datos de hace 3 horas: NO puede decir "recién"
 const viejo=JSON.parse(JSON.stringify(base));
 viejo.ts=Math.floor((ahora-3*3600*1000)/1000);
 viejo.fecha=new Date(ahora-3*3600*1000).toISOString().slice(0,16).replace('T',' ');
 let r=await abrir(viejo);
 let p=r.w.document.querySelector('#frescura').textContent.trim();
 ok('datos de 3 horas NO dicen "recién"',!/recién/.test(p),p);
 // B) datos de recién: SI
 const nuevo=JSON.parse(JSON.stringify(base));
 nuevo.ts=Math.floor(ahora/1000);
 nuevo.fecha=new Date(ahora).toISOString().slice(0,16).replace('T',' ');
 r=await abrir(nuevo);
 p=r.w.document.querySelector('#frescura').textContent.trim();
 ok('datos de recién SI lo dicen',/recién|hace 0|hace 1/.test(p),p);
 // C) payload viejo, sin ts: se lee como UTC igual
 const sinTs=JSON.parse(JSON.stringify(base));
 delete sinTs.ts;
 sinTs.fecha=new Date(ahora-3*3600*1000).toISOString().slice(0,16).replace('T',' ');
 r=await abrir(sinTs);
 p=r.w.document.querySelector('#frescura').textContent.trim();
 ok('un payload viejo sin ts tambien se lee bien',!/recién/.test(p),p);
 // D) la URL de datos.json lleva el parametro
 ok('datos.json se pide con parametro anti-cache',
    r.pedidas.some(u=>/datos\.json\?v=/.test(u)),
    r.pedidas.filter(u=>u.includes('datos.json')).join(' '));
 console.log(fallas?'\nFALLAS: '+fallas:'\nFRESCURA OK');
 process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
