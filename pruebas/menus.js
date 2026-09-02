/* ===========================================================================
   LA BARRA: FILTROS, INDICADORES Y EL ENGRANAJE
   ===========================================================================
   Los filtros y la configuracion de indicadores se fueron de la columna
   izquierda a dos desplegables de la barra, y lo que es de la PAGINA -- como se
   ve, de donde bajan los datos, el respaldo -- se fue abajo de todo, detras de
   un engranaje.

   Mover controles de lugar en el HTML parece inofensivo y no lo es. En este
   mismo cambio, TODOS los controles quedaron desconectados en silencio: el
   cableado decia `$$('aside input, aside select')`, o sea que dependia de
   DONDE estaba cada control, y al sacarlos del aside dejaron de guardar la
   sesion y de disparar el recalculo. La pagina seguia cargando igual, la tabla
   se veia bien, y once pruebas de interfaz.js fueron lo unico que lo dijo.

   Por eso la primera prueba de este archivo no mira la pantalla: mira que
   todos los controles de estado sigan colgando de un .ctrl-host. Es la que
   avisa si alguien los vuelve a mudar.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(S,'index.html'),'utf8');
const datos=fs.readFileSync(path.join(S,'datos.json'),'utf8');
let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));

function abrir(){return new Promise(res=>{
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
   w.fetch=async u=>{const s=String(u);
    if(s.indexOf('api/')===0)throw new Error('sin servidor');
    if(s.indexOf('bonos.json')>=0)return{ok:false,status:404};
    if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};
    throw new TypeError('Failed to fetch');};}});
 const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
   clearInterval(t);res(dom.window);}},20);});}

(async()=>{
const w=await abrir(), d=w.document;
const $=s=>d.querySelector(s), $$=s=>[...d.querySelectorAll(s)];
const clic=el=>el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));

console.log('== ningun control quedo huerfano al mudarse ==');
/* Uno de cada seccion que se movio, mas uno de los que se quedaron. Si alguno
   deja de colgar de un .ctrl-host, no se guarda ni recalcula y nadie se entera
   mirando la pantalla. */
const CONTROLES=['ashModo','ashMa','ashLen','ashSmooth','almaOff','almaSig',
  'parRap','parLen','parK','parFresco','adrLen','rsiLen','atrLen','adxLen',
  'fAdr','fRsiMin','srvPeriodo','yaAuto','chipsLetra'];
const huerfanos=CONTROLES.filter(id=>{
  const el=$('#'+id);return el && !el.closest('.ctrl-host');});
ok('todos los controles cuelgan de un .ctrl-host',huerfanos.length===0,huerfanos.join(' '));
const faltantes=CONTROLES.filter(id=>!$('#'+id));
ok('y ninguno desaparecio del HTML',faltantes.length===0,faltantes.join(' '));
/* La prueba de verdad: que un control mudado siga moviendo la tabla. */
$('#fRsiMin').value='95';
$('#fRsiMin').dispatchEvent(new w.Event('input',{bubbles:true}));
await esperar(400);
const conFiltro=$$('#tabla tbody tr').length;
$('#fRsiMin').value='0';
$('#fRsiMin').dispatchEvent(new w.Event('input',{bubbles:true}));
await esperar(400);
const sinFiltro=$$('#tabla tbody tr').length;
ok('un filtro mudado sigue filtrando de verdad',conFiltro<sinFiltro,
   conFiltro+' vs '+sinFiltro);

console.log('\n== los tres menus de la barra ==');
ok('el de sectores ya no esta suelto en la barra',!$('#btnInd'));
ok('estan filtros, indicadores y columnas',
   !!$('#btnFiltros')&&!!$('#btnIndic')&&!!$('#btnCols'));
const abiertos=()=>['#panelFiltros','#panelIndic','#panelCols']
  .filter(s=>$(s).classList.contains('abierto'));
ok('arrancan todos cerrados',abiertos().length===0,abiertos().join());
clic($('#btnFiltros'));
ok('se abre el de filtros',abiertos().join()==='#panelFiltros',abiertos().join());
/* Dos abiertos a la vez se pisan. Ya paso con industrias contra columnas. */
clic($('#btnIndic'));
ok('abrir otro cierra el anterior',abiertos().join()==='#panelIndic',abiertos().join());
clic($('#btnCols'));
ok('y el tercero tambien',abiertos().join()==='#panelCols',abiertos().join());
d.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
ok('tocar afuera los cierra',abiertos().length===0,abiertos().join());

console.log('\n== el ranking de sectores se mudo adentro de filtros ==');
ok('la tabla de sectores vive en el panel de filtros',
   !!$('#tablaInd')&&!!$('#tablaInd').closest('#panelFiltros'));
clic($('#btnFiltros'));
await esperar(120);
const filasInd=$$('#tablaInd tr[data-ind]');
ok('y se llena al abrir el panel',filasInd.length>0,filasInd.length);
const antes=$$('#tabla tbody tr').length;
clic(filasInd[0]);
await esperar(300);
ok('elegir un sector sigue filtrando la tabla',$$('#tabla tbody tr').length<antes,
   $$('#tabla tbody tr').length+' vs '+antes);

console.log('\n== la barra avisa que hay filtros puestos ==');
/* Con los filtros escondidos detras de un icono, el numero es lo unico que
   avisa que la tabla NO esta mostrando todo. */
ok('el icono se enciende',$('#btnFiltros').classList.contains('puesto'));
ok('y dice cuantos hay',$('#cuentaFiltrosBarra').textContent!=='',
   $('#cuentaFiltrosBarra').textContent);
/* "Limpiar todo" tiene que dejar la barra sin marca: el sector elegido cuenta
   como filtro igual que un RSI, y si el boton limpia uno y no el otro la barra
   miente. */
clic($('#filtrosLimpiar'));
await esperar(400);
ok('limpiar todo apaga el icono',!$('#btnFiltros').classList.contains('puesto'));
ok('y borra el numero',$('#cuentaFiltrosBarra').textContent==='',
   $('#cuentaFiltrosBarra').textContent);
ok('y suelta el sector elegido',$$('#tablaInd tr.sel').length===0);

console.log('\n== los filtros son de la renta variable, y solo de ahi ==');
d.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
ok('en la tabla se ven',!$('#menusTabla').hidden);
clic($('#chipVista'));await esperar(250);
ok('en Panorama no hay nada que filtrar: se esconden',$('#menusTabla').hidden);
clic($('#chipBonos'));await esperar(350);
ok('en la curva de bonos tampoco',$('#menusTabla').hidden);
clic($('#chipTabla'));await esperar(250);
ok('y vuelven al volver a la tabla',!$('#menusTabla').hidden);
/* Cambiar de vista con un menu abierto dejaba el menu flotando sobre una
   pantalla que ya no era la suya. */
clic($('#btnFiltros'));
clic($('#chipVista'));await esperar(250);
ok('cambiar de vista cierra el menu que estaba abierto',abiertos().length===0,
   abiertos().join());
clic($('#chipTabla'));await esperar(250);

console.log('\n== el engranaje ==');
ok('esta al pie de la navegacion',!!$('#chipAjustes')&&
   !!$('#chipAjustes').closest('#navVistas'));
ok('arranca cerrado',$('#secAjustes').hidden);
clic($('#chipAjustes'));
ok('se abre',!$('#secAjustes').hidden&&$('#chipAjustes').classList.contains('on'));
const texto=$('#secAjustes').textContent;
ok('adentro esta como se ve la pagina',/Tama.o de letra/.test(texto));
ok('el alto de las filas',/Alto de las filas/.test(texto));
ok('de donde salen los datos',/Historial a descargar|Traer precios/.test(texto));
ok('y el respaldo',/[Rr]espaldo/.test(texto));
/* Es un panel de la PAGINA: abrirlo no cambia de pantalla. */
ok('abrirlo NO te saca de la tabla',$('#chipTabla').classList.contains('on')&&
   !d.body.classList.contains('panorama')&&!d.body.classList.contains('bonos'));
clic($('#chipAjustes'));
ok('y se vuelve a cerrar',$('#secAjustes').hidden);
clic($('#chipAjustes'));
clic($('#chipVista'));await esperar(250);
ok('cambiar de vista lo suelta',$('#secAjustes').hidden);

console.log(fallas?'\nFALLAS: '+fallas:'\nMENUS OK');
process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
