// (d) Brute-force check of test60.html's BigInt price core, copied verbatim from lines 3890-3934 / 4116
// with $('tax').value replaced by a parameter. Run: node bigint_check.js
function dec(str){var s=String(str).trim(),neg=s.charAt(0)==='-';if(neg||s.charAt(0)==='+')s=s.slice(1);
  if(s===''||s==='.'||!/^\d*(\.\d*)?$/.test(s))return null;var p=s.split('.'),i=BigInt((p[0]||'0')+(p[1]||''));return {i:neg?-i:i,s:(p[1]||'').length}}
function decStr(d){var neg=d.i<0n,a=(neg?-d.i:d.i).toString();if(d.s===0)return(neg?'-':'')+a;while(a.length<=d.s)a='0'+a;return(neg?'-':'')+a.slice(0,a.length-d.s)+'.'+a.slice(a.length-d.s)}
function extractNumber(text){var m=String(text==null?'':text).match(/\d[\d.,\s]*\d|\d/);if(!m)return null;
  var s=m[0].replace(/\s/g,''),ld=s.lastIndexOf('.'),lc=s.lastIndexOf(',');
  if(ld>-1&&lc>-1){if(ld>lc)s=s.replace(/,/g,'');else s=s.replace(/\./g,'').replace(',','.')}else if(lc>-1)s=s.replace(',','.');
  var parts=s.split('.');if(parts.length>2)s=parts.slice(0,-1).join('')+'.'+parts[parts.length-1];return /^\d+(\.\d+)?$/.test(s)?s:null}
function toThousandths(R){if(R.s<=3)return R.i*(10n**BigInt(3-R.s));var div=10n**BigInt(R.s-3);return(R.i+div/2n)/div}
function taxFrac(taxStr){var T=dec(String(taxStr))||{i:0n,s:0};var den=100n*(10n**BigInt(T.s));return {num:den+T.i,den:den}}
function undercutEntry(i3,num,den){var target={i:i3*10n-5n,s:4};if(target.i<=0n)return null;var D=num*(10n**BigInt(target.s));var N=target.i*(10n**3n)*den;var q=N/D,e=(q*D===N)?q-1n:q;return e>0n?{i:e,s:3}:null}
function entryForDisplayed(displayed,beat,taxStr){var R=dec(String(displayed));if(!R||R.i<=0n)return null;var frac=taxFrac(taxStr),i3=toThousandths(R);
  if(beat)return undercutEntry(i3,frac.num,frac.den);var target={i:i3,s:3},D=frac.num*(10n**BigInt(target.s));var N=target.i*(10n**3n)*frac.den;var rounded=(2n*N+D)/(2n*D);return {i:rounded<=0n?1n:rounded,s:3}}
function s3For(buyI3,frac){return (10n*(buyI3+1n)*frac.num+5n*frac.den)/(10n*frac.den)+1n}

// Ground truth: the game displays round-half-up(typed*(1+tax), 3dp) (README: skip residues match half-up).
// Exact integer arithmetic: typed e in thousandths, tax as num/den. displayed3(e) = floor((e*num*2+den)/(2*den))  (half-up)
function disp(e,frac){return (2n*e*frac.num+frac.den)/(2n*frac.den)}
function dispHE(e,frac){ // half-even
  var N=e*frac.num,D=frac.den,q=N/D,r=N%D;
  if(2n*r>D)return q+1n; if(2n*r<D)return q; return (q%2n===0n)?q:q+1n }
const taxes=['0','0.5','1','2.5','5','12.5'];
const MAX=50000n;
let report={};
for(const tax of taxes){
  const frac=taxFrac(tax);
  // reachable displayed values and the set of typed that map to each
  const reach=new Map();
  for(let e=1n;e<=MAX+10000n;e++){const d=disp(e,frac);if(!reach.has(d))reach.set(d,[]);reach.get(d).push(e)}
  let undercutFail=[],undercutNotMax=[],undercutNull=0,nonbeatFail=[],nonbeatUnreach=0,nonbeatUnreachAbove=0,nonbeatUnreachBelow=0,s3Fail=[],s3NotMin=[],heTieDiff=0,buyI3Mismatch=[];
  for(let P=1n;P<=MAX;P++){
    const Pstr=decStr({i:P,s:3});
    const u=entryForDisplayed(Pstr,true,tax);
    if(!u){undercutNull++;}
    else{
      if(!(disp(u.i,frac)<P))undercutFail.push([Pstr,decStr(u)]);
      if(disp(u.i+1n,frac)<P)undercutNotMax.push([Pstr,decStr(u)]);
      if(dispHE(u.i+1n,frac)<P)heTieDiff++;
    }
    const nb=entryForDisplayed(Pstr,false,tax);
    const set=reach.get(P);
    if(set){ if(!set.includes(nb.i))nonbeatFail.push([Pstr,decStr(nb),set.map(x=>decStr({i:x,s:3}))]) }
    else{ nonbeatUnreach++; const d=disp(nb.i,frac); if(d>P)nonbeatUnreachAbove++; else nonbeatUnreachBelow++ }
    // flipCheckCore: buy displayed = P; s3 = smallest second offer S such that undercutEntry(S) >= P+1 (profit>=0.001 under the page's model)
    const s3=s3For(P,frac);
    const eAt=undercutEntry(s3,frac.num,frac.den), eBelow=undercutEntry(s3-1n,frac.num,frac.den);
    if(!eAt||eAt.i<P+1n)s3Fail.push([Pstr,decStr({i:s3,s:3}),eAt&&decStr(eAt)]);
    if(eBelow&&eBelow.i>=P+1n)s3NotMin.push([Pstr,decStr({i:s3,s:3}),decStr(eBelow)]);
    // buyI3 via float vs toThousandths (3-decimal inputs)
    if(BigInt(Math.round(Number(Pstr)*1000))!==P)buyI3Mismatch.push(Pstr);
  }
  report[tax]={undercutFail:undercutFail.length,undercutNotMax:undercutNotMax.length,undercutNull,halfEvenWouldAllowOneMore:heTieDiff,
    nonbeatFail:nonbeatFail.length,nonbeatUnreach,nonbeatUnreachAbove,nonbeatUnreachBelow,s3Fail:s3Fail.length,s3NotMin:s3NotMin.length,buyI3Mismatch:buyI3Mismatch.length,
    ex:{undercutFail:undercutFail.slice(0,3),undercutNotMax:undercutNotMax.slice(0,3),nonbeatFail:nonbeatFail.slice(0,3),s3Fail:s3Fail.slice(0,3),s3NotMin:s3NotMin.slice(0,3)}};
  // examples of unreachable handling at tax 1
  if(tax==='1'){const ex=[];for(const P of [1868n,2474n,2777n]){const nb=entryForDisplayed(decStr({i:P,s:3}),false,tax);ex.push([decStr({i:P,s:3}),'typed '+decStr(nb),'displays '+decStr({i:disp(nb.i,frac),s:3})])}report[tax].unreachExamples=ex;
    report[tax].sample={undercut_3_550:decStr(entryForDisplayed('3.550',true,tax)),nonbeat_3_550:decStr(entryForDisplayed('3.550',false,tax)),s3_for_buy_3_550:decStr({i:s3For(3550n,frac),s:3})}}
}
console.log(JSON.stringify(report,null,1));
// 4-decimal inputs: flipCheckCore's float buyI3 vs toThousandths
let mm=[];for(let i=1;i<=500000;i++){const s=(i/10000).toFixed(4);const a=BigInt(Math.round(Number(s)*1000)),b=toThousandths(dec(s));if(a!==b)mm.push([s,String(a),String(b)])}
console.log('4dp inputs 0.0001..50.0000: flipCheckCore buyI3 != toThousandths in',mm.length,'cases, e.g.',mm.slice(0,5));
// extractNumber locale
for(const s of ['1.234,56','1,234.56','1,234','1,234,567','1.234.567','12 345','3.55','0,5','1,5','  2,50 gold','3.5.5','1e3','−1.5','1.'])console.log('extractNumber(%j) = %j',s,extractNumber(s));
// bookLevels float keys
const snap=JSON.parse(require('fs').readFileSync('/home/user/-warera-case1-collector/data/warera_case1_market.json','utf8'));
let bad=0,tot=0;for(const c of Object.keys(snap.commodities)){const ob=snap.commodities[c].order_book;for(const side of ['buy_orders','sell_orders'])for(const o of ob[side]){tot++;const by={};by[Number(o.price)]=1;if(Number(Object.keys(by)[0])!==Number(o.price))bad++}}
console.log('bookLevels key roundtrip: ',bad,'of',tot,'order prices fail Number(String(p))===p');
// tax string parsing consistency
for(const t of ['1','1,5','1.5','','abc','-1'])console.log('tax %j -> Number %s, taxFrac %s/%s',t,Number(t),String(taxFrac(t).num),String(taxFrac(t).den));
