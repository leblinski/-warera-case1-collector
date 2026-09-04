// Independent DOM check: class of the four cells, readout text on tap, and the list row of the SAME roll (by crit band).
const {withPage,text}=require('/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/harness.js');
const targets={2:['60/10','60/6'],3:['80/14','87/11','89/11','79/15']};
withPage({tab:'sort'},async(page)=>{
  await page.waitForFunction(()=>document.querySelectorAll('#sortRows .cut-row.tap').length>0,null,{timeout:20000});
  const out={sortMin:await page.evaluate(()=>localStorage.getItem('warera-sort-min')),tax:await page.$eval('#tax',e=>e.value),gate:await text(page,'#sortGateNote')};
  for(const t of Object.keys(targets)){
    await page.click('#sortPick [data-sorttier="'+t+'"]');
    const id=t+'-weapon';
    await page.waitForFunction((id)=>!!document.querySelector('#sortRows [data-cut="'+id+'"]'),id,{timeout:10000});
    await (await page.$('#sortRows [data-cut="'+id+'"]')).click();
    out['tier'+t]={rule:await text(page,'#sortRows [data-cut="'+id+'"] .cut-rule'),cells:{}};
    for(const k of targets[t]){
      const cell=await page.$('#cutd-'+id+' [data-heat="'+id+'|'+k+'"]');
      const cls=await cell.getAttribute('class'); const fill=await cell.evaluate(e=>e.style.getPropertyValue('--fill'));
      await cell.click();
      const readout=await text(page,'#heatread-'+id);
      const row=await page.evaluate(([id,k])=>{const [a,c]=k.split('/');let band=null;
        for(const e of document.querySelectorAll('#cutd-'+id+' .cut-band, #cutd-'+id+' .cut-line')){
          if(e.classList.contains('cut-band')){band=e.textContent;continue}
          if(band==='crit '+c&&e.firstChild.textContent===a)return e.className+' | '+e.textContent}
        return null},[id,k]);
      out['tier'+t].cells[k]={cls,fill,readout,row};
    }
  }
  console.log(JSON.stringify(out,null,1));
}).catch(e=>{console.error('FAIL',e);process.exit(1)});
