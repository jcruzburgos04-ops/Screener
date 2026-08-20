/* ===========================================================================
   ORDEN DE LAS COLUMNAS, TAMAÑO DE LETRA Y DENSIDAD
   ===========================================================================
   Tres cosas que el usuario maneja y que tienen que sobrevivir a una recarga:
   en que orden salen las columnas, que tan grande es la letra y cuanto aire
   tienen las filas.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const SITIO=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
const datos=fs.readFileSync(path.join(SITIO,'datos.json'),'utf8');

let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'   -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));

function nuevoAlmacen(ini){const m={...(ini||{})};return{
  getItem:k=>k in m?m[k]:null,setItem:(k,v)=>{m[k]=String(v)},
  removeItem:k=>{delete m[k]},_m:m};}

function abrir(almacen){
  return new Promise(res=>{
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
      url:'https://local/',
      beforeParse(w){
        const noop=()=>{};
        w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>noop,set:()=>true});
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
        Object.defineProperty(w,'localStorage',{value:almacen,configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.requestAnimationFrame=f=>setTimeout(f,0);
        w.fetch=async u=>{
          const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>datos};
          throw new TypeError('Failed to fetch');};
      }});
    const t=setInterval(()=>{
      if(dom.window.document.querySelectorAll('#tabla tbody tr').length){
        clearInterval(t);res(dom.window);}},20);
  });
}
const cols=w=>[...w.document.querySelectorAll('#tabla thead th')].map(x=>x.dataset.k);
const filasOrd=w=>[...w.document.querySelectorAll('#ordenCols .fila-ord')]
  .map(x=>x.dataset.k);

(async()=>{
  const SIN={screener_ash_yahoo_auto:'0'};
  const almacen=nuevoAlmacen(SIN);
  const w=await abrir(almacen);
  const d=w.document,$=s=>d.querySelector(s),$$=s=>[...d.querySelectorAll(s)];

  console.log('== la lista de orden refleja la tabla ==');
  ok('hay filas para reordenar',filasOrd(w).length>0,filasOrd(w).length);
  {
    // "__emas" es UNA entrada en la lista pero la tabla la expande en una
    // columna por EMA, asi que se compara el orden RELATIVO de las que si
    // aparecen con el mismo nombre.
    const enTabla=cols(w).slice(2);
    const comunes=filasOrd(w).filter(k=>enTabla.includes(k));
    const posiciones=comunes.map(k=>enTabla.indexOf(k));
    ok('la lista sigue el orden de la tabla',
       posiciones.every((v,i,a)=>i===0||a[i-1]<v),
       comunes.slice(0,5).join(',')+' -> '+posiciones.slice(0,5).join(','));
    ok('estan todas las encendidas menos las dos fijas',
       comunes.length>=filasOrd(w).length-1,
       comunes.length+' de '+filasOrd(w).length);
  }
  ok('la primera no se puede subir',
     $$('#ordenCols .fila-ord')[0].querySelector('[data-mover="-1"]').disabled);
  ok('la ultima no se puede bajar',
     $$('#ordenCols .fila-ord').slice(-1)[0].querySelector('[data-mover="1"]').disabled);

  console.log('\n== bajar una columna con la flecha ==');
  {
    const antes=cols(w).slice();
    const primera=filasOrd(w)[0], segunda=filasOrd(w)[1];
    $$('#ordenCols .fila-ord')[0].querySelector('[data-mover="1"]')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(200);
    const ahora=cols(w);
    ok('se intercambiaron',ahora[2]===segunda&&ahora[3]===primera,
       ahora.slice(0,5).join(','));
    ok('la estrella y el ticker no se movieron',
       ahora[0]==='fav'&&ahora[1]==='t',ahora.slice(0,2).join(','));
    ok('la tabla tiene la misma cantidad de columnas',ahora.length===antes.length,
       ahora.length+' vs '+antes.length);
    ok('la lista tambien se actualizo',filasOrd(w)[0]===segunda,filasOrd(w)[0]);
    ok('los numeros se renumeraron',
       $$('#ordenCols .ord-n')[0].textContent==='1'&&
       $$('#ordenCols .ord-n')[1].textContent==='2');
  }

  console.log('\n== subir una columna ==');
  {
    const tercera=filasOrd(w)[2];
    $$('#ordenCols .fila-ord')[2].querySelector('[data-mover="-1"]')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(200);
    ok('quedo segunda de las movibles',filasOrd(w)[1]===tercera,filasOrd(w).slice(0,3).join(','));
  }

  console.log('\n== mover una columna a otro lugar (lo que hace el arrastre) ==');
  {
    const lista=filasOrd(w);
    const ultima=lista[lista.length-1];
    w.eval(`reordenar(${JSON.stringify(ultima)},${JSON.stringify(lista[0])});
            montarColumnas();render();`);
    await esperar(200);
    ok('la ultima paso a ser la primera',filasOrd(w)[0]===ultima,filasOrd(w)[0]);
    ok('y la tabla la muestra ahi',cols(w)[2]===ultima,cols(w).slice(0,4).join(','));
  }

  console.log('\n== el orden sobrevive a recargar ==');
  {
    const esperado=filasOrd(w).slice();
    w.dispatchEvent(new w.Event('pagehide'));
    const g=JSON.parse(almacen.getItem('screener_ash_sesion'));
    ok('la sesion lo guarda',Array.isArray(g._ordenCols)&&g._ordenCols.length>0,
       (g._ordenCols||[]).slice(0,3).join(','));
    const w2=await abrir(almacen);
    ok('al reabrir sale igual',JSON.stringify(filasOrd(w2))===JSON.stringify(esperado),
       filasOrd(w2).slice(0,4).join(',')+' vs '+esperado.slice(0,4).join(','));
  }

  console.log('\n== apagar una columna no rompe el orden del resto ==');
  {
    const antes=filasOrd(w).slice();
    const quitar=antes[1];
    $$('#chipsCols .chip').find(c=>c.dataset.v===quitar)
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(200);
    ok('desaparece de la lista',!filasOrd(w).includes(quitar),quitar);
    ok('el resto queda en el mismo orden',
       JSON.stringify(filasOrd(w))===JSON.stringify(antes.filter(k=>k!==quitar)),
       filasOrd(w).slice(0,4).join(','));
    $$('#chipsCols .chip').find(c=>c.dataset.v===quitar)
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(200);
    ok('al prenderla vuelve',filasOrd(w).includes(quitar));
  }

  console.log('\n== "las de siempre" devuelve tambien el orden ==');
  {
    $('#colEsencial').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(200);
    ok('el orden vuelve al de fabrica',w.eval('ordenCols.length')===0,
       w.eval('ordenCols.length'));
    ok('y las columnas tambien',cols(w).length>10,cols(w).length);
  }

  console.log('\n== el CSV sale con lo que se ve, en ese orden ==');
  {
    let blob=null;
    w.URL.createObjectURL=b=>{blob=b;return 'blob:x';};
    $('#btnCsv').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    ok('genera el CSV',!!blob&&blob.size>500,blob&&blob.size);
    const texto=await blob.text();
    const cab=texto.split('\n')[0].split(',');
    const titulos=[...d.querySelectorAll('#tabla thead th')]
      .map(x=>x.textContent.replace(/[ ↑↓]+$/,'')).slice(1);
    ok('el encabezado son los titulos visibles, sin la estrella',
       cab[0]==='Ticker'&&cab.length===titulos.length,
       cab.slice(0,4).join('|')+'  ('+cab.length+' vs '+titulos.length+')');
    ok('y en el mismo orden',cab[1]===titulos[1],cab[1]+' vs '+titulos[1]);
    ok('las filas tienen las mismas celdas que el encabezado',
       texto.split('\n')[1].split(',').length>=cab.length-2,
       texto.split('\n')[1].slice(0,60));
  }

  console.log('\n== tamaño de letra y alto de fila ==');
  {
    const raiz=()=>w.document.documentElement.style.getPropertyValue('--escala');
    const aire=()=>w.document.documentElement.style.getPropertyValue('--aire');
    ok('arranca en 1',(+raiz()||1)===1&&(+aire()||1)===1,raiz()+'/'+aire());
    $$('#chipsLetra .chip').find(c=>c.dataset.escala==='1.26')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(150);
    ok('"muy grande" agranda la letra',+raiz()===1.26,raiz());
    ok('y el chip queda marcado',
       $$('#chipsLetra .chip').find(c=>c.dataset.escala==='1.26').classList.contains('on'));
    $$('#chipsAire .chip').find(c=>c.dataset.aire==='0.8')
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    await esperar(150);
    ok('"apretado" achica el alto de fila',+aire()===0.8,aire());
    ok('la tabla sigue entera',$$('#tabla tbody tr').length>100,$$('#tabla tbody tr').length);
    ok('queda guardado',almacen.getItem('screener_ash_escala')==='1.26'&&
       almacen.getItem('screener_ash_aire')==='0.8',
       almacen.getItem('screener_ash_escala')+'/'+almacen.getItem('screener_ash_aire'));
    const w3=await abrir(almacen);
    ok('y vuelve al reabrir',
       +w3.document.documentElement.style.getPropertyValue('--escala')===1.26,
       w3.document.documentElement.style.getPropertyValue('--escala'));
  }

  console.log(fallas?'\nFALLAS: '+fallas:'\nCOLUMNAS Y LECTURA OK');
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
