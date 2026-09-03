// Confirms ev_ref counterfactuals against the rendered page: tax 0, missing scrap bid, either-join pct bar.
const {withPage,text,DEFAULT_PUBLIC}=require('../harness'); const fs=require('fs');
const wait=async(page)=>{await page.waitForFunction(()=>{const v=document.getElementById('caseVerdict');return v&&v.textContent.trim()!=='—'&&v.textContent.trim()!=='—'},null,{timeout:15000}).catch(()=>{})};
(async()=>{
  const out={};
  await withPage({tab:'cases',localStorage:{'warera-calc-tax':'0'}},async(page)=>{await wait(page);out.tax0={detail:await text(page,'#caseDetail'),rows:await text(page,'#caseRows')}});
  const com=JSON.parse(fs.readFileSync(DEFAULT_PUBLIC+'/commodities.json','utf8')); com.commodities.scraps.order_book.best_bid=null; com.commodities.scraps.order_book.buy_orders=[];
  const idx=JSON.parse(fs.readFileSync(DEFAULT_PUBLIC+'/index.json','utf8')); if(idx.commodities&&idx.commodities.scraps)idx.commodities.scraps.best_bid=null;
  await withPage({tab:'cases',overrides:{'commodities.json':com,'index.json':idx}},async(page)=>{await wait(page);out.noBid={detail:await text(page,'#caseDetail'),rows:await text(page,'#caseRows'),foot:await text(page,'#caseFoot')}});
  await withPage({tab:'cases',localStorage:{'warera-sort-min':JSON.stringify({abs:0.10,pct:0.5,join:'either'})}},async(page)=>{await wait(page);out.eitherPct05={detail:await text(page,'#caseDetail')}});
  await withPage({tab:'cases',localStorage:{'warera-sort-min':JSON.stringify({abs:0,pct:0,join:'both'})}},async(page)=>{await wait(page);out.bar0={detail:await text(page,'#caseDetail')}});
  console.log(JSON.stringify(out,null,1));
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
