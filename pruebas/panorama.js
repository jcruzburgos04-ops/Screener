/* ===========================================================================
   VISTA PANORAMA
   ===========================================================================
   Las tarjetas de indices y sectores. Se comprueba la maquinaria: que cada
   panel traiga sus simbolos, que el orden funcione, que la barra de amplitud
   cuente bien, que el pre-market se muestre cuando viene y que la seleccion y
   los favoritos anden desde la tarjeta.

   Lo visual (que las velas se vean bien en 84 px) no se puede probar aca.
   ======================================================================== */
const fs=require('fs'),path=require('path');
const SITIO=process.env.SCREENER_SITIO||path.join(__dirname,'tmp','sitio');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync(path.join(SITIO,'index.html'),'utf8');
const base=JSON.parse(fs.readFileSync(path.join(SITIO,'datos.json'),'utf8'));

let fallas=0;
const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;
  console.log('  FALLA  '+n+(x!==undefined?'   -> '+x:''));}};
const esperar=ms=>new Promise(r=>setTimeout(r,ms));

function abrir(payload,almacen){
  const texto=JSON.stringify(payload||base);
  return new Promise(res=>{
    const dibujos=[];
    const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,
      url:'https://local/',
      beforeParse(w){
        const noop=()=>{};
        // solo se registran las velas de los MINI graficos: el grafico grande
        // mide 286 px y mezclarlos daba un falso positivo
        w.HTMLCanvasElement.prototype.getContext=function(){
          const mini=this.hasAttribute&&this.hasAttribute('data-mini');
          return {setTransform:noop,clearRect:noop,beginPath:noop,closePath:noop,fill:noop,roundRect:noop,moveTo:noop,
            lineTo:noop,stroke:noop,setLineDash:noop,save:noop,restore:noop,
            clip:noop,rect:noop,roundRect:noop,measureText:()=>({width:8}),fillText:noop,
            fillRect:(x,y,ww,hh)=>{if(mini)dibujos.push([x,y,ww,hh]);},
            set strokeStyle(v){},set fillStyle(v){},set lineWidth(v){},
            set font(v){},set textAlign(v){}};};
        w.Element.prototype.scrollIntoView=noop;
        Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 220}});
        Object.defineProperty(w.HTMLElement.prototype,'clientHeight',{get(){return 84}});
        Object.defineProperty(w,'localStorage',{value:{_m:{...(almacen||{})},
          getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=String(v)},
          removeItem(k){delete this._m[k]}},configurable:true});
        w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
        w.requestAnimationFrame=f=>setTimeout(f,0);
        w.fetch=async u=>{
          const s=String(u);
          if(s.indexOf('api/')===0)throw new Error('sin servidor');
          if(s.indexOf('datos.json')>=0)return {ok:true,body:null,text:async()=>texto};
          throw new TypeError('Failed to fetch');};
      }});
    const t=setInterval(()=>{
      if(dom.window.document.querySelectorAll('#tabla tbody tr').length ||
         dom.window.document.querySelectorAll('.tarjeta').length){
        clearInterval(t);dom.window.__dibujos=dibujos;res(dom.window);}},20);
  });
}

(async()=>{
  const SIN_YAHOO={screener_ash_yahoo_auto:'0'};

  console.log('== entrar y salir de la vista ==');
  const w=await abrir(null,SIN_YAHOO);
  const d=w.document,$=s=>d.querySelector(s),$$=s=>[...d.querySelectorAll(s)];
  ok('arranca en la tabla',!d.body.classList.contains('panorama'));
  $('#chipVista').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  ok('el chip la abre',d.body.classList.contains('panorama'));
  ok('hay tarjetas',$$('.tarjeta').length>0,$$('.tarjeta').length);
  ok('la tabla se esconde',w.getComputedStyle($('.tabla-wrap')).display==='none');
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'p',bubbles:true}));
  await esperar(200);
  ok('la tecla P la cierra',!d.body.classList.contains('panorama'));
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'p',bubbles:true}));
  await esperar(200);

  console.log('\n== los paneles ==');
  const tabs=$$('#panTabs .chip');
  ok('hay seis paneles',tabs.length===6,tabs.length);
  const nombres=tabs.map(c=>c.textContent);
  ok('estan indices y sectores',nombres.includes('Índices')&&nombres.includes('Sectores'),
     nombres.join('|'));
  const tickers=()=>$$('.tarjeta').map(t=>t.dataset.t);
  ok('el panel de indices trae SPY y QQQ',
     tickers().includes('SPY')&&tickers().includes('QQQ'),tickers().join(','));

  tabs[1].dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  const sec=tickers();
  ok('el de sectores trae los XL*',sec.filter(t=>/^XL/.test(t)).length>=9,sec.join(','));
  ok('y ninguno que no sea sector',sec.every(t=>/^XL/.test(t)),sec.join(','));

  console.log('\n== el orden ==');
  const rs=()=>$$('.tarjeta').map(t=>+t.querySelector('.tj-rs b').textContent||0);
  ok('por RS viene de mayor a menor',rs().every((v,i,a)=>i===0||a[i-1]>=v),rs().join(','));
  $$('#panorama .tf .chip[data-orden]').find(c=>c.dataset.orden==='sube')
    .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  const chg=()=>$$('.tarjeta').map(t=>parseFloat(t.querySelector('.tj-chg').textContent));
  ok('por subas viene de mayor a menor',chg().every((v,i,a)=>i===0||a[i-1]>=v),chg().join(','));
  $$('#panorama .tf .chip[data-orden]').find(c=>c.dataset.orden==='baja')
    .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  ok('por bajas viene de menor a mayor',chg().every((v,i,a)=>i===0||a[i-1]<=v),chg().join(','));

  console.log('\n== la barra de amplitud ==');
  const txt=$('#ampTxt').textContent;
  ok('cuenta cuantos suben y bajan',/\d+ suben/.test(txt)&&/\d+ bajan/.test(txt),txt);
  ok('nombra la mayor suba y la mayor baja',/Mayor suba/.test(txt)&&/Mayor baja/.test(txt),txt);
  const suben=+(txt.match(/(\d+) suben/)||[])[1];
  const enVerde=$$('.tarjeta .tj-chg.up').length;
  ok('el conteo coincide con las tarjetas en verde',suben===enVerde,suben+' vs '+enVerde);

  console.log('\n== cada tarjeta muestra RS y lo que marca el ASH ==');
  const t0=$$('.tarjeta')[0];
  ok('tiene el ticker',!!t0.querySelector('.tj-tk').textContent.trim());
  ok('tiene precio y variacion',!!t0.querySelector('.tj-px').textContent.trim()&&
     !!t0.querySelector('.tj-chg').textContent.trim());
  ok('tiene el RS',/RS/.test(t0.querySelector('.tj-rs').textContent),
     t0.querySelector('.tj-rs').textContent);
  ok('tiene el ASH diario y el semanal',/D [▲▼·]/.test(t0.textContent)&&
     /W [▲▼·]/.test(t0.textContent),t0.querySelector('.tj-pie').textContent);
  ok('tiene su mini grafico',!!t0.querySelector('canvas[data-mini]'));
  ok('los mini graficos dibujaron velas',w.__dibujos.length>100,w.__dibujos.length);
  const fuera=w.__dibujos.filter(([x,y,ww,hh])=>!isFinite(x)||!isFinite(y)||y<-1||y+hh>85);
  ok('ninguna vela se sale de la tarjeta',fuera.length===0,JSON.stringify(fuera.slice(0,3)));

  console.log('\n== la cabecera nueva ==');
  ok('tiene el titulo grande',/Panorama/.test(d.querySelector('.pan-titulo').textContent));
  ok('dice el estado del mercado',/NYSE/.test($('#mercados').textContent),
     $('#mercados').textContent);
  ok('el estado es uno de los cuatro',
     /Abierto|Cerrado|Pre-market|After-hours/.test($('#mercados').textContent),
     $('#mercados').textContent);
  ok('dice cuando se actualizo',/actualizado/.test($('#envivo').textContent),
     $('#envivo').textContent);
  ok('cada tarjeta muestra el volumen',!!$$('.tarjeta')[0].querySelector('.tj-vol'),
     $$('.tarjeta')[0].textContent);
  ok('el volumen va en magnitud, no en crudo',
     /US\$ \d+([.,]\d+)? ?(K|M|MM)?/.test($$('.tarjeta')[0].querySelector('.tj-vol').textContent),
     $$('.tarjeta')[0].querySelector('.tj-vol').textContent);

  console.log('\n== el buscador del panorama ==');
  {
    const antes=$$('.tarjeta').length;
    $('#buscarPan').value='NVD';
    $('#buscarPan').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(200);
    const hallados=$$('.tarjeta').map(x=>x.dataset.t);
    ok('busca en todo el universo, no solo en el panel',
       hallados.some(t=>/^NVD/.test(t)),hallados.join(','));
    ok('y achica la grilla',$$('.tarjeta').length<=60,$$('.tarjeta').length);
    $('#buscarPan').value='zzzzz';
    $('#buscarPan').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(200);
    ok('sin resultados lo dice',/Nada coincide/.test($('#tarjetas').textContent),
       $('#tarjetas').textContent.slice(0,50));
    $('#buscarPan').value='';
    $('#buscarPan').dispatchEvent(new w.Event('input',{bubbles:true}));
    await esperar(200);
    ok('al vaciarlo vuelve el panel',$$('.tarjeta').length===antes,
       $$('.tarjeta').length+' vs '+antes);
  }

  console.log('\n== favoritos y seleccion desde la tarjeta ==');
  const tk=$$('.tarjeta')[0].dataset.t;
  $$('.tarjeta')[0].querySelector('.tj-fav').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  ok('la estrella marca el favorito',w.eval('favoritos.has('+JSON.stringify(tk)+')'));
  const otra=$$('.tarjeta').find(t=>t.dataset.t!==tk);
  otra.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  ok('tocar la tarjeta selecciona el simbolo',w.eval('seleccion')===otra.dataset.t,
     w.eval('seleccion'));
  ok('y queda marcada',$$('.tarjeta').find(t=>t.dataset.t===otra.dataset.t)
     .classList.contains('sel'));

  console.log('\n== el panel de favoritos ==');
  $$('#panTabs .chip')[5].dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await esperar(200);
  ok('muestra los favoritos marcados',tickers().includes(tk),tickers().join(','));

  console.log('\n== pre-market y after-hours ==');
  {
    const conExt=JSON.parse(JSON.stringify(base));
    for(const s of conExt.simbolos){
      if(s.t==='SPY'){s.ex=s.c[s.c.length-1]*1.012;s.exp=0.012;s.ext='pre';s.exv=250000;}
      if(s.t==='QQQ'){s.ex=s.c[s.c.length-1]*0.994;s.exp=-0.006;s.ext='post';s.exv=90000;}
    }
    const w2=await abrir(conExt,{...SIN_YAHOO,screener_ash_vista:'p'});
    await esperar(400);
    const d2=w2.document;
    const spy=[...d2.querySelectorAll('.tarjeta')].find(t=>t.dataset.t==='SPY');
    const qqq=[...d2.querySelectorAll('.tarjeta')].find(t=>t.dataset.t==='QQQ');
    ok('la vista se restauro sola',d2.body.classList.contains('panorama'));
    ok('SPY muestra la etiqueta PRE',/PRE/.test(spy.textContent),spy.querySelector('.tj-pie').textContent);
    ok('con su porcentaje y su signo',/\+1\.20%/.test(spy.textContent),
       spy.querySelector('.tj-ext').textContent);
    ok('el after-hours negativo va con menos',/-0\.60%/.test(qqq.textContent),
       qqq.querySelector('.tj-ext').textContent);
    ok('QQQ muestra AH',/AH/.test(qqq.textContent),qqq.querySelector('.tj-pie').textContent);
    ok('el que no tiene extendido no muestra nada',
       [...d2.querySelectorAll('.tarjeta')].filter(t=>t.querySelector('.tj-ext')).length===2,
       [...d2.querySelectorAll('.tarjeta')].filter(t=>t.querySelector('.tj-ext')).length);
    ok('el volumen extendido esta en el title',
       /volumen/.test(spy.querySelector('.tj-ext').getAttribute('title')),
       spy.querySelector('.tj-ext').getAttribute('title'));
  }

  console.log('\n== sin favoritos, el panel lo dice ==');
  {
    const w3=await abrir(null,{...SIN_YAHOO,screener_ash_vista:'p'});
    await esperar(300);
    const d3=w3.document;
    [...d3.querySelectorAll('#panTabs .chip')][5]
      .dispatchEvent(new w3.MouseEvent('click',{bubbles:true}));
    await esperar(200);
    ok('avisa que no hay favoritos',/favorito/.test(d3.querySelector('#tarjetas').textContent),
       d3.querySelector('#tarjetas').textContent.slice(0,60));
  }

  console.log(fallas?'\nFALLAS: '+fallas:'\nPANORAMA OK');
  process.exit(fallas?1:0);
})().catch(e=>{console.error('EXPLOTO:',e);process.exit(1);});
