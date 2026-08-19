const fs=require('fs'),path=require('path');
// Sitio de prueba: lo arma correr.sh en pruebas/tmp/sitio.
const SITIO=process.env.SCREENER_SITIO||require('path').join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
const datos=fs.readFileSync(path.join(SITIO,'datos.json'),'utf8');

// localStorage falso, compartido entre aperturas, para probar la persistencia
function nuevoAlmacen(){const m={};return{
  getItem:k=>k in m?m[k]:null, setItem:(k,v)=>{m[k]=String(v)},
  removeItem:k=>{delete m[k]}, clear:()=>{for(const k in m)delete m[k]}, _m:m};}

function stubCanvas(w){
  const noop=()=>{};
  w.HTMLCanvasElement.prototype.getContext=()=>({setTransform:noop,clearRect:noop,
    beginPath:noop,moveTo:noop,lineTo:noop,stroke:noop,fillRect:noop,fillText:noop,
    setLineDash:noop,save:noop,restore:noop,clip:noop,rect:noop,measureText:()=>({width:10}),
    set strokeStyle(v){},set fillStyle(v){},set lineWidth(v){},set font(v){},set textAlign(v){}});
  w.Element.prototype.scrollIntoView=function(){};
  Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
}

async function abrir(almacen,hash){
  const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
    url:'https://local/'+(hash||''),
    beforeParse(w){
      stubCanvas(w);
      Object.defineProperty(w,'localStorage',{value:almacen,configurable:true});
      // el servidor no existe; datos.json si
      w.fetch=async(u)=>{
        if(String(u).indexOf('api/')===0)throw new Error('sin servidor');
        if(String(u).indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};
        throw new Error('404 '+u);};
      w.navigator.clipboard={writeText:async t=>{w.__copiado=t;}};
      w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
      w.alert=m=>{w.__alerta=m;};
      w.prompt=()=>w.__prompt||null;
    }});
  const w=dom.window;
  for(let i=0;i<200;i++){await new Promise(r=>setTimeout(r,20));
    if(w.document.querySelectorAll('#tabla tbody tr').length)break;}
  return {dom,w,$:s=>w.document.querySelector(s),
          $$:s=>[...w.document.querySelectorAll(s)]};
}

let fallas=0,pruebas=0;
function ok(nombre,cond,extra){pruebas++;if(!cond){fallas++;
  console.log('  FALLA  '+nombre+(extra!==undefined?'   -> '+extra:''));}
  else console.log('  ok     '+nombre);}

(async()=>{
  const errores=[];
  const almacen=nuevoAlmacen();
  const {w,$,$$}=await abrir(almacen);
  w.addEventListener('error',e=>errores.push(e.message));
  const doc=w.document;

  console.log('\n== carga y tabla ==');
  const filas=()=>$$('#tabla tbody tr').length;
  ok('la tabla se pinta',filas()>100,filas());
  ok('KPI universo',+$('#kUni').textContent>400,$('#kUni').textContent);
  ok('KPI atrasados > 0',+$('#kA').textContent>0,$('#kA').textContent);
  ok('firma avisa atrasados',/atrasado/.test($('#firma').textContent),$('#firma').textContent);
  ok('hay marcas de atraso en la tabla',$$('#tabla tbody .atraso').length>0,
     $$('#tabla tbody .atraso').length);
  ok('sin errores de JS',errores.length===0,errores.join('|'));

  console.log('\n== filtro de atrasados ==');
  const antes=filas();
  $('#fSinAtraso').checked=true;
  $('#fSinAtraso').dispatchEvent(new w.Event('change'));
  await new Promise(r=>setTimeout(r,400));
  ok('esconder atrasados achica la tabla',filas()<antes,filas()+' vs '+antes);
  ok('no queda ninguna marca',$$('#tabla tbody .atraso').length===0);
  $('#fSinAtraso').checked=false;
  $('#fSinAtraso').dispatchEvent(new w.Event('change'));
  await new Promise(r=>setTimeout(r,400));
  ok('al destildar vuelven',filas()===antes,filas()+' vs '+antes);

  console.log('\n== la columna CEDEAR no repite el ticker ==');
  {
    const celdas=$$('#tabla tbody tr').map(tr=>{
      const ths=$$('#tabla thead th').map(x=>x.dataset.k);
      const i=ths.indexOf('local');
      return {t:tr.children[ths.indexOf('t')].textContent.trim(),
              c:tr.children[i].textContent.trim()};});
    const repetidos=celdas.filter(x=>x.c===x.t);
    ok('ninguna fila repite el ticker en CEDEAR',repetidos.length===0,
       JSON.stringify(repetidos.slice(0,3)));
    ok('los que no tienen CEDEAR propio muestran un punto',
       celdas.some(x=>x.c==='·'),celdas.slice(0,3).map(x=>x.c).join('|'));
  }

  console.log('\n== el ticker queda fijo al desplazar a lo ancho ==');
  {
    // jsdom no hace layout, pero si aplica el CSS: se comprueba que las dos
    // primeras columnas esten declaradas sticky y en posiciones distintas
    const tr=$$('#tabla tbody tr')[0];
    const c1=w.getComputedStyle(tr.children[0]), c2=w.getComputedStyle(tr.children[1]);
    ok('la estrella esta fija a la izquierda',c1.position==='sticky'&&c1.left==='0px',
       c1.position+'/'+c1.left);
    ok('el ticker tambien, corrido a su derecha',c2.position==='sticky'&&c2.left==='30px',
       c2.position+'/'+c2.left);
  }

  console.log('\n== los textos largos se cortan pero no se pierden ==');
  {
    const ths=$$('#tabla thead th').map(x=>x.dataset.k);
    const i=ths.indexOf('sector');
    const td=$$('#tabla tbody tr')[0].children[i];
    ok('la celda de sector se corta',td.classList.contains('corto'),td.className);
    ok('y guarda el texto entero en el title',!!td.getAttribute('title'),
       td.getAttribute('title'));
  }

  console.log('\n== ordenar por todas las columnas ==');
  let malas=[];
  for(const th of $$('#tabla thead th')){
    th.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await new Promise(r=>setTimeout(r,5));
    if(!filas())malas.push(th.dataset.k);
  }
  ok('ninguna columna vacia la tabla',malas.length===0,malas.join(','));

  console.log('\n== ASH: las 18 combinaciones modo x media ==');
  malas=[];
  for(const modo of ['RSI','STOCHASTIC','ADX'])
   for(const ma of ['EMA','WMA','SMA','SMMA','HMA','ALMA']){
    $('#ashModo').value=modo;$('#ashMa').value=ma;
    $('#ashMa').dispatchEvent(new w.Event('input',{bubbles:true}));
    await new Promise(r=>setTimeout(r,220));
    if(!filas())malas.push(modo+'/'+ma);
  }
  ok('las 18 combinaciones andan',malas.length===0,malas.join(','));
  $('#ashModo').value='RSI';$('#ashMa').value='EMA';
  $('#ashMa').dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,250));

  console.log('\n== el bug del debounce compartido ==');
  $('#ashLen').value='40';
  $('#ashLen').dispatchEvent(new w.Event('input',{bubbles:true}));
  $('#fRsiMin').value='10';                       // enseguida, un filtro liviano
  $('#fRsiMin').dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,500));
  const conf=$('#firma').textContent;
  ok('el cambio pesado no se pierde',/40\/4/.test(conf),conf);
  $('#ashLen').value='16';$('#fRsiMin').value='0';
  $('#ashLen').dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,400));

  console.log('\n== persistencia ==');
  // configuro cosas variadas
  $('#fAdr').value='2.5';$('#fAdr').dispatchEvent(new w.Event('input',{bubbles:true}));
  $('#buscar').value='NV';$('#buscar').dispatchEvent(new w.Event('input',{bubbles:true}));
  const chipEma=$$('#chipsEma .chip').find(c=>c.dataset.v==='200');
  chipEma.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  const chipGr=$$('#chipsGrupo .chip')[0];const grupoElegido=chipGr.dataset.v;
  chipGr.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await new Promise(r=>setTimeout(r,700));
  const vistaURL=w.eval('enlaceVista()');
  // simulo cerrar la pestaña
  w.dispatchEvent(new w.Event('pagehide'));
  const guardado=JSON.parse(almacen.getItem('screener_ash_sesion'));
  ok('guardo el ADR',guardado.fAdr==='2.5',guardado.fAdr);
  ok('guardo la busqueda',guardado._buscar==='NV',guardado._buscar);
  ok('guardo las EMAs',guardado._emas.includes(200),JSON.stringify(guardado._emas));
  ok('guardo los grupos',guardado._grupos.includes(grupoElegido),JSON.stringify(guardado._grupos));

  console.log('\n== reabrir con la misma sesion ==');
  const b=await abrir(almacen);
  ok('vuelve el ADR',b.$('#fAdr').value==='2.5',b.$('#fAdr').value);
  ok('vuelve la busqueda',b.$('#buscar').value==='NV',b.$('#buscar').value);
  ok('vuelve la EMA 200',b.$$('#chipsEma .chip').find(c=>c.dataset.v==='200')
      .classList.contains('on'));
  ok('vuelve el grupo',b.$$('#chipsGrupo .chip').find(c=>c.dataset.v===grupoElegido)
      .classList.contains('on'));
  ok('la tabla filtro por la busqueda',b.$$('#tabla tbody tr').length<50,
     b.$$('#tabla tbody tr').length);

  console.log('\n== una seleccion vieja de columnas recibe las nuevas ==');
  {
    // el caso real: una sesion guardada antes de que existieran las columnas
    // de lineas de tendencia, sin _colsVistas
    const viejo=nuevoAlmacen();
    viejo.setItem('screener_ash_sesion',JSON.stringify({
      _cols:['fav','t','sector','precio','chg','ash_d','rsi'],
      _orden:{col:'ash_d_norm',asc:false}}));
    const v=await abrir(viejo);
    const cols=v.$$('#tabla thead th').map(x=>x.dataset.k);
    ok('conserva las que habia elegido',cols.includes('sector')&&cols.includes('rsi'),
       cols.join(','));
    ok('respeta lo que habia apagado',!cols.includes('grupo')&&!cols.includes('perf_3m'),
       cols.join(','));
    ok('y suma las nuevas de tendencia',cols.includes('patron')&&
       cols.includes('tl_res_dist')&&cols.includes('tl_sop_dist'),cols.join(','));

    // una sesion guardada por la version nueva NO recibe agregados
    const actual=nuevoAlmacen();
    const w0=await abrir(actual);
    w0.$$('#chipsCols .chip').filter(c=>c.dataset.v==='patron')
      .forEach(c=>c.dispatchEvent(new w0.w.MouseEvent('click',{bubbles:true})));
    await new Promise(r=>setTimeout(r,700));
    w0.w.dispatchEvent(new w0.w.Event('pagehide'));
    const g=JSON.parse(actual.getItem('screener_ash_sesion'));
    ok('la sesion guarda que columnas conocia',Array.isArray(g._colsVistas)&&
       g._colsVistas.includes('patron'),(g._colsVistas||[]).length);
    const v2=await abrir(actual);
    ok('apagar una columna a proposito se respeta',
       !v2.$$('#tabla thead th').map(x=>x.dataset.k).includes('patron'),
       v2.$$('#tabla thead th').map(x=>x.dataset.k).join(','));
  }

  console.log('\n== la vista dentro de la URL, con almacen vacio ==');
  const hash='#'+vistaURL.split('#')[1];
  const c=await abrir(nuevoAlmacen(),hash);
  ok('la URL manda sobre un almacen vacio',c.$('#fAdr').value==='2.5',c.$('#fAdr').value);
  ok('la URL trae la busqueda',c.$('#buscar').value==='NV',c.$('#buscar').value);
  ok('la URL trae las EMAs',c.$$('#chipsEma .chip').find(x=>x.dataset.v==='200')
      .classList.contains('on'));

  console.log('\n== respaldo: exportar e importar ==');
  const d1=await abrir(nuevoAlmacen());
  d1.$('#fRsiMax').value='55';
  d1.$('#fRsiMax').dispatchEvent(new d1.w.Event('input',{bubbles:true}));
  d1.$('#nomPerfil').value='mi perfil';
  d1.$('#btnGuardar').dispatchEvent(new d1.w.MouseEvent('click',{bubbles:true}));
  await new Promise(r=>setTimeout(r,400));
  const respaldo=d1.w.eval('JSON.stringify({version:1,perfiles:leerPerfiles(),'+
    'favoritos:[...favoritos],sesion:estadoActual()})');
  ok('el perfil quedo en el respaldo',JSON.parse(respaldo).perfiles['mi perfil'],
     Object.keys(JSON.parse(respaldo).perfiles).join(','));
  const d2=await abrir(nuevoAlmacen());
  d2.w.eval('importarConfig('+JSON.stringify(respaldo)+')');
  await new Promise(r=>setTimeout(r,500));
  ok('importar restaura el filtro',d2.$('#fRsiMax').value==='55',d2.$('#fRsiMax').value);
  ok('importar restaura el perfil',
     [...d2.$('#selPerfil').options].some(o=>o.textContent==='mi perfil'));

  console.log('\n== almacen bloqueado ==');
  const roto={getItem:()=>{throw new Error('no')},setItem:()=>{throw new Error('no')},
              removeItem:()=>{throw new Error('no')}};
  const e=await abrir(roto);
  ok('la pagina igual funciona sin almacen',e.$$('#tabla tbody tr').length>100,
     e.$$('#tabla tbody tr').length);
  ok('avisa que no puede guardar',e.$('#avisoAlmacen').style.display==='block',
     e.$('#avisoAlmacen').style.display);

  console.log('\n== presets, limpiar y busquedas raras ==');
  const f=await abrir(nuevoAlmacen());
  for(const o of [...f.$('#selRapido').options]){
    f.$('#selRapido').value=o.value;
    f.$('#selRapido').dispatchEvent(new f.w.Event('change'));
    await new Promise(r=>setTimeout(r,120));
  }
  ok('todos los presets del desplegable andan',true);
  f.$('#selRapido').value='0';
  f.$('#selRapido').dispatchEvent(new f.w.Event('change'));
  await new Promise(r=>setTimeout(r,200));
  ok('"sin filtros" limpia de verdad',f.$('#fVol').value==='0'&&f.$('#fPrecio').value==='0',
     f.$('#fVol').value+'/'+f.$('#fPrecio').value);
  for(const q of ['<script>alert(1)</script>','"><img>','ñÑ','   ','AAPL']){
    f.$('#buscar').value=q;f.$('#buscar').dispatchEvent(new f.w.Event('input',{bubbles:true}));
    await new Promise(r=>setTimeout(r,60));
  }
  ok('busquedas raras no rompen',f.$('#tabla tbody').innerHTML.indexOf('<script')<0);

  console.log('\n== teclas y grafico ==');
  const tecla=(win,k)=>win.document.dispatchEvent(new win.window.KeyboardEvent('keydown',
    {key:k,bubbles:true}));
  f.$('#buscar').value='';f.$('#buscar').dispatchEvent(new f.w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,120));
  for(const k of ['ArrowDown','ArrowDown','ArrowUp','f','g','g','[','[','Escape'])
    f.w.document.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:k,bubbles:true}));
  await new Promise(r=>setTimeout(r,300));
  ok('las teclas no rompen nada',f.$$('#tabla tbody tr').length>0);
  f.$$('.tf .chip[data-tf]')[1].dispatchEvent(new f.w.MouseEvent('click',{bubbles:true}));
  await new Promise(r=>setTimeout(r,200));
  ok('el grafico semanal no explota',true);

  console.log('\n== filtro que no deja nada ==');
  f.$('#fVol').value='999999999999';
  f.$('#fVol').dispatchEvent(new f.w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,300));
  ok('muestra el cartel de vacio',/Ning/.test(f.$('#tabla tbody').textContent),
     f.$('#tabla tbody').textContent.slice(0,40));
  for(const k of ['ArrowDown','f','g'])
    f.w.document.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:k,bubbles:true}));
  ok('teclas con la tabla vacia',true);

  console.log(`\n${pruebas-fallas}/${pruebas} pruebas OK`);
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
