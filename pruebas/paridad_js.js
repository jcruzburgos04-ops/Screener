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
  // --- Paragon: las dos EMAs de cada conjunto y el rVWAP ---
  // El conjunto W va con las longitudes tal cual (k=1, exacto) y el D con las
  // convertidas (k=2 y k=6, que son la rueda de EEUU y cripto).
  r.emaPine100=M.emaPine(b.c,100);
  r.emaPine200=M.emaPine(b.c,200);
  r.largos={};
  for(const k of [1,2,6,12])
    r.largos[k]=[M.largoEquivalente(100,k),M.largoEquivalente(200,k)];
  // el conjunto entero, que ademas del largo convertido aplica el warmup del ancla
  for(const k of [1,2,6]){
    const P=M.paragonSeries(b.c,100,200,k);
    r['parA'+k]=[P.rap,P.len];}
  // la caja: los cinco numeros, en tres ventanas distintas
  r.consol={};
  for(const N of [20,40,60]){const K=M.consolidacion(b,{consolBarras:N,consolAlto:18});
    r.consol[N]=[K.estado,K.rango,K.barras,K.pos,K.aprieta,K.estrechez];}
  for(const f of ['hl2','hlc3','close'])
    r['rvwap_'+f]=M.rvwapExpansivo(b,365,f).serie;
  out[k]=r;
}
fs.writeFileSync(__dirname+'/salida_js.json',JSON.stringify(out));
console.log('js listo');
