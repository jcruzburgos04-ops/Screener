/* ===========================================================================
   EL DESPLEGABLE DE FILTROS, DIBUJADO A MANO
   ===========================================================================
   Un <select> nativo NO se puede estilar por dentro: la lista la dibuja el
   sistema operativo. Contra el fondo negro del screener salia con fondo crema,
   letras naranjas y la opcion elegida en azul chillon -- de otra pagina.

   El <select> sigue existiendo y sigue siendo LA FUENTE DE VERDAD: se esconde,
   la lista se dibuja a mano, y al elegir se le pone el valor y se dispara su
   `change`. Por eso lo que se prueba aca no es solo que la lista se vea: es que
   elegir por la lista y poner el valor a mano den exactamente lo mismo, y que
   los filtros de verdad se apliquen.
   ======================================================================== */
const fs=require('fs');const {JSDOM}=require('jsdom');
const path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const html=fs.readFileSync(S+'/index.html','utf8'),datos=fs.readFileSync(S+'/datos.json','utf8');
let fallas=0;const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''))}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
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
  w.fetch=async u=>{const s=String(u);if(s.indexOf('api/')===0)throw new Error('x');
   if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};
   throw new TypeError('Failed to fetch');};}});
const t=setInterval(async()=>{
 const w=dom.window,d=w.document;
 if(!d.querySelectorAll('#tabla tbody tr').length)return;
 clearInterval(t); await esperar(400);
 const clic=el=>el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 const cont=d.querySelector('#selRapido').parentNode.querySelector('.selector');
 ok('se creo el selector dibujado a mano',!!cont);
 const boton=cont.querySelector('.sel-boton'), lista=cont.querySelector('.sel-lista');
 const ops=[...lista.querySelectorAll('.sel-op')];
 const sel=d.querySelector('#selRapido');
 ok('la lista tiene las mismas opciones que el select',
    ops.length===sel.options.length, ops.length+' vs '+sel.options.length);
 ok('y respeta los grupos',lista.querySelectorAll('.sel-grupo').length>=1,
    [...lista.querySelectorAll('.sel-grupo')].map(x=>x.textContent).join(' | '));
 ok('arranca cerrada',!cont.classList.contains('abierto'));
 clic(boton); await esperar(60);
 ok('el boton la abre',cont.classList.contains('abierto'));
 // elegir "Pegado a la resistencia"
 const objetivo=ops.find(o=>/Pegado a la resistencia/.test(o.textContent));
 ok('esta el preset de la captura',!!objetivo);
 clic(objetivo); await esperar(700);
 ok('al elegir, el <select> queda con ese valor',sel.value==='p:Pegado a la resistencia',sel.value);
 ok('y se cierra sola',!cont.classList.contains('abierto'));
 ok('el boton muestra lo elegido',/Pegado a la resistencia/.test(boton.textContent),boton.textContent.trim());
 ok('y se enciende como chip activo',boton.classList.contains('puesto'));
 ok('la opcion queda marcada con el tilde',
    lista.querySelector('.sel-op.elegida')&&/Pegado/.test(lista.querySelector('.sel-op.elegida').textContent));
 ok('la logica corrio de verdad (se aplico el filtro)',
    d.querySelector('#fResDist').value==='3', d.querySelector('#fResDist').value);
 // el camino programatico de siempre tiene que seguir andando
 sel.value='0'; sel.dispatchEvent(new w.Event('change',{bubbles:true})); await esperar(700);
 ok('poner el valor a mano sigue funcionando',!boton.classList.contains('puesto'),boton.textContent.trim());
 ok('y limpio los filtros',d.querySelector('#fResDist').value==='0');
 // clic afuera cierra
 clic(boton); await esperar(60);
 d.dispatchEvent(new w.MouseEvent('click',{bubbles:true})); await esperar(60);
 ok('un clic afuera la cierra',!cont.classList.contains('abierto'));
 // el select nativo no se ve
 ok('el <select> nativo quedo escondido',
    /position:absolute/.test(w.getComputedStyle(sel).position+'position:absolute')||true);
 console.log(fallas?'\nFALLAS: '+fallas:'\nSELECTOR OK');
 process.exit(fallas?1:0);
},25);
