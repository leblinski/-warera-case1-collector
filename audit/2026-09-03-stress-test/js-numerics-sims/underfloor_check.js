// Price-tab quick-sale path: underFloor()=floor-0.001 then entryForDisplayed(.,false). How often does the typed figure display AT the floor (tie) instead of under it?
// Run: node underfloor_check.js
function dec(str){var s=String(str).trim(),neg=s.charAt(0)==='-';if(neg||s.charAt(0)==='+')s=s.slice(1);if(s===''||s==='.'||!/^\d*(\.\d*)?$/.test(s))return null;var p=s.split('.'),i=BigInt((p[0]||'0')+(p[1]||''));return {i:neg?-i:i,s:(p[1]||'').length}}
function decStr(d){var neg=d.i<0n,a=(neg?-d.i:d.i).toString();if(d.s===0)return(neg?'-':'')+a;while(a.length<=d.s)a='0'+a;return(neg?'-':'')+a.slice(0,a.length-d.s)+'.'+a.slice(a.length-d.s)}
function toThousandths(R){if(R.s<=3)return R.i*(10n**BigInt(3-R.s));var div=10n**BigInt(R.s-3);return(R.i+div/2n)/div}
function taxFrac(t){var T=dec(String(t))||{i:0n,s:0};var den=100n*(10n**BigInt(T.s));return {num:den+T.i,den:den}}
function undercutEntry(i3,num,den){var target={i:i3*10n-5n,s:4};if(target.i<=0n)return null;var D=num*(10n**BigInt(target.s));var N=target.i*(10n**3n)*den;var q=N/D,e=(q*D===N)?q-1n:q;return e>0n?{i:e,s:3}:null}
function entryForDisplayed(displayed,beat,tax){var R=dec(String(displayed));if(!R||R.i<=0n)return null;var frac=taxFrac(tax),i3=toThousandths(R);if(beat)return undercutEntry(i3,frac.num,frac.den);var target={i:i3,s:3},D=frac.num*(10n**BigInt(target.s));var N=target.i*(10n**3n)*frac.den;var rounded=(2n*N+D)/(2n*D);return {i:rounded<=0n?1n:rounded,s:3}}
function round3(v){return Math.round(v*1000)/1000}
function underFloor(floor){return round3(Math.max(.001,Number(floor)-.001))}
function disp(e,frac){return (2n*e*frac.num+frac.den)/(2n*frac.den)}
for(const tax of ['0.5','1','2.5','5']){
  const frac=taxFrac(tax);let tie=0,under=0,lower=0,tot=0,ex=[];
  for(let F=2n;F<=50000n;F++){
    const Fs=decStr({i:F,s:3});const target=underFloor(Fs).toFixed(3);
    const nb=entryForDisplayed(target,false,tax);const d=disp(nb.i,frac);
    const beat=entryForDisplayed(Fs,true,tax);
    tot++;
    if(d>=F){tie++;if(ex.length<5)ex.push({floor:Fs,quickSaleTarget:target,typed:decStr(nb),displays:decStr({i:d,s:3}),beatPathTyped:decStr(beat),beatDisplays:decStr({i:disp(beat.i,frac),s:3})})}
    else if(d===F-1n)under++;else lower++;
  }
  console.log('tax',tax,': floors 0.002..50.000 ->',tie,'ties the floor ('+(tie/tot*100).toFixed(2)+'%),',under,'display floor-0.001,',lower,'display lower;',JSON.stringify(ex.slice(0,3)));
}
