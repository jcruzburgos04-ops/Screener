// Lo unico verificable del grafico sin navegador: que no lance y que todo lo
// que dibuja caiga DENTRO del canvas (el bug de las barras tapando las fechas).
const fs=require('fs'),{JSDOM}=require('jsdom');
// Sitio de prueba: lo arma correr.sh en pruebas/tmp/sitio.
const SITIO=process.env.SCREENER_SITIO||require('path').join(__dirname,'tmp','sitio');
const html=fs.readFileSync(SITIO+'/index.html','utf8');
let datos=JSON.parse(fs.readFileSync(SITIO+'/datos.json','utf8'));
// un nombre hostil, para probar el escapado
datos.simbolos[0].n='<img src=x onerror=alert(1)>  "AT&T" & <b>';
// el panel agrupa por SECTOR, asi que el nombre hostil va ahi
datos.simbolos[0].sec='Sector "raro" & <peligroso>';
datos.simbolos[0].ind='Industria & <rara>';
datos=JSON.stringify(datos);

const rects=[],textos=[];
const dom=new JSDOM(html,{runScripts:'dangerously',pretendToBeVisual:true,url:'https://local/',
  beforeParse(w){
    const noop=()=>{};
    w.HTMLCanvasElement.prototype.getContext=()=>({setTransform:noop,clearRect:noop,
      beginPath:noop,moveTo:noop,lineTo:noop,stroke:noop,setLineDash:noop,save:noop,
      restore:noop,clip:noop,rect:noop,measureText:()=>({width:8}),
      fillRect:(x,y,w2,h2)=>rects.push([x,y,w2,h2]),
      fillText:(t,x,y)=>textos.push([t,x,y]),
      set strokeStyle(v){},set fillStyle(v){},set lineWidth(v){},set font(v){},set textAlign(v){}});
    w.Element.prototype.scrollIntoView=noop;
    Object.defineProperty(w.HTMLElement.prototype,'clientWidth',{get(){return 1200}});
    Object.defineProperty(w,'localStorage',{value:{_m:{},getItem(k){return this._m[k]??null},
      setItem(k,v){this._m[k]=String(v)},removeItem(k){delete this._m[k]}},configurable:true});
    w.fetch=async u=>{if(String(u).indexOf('api/')===0)throw new Error('sin servidor');
      return {ok:true,body:null,text:async()=>datos};};
    w.TextEncoder=require('util').TextEncoder;w.TextDecoder=require('util').TextDecoder;
  }});
const w=dom.window;const errores=[];w.addEventListener('error',e=>errores.push(e.message));
setTimeout(async()=>{
  const doc=w.document;
  let fallas=0;
  const ok=(n,c,x)=>{if(c)console.log('  ok     '+n);else{fallas++;console.log('  FALLA  '+n+'  -> '+x);}};

  // dibujar varios simbolos, diario y semanal
  for(const tf of ['d','w']){
    [...doc.querySelectorAll('.tf .chip[data-tf]')].find(c=>c.dataset.tf===tf)
      .dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
    for(let i=0;i<12;i++){
      const tr=doc.querySelectorAll('#tabla tbody tr')[i];
      if(tr)tr.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
      await new Promise(r=>setTimeout(r,10));
    }
  }
  const H=286,W=1200;
  const fuera=rects.filter(([x,y,ww,hh])=>!isFinite(x)||!isFinite(y)||!isFinite(ww)||!isFinite(hh)
    ||y<-1||y+hh>H+1||x<-2||x>W+2);
  ok('dibujo algo',rects.length>500,rects.length);
  ok('nada se sale del canvas',fuera.length===0,JSON.stringify(fuera.slice(0,3)));
  const fechasAbajo=textos.filter(([t,x,y])=>/^\d\d\/\d\d\/\d\d$/.test(t));
  ok('las fechas se escriben al pie',fechasAbajo.length>0&&fechasAbajo.every(([,,y])=>y>H-12),
     fechasAbajo.length);
  ok('sin excepciones',errores.length===0,errores.join('|'));

  // crosshair sobre el canvas
  const cv=doc.querySelector('#grafico');
  cv.getBoundingClientRect=()=>({left:0,top:0,width:1200,height:286});
  for(const x of [10,300,900,1199,-5,5000])
    cv.dispatchEvent(new w.MouseEvent('mousemove',{clientX:x,clientY:100,bubbles:true}));
  cv.dispatchEvent(new w.MouseEvent('mouseleave',{bubbles:true}));
  ok('el crosshair no rompe ni en los bordes',errores.length===0,errores.join('|'));

  // escapado
  const cuerpo=doc.querySelector('#tabla tbody').innerHTML;
  ok('el nombre hostil no inyecta HTML',cuerpo.indexOf('onerror=')<0&&cuerpo.indexOf('<img')<0);
  doc.querySelector('#btnInd').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  await new Promise(r=>setTimeout(r,120));
  const ind=doc.querySelector('#tablaInd').innerHTML;
  ok('un sector con comillas no rompe el data-ind',
     ind.indexOf('data-ind="Sector &quot;raro&quot;')>=0,ind.slice(0,140));
  // seleccionar EXPLICITAMENTE el simbolo hostil
  doc.querySelector('#btnInd').dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
  w.eval('limpiarFiltros()');
  await new Promise(r=>setTimeout(r,200));
  w.eval('seleccionar('+JSON.stringify(JSON.parse(datos).simbolos[0].t)+')');
  await new Promise(r=>setTimeout(r,200));
  const meta=doc.querySelector('#detMeta').innerHTML;
  ok('el detalle escapa el nombre',meta.indexOf('<img')<0&&meta.indexOf('&amp;')>=0,meta.slice(0,90));

  console.log(fallas?'\nFALLAS: '+fallas:'\ngrafico y escapado OK');
  process.exit(fallas?1:0);
},3500);
