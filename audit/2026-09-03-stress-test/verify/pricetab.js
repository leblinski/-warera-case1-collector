const {withPage,text}=require('../harness');
const NOW=1788449450113; // generated_at
async function analyse(page,{tier,price,slot,attack,crit,stat}){
  await page.waitForFunction(()=>document.getElementById('caseVerdict').textContent.trim()!=='—',null,{timeout:20000});
  await page.fill('#price',String(price));
  await page.click('#rarityBtns [data-tier="'+tier+'"]');
  await page.click('#slotGrid [data-slot="'+slot+'"]');
  if(slot==='weapon'){ await page.fill('#rollGrid [data-rollinput="attack"]',String(attack)); await page.click('#rollGrid [data-rollkey="criticalChance"][data-roll="'+crit+'"]'); }
  else { const inp=await page.$('#rollGrid [data-rollinput]'); if(inp) await inp.fill(String(stat)); else await page.click('#rollGrid [data-roll="'+stat+'"]'); }
  await page.waitForFunction(()=>!document.getElementById('analyseBtn').disabled,null,{timeout:5000});
  await page.click('#analyseBtn');
  await page.waitForFunction(()=>/window/.test(document.getElementById('salesStatus').textContent),null,{timeout:20000});
  return {rollFacts:await text(page,'#rollFacts'),miniTarget:await text(page,'#miniTarget'),confidence:await text(page,'#confidence'),
          resultText:await text(page,'#resultText'),figure:await text(page,'#figure'),docketLabel:await text(page,'#docketLabel'),status:await text(page,'#salesStatus'),
          trendKicker:await text(page,'#trendMiniKicker'),trendPrice:await text(page,'#trendMiniPrice')};
}
(async()=>{
  for(const c of [{tier:1,price:4.2,slot:'weapon',attack:40,crit:5},{tier:1,price:1.8,slot:'weapon',attack:40,crit:5},{tier:4,price:68,slot:'boots',stat:25}]){
    const r=await withPage({now:NOW},p=>analyse(p,c));
    console.log('CASE',JSON.stringify(c)); console.log(JSON.stringify(r,null,1));
  }
  // tier inference from a typed 4.329 with nothing pinned
  const t=await withPage({now:NOW},async p=>{await p.waitForFunction(()=>document.getElementById('caseVerdict').textContent.trim()!=='—',null,{timeout:20000});
    await p.fill('#price','4.329'); const pressed=await p.$eval('#rarityBtns [aria-pressed="true"]',e=>e.getAttribute('data-tier'));
    return {pressed,note:await text(p,'#rarityNote'),scrap:await text(p,'#scrapVerdict'),head:await text(p,'#salesHead')}});
  console.log('TIER-INFERENCE 4.329',JSON.stringify(t));
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
