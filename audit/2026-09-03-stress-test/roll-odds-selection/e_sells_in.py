"""(e) Which population produces 'sells in 8 min'?  Medians of time-to-sell across populations."""
import os
import json, statistics, collections
from load import load, TIERS
import ev_ref
p,now,rows=load()
def med(v): return statistics.median(v) if v else None
comp=[r for r in rows if r['elig'] and not r['stale'] and r['ri']>=0]
selmed={};rollsecs=[];rollsecs_t=collections.defaultdict(list);retsecs=[];retsecs_t=collections.defaultdict(list);wsecs=[]
for code,cat in p['categories'].items():
    t=cat['tier']
    for k,row in cat['rolls'].items():
        kk=ev_ref.roll_key(cat['slot'],row['exact_roll']['skills']);st=row['selected'] or row['fallback_48h']
        if st and st['median'] is not None:
            selmed[(code,kk)]=st['median']
            if st['median_time_to_sell_seconds'] is not None:
                rollsecs.append(st['median_time_to_sell_seconds']);rollsecs_t[t].append(st['median_time_to_sell_seconds']);wsecs+= [st['median_time_to_sell_seconds']]*st['count']
        rw=row['retained_window']
        if rw['median_time_to_sell_seconds'] is not None:retsecs.append(rw['median_time_to_sell_seconds']);retsecs_t[t].append(rw['median_time_to_sell_seconds'])
out={}
print('median over priced rolls of selected.median_time_to_sell_seconds: %.1f min (n=%d rolls); count-weighted %.1f min'%(med(rollsecs)/60,len(rollsecs),med(wsecs)/60))
print('median over rolls of retained_window.median_time_to_sell_seconds: %.1f min (n=%d)'%(med(retsecs)/60,len(retsecs)))
out['roll_median_selected_min']=med(rollsecs)/60;out['roll_median_retained_min']=med(retsecs)/60;out['roll_median_selected_countwtd_min']=med(wsecs)/60
allt=[r['tts'] for r in comp if r['tts'] is not None]
print('sale-weighted median tts, all comps-eligible non-stale retained sales: %.1f min (n=%d)'%(med(allt)/60,len(allt)))
w48=[r['tts'] for r in comp if r['tts'] is not None and r['sold']>=now-48*3600];w24=[r['tts'] for r in comp if r['tts'] is not None and r['sold']>=now-24*3600]
print('  48h window: %.1f min (n=%d); 24h window: %.1f min (n=%d)'%(med(w48)/60,len(w48),med(w24)/60,len(w24)))
out['sale_median_all_min']=med(allt)/60;out['sale_median_48h_min']=med(w48)/60;out['sale_median_24h_min']=med(w24)/60
print('\nper tier: median-of-roll-medians (selected) | retained | sale-wtd all | sales <= roll median | sales > roll median | sell-verdict rolls only')
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
sellset=set()
for t in range(1,7):
    for slot in ev_ref.SLOTS:
        v=m.slot_value(slot,t)
        for k,pr,sale,sells in v['rows']:
            if sells:sellset.add((ev_ref.item_code(slot,t),k))
out['tier']={}
for i,t in enumerate(TIERS):
    rs=[r for r in comp if r['tier']==i+1 and r['tts'] is not None and (r['code'],r['roll']) in selmed]
    lo=[r['tts'] for r in rs if r['price']<=selmed[(r['code'],r['roll'])]];hi=[r['tts'] for r in rs if r['price']>selmed[(r['code'],r['roll'])]]
    sv=[x for x in rollsecs_t[t]]
    sellrolls=[]
    for code,cat in p['categories'].items():
        if cat['tier']!=t:continue
        for k,row in cat['rolls'].items():
            kk=ev_ref.roll_key(cat['slot'],row['exact_roll']['skills']);st=row['selected'] or row['fallback_48h']
            if (code,kk) in sellset and st['median_time_to_sell_seconds'] is not None:sellrolls.append(st['median_time_to_sell_seconds'])
    out['tier'][t]={'roll_med_sel_min':med(sv)/60 if sv else None,'roll_med_ret_min':med(retsecs_t[t])/60,'sale_all_min':med([r['tts'] for r in rs])/60,'le_median_min':med(lo)/60,'gt_median_min':med(hi)/60,'n_le':len(lo),'n_gt':len(hi),'sell_rolls_min':med(sellrolls)/60 if sellrolls else None,'n_sell_rolls':len(sellrolls)}
    print('  %-10s rolls %.1f | ret %.1f | sales %.1f | <=med %.1f (n=%d) | >med %.1f (n=%d) | sell-verdict rolls %s (n=%d)'%(t,med(sv)/60,med(retsecs_t[t])/60,med([r['tts'] for r in rs])/60,med(lo)/60,len(lo),med(hi)/60,len(hi),'%.1f'%(med(sellrolls)/60) if sellrolls else '-',len(sellrolls)))
# overall <= vs >
lo=[r['tts'] for r in comp if r['tts'] is not None and (r['code'],r['roll']) in selmed and r['price']<=selmed[(r['code'],r['roll'])]]
hi=[r['tts'] for r in comp if r['tts'] is not None and (r['code'],r['roll']) in selmed and r['price']>selmed[(r['code'],r['roll'])]]
print('overall: sales <= roll median %.1f min (n=%d); > roll median %.1f min (n=%d)'%(med(lo)/60,len(lo),med(hi)/60,len(hi)))
out['le_median_min']=med(lo)/60;out['gt_median_min']=med(hi)/60
# candidate populations near 8 min
cands={}
for label,v in [('rolls_selected',rollsecs),('rolls_retained',retsecs),('sales_all',allt),('sales_48h',w48),('sales_24h',w24),('sales_le_med',lo),('sales_gt_med',hi)]:
    cands[label]=med(v)/60
for t in TIERS:
    cands['rolls_sel_'+t]=out['tier'][t]['roll_med_sel_min'];cands['sales_'+t]=out['tier'][t]['sale_all_min']
    cands['sellrolls_'+t]=out['tier'][t]['sell_rolls_min']
# sell-verdict rolls overall; and the knife/gun specific
sr=[]
for code,cat in p['categories'].items():
    for k,row in cat['rolls'].items():
        kk=ev_ref.roll_key(cat['slot'],row['exact_roll']['skills']);st=row['selected'] or row['fallback_48h']
        if (code,kk) in sellset and st['median_time_to_sell_seconds'] is not None:sr.append(st['median_time_to_sell_seconds'])
cands['sell_verdict_rolls_all']=med(sr)/60
# Cases-tab style: odds-weighted?  case-draw-weighted median of roll medians (each roll weight = odds*slotw/space)
wl=[]
for t in range(1,7):
    for slot in ev_ref.SLOTS:
        code=ev_ref.item_code(slot,t);cat=p['categories'][code];sp=len(ev_ref.roll_space(slot,t))
        w=ev_ref.CASE_TIER_ODDS[t-1]*ev_ref.CRAFT_SLOT_WEIGHT[slot]/sp
        for k,row in cat['rolls'].items():
            st=row['selected'] or row['fallback_48h']
            if st and st['median_time_to_sell_seconds'] is not None:wl.append((st['median_time_to_sell_seconds'],w))
wl.sort();tot=sum(w for _,w in wl);c=0
for s,w in wl:
    c+=w
    if c>=tot/2:cands['case_draw_weighted_roll_median']=s/60;break
print('\ncandidate populations (median minutes):')
for k,v in sorted(cands.items(),key=lambda x:(x[1] is None,x[1] or 0)):
    print('  %-34s %s'%(k,'%.1f'%v if v is not None else '-'))
out['candidates']=cands
json.dump(out,open(os.environ.get('EOUT','e_sells_in.json'),'w'),indent=1)
