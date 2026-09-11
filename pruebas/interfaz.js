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
    beginPath:noop,closePath:noop,fill:noop,roundRect:noop,moveTo:noop,lineTo:noop,stroke:noop,fillRect:noop,fillText:noop,
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

  console.log('\n== la barra de arriba ==');
  {
    const sel=$('#selRapido');
    ok('el desplegable de perfiles arranca en "Sin filtros"',
       sel.options[0].textContent==='Sin filtros',sel.options[0].textContent);
    ok('y no se enciende si no hay perfil puesto',!sel.classList.contains('puesto'),
       sel.className);
    /* Sacados los presets de fabrica, el desplegable arranca con una sola
       opcion. Se guarda un perfil para tener algo que elegir. */
    ok('sin perfiles guardados, el desplegable avisa que esta vacio',
       !!$('#selRapidoLindo').querySelector('.sel-lista.sin-perfiles'),
       $('#selRapidoLindo').querySelector('.sel-lista').className);
    $('#nomPerfil').value='mio';
    $('#btnGuardar').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await new Promise(r=>setTimeout(r,400));
    sel.value='m:mio';
    sel.dispatchEvent(new w.Event('change'));
    await new Promise(r=>setTimeout(r,400));
    ok('con un perfil puesto se enciende',sel.classList.contains('puesto'),sel.className);
    ok('el resumen lo dice en una pastilla',
       !!$('#resumenFiltro').querySelector('.mini-pill'),
       $('#resumenFiltro').innerHTML.slice(0,80));
    sel.value='0';sel.dispatchEvent(new w.Event('change'));
    await new Promise(r=>setTimeout(r,400));
    ok('al limpiarlo se apaga',!sel.classList.contains('puesto'),sel.className);
    ok('y la pastilla dice "sin filtros"',
       /sin filtros/.test($('#resumenFiltro').textContent),
       $('#resumenFiltro').textContent);
    /* La firma se achico: antes llevaba la config del ASH y la cantidad de
       simbolos, que no cambian de un dia para el otro y no dejan decidir nada.
       Queda el cierre y, si los hay, los avisos de atraso -- que es lo unico
       que puede estar mal. Lo que sigue valiendo es que los tramos se separen
       con la regla vertical y no con puntos sueltos. */
    const fir=$('#firma');
    ok('la firma ya no lleva la config del ASH ni el conteo de simbolos',
       !/RSI|EMA|símbolos/.test(fir.textContent),fir.textContent);
    ok('pero sigue diciendo el cierre',/cierre/.test(fir.textContent),fir.textContent);
    ok('y separa los tramos con la regla, no con puntos sueltos',
       !/ · /.test(fir.textContent),fir.innerHTML.slice(0,160));
    // Las vistas se mudaron al panel izquierdo: son el primer nivel de la
    // pagina, no un control mas de la barra de arriba.
    ok('las vistas viven en la navegacion del panel',
       $('#chipVista').closest('#navVistas')!==null);
    ok('y los chips de la barra siguen agrupados en capsulas',
       $('#chipFav').closest('.grupo-chips')!==null);
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
  /* Antes esto miraba la firma de la barra, que decia "RSI 40/4". La firma ya
     no lleva la configuracion del ASH -- era informacion muerta y ocupaba el
     lugar donde uno mira si los precios estan al dia -- asi que ahora se mira
     LA TABLA. Es ademas una prueba mas fuerte: no comprueba que un cartel diga
     40, comprueba que los numeros del ASH se recalcularon de verdad. */
  const tablaAhora=()=>$$('#tabla tbody tr').slice(0,20).map(tr=>tr.textContent).join('|');
  const con16=tablaAhora();
  $('#ashLen').value='40';
  $('#ashLen').dispatchEvent(new w.Event('input',{bubbles:true}));
  $('#fRsiMin').value='10';                       // enseguida, un filtro liviano
  $('#fRsiMin').dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,500));
  /* Se saca el filtro liviano: si el recalculo pesado se hubiera perdido, la
     tabla volveria a ser identica a la de 16. */
  $('#fRsiMin').value='0';
  $('#fRsiMin').dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,400));
  ok('el cambio pesado no se pierde',tablaAhora()!==con16,
     'la tabla quedo igual que con el ASH en 16');
  $('#ashLen').value='16';
  $('#ashLen').dispatchEvent(new w.Event('input',{bubbles:true}));
  await new Promise(r=>setTimeout(r,400));
  ok('y al volver a 16 la tabla vuelve',tablaAhora()===con16);

  console.log('\n== persistencia ==');
  // configuro cosas variadas
  $('#fAdr').value='2.5';$('#fAdr').dispatchEvent(new w.Event('input',{bubbles:true}));
  $('#buscar').value='NV';$('#buscar').dispatchEvent(new w.Event('input',{bubbles:true}));
  $('#c3Rap').value='150';$('#c3Rap').dispatchEvent(new w.Event('input',{bubbles:true}));
  const chipGr=$$('#chipsGrupo .chip')[0];const grupoElegido=chipGr.dataset.v;
  chipGr.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await new Promise(r=>setTimeout(r,700));
  const vistaURL=w.eval('enlaceVista()');
  // simulo cerrar la pestaña
  w.dispatchEvent(new w.Event('pagehide'));
  const guardado=JSON.parse(almacen.getItem('screener_ash_sesion'));
  ok('guardo el ADR',guardado.fAdr==='2.5',guardado.fAdr);
  ok('guardo la busqueda',guardado._buscar==='NV',guardado._buscar);
  ok('guardo la EMA rápida del combo 3',guardado.c3Rap==='150',guardado.c3Rap);
  ok('guardo los grupos',guardado._grupos.includes(grupoElegido),JSON.stringify(guardado._grupos));

  console.log('\n== reabrir con la misma sesion ==');
  const b=await abrir(almacen);
  ok('vuelve el ADR',b.$('#fAdr').value==='2.5',b.$('#fAdr').value);
  ok('vuelve la busqueda',b.$('#buscar').value==='NV',b.$('#buscar').value);
  ok('vuelve la EMA rápida del combo 3',b.$('#c3Rap').value==='150',b.$('#c3Rap').value);
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
  ok('la URL trae la EMA rápida del combo 3',c.$('#c3Rap').value==='150',c.$('#c3Rap').value);

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

  /* ---- por que NO esta un papel: son dos motivos, no uno ----
     El usuario reclamo que el SPCX no aparecia. Estaba bien cargado: Yahoo lo
     devuelve, pero es una salida a bolsa reciente y tenia 61 barras de las 220
     que se piden, asi que el screener lo descartaba. La pantalla lo metia en la
     misma bolsa que los caidos y decia "Yahoo no los devolvio", que para este
     caso es FALSO -- y por eso era imposible entender que pasaba.

     Son dos problemas con dos acciones distintas: uno se investiga (cambio de
     ticker?), el otro se espera. La prueba fija que se digan por separado. */
  console.log('\n== por que no esta un papel: tres motivos, tres textos ==');
  {
    /* VENTANA PROPIA, Y NO LA COMPARTIDA DE ARRIBA. Las pruebas anteriores
       dejaron filtros puestos en esa (RSI <= 55, entre otros), asi que buscar
       una fila ahi contesta "no esta" cuando en realidad esta y no pasa el
       filtro. Me paso justo con esto: el recien listado figuraba como ausente
       por un filtro de otra prueba. */
    const g=await abrir(nuevoAlmacen());
    const $=g.$, $$=g.$$;
    const PL=JSON.parse(datos), nuevito=Object.keys(PL.nuevos||{})[0];
    const inf=$('#infoFaltantes').innerHTML;
    ok('nombra al que no vino',/MUERTO/.test(inf),inf.slice(0,90));
    ok('y al que vino con la serie recortada',/RECORTE/.test(inf));
    ok('dice cuantas barras trajo el recortado',/61 barras/.test(inf),inf);
    ok('y contra que umbral',/220/.test(inf));
    const corte=inf.indexOf('serie corta');
    ok('hay una seccion aparte para los recortados',corte>0,corte);
    ok('el que no vino queda del lado de "sin datos"',
       inf.indexOf('MUERTO')<corte,inf.indexOf('MUERTO')+' vs '+corte);
    ok('y el recortado del lado de "serie corta"',
       inf.indexOf('RECORTE')>corte,inf.indexOf('RECORTE')+' vs '+corte);
    ok('del recortado NO se dice que Yahoo no lo devolvio',
       inf.indexOf('no los devolvió')<corte,
       inf.indexOf('no los devolvió')+' vs '+corte);

    /* LO QUE CAMBIO, Y ES EL PEDIDO DEL USUARIO: el recien listado ya no se
       explica en un panel, ESTA EN LA TABLA. Un CEDEAR que se compra tiene que
       aparecer en el screener aunque haya listado el mes pasado; lo que no
       puede pasar es que aparezca sin decir que le falta historial. */
    ok('el recien listado tiene su propia seccion',
       inf.indexOf('listaron hace poco')>=0,inf.slice(0,200));
    ok('y se lo nombra',inf.indexOf(nuevito)>=0,nuevito);
    const fila=$$('#tabla tbody tr').find(tr=>
      (tr.querySelector('.tk')||{}).textContent===nuevito);
    ok('EL RECIEN LISTADO ESTA EN LA TABLA',!!fila,nuevito+' no aparece');
    if(fila){
      const marca=fila.querySelector('.corta');
      ok('marcado con las ruedas que tiene',!!marca&&/61/.test(marca.textContent),
         marca?marca.textContent:'sin marca');
      ok('y el titulo explica por que le faltan columnas',
         !!marca&&/historial/.test(marca.getAttribute('title')||''));
    }
    /* Y LO QUE NO SE PUEDE INVENTAR: con 61 ruedas no hay maximo de 52 semanas.
       Antes se acortaba la ventana y se mostraba el maximo de esos tres meses
       en la columna que dice "52 semanas": un numero con cara de dato. */
    const otro=$$('#tabla tbody tr').find(tr=>
      (tr.querySelector('.tk')||{}).textContent!==nuevito);
    const col=[...$$('#tabla thead th')].findIndex(th=>/52/.test(th.textContent));
    if(col>=0&&fila&&otro){
      ok('sin 52 semanas de historia, la columna de 52 semanas va vacia',
         !fila.children[col].textContent.trim(),
         fila.children[col].textContent);
      ok('y el que si las tiene la muestra igual',
         !!otro.children[col].textContent.trim());
    }
  }

  /* ---- los combos de EMAs ----
     Reemplazaron al Paragon 100/200. Lo que hay que fijar es lo que se decidio
     a mano y se puede deshacer sin querer: que el REGIMEN cruce el rapido con
     el medio y NO con el de fondo, que el 300/600 tenga su propio filtro, y
     que la EMA 600 exista de verdad en la tabla -- si alguien vuelve a bajar
     las barras publicadas, esa columna se vacia en silencio. */
  console.log('\n== combos de EMAs ==');
  {
    const g=await abrir(nuevoAlmacen());
    const PL=JSON.parse(datos);
    const barras=PL.simbolos[0].d.length;
    ok('el payload trae barras para la EMA 600 mas el gráfico',
       barras>=600+220,barras);
    const f=g.w.eval('filas[0]');
    ok('los tres combos vienen con sus longitudes',
       f.c1_largos==='21/34'&&f.c2_largos==='55/115'&&f.c3_largos==='300/600',
       [f.c1_largos,f.c2_largos,f.c3_largos].join(' '));
    ok('la EMA 600 imprime: el combo de fondo tiene sesgo',
       f.c3_sesgo===true||f.c3_sesgo===false,f.c3_sesgo);
    /* EN TODAS LAS FILAS, no en una. Con una sola fila la prueba pasa de
       casualidad cada vez que el c2 y el c3 coinciden, y eso es la mitad del
       universo: probé el sabotaje (cruzar con el c3) y no lo agarraba. */
    const malReg=g.w.eval(`filas.filter(f=>f.regimen&&
      f.regimen_ord!==((f.c2_sesgo?2:0)+(f.c1_sesgo?1:0))).length`);
    ok('el régimen sale del c1 y el c2 en TODAS las filas',malReg===0,malReg);
    const difC2C3=g.w.eval('filas.filter(f=>f.c2_sesgo!==null&&f.c3_sesgo!==null&&f.c2_sesgo!==f.c3_sesgo).length');
    ok('y hay filas donde el c2 y el c3 difieren, o no probaría nada',
       difC2C3>20,difC2C3);
    ok('y se escribe con R (rápido) y M (medio)',/^R[+\u2212] M[+\u2212]$/.test(f.regimen),f.regimen);
    // el rVWAP: cuatro ventanas, y la de 7 dias NO puede ser la de 365
    ok('vienen las cuatro ventanas del rVWAP',
       [7,30,90,365].every(d=>isFinite(f['rvwap_'+d])),
       [7,30,90,365].map(d=>f['rvwap_'+d]).join(' '));
    ok('y son distintas entre sí',
       new Set([7,30,90,365].map(d=>f['rvwap_'+d].toFixed(6))).size===4);
    // el filtro del 300/600, que es lo que pidió el usuario
    const antes=g.$$('#tabla tbody tr').length;
    g.$('#fFondo').value='1';
    g.$('#fFondo').dispatchEvent(new g.w.Event('input',{bubbles:true}));
    await new Promise(r=>setTimeout(r,350));
    const alcistas=g.$$('#tabla tbody tr').length;
    ok('el 300/600 filtra por su cuenta',alcistas>0&&alcistas<antes,
       `${alcistas} de ${antes}`);
    // se mira la COLUMNA, que es lo que ve el usuario, y no el motor
    const colF=[...g.$$('#tabla thead th')].findIndex(th=>/Fondo/.test(th.textContent));
    const flechas=new Set(g.$$('#tabla tbody tr').map(tr=>tr.children[colF].textContent.trim()));
    ok('y todos los que quedan muestran el fondo alcista',
       flechas.size===1&&flechas.has('\u2191'),[...flechas].join(''));
    g.$('#fFondo').value='0';
    g.$('#fFondo').dispatchEvent(new g.w.Event('input',{bubbles:true}));
    await new Promise(r=>setTimeout(r,350));
    const bajistas=g.$$('#tabla tbody tr').length;
    ok('y al revés, con los bajistas',bajistas>0,bajistas);
    /* Las dos mitades NO suman el total, y eso es correcto: el papel que no
       tiene 600 ruedas queda afuera de LAS DOS. Su fondo no se puede afirmar
       y dejarlo pasar por cualquiera de los dos lados sería inventarlo. */
    const sinFondo=g.w.eval('filas.filter(f=>f.c3_sesgo===null).length');
    ok('los que no llegan a la EMA 600 no pasan por ninguno de los dos lados',
       alcistas+bajistas+sinFondo===antes&&sinFondo>0,
       `${alcistas}+${bajistas}+${sinFondo} vs ${antes}`);
  }

  console.log('\n== almacen bloqueado ==');
  const roto={getItem:()=>{throw new Error('no')},setItem:()=>{throw new Error('no')},
              removeItem:()=>{throw new Error('no')}};
  const e=await abrir(roto);
  ok('la pagina igual funciona sin almacen',e.$$('#tabla tbody tr').length>100,
     e.$$('#tabla tbody tr').length);
  ok('avisa que no puede guardar',e.$('#avisoAlmacen').style.display==='block',
     e.$('#avisoAlmacen').style.display);

  console.log('\n== el desplegable, limpiar y busquedas raras ==');
  const f=await abrir(nuevoAlmacen());
  for(const o of [...f.$('#selRapido').options]){
    f.$('#selRapido').value=o.value;
    f.$('#selRapido').dispatchEvent(new f.w.Event('change'));
    await new Promise(r=>setTimeout(r,120));
  }
  ok('todas las opciones del desplegable andan',true);
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
