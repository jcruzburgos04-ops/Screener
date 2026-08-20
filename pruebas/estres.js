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

  console.log('== filtros del AVWAP ==');
  {
    const total=$$('#tabla tbody tr').length;
    const ths=$$('#tabla thead th').map(x=>x.dataset.k);
    const iEst=ths.indexOf('avwap_estado'), iDist=ths.indexOf('avwap_dist');
    ok('las columnas del AVWAP estan por defecto',iEst>=0&&iDist>=0,ths.join(','));

    $('#fAvwap').value='Recuperado';
    $('#fAvwap').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    const n=$$('#tabla tbody tr').length;
    ok('filtrar por estado achica',n<total,n+' de '+total);
    ok('y todos dicen Recuperado',n===0||
       $$('#tabla tbody tr').every(tr=>tr.children[iEst].textContent.trim()==='Recuperado'),
       $$('#tabla tbody tr').slice(0,3).map(tr=>tr.children[iEst].textContent).join('|'));
    $('#fAvwap').value='';
    $('#fAvwap').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);

    $('#fAvDist').value='2';
    $('#fAvDist').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    const cerca=$$('#tabla tbody tr');
    ok('"a menos de 2% del AVWAP" achica',cerca.length<total,cerca.length+' de '+total);
    ok('y toma los dos lados de la linea',cerca.length===0||
       cerca.every(tr=>Math.abs(parseFloat(tr.children[iDist].textContent))<=2.001),
       cerca.slice(0,4).map(tr=>tr.children[iDist].textContent).join('|'));
    ok('la etiqueta lo muestra',/2.0%/.test($('#lAvDist').textContent),
       $('#lAvDist').textContent);
    $('#fAvDist').value='0';
    $('#fAvDist').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(400);
    ok('al soltarlo vuelven todas',$$('#tabla tbody tr').length===total,
       $$('#tabla tbody tr').length+' vs '+total);
  }

  console.log('== las cuatro lecturas del cruce del ASH ==');
  {
    // El filtro viejo era uno solo: "cruzo hacia arriba hace menos de N". Los
    // otros tres casos son los que pidio el usuario, en especial "bajista hace
    // rato", que es donde se buscan los pisos.
    const total=$$('#tabla tbody tr').length;
    const ths=$$('#tabla thead th').map(x=>x.dataset.k);
    const iBar=ths.indexOf('ash_d_cruce'), iAsh=ths.indexOf('ash_d');
    ok('las columnas del cruce estan a la vista',iBar>=0&&iAsh>=0,ths.join(','));

    const poner=async(dir,n)=>{
      $('#fCruceDir').value=dir;
      $('#fCruceDir').dispatchEvent(new w.Event('input',{bubbles:true}));
      $('#fCruceMax').value=String(n);
      $('#fCruceMax').dispatchEvent(new w.Event('input',{bubbles:true}));
      await esperar(400);
      return $$('#tabla tbody tr');};
    const barras=tr=>parseFloat(tr.children[iBar].textContent);
    const ash=tr=>parseFloat(tr.children[iAsh].textContent);

    let fs=await poner('1',8);
    ok('alcista hace poco: achica',fs.length<total,fs.length+' de '+total);
    ok('todos con el ASH arriba y pocas barras',
       fs.length===0||fs.every(tr=>ash(tr)>0&&barras(tr)<=8),
       fs.slice(0,4).map(tr=>ash(tr)+'/'+barras(tr)).join('|'));
    ok('la etiqueta dice el sentido',/≤ 8 ruedas/.test($('#lCruce').textContent),
       $('#lCruce').textContent);

    fs=await poner('1+',8);
    ok('alcista hace rato: todos con muchas barras',
       fs.length===0||fs.every(tr=>ash(tr)>0&&barras(tr)>=8),
       fs.slice(0,4).map(tr=>ash(tr)+'/'+barras(tr)).join('|'));
    ok('y la etiqueta se da vuelta',/≥ 8 ruedas/.test($('#lCruce').textContent),
       $('#lCruce').textContent);

    fs=await poner('0',8);
    ok('bajista hace poco: todos con el ASH abajo',
       fs.length===0||fs.every(tr=>ash(tr)<0&&barras(tr)<=8),
       fs.slice(0,4).map(tr=>ash(tr)+'/'+barras(tr)).join('|'));

    fs=await poner('0+',8);
    ok('bajista hace rato: abajo y hace tiempo',
       fs.length===0||fs.every(tr=>ash(tr)<0&&barras(tr)>=8),
       fs.slice(0,4).map(tr=>ash(tr)+'/'+barras(tr)).join('|'));
    ok('los cuatro casos juntos no dejan pasar a nadie dos veces',
       (await poner('1',8)).length+(await poner('0',8)).length<=total);

    fs=await poner('1',0);
    ok('en cero se apaga y vuelven todas',fs.length===total,fs.length+' vs '+total);
    ok('y la etiqueta vuelve a off',$('#lCruce').textContent==='off',
       $('#lCruce').textContent);
  }

  console.log('== el panel de filtros no se pisa a si mismo ==');
  {
    // jsdom no resuelve calc(), pero si devuelve las variables: se verifica el
    // invariante de verdad, que el interior mida el panel MENOS la barra de
    // desplazamiento y que las dos salgan del mismo numero
    const raiz=w.getComputedStyle(w.document.documentElement);
    const ancho=parseFloat(raiz.getPropertyValue('--panel-ancho'));
    const barra=parseFloat(raiz.getPropertyValue('--barra-sc'));
    ok('el ancho del panel esta declarado',ancho>0,ancho);
    ok('se reserva lugar para la barra de desplazamiento',barra>0&&barra<ancho,barra);
    ok('el interior se calcula restandola',
       /calc\(var\(--panel-ancho\) - var\(--barra-sc\)\)/.test(html),
       'no encontre la regla');
    ok('hay subtitulos que agrupan los filtros',$$('.subt').length>=5,$$('.subt').length);
    const offs=$$('label b').filter(b=>b.textContent==='off');
    ok('los "off" van atenuados',offs.length>0&&offs.every(b=>b.classList.contains('apagado')),
       offs.length);
    $('#fAdr').value='3';
    $('#fAdr').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(300);
    ok('y al ponerle un valor se enciende',!$('#lAdr').classList.contains('apagado'),
       $('#lAdr').textContent);
    $('#fAdr').value='0';
    $('#fAdr').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(300);
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
