// On-screen figures: Sort tab per-1,000 rows for tiers 1,2,6; case swing line; sim "Expected" line at n=1000 with caseCount=1.
// Run: node screen_check.js
const {withPage,text}=require('/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit/harness');
withPage({tab:'cases'},async(page)=>{
  await page.waitForFunction(()=>{const v=document.getElementById('caseVerdict');return v&&v.textContent.trim()!=='—'},null,{timeout:15000});
  console.log('caseDetail:',await text(page,'#caseDetail'));
  console.log('caseSwing:',await text(page,'#caseSwing'));
  console.log('caseRows:',await text(page,'#caseRows'));
  // sim 1000 with caseCount=1 (default)
  await page.click('[data-sim="1000"]');
  await page.waitForFunction(()=>document.getElementById('simResult').textContent.indexOf('Expected')>=0,null,{timeout:15000});
  console.log('sim1000 (caseCount=1):',await text(page,'#simResult'),'|',await text(page,'#simHeadline'));
  // now caseCount=1000, sim 1
  await page.fill('#caseCount','1000');await page.dispatchEvent('#caseCount','input');
  console.log('caseDetail n=1000:',await text(page,'#caseDetail'));
  console.log('caseSwing n=1000:',await text(page,'#caseSwing'));
  await page.click('[data-sim="1000"]');
  await page.waitForFunction(()=>document.getElementById('simResult').textContent.indexOf('Expected')>=0,null,{timeout:15000});
  console.log('sim1000 (caseCount=1000):',await text(page,'#simResult'));
  await page.fill('#caseCount','9999');await page.dispatchEvent('#caseCount','input');
  console.log('caseDetail n=9999:',await text(page,'#caseDetail'));
  console.log('caseFoot n=9999:',await text(page,'#caseFoot'));
  console.log('caseSwing n=9999:',await text(page,'#caseSwing'));
  await page.click('#tabBar [data-tab="sort"]');
  for(const t of [1,2,6]){
    await page.click('#sortPick [data-sorttier="'+t+'"]');
    await page.waitForTimeout(200);
    console.log('SORT tier',t,':',await text(page,'#sortRows'));
    console.log('  foot:',await text(page,'#sortFoot'));
  }
}).catch(e=>{console.error('FAIL',e);process.exit(1)});
