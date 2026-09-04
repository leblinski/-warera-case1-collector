// Does the rendered Sort tab print a price in the "List at" column for quiet (week-only) rolls?
const {withPage,text}=require('/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/harness.js');
withPage({tab:'sort'},async(page)=>{
  await page.waitForFunction(()=>document.querySelectorAll('#sortRows .cut-row.tap').length>0,null,{timeout:20000});
  await page.click('#sortPick [data-sorttier="1"]');
  await page.waitForFunction(()=>!!document.querySelector('#sortRows [data-cut="1-weapon"]'),null,{timeout:10000});
  const row=await page.$('#sortRows [data-cut="1-weapon"]'); await row.click();
  const res=await page.evaluate(()=>{
    const g=document.getElementById('cutd-1-weapon');
    const head=Array.from(g.querySelectorAll('.cut-line.head span')).map(e=>e.textContent);
    const quiet=Array.from(g.querySelectorAll('.cut-line.quiet')).map(e=>Array.from(e.children).map(c=>c.textContent));
    const priced=Array.from(g.querySelectorAll('.cut-line.yes,.cut-line.no')).slice(0,3).map(e=>Array.from(e.children).map(c=>c.textContent));
    const withPrice=quiet.filter(r=>/^\d/.test(r[1])).length, dash=quiet.filter(r=>r[1]==='—').length;
    return {head,quietRows:quiet.length,quietWithPrice:withPrice,quietDash:dash,sampleQuiet:quiet.slice(0,4).concat(quiet.filter(r=>r[1]==='—').slice(0,3)),samplePriced:priced,
      quietCss:getComputedStyle(g.querySelector('.cut-line.quiet span:nth-child(2)')).color+' / opacity '+getComputedStyle(g.querySelector('.cut-line.quiet')).opacity,
      pricedCss:getComputedStyle(g.querySelector('.cut-line.yes span:nth-child(2)')).color};
  });
  // heat readout for a wide-only knife roll: find a quiet cell that is not guess/none
  const cell=await page.$('#cutd-1-weapon .heat-cell.quiet:not(.guess):not(.none), #cutd-1-weapon .heat-cell.wide');
  if(cell){await cell.click(); res.wideReadout=await text(page,'#heatread-1-weapon'); res.wideCellCls=await cell.getAttribute('class');}
  // count all quiet rows with price across every tier/slot
  let all={rows:0,price:0,dash:0};
  for(const t of [1,2,3,4,5,6]){
    await page.click('#sortPick [data-sorttier="'+t+'"]');
    await page.waitForFunction((t)=>!!document.querySelector('#sortRows [data-cut="'+t+'-weapon"]'),t,{timeout:10000});
    for(const s of ['weapon','helmet','chest','gloves','pants','boots']){
      const r=await page.$('#sortRows [data-cut="'+t+'-'+s+'"]'); if(!r) continue;
      const open=await page.evaluate((id)=>{const d=document.getElementById('cutd-'+id);return d&&!d.hidden},t+'-'+s);
      if(!open) await r.click();
      const c=await page.evaluate((id)=>{const g=document.getElementById('cutd-'+id);const q=Array.from(g.querySelectorAll('.cut-line.quiet'));return {rows:q.length,price:q.filter(e=>/^\d/.test(e.children[1].textContent)).length,dash:q.filter(e=>e.children[1].textContent==='—').length}},t+'-'+s);
      all.rows+=c.rows;all.price+=c.price;all.dash+=c.dash;
    }
  }
  res.allTiers=all;
  console.log(JSON.stringify(res,null,1));
}).catch(e=>{console.error('FAIL',e);process.exit(1)});
