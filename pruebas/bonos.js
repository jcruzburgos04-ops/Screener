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
 /* Una curva por familia CON AL MENOS DOS PAPELES. Un punto suelto sobre dos
    ejes no dice nada y dibujarlo sugiere una forma que no existe.

    NO hay una curva que las superponga a todas: se probo y era ilegible. Los
    rotulos de cincuenta papeles se pisan, y sobre todo las escalas no son
    comparables -- un CER rinde 0,3% mensual REAL y una LECAP 2,1% NOMINAL, asi
    que en el mismo eje parece que una paga siete veces mas que la otra. */
 /* El eje X es la DURATION, no los dias: con dias, un papel largo estiraba el
    eje y apilaba a los cortos contra el margen. El predicado tiene que ser el
    mismo que usa la pantalla o el test cuenta puntos que no se dibujan. */
 const dibujable=c=>c.filas.filter(
   f=>f.opero!==false&&f.tem!=null&&f.duration>0);
 const conCurva=curvas.filter(c=>dibujable(c).length>=2);
 const svgs=d.querySelectorAll('#bonosCuerpo svg.cv');
 ok('una curva por familia con dos papeles o mas, y ninguna que las mezcle',
    svgs.length===conCurva.length,svgs.length+' vs '+conCurva.length);
 ok('pero la TABLA sale igual aunque la familia tenga un solo papel',
    curvas.length>conCurva.length&&
    tp.indexOf(curvas.find(c=>!conCurva.includes(c)).filas[0].t)>=0);
 /* LOS ROTULOS NO SE PUEDEN PISAR. Es la queja concreta del usuario sobre una
    captura de produccion: con once papeles de tasa fija los tickers salian
    encimados hasta quedar ilegibles ("S3N0O6E7").

    Se prueba con los ONCE REALES de esa captura -- su duration y su TEM de
    verdad -- porque la fixtura tiene pocos por curva y no reproduce el
    amontonamiento. Se mide sobre el SVG que sale, teniendo en cuenta el ancla
    de cada rotulo: uno con text-anchor=start crece hacia la derecha de su x,
    no alrededor, y medirlos todos como centrados da choques que no existen. */
 const REAL=[['S15S6',0.03,1.82],['S30S6',0.06,1.94],['TO26',0.11,1.98],
   ['S30O6',0.12,1.96],['S13N6',0.15,2.07],['S30N6',0.19,2.08],
   ['T15E7',0.29,2.07],['T30A7',0.51,2.14],['T31Y7',0.57,2.17],
   ['T30J7',0.64,2.15],['TY30P',2.05,2.20]];
 {
  const svgTxt=w.curvaXY(REAL.map(([t,x,y])=>({x,y,t})),
                         {rotuloX:'duration · años',alto:300,desnuda:1});
  const doc=new JSDOM('<div>'+svgTxt+'</div>').window.document;
  const AN=7.8, AL=14;                    // mono a 13px, el tamaño real
  const cajas=[...doc.querySelectorAll('.cv-pt text')].map(t=>{
    const x=+t.getAttribute('x'), y=+t.getAttribute('y');
    const an=t.textContent.length*AN, a=t.getAttribute('text-anchor');
    const x1=a==='start'?x:(a==='end'?x-an:x-an/2);
    return {t:t.textContent,x1,x2:x1+an,y1:y-AL,y2:y};});
  const pisados=[];
  for(let i=0;i<cajas.length;i++)for(let j=i+1;j<cajas.length;j++){
    const a=cajas[i],b=cajas[j];
    if(!(a.x2<b.x1||a.x1>b.x2||a.y2<b.y1||a.y1>b.y2))
      pisados.push(a.t+'/'+b.t);}
  ok('con los once papeles reales, ningun rotulo pisa a otro',
     pisados.length===0, pisados.join(' '));
  ok('y los once quedan rotulados', cajas.length===REAL.length,
     cajas.length+' de '+REAL.length);
  /* Y ninguno se sale del lienzo, que es el otro modo de quedar ilegible. */
  const vb=(doc.querySelector('svg').getAttribute('viewBox')||'').split(' ').map(Number);
  ok('ni se sale del lienzo',
     cajas.every(c=>c.x1>=0&&c.x2<=vb[2]&&c.y1>=0&&c.y2<=vb[3]));
  /* La tendencia se AJUSTA, no une los puntos: unirlos daba un zigzag que se
     lee como saltos del mercado donde solo hay dispersion. */
  ok('hay una linea de tendencia punteada y no una quebrada',
     doc.querySelectorAll('.cv-ajuste').length===1&&
     !doc.querySelector('.cv-linea'),
     doc.querySelectorAll('.cv-ajuste').length+'/'+doc.querySelectorAll('.cv-linea').length);
 }

 /* El grafico va AL LADO de la tabla, no arriba: apilados, una familia sola
    ocupaba dos pantallas. Y la tabla va primero, como en el informe. */
 ok('cada familia tiene la tabla y el grafico lado a lado',
    d.querySelectorAll('#bonosCuerpo .bo-par').length===curvas.length,
    d.querySelectorAll('#bonosCuerpo .bo-par').length+' vs '+curvas.length);
 ok('con la tabla a la izquierda y la curva a la derecha',
    [...d.querySelector('#bonosCuerpo .bo-par').children]
      .map(c=>c.className).join('|')==='bo-par-t|bo-par-g',
    [...d.querySelector('#bonosCuerpo .bo-par').children].map(c=>c.className).join('|'));

 /* El grafico y su tabla van en la MISMA tarjeta: si no, hay que ir y volver
    entre la curva y los numeros del mismo instrumento. */
 ok('cada curva vive en la misma tarjeta que su tabla',
    [...svgs].every(g=>{const t=g.closest('.bo-tarjeta');
      return t&&t.querySelector('table');}));
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

 /* Los papeles que hoy no operaron. Su "precio" es una punta que puede ser de
    hace dias, y uno solo abre el eje de toda la curva: en el panel real un
    dolar linked sin operar hacia que la familia entera saliera con 0,8% y
    10,8% mezclados. Se sacan DEL DIBUJO y se dejan en la tabla, apagados.
    Quien decide es bonos.py, no esta pantalla: la regla es una sola. */
 const cer=curvas.find(c=>c.clave==='CER');
 const quieto=cer.filas.find(f=>f.opero===false);
 ok('la fuente marca el papel que no opero',!!quieto&&quieto.volumen===0,
    quieto&&quieto.volumen);
 const svgCer=[...svgs].find(g=>g.closest('.bo-tarjeta')
   .querySelector('.bo-tit').textContent.trim().indexOf('CER')===0);
 ok('no lo dibuja',
    svgCer.textContent.indexOf(quieto.t)<0,svgCer.textContent.slice(0,90));
 ok('pero dibuja a los que si operaron',
    svgCer.querySelectorAll('.cv-pt').length===dibujable(cer).length,
    svgCer.querySelectorAll('.cv-pt').length+' vs '+dibujable(cer).length);
 const trQ=[...d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr')]
   .find(tr=>tr.textContent.indexOf(quieto.t)>=0);
 ok('sigue en la tabla',!!trQ,quieto.t);
 ok('y ahi se ve apagado',trQ.className.indexOf('bo-quieto')>=0,trQ.className);
 // El texto viene con saltos de linea del template, asi que se compara plano.
 const plano=tp.replace(/\s+/g,' ');
 ok('la pantalla dice cuantos dejo afuera y por que',
    /1 papel no operó hoy: fuera del gráfico/.test(plano)&&/punta/.test(plano),
    plano.slice(plano.indexOf('no operó')-30,plano.indexOf('no operó')+120));
 ok('y cuenta cuantos operaron en el titulo de la familia',
    tp.indexOf(dibujable(cer).length+' operaron hoy')>=0);
 /* Los dos casos en que NO se puede dibujar: uno solo opero (un punto sobre
    dos ejes no es una curva) y no opero ninguno. Las dos veces la pantalla lo
    dice, en vez de dejar un hueco que se lee como que fallo algo. */
 ok('con un solo papel operado lo dice en vez de dejar el hueco',
    /operó un solo papel/.test(plano),plano.slice(0,60));
 const badlar=curvas.find(c=>c.clave==='Badlar');
 ok('hay una familia donde no opero nadie',badlar&&badlar.operados===0);
 ok('y ahi tambien lo dice',/no operó ninguno de estos papeles/.test(plano));
 ok('pero el papel sigue estando',tp.indexOf(badlar.filas[0].t)>=0);

 /* EL PROXIMO PAGO. Es la pregunta que se le hace a un bono antes que
    cualquier otra -- cuando cobro y cuanto -- y hasta ahora solo la
    contestaban los soberanos, que son los unicos con cronograma cargado.

    Lo que hay que verificar no es que aparezca una fecha, sino que la
    pantalla DISTINGA los dos casos: si despues de ese pago no queda nada,
    esa linea es el cronograma completo; si faltan mas, el importe no es el
    total y no puede leerse como si lo fuera. */
 const conPago=c=>c.filas.filter(f=>f.pago);
 const todasP=curvas.flatMap(c=>c.filas);
 ok('el payload trae el proximo pago de los papeles en pesos',
    todasP.filter(f=>f.pago).length>=5, todasP.filter(f=>f.pago).length);
 ok('la tabla tiene las tres columnas del pago',
    ['próx. pago','en','cobra'].every(h=>tp.indexOf(h)>=0));

 const unUltimo=todasP.find(f=>f.pago&&f.pago.ultimo);
 const unParcial=todasP.find(f=>f.pago&&!f.pago.ultimo);
 ok('hay un papel cuyo proximo pago es el ultimo',!!unUltimo,unUltimo&&unUltimo.t);
 ok('y otro al que le faltan pagos',!!unParcial,unParcial&&unParcial.t);
 /* Si es el ultimo, el pago ES el vencimiento: las dos columnas de la misma
    fila no pueden decir dias distintos del mismo evento. */
 ok('cuando es el ultimo, el pago cae en el vencimiento de su propia fila',
    unUltimo.pago.fecha===unUltimo.vto&&unUltimo.pago.dias===unUltimo.dias,
    JSON.stringify([unUltimo.vto,unUltimo.dias,unUltimo.pago]));
 ok('al que le faltan pagos, el proximo es ANTES del vencimiento',
    unParcial.pago.fecha<unParcial.vto&&unParcial.pago.dias<unParcial.dias,
    JSON.stringify([unParcial.vto,unParcial.dias,unParcial.pago]));

 const trU=[...d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr')]
   .find(tr=>tr.textContent.indexOf(unUltimo.t)>=0);
 ok('el ultimo pago se resalta en la tabla',
    !!trU.querySelector('.bo-final'),trU.textContent.slice(0,60));
 ok('y el parcial NO',!([...d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr')]
    .find(tr=>tr.textContent.indexOf(unParcial.t)>=0).querySelector('.bo-final')));
 ok('el importe de un pago parcial lleva el + que avisa que no es el total',
    !!([...d.querySelectorAll('#bonosCuerpo .bo-grande tbody tr')]
    .find(tr=>tr.textContent.indexOf(unParcial.t)>=0).querySelector('.bo-mas')));
 ok('el del ultimo no lo lleva',!trU.querySelector('.bo-mas'));

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
 /* El grafico de futuros NO es una curvaXY: el eje X son los contratos, uno
    al lado del otro, cada punto lleva su porcentaje y entre las dos lineas van
    las barras del spread. Es la figura con la que se mira el carry. */
 const svgF=d.querySelector('#bonosCuerpo svg.cv');
 ok('dibuja el grafico',!!svgF);
 ok('con la linea del futuro',svgF.querySelectorAll('.fu-linea.fu-c-fut').length===1);
 ok('y la de la tasa fija en pesos',
    svgF.querySelectorAll('.fu-linea.fu-c-pesos').length===1);
 ok('un punto por contrato en la linea del futuro',
    svgF.querySelectorAll('.fu-pt.fu-c-fut').length===futs.filter(x=>x.tna!=null).length);
 /* Los rotulos son PORCENTAJES, no tickers: es lo que se lee en el grafico de
    referencia y lo que se necesita para comparar dos lineas de un vistazo. */
 ok('cada punto lleva su porcentaje',
    [...svgF.querySelectorAll('.fu-val')].every(t=>/%$/.test(t.textContent)));
 ok('hay barras de spread entre las dos lineas',
    svgF.querySelectorAll('.fu-spread').length>0);
 ok('y una franja de volumen abajo',svgF.querySelectorAll('.fu-vol').length>0);
 /* Mismo invariante que en el grafico del screener. */
 const vbF=svgF.getAttribute('viewBox').split(' ').map(Number);
 const fueraF=[...svgF.querySelectorAll('circle')].filter(c=>{
   const x=+c.getAttribute('cx'),y=+c.getAttribute('cy');
   return !(x>=0&&x<=vbF[2]&&y>=0&&y<=vbF[3]);});
 ok('nada se dibuja fuera del lienzo',fueraF.length===0,fueraF.length);
 const barras=[...svgF.querySelectorAll('rect')].filter(r=>{
   const y=+r.getAttribute('y'), h=+r.getAttribute('height');
   return !(y>=0&&y+h<=vbF[3]);});
 ok('ni las barras',barras.length===0,barras.length);

 console.log('\n== la tasa fija se interpola, y no se extrapola ==');
 /* Comparar el DLR/DIC26 (121 dias) contra una LECAP de 88 no dice nada: hay
    que interpolar al plazo del contrato. Pero MAS ALLA de la letra mas larga
    no se inventa nada, que es lo que haria una extrapolacion. */
 const fijaF=(pay.pesos.find(c=>c.clave==='Fijo')||{filas:[]}).filas
   .filter(x=>x.opero!==false&&x.tna!=null&&x.dias!=null).sort((a,b)=>a.dias-b.dias);
 const masLarga=fijaF.length?fijaF[fijaF.length-1].dias:0;
 const dentro=futs.filter(x=>x.tna!=null&&x.dias>0&&x.dias<=masLarga&&x.dias>=fijaF[0].dias);
 ok('la linea de pesos llega hasta donde llega la curva, y no mas',
    svgF.querySelectorAll('.fu-pt.fu-c-pesos').length===dentro.length,
    svgF.querySelectorAll('.fu-pt.fu-c-pesos').length+' vs '+dentro.length);
 if(futs.some(x=>x.dias>masLarga))
   ok('y avisa por los contratos que quedaron sin ella',
      /no se extrapola/.test(d.querySelector('#bonosCuerpo').textContent));

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
 const tOnsPlano=tOns.replace(/\s+/g,' ');
 ok('y que no hay calificacion de riesgo',
    /calificaci.n de riesgo/i.test(tOnsPlano),tOnsPlano.slice(-260));

 /* Las ONs tambien. Era el pedido explicito: "que todo lo que sea renta fija
    me aparezca cuales son sus pagos, tambien en las ONs". De ellas NO hay
    cronograma completo en ninguna fuente abierta -- ya esta verificado --,
    pero el proximo servicio si lo publica la fuente, y para las que ya
    entraron en su ultimo tramo ESE es el cronograma entero. */
 const ons=pay.ons||[];
 ok('el payload trae el proximo pago de las ONs',
    ons.filter(o=>o.pago).length>=3, ons.filter(o=>o.pago).length);
 ok('y la tabla las muestra',
    ['próx. pago','en','cobra'].every(h=>tOns.indexOf(h)>=0));
 const oU=ons.find(o=>o.pago&&o.pago.ultimo), oP=ons.find(o=>o.pago&&!o.pago.ultimo);
 ok('hay una ON en su ultimo tramo',!!oU,oU&&oU.t);
 ok('y otra con cupones por delante',!!oP,oP&&oP.t);
 ok('a la del ultimo tramo el pago le cae en su vencimiento',
    oU.pago.fecha===oU.vto&&oU.pago.dias===oU.dias,
    JSON.stringify([oU.vto,oU.dias,oU.pago]));
 ok('y a la otra, antes',oP.pago.fecha<oP.vto,
    JSON.stringify([oP.vto,oP.pago.fecha]));
 const trOU=[...d.querySelectorAll('#bonosCuerpo .bo-tabla tbody tr')]
   .find(tr=>tr.textContent.indexOf(oU.t)>=0);
 ok('en la tabla el ultimo tramo va resaltado',!!trOU.querySelector('.bo-final'),
    trOU.textContent.slice(0,60));
 /* Y que la tarjeta diga que el + NO es el total. Es la unica defensa contra
    leer un cupon suelto como todo lo que queda por cobrar. */
 ok('la tarjeta explica que el + no es el total',
    /no es el total/i.test(tOnsPlano),tOnsPlano.slice(-200));

 console.log('\n== ordenar la tabla plana ==');
 /* Ordenar es la razon de aplanarla: sin esto, 600 filas planas son peores
    que agrupadas. */
 /* La columna se busca POR SU ENCABEZADO, no por indice. Con un td[7] fijo,
    agregar una columna a la izquierda hacia que el test siguiera pasando o
    fallando por el motivo equivocado -- es la misma trampa de los selectores
    por posicion que ya se pago cara con `aside input`. */
 const colDe=(nombre)=>{
   const th=[...d.querySelectorAll('#bonosCuerpo .bo-tabla thead th')];
   const i=th.findIndex(x=>x.textContent.trim().toLowerCase()===nombre);
   if(i<0)throw new Error('no existe la columna '+nombre);
   return i;};
 const iTir=colDe('tir');
 const tirDe=tr=>{const c=tr.querySelectorAll('td')[iTir].textContent;
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
