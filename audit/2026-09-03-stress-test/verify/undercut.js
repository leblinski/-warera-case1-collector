// Extract the page's BigInt core verbatim and brute-force the Trends 'minimum undercut' path.
const fs=require('fs'); const src=fs.readFileSync('/home/user/WarEra-Selling-Price-Calc/test60.html','utf8');
const a=src.indexOf('function dec(str)'), b=src.indexOf('function coreDisplayed()');
let TAX='1'; const $=()=>({value:TAX});
const core=new Function('$', src.slice(a,b)+'; return {dec,decStr,toThousandths,taxFrac,undercutEntry,entryForDisplayed};')($);
function displayed(typedStr,tax){ // round-half-up(typed*(1+tax),3) as the money grid established
  const t=Math.round(parseFloat(typedStr)*1000); const d=t*(1+tax/100); return Math.round(d+1e-9)/1000; }
function round3(n){return Math.round((Number(n)+Number.EPSILON)*1000)/1000}
for(const tax of [0.5,1,2.5,5]){
  TAX=String(tax); let ties=0,lower=0,ok=0,ex=[];
  for(let u=2;u<=50000;u++){
    const floor=u/1000, target=round3(Math.max(.001,floor-.001)); // underFloor()
    const e=core.entryForDisplayed(String(target.toFixed(3)),false); if(!e) continue;
    const typed=core.decStr(e); const disp=displayed(typed,tax);
    if(Math.abs(disp-floor)<1e-9){ties++; if(ex.length<4) ex.push({floor,typed,disp});}
    else if(disp<floor) ok++; else lower++;
  }
  // and the core docket's beat path for comparison
  let beatTies=0; for(let u=2;u<=50000;u++){const floor=u/1000; const e=core.entryForDisplayed(floor.toFixed(3),true); if(!e)continue; const disp=displayed(core.decStr(e),tax); if(disp>=floor) beatTies++;}
  console.log(`tax ${tax}%: Trends typed figure displays AT the floor ${ties} of 49,999 floors (${(100*ties/49999).toFixed(2)}%), below ${ok}, above ${lower}; beat-path (core docket) failures ${beatTies}; examples ${JSON.stringify(ex)}`);
}
