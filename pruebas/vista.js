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
const srv=http.createServer((q,r)=>{
  const f=path.join(S, q.url==='/'?'index.html':q.url.split('?')[0]);
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

 console.log('\n== las otras vistas tampoco explotan ==');
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
