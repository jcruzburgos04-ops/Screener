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

  console.log('== filtro por sector (y por industria) ==');
  $('#btnInd').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  ok('el boton dice Sectores',/Sectores/.test($('#btnInd').textContent),$('#btnInd').textContent);
  const sectores=$$('#tablaInd tr[data-ind]');
  ok('hay ranking de sectores',sectores.length>0,sectores.length);
  ok('son pocos grupos, no cien',sectores.length<=20,sectores.length);
  const antes=$$('#tabla tbody tr').length;
  const nombreSec=sectores[0].querySelector('td').textContent;
  sectores[0].dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(700);   // el guardado tiene 400 ms de debounce
  ok('filtrar por sector achica',$$('#tabla tbody tr').length<antes,
     $$('#tabla tbody tr').length+' vs '+antes);
  const ths=$$('#tabla thead th').map(x=>x.dataset.k);
  const iSec=ths.indexOf('sector');
  ok('y todas las filas son de ese sector',
     $$('#tabla tbody tr').every(tr=>tr.children[iSec].textContent.trim()===nombreSec),
     nombreSec);
  const ses=JSON.parse(w.localStorage.getItem('screener_ash_sesion'));
  ok('queda guardado el sector',ses._ind===nombreSec,ses._ind);
  ok('y el campo elegido',ses._indCampo==='sector',ses._indCampo);

  $$('#panelInd .chip[data-campo]').find(c=>c.dataset.campo==='industria')
    .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(400);
  ok('se puede cambiar a industria',/Industrias/.test($('#btnInd').textContent),
     $('#btnInd').textContent);
  ok('cambiar de campo suelta el filtro',$$('#tabla tbody tr').length===antes,
     $$('#tabla tbody tr').length+' vs '+antes);
  ok('y hay mas industrias que sectores',
     $$('#tablaInd tr[data-ind]').length>sectores.length,
     $$('#tablaInd tr[data-ind]').length+' vs '+sectores.length);
  $$('#panelInd .chip[data-campo]').find(c=>c.dataset.campo==='sector')
    .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(300);
  $('#indTodas').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(300);
  ok('"Todos" lo saca',$$('#tabla tbody tr').length===antes,$$('#tabla tbody tr').length);

  console.log('== la etiqueta del boton acompaña al campo elegido ==');
  {
    $$('#panelInd .chip[data-campo]').find(c=>c.dataset.campo==='industria')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(300);
    $('#nomPerfil').value='con industrias';
    $('#btnGuardar').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(300);
    $$('#panelInd .chip[data-campo]').find(c=>c.dataset.campo==='sector')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(300);
    ok('al volver a sector el boton lo dice',/Sectores/.test($('#btnInd').textContent),
       $('#btnInd').textContent);
    $('#selPerfil').value='m:con industrias';
    $('#selPerfil').dispatchEvent(new w.Event('change'));
    await esperar(500);
    ok('al cargar el perfil el boton se actualiza',/Industrias/.test($('#btnInd').textContent),
       $('#btnInd').textContent);
    ok('y el panel lista industrias',w.eval('campoGrupo')==='industria',w.eval('campoGrupo'));
    $$('#panelInd .chip[data-campo]').find(c=>c.dataset.campo==='sector')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(300);
  }

  console.log('== el buscador entiende sectores ==');
  $('#buscar').value=nombreSec;
  $('#buscar').dispatchEvent(new w.Event('input',{bubbles:true}));
  await esperar(300);
  ok('buscar el nombre de un sector filtra',
     $$('#tabla tbody tr').length>0&&$$('#tabla tbody tr').length<antes,
     $$('#tabla tbody tr').length);
  $('#buscar').value='';
  $('#buscar').dispatchEvent(new w.Event('input',{bubbles:true}));
  await esperar(200);

  console.log('== filtros por linea de tendencia ==');
  {
    const total=$$('#tabla tbody tr').length;
    const ths=$$('#tabla thead th').map(x=>x.dataset.k);
    const iFig=ths.indexOf('patron');
    ok('la columna Figura esta por defecto',iFig>=0,ths.join(','));

    $('#fPatron').value='Canal alcista';
    $('#fPatron').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    const n=$$('#tabla tbody tr').length;
    ok('filtrar por figura achica',n>0&&n<total,n+' de '+total);
    ok('y todas son canales alcistas',
       $$('#tabla tbody tr').every(tr=>tr.children[iFig].textContent.trim()==='Canal alcista'));
    $('#fPatron').value='';
    $('#fPatron').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);

    $('#fResDist').value='3';
    $('#fResDist').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    const iRes=ths.indexOf('tl_res_dist');
    const cerca=$$('#tabla tbody tr').length;
    ok('"cerca de la resistencia" achica',cerca<total,cerca+' de '+total);
    ok('la etiqueta muestra el valor',/3.0%/.test($('#lResDist').textContent),
       $('#lResDist').textContent);
    ok('ninguna queda a mas de 3% de la resistencia',
       $$('#tabla tbody tr').every(tr=>{
         const s=tr.children[iRes].textContent.trim();
         if(!s)return false;
         if(/rota/.test(s))return true;          // ya la rompio: cuenta
         return parseFloat(s)<=3.0001;}),
       $$('#tabla tbody tr').slice(0,3).map(tr=>tr.children[iRes].textContent).join(' | '));
    $('#fResDist').value='0';
    $('#fResDist').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);

    $('#fToques').value='4';
    $('#fToques').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    ok('el filtro de toques achica',$$('#tabla tbody tr').length<total,
       $$('#tabla tbody tr').length+' de '+total);
    $('#fToques').value='0';
    $('#fToques').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    ok('al soltarlos vuelven todas',$$('#tabla tbody tr').length===total,
       $$('#tabla tbody tr').length+' vs '+total);

    // cambiar la ventana rehace las lineas y no debe romper
    for(const [barras,piv] of [[40,2],[400,20],[120,5]]){
      $('#tlBarras').value=barras;$('#tlPivote').value=piv;
      $('#tlBarras').dispatchEvent(new w.Event('input',{bubbles:true}));
      await esperar(450);
    }
    ok('cambiar los parametros de la tendencia no rompe',
       $$('#tabla tbody tr').length>0&&errores.length===0,errores.join('|'));
  }

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
