const fs=require('fs'),{JSDOM}=require('jsdom');
// Sitio de prueba: lo arma correr.sh en pruebas/tmp/sitio.
const SITIO=process.env.SCREENER_SITIO||require('path').join(__dirname,'tmp','sitio');
const html=fs.readFileSync(SITIO+'/index.html','utf8');
const datos=fs.readFileSync(SITIO+'/datos.json','utf8');
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
  beforeParse(w){
    const noop=()=>{};
    w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>noop,set:()=>true});
    w.Element.prototype.scrollIntoView=noop;
    Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
    Object.defineProperty(w,'localStorage',{value:{_m:{},getItem(k){return this._m[k]??null},
      setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}},configurable:true});
    w.fetch=async u=>{if(String(u).indexOf('api/')===0)throw new Error('sin servidor');
      return {ok:true,body:null,text:async()=>datos};};
    w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
  }});
const w=dom.window,doc=w.window.document;const errores=[];
w.addEventListener('error',e=>errores.push(e.message));
const $=s=>doc.querySelector(s),$$=s=>[...doc.querySelectorAll(s)];
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+'  -> '+x);}};

setTimeout(async()=>{
  console.log('== periodos extremos del ASH ==');
  const tiempos=[];
  for(const [L,S] of [[2,1],[200,100],[2,100],[16,4],[9,3],[100,2]]){
    $('#ashLen').value=L;$('#ashSmooth').value=S;
    const t0=Date.now();
    $('#ashLen').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    tiempos.push([L+'/'+S,$('#estado').textContent]);
  }
  ok('los periodos extremos no rompen',errores.length===0,errores.join('|'));
  console.log('   tiempos:',tiempos.map(t=>t[0]+' '+t[1]).join(' · '));
  $('#ashLen').value=16;$('#ashSmooth').value=4;
  $('#ashLen').dispatchEvent(new w.Event('input',{bubbles:true}));
  await esperar(400);

  console.log('== sin ninguna EMA ==');
  for(const c of $$('#chipsEma .chip'))
    if(c.classList.contains('on'))c.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(400);
  ok('sin EMAs sigue habiendo tabla',$$('#tabla tbody tr').length>100,$$('#tabla tbody tr').length);
  for(const v of ['20','50'])
    $$('#chipsEma .chip').find(c=>c.dataset.v===v).dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(400);

  console.log('== sin ninguna columna elegible ==');
  w.eval('ponerColumnas([])');
  await esperar(200);
  ok('quedan las dos fijas',$$('#tabla thead th').length===2,$$('#tabla thead th').length);
  ok('las filas siguen',$$('#tabla tbody tr').length>100,$$('#tabla tbody tr').length);
  $('#colTodo').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(300);
  ok('todas las columnas',$$('#tabla thead th').length>30,$$('#tabla thead th').length);
  $('#colEsencial').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(300);

  console.log('== filtro por industria ==');
  $('#btnInd').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  const fils=$$('#tablaInd tr[data-ind]');
  ok('hay ranking de industrias',fils.length>0,fils.length);
  const antes=$$('#tabla tbody tr').length;
  fils[0].dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(700);   // el guardado tiene 400 ms de debounce
  ok('filtrar por industria achica',$$('#tabla tbody tr').length<antes,
     $$('#tabla tbody tr').length+' vs '+antes);
  ok('y queda guardado',JSON.parse(w.localStorage.getItem('screener_ash_sesion'))._ind!=null);
  $('#indTodas').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(300);
  ok('"Todas" lo saca',$$('#tabla tbody tr').length===antes,$$('#tabla tbody tr').length);

  console.log('== CSV ==');
  let blob=null;
  w.URL.createObjectURL=b=>{blob=b;return 'blob:x';};
  $('#btnCsv').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  ok('genera el CSV',blob!==null&&blob.size>1000,blob&&blob.size);

  console.log('== copiar tickers y vista ==');
  w.navigator.clipboard={writeText:async t=>{w.__copiado=t;}};
  $('#btnCopiar').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(150);
  ok('copia los tickers',(w.__copiado||'').split(',').length>100,(w.__copiado||'').slice(0,40));
  $('#btnVista2').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(150);
  ok('copia el enlace de la vista',/#v=/.test(w.__copiado||''),(w.__copiado||'').slice(0,60));

  ok('cero errores de JS en toda la corrida',errores.length===0,errores.join('|'));
  console.log(fallas?'\nFALLAS: '+fallas:'\nESTRES OK');
  process.exit(fallas?1:0);
},3000);
