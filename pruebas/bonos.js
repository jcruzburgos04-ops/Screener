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

 console.log('\n== las cuatro pestañas ==');
 const pest=()=>[...d.querySelectorAll('#bonosPestanas button')];
 ok('hay cuatro',pest().length===4,pest().length);
 ok('arranca en Soberanos',pest()[0].classList.contains('on'));
 const irA=async k=>{pest().find(b=>b.dataset.pest===k)
   .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));await esperar(200);};

 console.log('\n== curvas en pesos ==');
 await irA('ars');
 const tp=d.querySelector('#bonosCuerpo').textContent;
 const curvas=pay.pesos;
 ok('el payload trae curvas',curvas.length>=3,curvas.length);
 ok('todas tienen su titulo en pantalla',
    curvas.every(c=>tp.indexOf(c.titulo)>=0),
    curvas.map(c=>c.titulo).join(' '));
 /* Una por familia CON AL MENOS DOS PAPELES, mas la de "todas juntas". Una
    familia con un solo papel no tiene curva: un punto suelto sobre dos ejes no
    dice nada, y dibujarlo igual sugiere una forma que no existe. */
 const conCurva=curvas.filter(c=>c.filas.filter(f=>f.tem!=null&&f.dias!=null).length>=2);
 const svgs=d.querySelectorAll('#bonosCuerpo svg.cv');
 ok('dibuja una curva por familia con dos papeles o mas, y la general',
    svgs.length===conCurva.length+1,svgs.length+' vs '+(conCurva.length+1));
 ok('pero la TABLA sale igual aunque la familia tenga un solo papel',
    curvas.length>conCurva.length&&
    tp.indexOf(curvas.find(c=>!conCurva.includes(c)).filas[0].t)>=0);
 const filasP=d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr');
 const totalP=curvas.reduce((a,c)=>a+c.filas.length,0);
 ok('y un renglon por papel',filasP.length===totalP,filasP.length+' vs '+totalP);
 ok('con TNA, TIR y TEM',['TNA','TIR','TEM'].every(h=>tp.indexOf(h)>=0));
 /* Lo que hace que esto no haya que mantenerlo: la pantalla lo dice. */
 ok('avisa que las curvas se arman solas',/se arman solas/i.test(tp));
 ok('y de quien son los rendimientos',/bonistas/i.test(tp));
 const s30=curvas[0].filas.find(x=>x.t==='S30S6');
 ok('la TEM que muestra es la del payload',
    tp.indexOf((s30.tem*100).toFixed(2))>=0,(s30.tem*100).toFixed(2));

 console.log('\n== futuros de dolar ==');
 await irA('fut');
 const tf=d.querySelector('#bonosCuerpo').textContent;
 const futs=pay.futuros;
 ok('el payload trae contratos',futs.length>=3,futs.length);
 const filasF=d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr');
 ok('un renglon por contrato vivo',filasF.length===futs.length,
    filasF.length+' vs '+futs.length);
 ok('los nombra como el mercado',/DLR\/SEP26/.test(tf),tf.slice(0,120));
 /* La pantalla escribe en es-AR: 1508.5 sale como "1.508,50". */
 const arSpot=pay.spot.toLocaleString('es-AR',{minimumFractionDigits:2,maximumFractionDigits:2});
 ok('muestra el spot',tf.indexOf(arSpot)>=0,arSpot);
 /* De donde salio el spot NO es un detalle: la tasa directa es precio/spot-1,
    asi que un spot deducido y uno oficial no son lo mismo y la pantalla tiene
    que decir cual es. */
 ok('y dice de donde salio',tf.indexOf(pay.spot_fuente)>=0,pay.spot_fuente);
 ok('con el aviso que corresponde a ESA fuente',
    /despej.|A3500|contrato más corto/.test(tf));
 ok('trae tasa directa, TNA y TEM',
    ['directa','TNA','TEM'].every(h=>tf.indexOf(h)>=0));
 ok('y la implicita de A3 aparte',/A3/.test(tf));
 ok('avisa que los vencimientos salen de A3',/salen de A3/i.test(tf));
 /* Dos series: el futuro y la tasa fija. La distancia es el carry, que es la
    unica razon para mirarlas juntas. */
 const svgF=d.querySelector('#bonosCuerpo svg.cv');
 ok('dibuja la curva',!!svgF);
 const series=new Set([...svgF.querySelectorAll('.cv-pt')]
   .map(g=>g.getAttribute('class').replace('cv-pt ','')));
 ok('con dos series, futuro y tasa fija',series.size===2,[...series].join());
 /* Mismo invariante que en el grafico del screener. */
 const vbF=svgF.getAttribute('viewBox').split(' ').map(Number);
 ok('nada se dibuja fuera del lienzo',
    [...svgF.querySelectorAll('circle')].every(c=>{
      const x=+c.getAttribute('cx'),y=+c.getAttribute('cy');
      return x>=0&&x<=vbF[2]&&y>=0&&y<=vbF[3];}));

 console.log('\n== corporativos: tabla plana, no agrupada ==');
 await irA('ons');
 const tOns=d.querySelector('#bonosCuerpo').textContent;
 const filasO=()=>[...d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr')];
 ok('NO agrupa por emisor',!d.querySelector('#bonosCuerpo .bo-fila[data-emisor]'));
 ok('un renglon por especie',filasO().length===pay.ons.length,
    filasO().length+' vs '+pay.ons.length);
 ok('el emisor queda como columna',
    pay.ons.every(o=>tOns.indexOf(o.emisor)>=0));
 ok('con precio, cupon, TIR y paridad',
    ['precio','cupón','TIR','paridad'].every(h=>tOns.indexOf(h)>=0));
 ok('dice de quien es la TIR',/bonistas/i.test(tOns));
 ok('y que no hay calificacion de riesgo',/calificaci.n de riesgo/i.test(tOns));

 console.log('\n== ordenar la tabla plana ==');
 /* Ordenar es la razon de aplanarla: sin esto, 600 filas planas son peores
    que agrupadas. */
 const tirDe=tr=>{const c=tr.querySelectorAll('td')[7].textContent;
   return c==='·'?null:parseFloat(c.replace('%',''));};
 const arranque=filasO().map(tirDe);
 ok('arranca ordenada por TIR de mayor a menor',
    arranque.every((v,i)=>i===0||v===null||arranque[i-1]===null||arranque[i-1]>=v),
    arranque.join(' '));
 const th=[...d.querySelectorAll('#bonosCuerpo th[data-ord]')];
 const thTir=th.find(x=>x.dataset.ord==='tir');
 thTir.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(150);
 const alReves=filasO().map(tirDe);
 ok('tocar la misma columna la da vuelta',
    alReves[0]<=arranque[0],alReves.join(' '));
 const thEm=[...d.querySelectorAll('#bonosCuerpo th[data-ord]')]
   .find(x=>x.dataset.ord==='emisor');
 thEm.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
 await esperar(150);
 ok('se puede ordenar por emisor',
    d.querySelector('#bonosCuerpo th[data-ord="emisor"]').classList.contains('on'));

 console.log('\n== buscar en la tabla plana ==');
 const inp=d.querySelector('#buscaOns');
 ok('hay buscador',!!inp);
 inp.value='YPF';inp.dispatchEvent(new w.Event('input',{bubbles:true}));
 await esperar(200);
 const conY=filasO();
 ok('filtra por emisor',conY.length>0&&conY.length<pay.ons.length,
    conY.length+' de '+pay.ons.length);
 ok('y lo que queda es de ese emisor',
    conY.every(tr=>/YPF/i.test(tr.textContent)));
 const inp2=d.querySelector('#buscaOns');
 inp2.value='';inp2.dispatchEvent(new w.Event('input',{bubbles:true}));
 await esperar(200);
 ok('al borrar vuelven todas',filasO().length===pay.ons.length);

 console.log('\n== volver a Soberanos ==');
 await irA('sob');
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
