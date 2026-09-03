// Playwright check of the rendered Sort tab against the Python mirror: cut-rule text, heat-cell classes,
// quiet rows, and the gun 60/10 cell (green on the grid, "break" in the readout).
const {withPage,text}=require('/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/harness.js');
const bar=process.argv[2]||'0.1';
withPage({tab:'sort',localStorage:{'warera-sort-min':JSON.stringify({abs:Number(bar),pct:0,join:'both'})}},async(page)=>{
  await page.waitForFunction(()=>document.querySelectorAll('#sortRows .cut-row.tap').length>0,null,{timeout:20000});
  const out={bar};
  for(const t of [1,2,3,6]){
    await page.click('#sortPick [data-sorttier="'+t+'"]');
    await page.waitForFunction((t)=>!!document.querySelector('#sortRows [data-cut="'+t+'-weapon"]'),t,{timeout:10000});
    const id=t+'-weapon';
    const rule=await text(page,'#sortRows [data-cut="'+id+'"] .cut-rule');
    const row=await page.$('#sortRows [data-cut="'+id+'"]'); await row.click();
    const counts=await page.evaluate((id)=>{const g=document.getElementById('cutd-'+id);return {
      cells:g.querySelectorAll('.heat-cell').length, guess:g.querySelectorAll('.heat-cell.guess').length,
      none:g.querySelectorAll('.heat-cell.none').length, br:g.querySelectorAll('.heat-cell.br').length,
      quietRows:g.querySelectorAll('.cut-line.quiet').length, yes:g.querySelectorAll('.cut-line.yes').length, no:g.querySelectorAll('.cut-line.no').length,
      likeRows:Array.from(g.querySelectorAll('.cut-line.quiet .why')).filter(e=>/^like /.test(e.textContent)).length,
      weekRows:Array.from(g.querySelectorAll('.cut-line.quiet .why')).filter(e=>/^this week/.test(e.textContent)).length,
      noneRows:Array.from(g.querySelectorAll('.cut-line.quiet .why')).filter(e=>/none traded/.test(e.textContent)).length}},id);
    out['tier'+t]={rule,counts};
    if(t===2){
      const cell=await page.$('#cutd-'+id+' [data-heat="'+id+'|60/10"]');
      const cls=await cell.getAttribute('class'); await cell.click();
      out.gun6010={cls,readout:await text(page,'#heatread-'+id),
        listRow:await page.evaluate((id)=>{const r=Array.from(document.querySelectorAll('#cutd-'+id+' .cut-line')).find(e=>e.firstChild.textContent==='60'&&e.parentNode&&true);return r?r.className+' | '+r.textContent:null},id)};
    }
    if(t===1){const cell=await page.$('#cutd-'+id+' [data-heat="'+id+'|30/1"]');if(cell){await cell.click();out.knife3001={cls:await cell.getAttribute('class'),readout:await text(page,'#heatread-'+id)}}}
  }
  await page.click('#tabBar [data-tab="price"]').catch(()=>{});
  await page.click('#rarityBtns [data-tier="1"]').catch(()=>{});
  out.cutCard=await text(page,'#cutCardText');
  console.log(JSON.stringify(out,null,1));
}).catch(e=>{console.error('FAIL',e);process.exit(1)});
