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
  out[k]=r;
}
fs.writeFileSync(__dirname+'/salida_js.json',JSON.stringify(out));
console.log('js listo');
