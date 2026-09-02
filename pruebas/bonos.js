/* ===========================================================================
   LA VISTA DE BONOS
   ===========================================================================
   Lo que importa verificar acá no es que se vea lindo -- eso no se puede desde
   jsdom -- sino lo que se rompe solo:

     1. que el interruptor de vistas no pueda quedar en dos posiciones a la vez
        (es el mismo error que ya hubo con los chips de Panorama y favoritos);
     2. que la pantalla MUESTRE lo que el payload trae. Esta prueba nacio
        justamente porque bonos.py ya calculaba TIR, TNA, paridad y duration y
        la vista seguia mostrando solo precios: nadie se entero hasta que el
        usuario lo vio;
     3. que diga en la cara QUE bonos no tienen TIR todavia y cuales son
        provisorios, porque una tabla incompleta que no lo avisa se lee como
        completa;
     4. que la curva se dibuje con un punto por bono con rendimiento, y que
        ninguno caiga fuera del lienzo;
     5. que tocar una fila abra su cronograma, que es la pregunta concreta del
        que arma una cartera: cuando cobro y cuanto;
     6. que si bonos.json no existe todavia, la pantalla explique qué pasó en
        vez de quedarse en blanco o tirar un error.

   bonos_fixtura.json lo arma bonos_fixtura.py pasando un panel sintetico por
   el armar() de bonos.py de verdad, asi la fixtura no se queda vieja cuando el
   payload cambia. Los PRECIOS son de prueba; los CRONOGRAMAS son los reales.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const S=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(S,'index.html'),'utf8');
const datos=fs.readFileSync(path.join(S,'datos.json'),'utf8');
const bonos=fs.readFileSync(path.join(__dirname,'bonos_fixtura.json'),'utf8');
let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'  -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));
function abrir(hayBonos){return new Promise(res=>{
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
    if(s.indexOf('bonos.json')>=0){
      if(!hayBonos)return{ok:false,status:404};
      return{ok:true,json:async()=>JSON.parse(bonos)};}
    if(s.indexOf('datos.json')>=0)return{ok:true,body:null,text:async()=>datos};
    throw new TypeError('Failed to fetch');};}});
 const t=setInterval(()=>{if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
   clearInterval(t);res(dom.window);}},20);});}

(async()=>{
console.log('== el interruptor de tres posiciones ==');
{const w=await abrir(true), d=w.document;
 const clic=s=>d.querySelector(s).dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 const prendidos=()=>['#chipTabla','#chipVista','#chipBonos']
   .filter(s=>d.querySelector(s).classList.contains('on'));
 ok('arranca en Tabla',prendidos().join()==='#chipTabla',prendidos().join());
 clic('#chipBonos');await esperar(300);
 ok('al ir a Bonos queda SOLO Bonos prendido',prendidos().join()==='#chipBonos',prendidos().join());
 ok('y el body lo refleja',d.body.classList.contains('bonos')&&!d.body.classList.contains('panorama'));
 ok('la tabla del screener se esconde',
    w.getComputedStyle(d.querySelector('.tabla-wrap')).display==='none');
 ok('las tres vistas viven en la navegacion del panel',
    ['#chipTabla','#chipVista','#chipBonos'].every(s=>d.querySelector(s).closest('#navVistas')));
 clic('#chipVista');await esperar(300);
 ok('al ir a Panorama queda SOLO Panorama',prendidos().join()==='#chipVista',prendidos().join());
 ok('y sale de bonos',!d.body.classList.contains('bonos'));
 clic('#chipTabla');await esperar(200);
 ok('y se vuelve a la tabla',prendidos().join()==='#chipTabla'&&!d.body.classList.contains('bonos'));

 console.log('\n== lo que muestra ==');
 clic('#chipBonos');await esperar(400);
 const txt=d.querySelector('#bonosCuerpo').textContent;
 ok('separa por ley',/Ley Argentina/.test(txt)&&/Ley Nueva York/.test(txt));
 ok('muestra los tickers',/AL30/.test(txt)&&/GD30/.test(txt));
 ok('trae el tipo de cambio por bono',/Tipo de cambio por bono/.test(txt));
 ok('y el canje de leyes',/Canje de leyes/.test(txt));
 ok('con la mediana calculada',/1,0413/.test(txt)||/1\.0413/.test(txt),
    (txt.match(/mediana es[^,]{0,20}/)||[''])[0]);
 const filas=d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr.bo-fila');
 ok('dibuja una fila por bono',filas.length===11,filas.length);

 console.log('\n== los rendimientos llegan a la pantalla ==');
 /* LA prueba de esta tanda: bonos.py calculaba TIR, TNA, paridad y duration y
    la vista mostraba solo precios. Se compara contra el payload y no contra
    numeros escritos a mano, asi no hay dos verdades que mantener. */
 const pay=JSON.parse(bonos);
 const conTir=pay.bonos.filter(b=>b.tir!=null);
 ok('el payload de prueba trae bonos con TIR',conTir.length>=4,conTir.length);
 ok('la cabecera tiene TIR, TNA, paridad, duration y DV01',
    ['TIR','TNA','paridad','durat','DV01'].every(h=>txt.indexOf(h)>=0));
 /* La pantalla escribe en es-AR: la coma es el decimal. Los porcentajes salen
    con toFixed (punto) y los numeros sueltos con toLocaleString (coma), asi
    que hay que buscar cada uno como se escribe de verdad. */
 const ar=(v,dec)=>v.toFixed(dec).replace('.',',');
 const al30=conTir.find(b=>b.t==='AL30');
 const filaAl30=[...filas].find(tr=>tr.dataset.bono==='AL30').textContent;
 ok('la fila del AL30 muestra su TIR',
    filaAl30.indexOf((al30.tir*100).toFixed(2))>=0,filaAl30);
 ok('y su duration',filaAl30.indexOf(ar(al30.duration,2))>=0,filaAl30);
 ok('y su paridad',filaAl30.indexOf((al30.paridad*100).toFixed(1))>=0,filaAl30);

 console.log('\n== la curva de rendimientos ==');
 const pts=d.querySelectorAll('#bonosCuerpo .cv-pt');
 ok('hay un punto por bono con rendimiento',pts.length===conTir.length,
    pts.length+' vs '+conTir.length);
 ok('cada punto dice de quien es',[...pts].every(g=>g.dataset.t));
 /* Mismo error que ya se cazo en el grafico del screener: nada puede
    dibujarse afuera del lienzo. */
 const svg=d.querySelector('#bonosCuerpo svg.cv');
 const vb=svg.getAttribute('viewBox').split(' ').map(Number);
 const fuera=[...svg.querySelectorAll('circle')].filter(c=>{
   const x=+c.getAttribute('cx'),y=+c.getAttribute('cy');
   return !(x>=0&&x<=vb[2]&&y>=0&&y<=vb[3]);});
 ok('ningun punto cae fuera del lienzo',fuera.length===0,fuera.length);

 console.log('\n== abrir un bono muestra su cronograma ==');
 ok('arranca cerrado',!d.querySelector('#bonosCuerpo .bo-det'));
 [...filas].find(tr=>tr.dataset.bono==='AL30')
   .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(120);
 const det=d.querySelector('#bonosCuerpo .bo-det');
 ok('se abre el detalle',!!det);
 const pagos=d.querySelectorAll('#bonosCuerpo .bo-flujo tbody tr');
 ok('con un renglon por pago que falta',pagos.length===al30.flujo.length,
    pagos.length+' vs '+al30.flujo.length);
 ok('el primer pago es el que dice el payload',
    pagos[0].textContent.indexOf(ar(al30.flujo[0].total,3))>=0,pagos[0].textContent);
 ok('y se ve cuanto queda vivo despues',det.textContent.indexOf('queda vivo')>=0);
 ok('se abre UNO SOLO a la vez',d.querySelectorAll('#bonosCuerpo .bo-det').length===1);
 d.querySelector('#bonosCuerpo .bo-fila[data-bono="AL30"]')
   .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(120);
 ok('y tocarla de nuevo lo cierra',!d.querySelector('#bonosCuerpo .bo-det'));

 console.log('\n== dice lo que le falta ==');
 const sinTir=pay.bonos.filter(b=>b.tir==null).map(b=>b.t);
 const aviso=d.querySelector('#bonosCuerpo .bo-falta');
 if(sinTir.length){
   ok('avisa que hay bonos sin TIR',!!aviso&&/sin TIR/i.test(aviso.textContent));
   ok('y los nombra a todos',!!aviso&&sinTir.every(t=>aviso.textContent.indexOf(t)>=0),
      sinTir.join(' '));
 }else ok('con los once cargados no queda nada que avisar',
          !aviso||!/sin TIR/i.test(aviso.textContent));

 console.log('\n== obligaciones negociables ==');
 /* La otra mitad de la seccion Argentina. Se agrupa por emisor a proposito:
    una tabla plana de seiscientas filas no se lee, y el que arma una cartera
    decide primero a quien le presta. */
 const pest=d.querySelectorAll('#bonosPestanas button');
 ok('hay dos pestañas',pest.length===2,pest.length);
 ok('arranca en Soberanos',pest[0].classList.contains('on'));
 pest[1].dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(150);
 const tOns=d.querySelector('#bonosCuerpo').textContent;
 const emis=d.querySelectorAll('#bonosCuerpo .bo-fila[data-emisor]');
 ok('lista un renglon por emisor',emis.length===pay.emisores.length,
    emis.length+' vs '+pay.emisores.length);
 ok('ordenados por TIR mediana, el que mas paga arriba',
    emis[0].dataset.emisor===pay.emisores[0].emisor,emis[0].dataset.emisor);
 ok('dice de quien es la TIR y la duration',/bonistas/i.test(tOns));
 ok('y avisa que no hay calificacion de riesgo',/calificaci.n de riesgo/i.test(tOns));

 console.log('\n== abrir un emisor muestra sus papeles ==');
 emis[0].dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(120);
 const papeles=d.querySelectorAll('#bonosCuerpo .bo-ons tbody tr');
 ok('con un renglon por especie',papeles.length===pay.emisores[0].papeles,
    papeles.length+' vs '+pay.emisores[0].papeles);
 ok('se abre UNO SOLO a la vez',d.querySelectorAll('#bonosCuerpo .bo-det').length===1);
 /* Una ON step-up no tiene UNA tasa de cupon: tiene que salir el punto, no un
    numero elegido de la escalera. isFinite(null) es true en JS y con esa
    guarda la vista entera reventaba. */
 const sinCupon=pay.ons.filter(o=>o.emisor===pay.emisores[0].emisor&&o.cupon==null);
 if(sinCupon.length)ok('las step-up muestran punto y no un cupon inventado',
    [...papeles].some(tr=>tr.textContent.indexOf('·')>=0));

 console.log('\n== volver a Soberanos ==');
 d.querySelectorAll('#bonosPestanas button')[0]
   .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(150);
 ok('vuelve la curva',!!d.querySelector('#bonosCuerpo svg.cv'));
 ok('y la tabla por ley',
    /Ley Nueva York/.test(d.querySelector('#bonosCuerpo').textContent));

 console.log('\n== la vista se recuerda ==');
 const alm2=w.localStorage;
 ok('queda guardada como "b"',alm2.getItem('screener_ash_vista')==='b',
    alm2.getItem('screener_ash_vista'));

 console.log('\n== elegir un filtro te saca de bonos ==');
 const sel=d.querySelector('#selRapido');
 sel.value='p:Tendencia limpia';sel.dispatchEvent(new w.Event('change',{bubbles:true}));
 await esperar(700);
 ok('vuelve a la tabla sola',!d.body.classList.contains('bonos')&&
    d.querySelector('#chipTabla').classList.contains('on'));
}

console.log('\n== si todavia no hay bonos publicados ==');
{const w=await abrir(false), d=w.document;
 d.querySelector('#chipBonos').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(400);
 const txt=d.querySelector('#bonosCuerpo').textContent;
 ok('lo explica en vez de quedarse en blanco',/Todavía no hay datos/.test(txt),txt.slice(0,70));
 ok('y no dice "error"',!/error/i.test(txt));
}
console.log(fallas?'\nFALLAS: '+fallas:'\nBONOS OK');
process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
