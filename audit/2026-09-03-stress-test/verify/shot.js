const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs=require('fs');
(async()=>{
  const html=fs.readFileSync('report.html','utf8');
  const b=await chromium.launch(); 
  for(const [name,scheme] of [['light','light'],['dark','dark']]){
    const ctx=await b.newContext({viewport:{width:1100,height:900},colorScheme:scheme});
    const p=await ctx.newPage();
    await p.route('**/*',r=>{const u=r.request().url(); if(u.startsWith('https://fonts.')) return r.fulfill({status:403,body:''}); r.continue()});
    await p.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">'+html+'</body></html>');
    await p.waitForTimeout(400);
    await p.screenshot({path:'verify/report_'+name+'.png',fullPage:false});
    // chart region
    const fig=await p.$('figure'); if(fig){await fig.scrollIntoViewIfNeeded(); await fig.screenshot({path:'verify/report_chart_'+name+'.png'})}
    const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
    console.log(name,'ok; body height',await p.evaluate(()=>document.body.scrollHeight),'chart svg present',!!(await p.$('#edgeChart svg')));
    await ctx.close();
  }
  await b.close();
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
