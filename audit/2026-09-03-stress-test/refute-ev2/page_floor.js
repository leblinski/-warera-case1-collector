// Rendered-page check: Price-tab dismantle floor (listed/typed) vs Sort-tab 'list above' for tier 3 (Rare) and tier 1.
const {withPage,text}=require('../harness');
(async()=>{
  const out={};
  for (const [tier,price] of [[3,'12.100'],[1,'1.400'],[2,'4.100']]) {
    await withPage({},async(page)=>{
      await page.waitForFunction(()=>{const s=document.getElementById('scrapNote');return s&&s.textContent.includes('live')},null,{timeout:15000}).catch(()=>{});
      await page.fill('#price',price);
      await page.click('#rarityBtns [data-tier="'+tier+'"]');
      await page.click('#goBtn').catch(()=>{});
      await page.waitForTimeout(800);
      const r={tier,price,scrapNote:await text(page,'#scrapNote'),scrapPrice:await page.inputValue('#scrapPrice'),beat:await page.isChecked('#beatMode')};
      r.listed={verdict:await text(page,'#scrapVerdict'),detail:await text(page,'#scrapDetail'),rows:await text(page,'#scrapRows'),docket:await text(page,'#docketHint'),figure:await text(page,'#coreFigure')};
      await page.click('.scrap-tabs [data-view="typed"]'); await page.waitForTimeout(300);
      r.typed={verdict:await text(page,'#scrapVerdict'),rows:await text(page,'#scrapRows'),note:await text(page,'#scrapTabNote')};
      await page.click('#tabBar [data-tab="sort"]'); await page.waitForTimeout(800);
      await page.click('#sortPick [data-sorttier="'+tier+'"]').catch(()=>{}); await page.waitForTimeout(500);
      const heads=await page.$$eval('.cut-floor',els=>els.map(e=>e.textContent.trim()));
      r.sort={floors:heads,cutCard:await text(page,'#cutCardText')};
      out['t'+tier]=r;
    });
  }
  console.log(JSON.stringify(out,null,1));
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
