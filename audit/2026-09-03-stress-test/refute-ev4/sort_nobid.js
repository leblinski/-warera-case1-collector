// What the Sort tab and Craft-tab scrap book show when scraps.best_bid is null.
const {withPage,text,DEFAULT_PUBLIC}=require('../harness'); const fs=require('fs');
(async()=>{
  const com=JSON.parse(fs.readFileSync(DEFAULT_PUBLIC+'/commodities.json','utf8')); com.commodities.scraps.order_book.best_bid=null; com.commodities.scraps.order_book.buy_orders=[];
  const idx=JSON.parse(fs.readFileSync(DEFAULT_PUBLIC+'/index.json','utf8')); idx.commodities.scraps.best_bid=null;
  const out={};
  for(const tier of [1,2]){
    await withPage({tab:'sort',overrides:{'commodities.json':com,'index.json':idx}},async(page)=>{
      await page.waitForFunction(()=>document.querySelectorAll('#sortRows .cut-row.tap').length>0,null,{timeout:15000}).catch(()=>{});
      await page.click('#sortPick [data-sorttier="'+tier+'"]').catch(()=>{});
      await page.waitForTimeout(500);
      out['sortTier'+tier]={rows:await text(page,'#sortRows'),detail:await text(page,'#sortDetail'),gate:await text(page,'#sortGateNote'),foot:await text(page,'#sortFoot')};
    });
  }
  await withPage({tab:'sort'},async(page)=>{
      await page.waitForFunction(()=>document.querySelectorAll('#sortRows .cut-row.tap').length>0,null,{timeout:15000}).catch(()=>{});
      await page.click('#sortPick [data-sorttier="2"]').catch(()=>{});
      await page.waitForTimeout(500);
      out.sortTier2_realBid={rows:await text(page,'#sortRows'),detail:await text(page,'#sortDetail'),gate:await text(page,'#sortGateNote')};
  });
  await withPage({tab:'craft',overrides:{'commodities.json':com,'index.json':idx}},async(page)=>{
      await page.waitForTimeout(3000);
      out.craftBooks=await text(page,'#craftBooks').catch(()=>null); out.craftRows=await text(page,'#craftRows'); out.craftFoot=await text(page,'#craftFoot').catch(()=>null);
  });
  console.log(JSON.stringify(out,null,1));
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
