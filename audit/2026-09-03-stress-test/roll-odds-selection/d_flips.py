"""(d) Selection bias of completed sales: strict flip matching, flip share by tier, price of
resales vs first sales, time-to-sell with and without flips, and a survivorship bound."""
import json, statistics, collections
from load import load, TIERS
import ev_ref
p,now,rows=load()
def med(v): return statistics.median(v) if v else None
comp=[r for r in rows if r['elig'] and r['ri']>=0]  # includes stale (for tts distributions); comps filter applied where the collector applies it
# ---- (1) strict flip matching, weapons only (roll space >= 50)
space={c:len(ev_ref.roll_space(p['categories'][c]['slot'],TIERS.index(p['categories'][c]['tier'])+1)) for c in p['categories']}
big={c for c,s in space.items() if s>=50}
print('items with roll space >=50:',sorted(big))
by=sorted(comp,key=lambda r:r['sold'])
open_buys=collections.defaultdict(list);pair={}  # resale id -> purchase row
for r in by:
    key=(r['code'],r['roll'],r['seller'])
    if open_buys[key]:
        b=open_buys[key].pop(0);pair[r['id']]=b
    open_buys[(r['code'],r['roll'],r['buyer'])].append(r)
loose=set(pair)  # all items
strict={i for i in pair if pair[i]['code'] in big}
print('loose flips (all items, first-come pairing): %d of %d retained eligible sales (%.1f%%)'%(len(loose),len(comp),100*len(loose)/len(comp)))
out={'flip_share':{}}
print('\n%-6s %-9s %6s %6s %6s  %s'%('tier','item','sales','flips','share','median resale/purchase price ratio | resale vs roll-median (nonflip) ratio | median hold h'))
for c in sorted(big,key=lambda c:TIERS.index(p['categories'][c]['tier'])):
    rs=[r for r in comp if r['code']==c];fl=[r for r in rs if r['id'] in strict]
    ratios=[r['price']/pair[r['id']]['price'] for r in fl]
    nfmed=collections.defaultdict(list)
    for r in rs:
        if r['id'] not in strict and not r['stale']: nfmed[r['roll']].append(r['price'])
    rel=[r['price']/med(nfmed[r['roll']]) for r in fl if nfmed.get(r['roll'])]
    firstrel=[r['price']/med(nfmed[r['roll']]) for r in rs if r['id'] not in strict and nfmed.get(r['roll']) and not r['stale']]
    hold=[(r['sold']-pair[r['id']]['sold'])/3600 for r in fl]
    t=p['categories'][c]['tier']
    out['flip_share'][c]={'sales':len(rs),'flips':len(fl),'share':len(fl)/len(rs),'resale_over_purchase':med(ratios),'resale_over_rollmed':med(rel),'first_over_rollmed':med(firstrel),'hold_h':med(hold)}
    print('%-6s %-9s %6d %6d %5.1f%%  %.3f | %.3f (first sales %.3f) | %.1fh'%(t[:5],c,len(rs),len(fl),100*len(fl)/len(rs),med(ratios) or 0,med(rel) or 0,med(firstrel) or 0,med(hold) or 0))
# by tier, all items, loose matching
print('\nloose flip share by tier (all items):')
for i,t in enumerate(TIERS):
    rs=[r for r in comp if r['tier']==i+1];fl=[r for r in rs if r['id'] in loose]
    print('  %-10s %6d sales  %5d flips  %5.1f%%'%(t,len(rs),len(fl),100*len(fl)/len(rs)))
    out['flip_share']['tier_'+t]={'sales':len(rs),'flips':len(fl)}
# ---- (2) time to sell with and without flips: replicate selected.median_time_to_sell_seconds per roll
def selected_tts(rs):
    rs=[r for r in rs if not r['stale'] and r['sold']>=now-48*3600]
    rec=[r for r in rs if r['sold']>=now-24*3600]
    use=rec if len(rec)>=3 else rs
    d=[r['tts'] for r in use if r['tts'] is not None]
    return med(d),len(use)
byroll=collections.defaultdict(list)
for r in comp: byroll[(r['code'],r['roll'])].append(r)
# check replication against collector
mism=0;tot=0
for code,cat in p['categories'].items():
    for k,row in cat['rolls'].items():
        kk=ev_ref.roll_key(cat['slot'],row['exact_roll']['skills']);st=row['selected']
        if st['median'] is None:continue
        mine,n=selected_tts(byroll[(code,kk)]);tot+=1
        if st['median_time_to_sell_seconds'] is not None and mine is not None and abs(mine-st['median_time_to_sell_seconds'])>1:mism+=1
print('\nreplication of selected.median_time_to_sell_seconds: %d rolls, %d mismatches'%(tot,mism))
print('\n%-10s %8s %8s %8s | %8s %8s'%('tier','rolls','page(m)','noflip(m)','sale-wtd','noflip'))
out['tts']={}
for i,t in enumerate(TIERS):
    a=[];b=[];sa=[];sb=[]
    for (code,k),rs in byroll.items():
        if p['categories'][code]['tier']!=t:continue
        m1,_=selected_tts(rs);m2,_=selected_tts([r for r in rs if r['id'] not in loose])
        if m1 is not None:a.append(m1)
        if m2 is not None:b.append(m2)
        for r in rs:
            if not r['stale'] and r['sold']>=now-48*3600 and r['tts'] is not None:
                sa.append(r['tts'])
                if r['id'] not in loose:sb.append(r['tts'])
    out['tts'][t]={'rolls':len(a),'page_median_of_roll_medians_min':med(a)/60,'noflip':med(b)/60,'sale_wtd':med(sa)/60,'sale_wtd_noflip':med(sb)/60}
    print('%-10s %8d %8.1f %8.1f | %8.1f %8.1f'%(t,len(a),med(a)/60,med(b)/60,med(sa)/60,med(sb)/60))
fl_t=[r['tts'] for r in comp if r['id'] in loose and r['tts'] is not None];nf_t=[r['tts'] for r in comp if r['id'] not in loose and r['tts'] is not None]
print('median tts: flips %.1f min, non-flips %.1f min'%(med(fl_t)/60,med(nf_t)/60))
out['tts']['flip_median_min']=med(fl_t)/60;out['tts']['nonflip_median_min']=med(nf_t)/60
# ---- (3) survivorship bound: among ALL retained sales (incl stale) priced >= the roll's selected median, share with tts>24h / >48h
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
selmed={}
for code,cat in p['categories'].items():
    for k,row in cat['rolls'].items():
        st=row['selected'] or row['fallback_48h']
        if st and st['median'] is not None:selmed[(code,ev_ref.roll_key(cat['slot'],row['exact_roll']['skills']))]=st['median']
print('\nsurvivorship (sales at/above roll selected median, all retained incl. stale): share tts>24h, >48h, >7d; and below-median for contrast')
out['surv']={}
for i,t in enumerate(TIERS):
    hi=[r['tts'] for r in comp if r['tier']==i+1 and (r['code'],r['roll']) in selmed and r['price']>=selmed[(r['code'],r['roll'])] and r['tts'] is not None]
    lo=[r['tts'] for r in comp if r['tier']==i+1 and (r['code'],r['roll']) in selmed and r['price']<selmed[(r['code'],r['roll'])] and r['tts'] is not None]
    # listings created >= 48h before snapshot only (so a 48h sale could have been observed)
    hi_old=[r['tts'] for r in comp if r['tier']==i+1 and (r['code'],r['roll']) in selmed and r['price']>=selmed[(r['code'],r['roll'])] and r['tts'] is not None and r['sold']-r['tts']<=now-48*3600]
    f=lambda v,h:sum(x>h*3600 for x in v)/len(v) if v else float('nan')
    out['surv'][t]={'n_hi':len(hi),'hi_gt24':f(hi,24),'hi_gt48':f(hi,48),'hi_gt168':f(hi,168),'n_lo':len(lo),'lo_gt24':f(lo,24),'lo_gt48':f(lo,48),'hi_old_gt48':f(hi_old,48),'n_hi_old':len(hi_old)}
    print('  %-10s n=%6d  >=median: >24h %.1f%% >48h %.1f%% >7d %.1f%% | <median (n=%d): >24h %.1f%% >48h %.1f%% | listed>=48h ago (n=%d): >48h %.1f%%'%(t,len(hi),100*f(hi,24),100*f(hi,48),100*f(hi,168),len(lo),100*f(lo,24),100*f(lo,48),len(hi_old),100*f(hi_old,48)))
# haircut: sell-verdict rolls valued (1-u)*net + u*scrap
def gross_with_u(ufun):
    g=0
    for t in range(1,7):
        ws=ns=0;dis=m.dismantle(t)
        for slot in ev_ref.SLOTS:
            v=m.slot_value(slot,t);w=ev_ref.CRAFT_SLOT_WEIGHT[slot]
            u=ufun(t)
            vals=[((1-u)*sale+u*dis) if sells else dis for k,pr,sale,sells in v['rows']]
            ws+=w;ns+=w*sum(vals)/len(vals)
        g+=ev_ref.CASE_TIER_ODDS[t-1]*ns/ws
    return g
cost=ev_ref.craft_walk(p['commodities']['case1']['order_book'],1)['unit']
base=gross_with_u(lambda t:0)
print('\nhaircut sensitivity (case gross, edge vs cost %.3f; base %.4f):'%(cost,base))
out['haircut']={}
for label,uf in [('u=tier share >24h (>=median)',lambda t:out['surv'][TIERS[t-1]]['hi_gt24']),
                 ('u=tier share >48h (>=median)',lambda t:out['surv'][TIERS[t-1]]['hi_gt48']),
                 ('u=2x share >48h',lambda t:2*out['surv'][TIERS[t-1]]['hi_gt48']),
                 ('u=3x share >48h',lambda t:3*out['surv'][TIERS[t-1]]['hi_gt48']),
                 ('u=5% flat',lambda t:0.05),('u=10% flat',lambda t:0.10),('u=20% flat',lambda t:0.20),('u=30% flat',lambda t:0.30),('u=50% flat',lambda t:0.5)]:
    g=gross_with_u(uf);out['haircut'][label]={'gross':g,'pct':(g-cost)/cost*100}
    print('  %-32s gross %.4f  edge %+.4f  pct %+.2f%%'%(label,g,g-cost,(g-cost)/cost*100))
# break-even u (flat)
lo_,hi_=0,1
for _ in range(40):
    mid=(lo_+hi_)/2
    if gross_with_u(lambda t:mid)>cost:lo_=mid
    else:hi_=mid
print('  break-even flat u = %.1f%%'%(100*lo_));out['haircut']['breakeven_u']=lo_
json.dump(out,open('d_flips.json','w'),indent=1)
