/* ===========================================================================
   LO QUE JSDOM NO PUEDE VER
   ===========================================================================
   Durante mucho tiempo este proyecto asumio que no habia navegador y todo lo
   visual quedaba sin verificar. SI LO HAY: /opt/pw-browsers trae Chromium y
   Playwright lo maneja. Esta prueba existe porque dos bugs pasaron por delante
   de 811 pruebas de jsdom sin que ninguna los viera, y los dos eran del mismo
   tipo -- el DOM estaba perfecto y la pantalla no:

     1. La linea de tendencia se dibujaba con `stroke:none`. El <path> estaba
        ahi, con su `d` bien calculada, y en pantalla NO HABIA NINGUNA LINEA.
        Las reglas de color apuntaban a .cv-linea y la clase habia pasado a
        ser .cv-ajuste. jsdom no aplica CSS, asi que para el estaba todo bien.

     2. El grafico tenia un viewBox de 1000 y se pintaba en una columna de
        636: TODO salia al 64% y los rotulos de 13px quedaban en 8,3px. El
        usuario reporto "faltan las curvas" -- estaban, pero se leian como una
        mancha.

   Lo que se verifica es MEDIBLE, no estetico: que lo que tiene que tener color
   lo tenga, que el texto llegue a la pantalla con un tamaño legible, y que el
   grafico ocupe un lugar comparable a su tabla. Nada de comparar imagenes.

   Se saltea sola si no estan Playwright o Chromium, para que la bateria siga
   corriendo en cualquier maquina.
   ======================================================================== */
const fs=require('fs'), path=require('path'), http=require('http');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const CHROME=['/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
              '/opt/pw-browsers/chromium/chrome-linux/chrome']
             .find(p=>{try{fs.accessSync(p);return true}catch{return false}});
let chromium;
try{ chromium=require('playwright').chromium; }catch{ chromium=null; }
if(!chromium||!CHROME){
  console.log('  (sin Playwright o sin Chromium: me salteo la prueba visual)');
  console.log('VISTA SALTEADA'); process.exit(0);
}

let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''));}};

/* Un servidor de una linea: el sitio se abre por http y no por file://, que es
   como lo ve el usuario. Con file:// el fetch de datos.json falla por origen
   opaco y la pagina no llega a cargar. */
const TIPOS={'.html':'text/html','.json':'application/json'};
/* `fixtura.py` arma tmp/sitio con la pagina y los precios, pero el payload de
   bonos vive aparte -- las pruebas de jsdom lo inyectan por fetch. Aca se
   sirven archivos de verdad, asi que hay que mapearlo o la vista de bonos
   queda en "todavia no hay datos" y no se dibuja ninguna curva. */
const srv=http.createServer((q,r)=>{
  const pedido=q.url==='/'?'index.html':q.url.split('?')[0];
  const f=/bonos\.json$/.test(pedido)
    ? path.join(__dirname,'bonos_fixtura.json')
    : path.join(S, pedido);
  fs.readFile(f,(e,d)=>{ if(e){r.writeHead(404);r.end();return;}
    r.writeHead(200,{'Content-Type':TIPOS[path.extname(f)]||'text/plain'});r.end(d);});
});

(async()=>{
 await new Promise(r=>srv.listen(0,'127.0.0.1',r));
 const url='http://127.0.0.1:'+srv.address().port+'/index.html';
 const b=await chromium.launch({executablePath:CHROME,
   args:['--no-sandbox','--disable-dev-shm-usage']});
 const pg=await b.newPage({viewport:{width:1900,height:1100}});
 const rotos=[];
 pg.on('pageerror',e=>rotos.push(e.message));
 await pg.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
 await pg.waitForSelector('#tabla tbody tr',{timeout:60000});

 console.log('== la pagina carga en un navegador de verdad ==');
 ok('sin excepciones al arrancar', rotos.length===0, rotos.join(' | '));
 ok('la tabla tiene filas', (await pg.$$('#tabla tbody tr')).length>0);

 await pg.click('#chipBonos'); await pg.waitForTimeout(600);
 for(const x of await pg.$$('.bo-pest button')){
   if(/Pesos/i.test(await x.textContent())){await x.click();break;} }
 await pg.waitForTimeout(900);

 console.log('\n== la curva se VE, no solo esta en el DOM ==');
 const m=await pg.evaluate(()=>{
   const svg=document.querySelector('#bonosCuerpo svg.cv');
   if(!svg)return null;
   const vb=svg.getAttribute('viewBox').split(' ').map(Number);
   const r=svg.getBoundingClientRect();
   const esc=r.width/vb[2];
   const aj=svg.querySelector('.cv-ajuste');
   const rot=svg.querySelector('.cv-pt text');
   const eje=svg.querySelector('.cv-eje');
   const par=svg.closest('.bo-par');
   const tab=par&&par.querySelector('.bo-par-t table');
   const px=e=>e?parseFloat(getComputedStyle(e).fontSize)*esc:0;
   return {ancho:r.width, alto:r.height, escala:esc,
     ajuste: aj?getComputedStyle(aj).stroke:'no hay',
     rotuloPx:px(rot), ejePx:px(eje),
     altoTabla: tab?tab.getBoundingClientRect().height:0,
     cols:getComputedStyle(par).gridTemplateColumns};
 });
 ok('hay una curva dibujada', !!m);
 if(m){
   /* Lo que se pinta tiene que tener tamaño. Un svg de 0 de ancho o de alto
      esta en el DOM y no se ve, que es exactamente el sintoma reportado. */
   ok('con ancho y alto reales', m.ancho>200&&m.alto>150,
      Math.round(m.ancho)+'x'+Math.round(m.alto));
   /* EL BUG 1: la tendencia sin color. `stroke:none` es invisible. */
   ok('la tendencia tiene color, no stroke:none',
      m.ajuste!=='none'&&m.ajuste!=='no hay', m.ajuste);
   /* EL BUG 2: el texto achicado por la escala del viewBox. Abajo de 11px en
      pantalla un ticker no se lee, por mas que el <text> este ahi. */
   ok('los tickers llegan a la pantalla legibles (>=11px)',
      m.rotuloPx>=11, m.rotuloPx.toFixed(1)+'px');
   ok('y los numeros de los ejes tambien',
      m.ejePx>=11, m.ejePx.toFixed(1)+'px');
   /* El grafico al lado de su tabla y de un alto comparable: una curva de
      190px al lado de una tabla de 330 se lee como un hueco con motitas. */
   ok('esta al lado de la tabla, en dos columnas',
      /px .+px/.test(m.cols), m.cols);
   ok('y mide algo parecido a ella',
      m.altoTabla===0||m.alto>=m.altoTabla*0.7,
      Math.round(m.alto)+' vs tabla '+Math.round(m.altoTabla));
 }

 /* La tira de tipos de cambio: cinco cajas con NUMEROS, no vacias. Nacio
    rota y en el DOM se veia perfecta -- las cajas se filtraban con hay(), que
    pide un numero, y les llegaba el valor YA FORMATEADO ("1.529,99"), asi que
    isFinite daba false y las cinco se caian en silencio. */
 console.log('\n== la tira de tipos de cambio ==');
 const tc=await pg.evaluate(()=>[...document.querySelectorAll('.tc-caja')]
   .map(c=>({rot:c.querySelector('span').textContent.trim(),
             val:c.querySelector('b').textContent.trim()})));
 ok('estan las cinco cajas', tc.length===5, tc.length);
 ok('y ninguna vacia', tc.every(c=>c.val.length>0), JSON.stringify(tc));
 ok('con oficial, MEP, cable, brecha y canje',
    ['oficial','MEP','cable','brecha','canje']
      .every(r=>tc.some(c=>c.rot.toLowerCase()===r.toLowerCase())),
    tc.map(c=>c.rot).join(' '));
 /* Y esta arriba de las pestañas, porque vale para las cuatro. */
 ok('va antes de las pestañas',
    await pg.evaluate(()=>{const t=document.querySelector('.bo-tc'),
      p=document.querySelector('.bo-pest');
      return !!(t&&p)&&(t.compareDocumentPosition(p)&Node.DOCUMENT_POSITION_FOLLOWING)>0;}));

 /* LOS CONTROLES DE LA TABLA SE VAN CON ELLA. `hidden` lo pone el JS, pero
    quien decide si algo se ve es el CSS: `[hidden]{display:none}` viene de la
    hoja del navegador y PIERDE contra cualquier regla del autor, y aca habia
    un `.tf{display:flex}`. Resultado: el codigo decia que escondia, no
    escondia, y en la seccion de bonos seguian a la vista los filtros, los
    indicadores, las columnas y hasta el desplegable de filtros guardados
    diciendo "SOBRE W, 75 RSI, 60 RS, SIN DAILY" -- que ademas sugiere que esa
    vista esta filtrada por eso, y no lo esta.

    jsdom no puede ver esto: para el, hidden=true es hidden=true. Hay que
    preguntarle al navegador si el elemento OCUPA LUGAR. */
 console.log('\n== los controles de la tabla no aparecen en otras vistas ==');
 const seVe=()=>pg.evaluate(()=>['#menusTabla','#interTabla','#selRapidoLindo']
   .filter(s=>{const e=document.querySelector(s); if(!e)return false;
     const r=e.getBoundingClientRect(); return r.width>0&&r.height>0;}));
 ok('en bonos no se ve ninguno', (await seVe()).length===0, (await seVe()).join(' '));
 await pg.click('#chipVista'); await pg.waitForTimeout(600);
 ok('en panorama tampoco', (await seVe()).length===0, (await seVe()).join(' '));
 await pg.click('#chipTabla'); await pg.waitForTimeout(600);
 ok('y en la tabla vuelven los tres', (await seVe()).length===3, (await seVe()).join(' '));
 await pg.click('#chipBonos'); await pg.waitForTimeout(600);

 /* Las dos sinteticas viven en Futuros, que es donde se mira el carry. Se
    buscan por su CLASE y no por el titulo de la tarjeta: la prueba anterior
    buscaba /sintética/ en el titulo y se cayo sola en cuanto los titulos
    pasaron a decir que hace cada una. */
 console.log('\n== las dos sinteticas ==');
 for(const x of await pg.$$('.bo-pest button')){
   if(/Futuros/i.test(await x.textContent())){await x.click();break;} }
 await pg.waitForTimeout(800);
 const leer=cl=>pg.evaluate(c=>{
   const t=document.querySelector('#bonosCuerpo .'+c);
   if(!t)return null;
   const r=t.getBoundingClientRect();
   return {filas:t.querySelectorAll('tbody tr').length,
           cols:[...t.querySelectorAll('thead th')].map(h=>h.textContent.trim()),
           vacias:[...t.querySelectorAll('tbody td')].filter(d=>!d.textContent.trim()).length,
           ancho:r.width, alto:r.height};
 },cl);
 const sint=await leer('t-sinteticos');
 ok('la sintetica de tasa fija esta en Futuros', !!sint);
 if(sint){
   ok('con filas', sint.filas>0, sint.filas);
   ok('y ocupa lugar de verdad', sint.ancho>200&&sint.alto>40,
      Math.round(sint.ancho)+'x'+Math.round(sint.alto));
   /* EL DOLAR DE CADA PATA, que es lo que pidio el usuario: sin los dos
      numeros a la vista la tasa sale de la nada y no hay como auditarla. */
   ok('muestra el dolar de entrada y el de salida',
      sint.cols.some(c=>/entrada/i.test(c))&&sint.cols.some(c=>/salida/i.test(c)),
      sint.cols.join(' '));
   ok('y las columnas que importan',
      ['letra','futuro','descalce','efectiva','TNA','TEA']
        .every(c=>sint.cols.some(x=>x.toLowerCase()===c.toLowerCase())),
      sint.cols.join(' '));
   ok('sin celdas vacias', sint.vacias===0, sint.vacias);
 }
 const sdl=await leer('t-sinteticos-dl');
 ok('y la de dolar linked contra futuro tambien', !!sdl);
 if(sdl){
   ok('con filas', sdl.filas>0, sdl.filas);
   ok('y ocupa lugar', sdl.ancho>200&&sdl.alto>40,
      Math.round(sdl.ancho)+'x'+Math.round(sdl.alto));
   ok('con el dolar que se toma el bono',
      sdl.cols.some(c=>/del bono/i.test(c)), sdl.cols.join(' '));
   ok('sin celdas vacias', sdl.vacias===0, sdl.vacias);
 }
 /* Las dos tablas son distintas y estan las dos: contarlas juntas fue el bug
    que dio "8 renglones sobre 4" cuando se agrego la primera. */
 ok('las tres tablas de Futuros son tres tablas distintas',
    (await pg.$$('#bonosCuerpo .t-futuros')).length===1&&
    (await pg.$$('#bonosCuerpo .t-sinteticos')).length===1&&
    (await pg.$$('#bonosCuerpo .t-sinteticos-dl')).length===1);

 /* SIN FILTROS PREDETERMINADOS el desplegable queda con una sola opcion, y un
    desplegable de un solo item se lee como roto. El cartel que lo explica es un
    ::after de CSS, o sea que jsdom no puede verlo NUNCA: no aplica hojas de
    estilo y el contenido generado no existe en su DOM. Ahi la prueba de jsdom
    solo puede mirar la clase; el texto hay que preguntarselo al navegador. */
 console.log('\n== el desplegable vacio lo dice ==');
 await pg.click('#chipTabla'); await pg.waitForTimeout(600);
 const cartel=await pg.evaluate(()=>{
   const l=document.querySelector('#selRapidoLindo .sel-lista');
   if(!l)return null;
   const cs=getComputedStyle(l,'::after');
   return {clase:l.className, texto:cs.content||'', display:cs.display,
           seps:l.querySelectorAll('.sel-sep').length,
           ops:l.querySelectorAll('.sel-op').length};});
 ok('la lista se marca como vacia', !!cartel&&/sin-perfiles/.test(cartel.clase),
    cartel&&cartel.clase);
 ok('y el navegador pinta el cartel',
    !!cartel&&/guardaste/i.test(cartel.texto)&&cartel.display!=='none',
    cartel&&(cartel.texto.slice(0,50)+' · '+cartel.display));
 /* La raya separa "Sin filtros" de lo que sigue. Si no sigue nada, no va. */
 ok('sin nada abajo, la raya no queda colgando',
    !!cartel&&cartel.seps===0&&cartel.ops===1,
    cartel&&('seps '+cartel.seps+' · ops '+cartel.ops));

 console.log('\n== las otras vistas tampoco explotan ==');
 await pg.click('#chipBonos'); await pg.waitForTimeout(600);
 for(const [n,sel] of [['Soberanos','.cv-pt'],['Futuros','.fu-pt'],
                       ['Corporativos','.bo-tabla']]){
   for(const x of await pg.$$('.bo-pest button')){
     if(new RegExp(n,'i').test(await x.textContent())){await x.click();break;} }
   await pg.waitForTimeout(700);
   ok(n.toLowerCase()+': dibuja algo',
      (await pg.$$('#bonosCuerpo '+sel)).length>0);
 }
 ok('y ninguna tiro una excepcion', rotos.length===0, rotos.join(' | '));

 await b.close(); srv.close();
 console.log(fallas?'\nFALLAS: '+fallas:'\nVISTA OK');
 process.exit(fallas?1:0);
})().catch(e=>{console.log('EXPLOTO:',e.message);process.exit(1);});
