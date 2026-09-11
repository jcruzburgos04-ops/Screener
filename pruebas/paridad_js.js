const M=require('./motor.js'), fs=require('fs');
const S=JSON.parse(fs.readFileSync(__dirname+'/series.json','utf8'));
const out={};
for(const [k,b] of Object.entries(S)){
  const r={};
  for(const modo of ['RSI','STOCHASTIC','ADX'])
   for(const ma of ['EMA','WMA','SMA','SMMA','HMA','ALMA']){
    const cfg={length:16,smooth:4,modo,ma_type:ma,alma_offset:0.85,alma_sigma:6};
    const A=M.calcAsh(b,cfg);
    r[modo+'|'+ma]={bulls:A.bulls,bears:A.bears,hist:A.hist};
  }
  r.rsi=M.rsi(b.c,14);
  r.atr=M.atr(b,14);
  r.adx=M.adx(b,14);
  r.adr=M.adrPct(b,20);
  r.cruce=M.barrasDesdeCruce(M.calcAsh(b,{length:16,smooth:4,modo:'RSI',
    ma_type:'EMA',alma_offset:0.85,alma_sigma:6}).hist);
  // --- combos de EMAs: las dos EMAs de cada uno ---
  // Anclados a 1D, o sea al timeframe de estas mismas barras: las longitudes
  // van tal cual y no hay conversion que verificar.
  r.emaPine21=M.emaPine(b.c,21);
  r.emaPine115=M.emaPine(b.c,115);
  r.emaPine300=M.emaPine(b.c,300);
  for(const [n,par] of [['c1',[21,34]],['c2',[55,115]],['c3',[300,600]]]){
    const P=M.comboSeries(b.c,par[0],par[1]);
    r[n]=[P.rap,P.len];}
  // la caja: los cinco numeros, en tres ventanas distintas
  r.consol={};
  for(const N of [20,40,60]){const K=M.consolidacion(b,{consolBarras:N,consolAlto:18});
    r.consol[N]=[K.estado,K.rango,K.barras,K.pos,K.aprieta,K.estrechez];}
  /* El rVWAP en las tres fuentes y en las cuatro ventanas. La ventana va por
     DIAS CALENDARIO, asi que esto tambien verifica que las dos implementaciones
     cuenten los dias igual -- que es justo donde estaba el error. */
  for(const f of ['hl2','hlc3','close'])
    for(const d of [7,30,90,365]){
      const R=M.rvwapDias(b,d,f);
      r['rvwap_'+f+'_'+d]=R.serie;
      r['rvllena_'+f+'_'+d]=R.llena.map(x=>x?1:0);}
  out[k]=r;
}
fs.writeFileSync(__dirname+'/salida_js.json',JSON.stringify(out));
console.log('js listo');
