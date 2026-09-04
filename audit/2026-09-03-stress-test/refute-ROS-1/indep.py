"""Independent recomputation of ROS-1 (no ev_ref): craftSlotValue as coded (priced-only mean),
plus fills for unpriced rolls: scrap / nearest-worse priced same-band / fillQuiet-like / nearest-any.
Also a held-one-out bias test of the nearest-worse fill on priced rolls."""
import json,statistics
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
WEAPON=[(21,40,1,5),(51,60,6,10),(71,90,11,15),(101,130,16,20),(141,170,26,35),(221,300,41,50)]
RANGES={'helmet':('criticalDamages',[[1,15],[16,30],[31,50],[71,90],[91,110],[121,150]]),
 'boots':('dodge',[[1,5],[6,10],[11,15],[21,25],[31,40],[51,60]]),
 'chest':('armor',[[1,5],[6,10],[11,15],[21,30],[36,50],[56,70]]),
 'pants':('armor',[[1,5],[6,10],[11,15],[21,30],[36,50],[56,70]]),
 'gloves':('precision',[[1,5],[6,10],[11,15],[21,25],[31,40],[51,60]])}
WCODES=['knife','gun','rifle','sniper','tank','jet']
SLOTW={'weapon':0.30,'helmet':0.14,'chest':0.14,'boots':0.14,'gloves':0.14,'pants':0.14}
ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001];YIELD=[6,18,54,162,486,1458]
TAX=1.0;TM=1-TAX/100;BAR=0.10
bid=p['commodities']['scraps']['order_book']['best_bid'];ask=p['commodities']['case1']['order_book']['best_ask']
print('scrap bid',bid,'case ask',ask)
def space(slot,t):
    if slot=='weapon':
        a0,a1,c0,c1=WEAPON[t-1];return ['%d/%d'%(a,c) for a in range(a0,a1+1) for c in range(c0,c1+1)]
    lo,hi=RANGES[slot][1][t-1];return [str(v) for v in range(lo,hi+1)]
def key(slot,sk):
    if slot=='weapon': return None if sk.get('attack') is None or sk.get('criticalChance') is None else '%d/%d'%(sk['attack'],sk['criticalChance'])
    v=sk.get(RANGES[slot][0]);return None if v is None else str(v)
def code(slot,t): return WCODES[t-1] if slot=='weapon' else slot+str(t)
pos=lambda s,k:int(k.split('/')[0]) if s=='weapon' else int(k)
band=lambda s,k:k.split('/')[1] if s=='weapon' else ''
def rows(slot,t):
    cat=p['categories'][code(slot,t)];seen={}
    for r in cat['rolls'].values():
        k=key(slot,r['exact_roll']['skills'])
        if k: seen[k]=r
    dis=YIELD[t-1]*bid;need=dis+BAR;out=[]
    for k in space(slot,t):
        r=seen.get(k);st=r and (r.get('selected') or r.get('fallback_48h'));w=r and r.get('retained_window')
        d={'key':k,'net':None,'val':None,'wide':None}
        if st and st.get('median') is not None:
            n=st['median']*TM;d['net']=n;d['val']=n if n>need else dis
        elif w and w.get('median') is not None:
            n=w['median']*TM;d['wide']={'net':n,'val':n if n>need else dis,'sell':n>need}
        out.append(d)
    return out,dis,need
def worse_priced(out,slot,x,use_wide=False):
    best=None
    for y in out:
        ok=y['net'] is not None or (use_wide and y['wide'])
        if not ok or band(slot,y['key'])!=band(slot,x['key']) or pos(slot,y['key'])>=pos(slot,x['key']):continue
        if best is None or pos(slot,y['key'])>pos(slot,best['key']):best=y
    return best
def slot_net(slot,t,mode):
    out,dis,need=rows(slot,t);vals=[]
    for x in out:
        if x['net'] is not None: vals.append(x['val']);continue
        if mode=='page':continue
        if mode=='scrap': vals.append(dis)
        elif mode=='worse':
            b=worse_priced(out,slot,x);vals.append(b['val'] if b else dis)
        elif mode=='fillquiet':
            if x['wide']: vals.append(x['wide']['val']);continue
            b=worse_priced(out,slot,x,True)
            vals.append((b['val'] if b['net'] is not None else b['wide']['val']) if b else dis)
    return sum(vals)/len(vals) if vals else None
res={}
for mode in ['page','scrap','worse','fillquiet']:
    gross=0;tiers=[]
    for t in range(1,7):
        ws=ns=0
        for slot in SLOTW:
            n=slot_net(slot,t,mode)
            if n is None:continue
            ws+=SLOTW[slot];ns+=SLOTW[slot]*n
            res.setdefault(code(slot,t),{})[mode]=n
        tiers.append(ns/ws);gross+=ODDS[t-1]*ns/ws
    print('%-10s gross %.4f edge %+.4f (%+.2f%%) tiers %s'%(mode,gross,gross-ask,(gross-ask)/ask*100,' '.join('%.3f'%x for x in tiers)))
for c in ['knife','tank','jet']:
    print(c,{m:round(v,3) for m,v in res[c].items()})
# knife details
out,dis,need=rows('weapon',1)
pr=[x for x in out if x['net'] is not None];un=[x for x in out if x['net'] is None]
print('knife priced',len(pr),'unpriced',len(un),'wide-only',sum(1 for x in un if x['wide']),'never',sum(1 for x in un if not x['wide']))
print('knife 40/5 net',[round(x['net'],3) for x in pr if x['key']=='40/5'],'priced mean val',round(statistics.mean(x['val'] for x in pr),4),'median val',round(statistics.median(x['val'] for x in pr),4))
print('knife priced keys:',' '.join(x['key'] for x in pr))
# fillQuiet verdict tally for knife unpriced
tal={'sell':0,'break':0,'none':0}
for x in un:
    if x['wide']: tal['sell' if x['wide']['sell'] else 'break']+=1;continue
    b=worse_priced(out,'weapon',x,True)
    if not b: tal['none']+=1
    else: tal['sell' if (b['val']>dis if b['net'] is not None else b['wide']['sell']) else 'break']+=1
print('knife fillQuiet verdicts',tal)
# held-one-out bias of nearest-worse fill on priced rolls (same band)
for slot,t,name in [('weapon',1,'knife'),('weapon',5,'tank'),('weapon',6,'jet'),('weapon',3,'rifle')]:
    out,dis,need=rows(slot,t);errs=[];under=0;n=0
    for x in out:
        if x['net'] is None:continue
        b=worse_priced(out,slot,x)
        if not b:continue
        n+=1;errs.append(b['val']-x['val']);under+=b['val']<=x['val']
    print('%s held-one-out worse-fill: n=%d mean err %+.4f (%.1f%% of actual mean) lower-bound %.0f%%'%(name,n,statistics.mean(errs),100*statistics.mean(errs)/statistics.mean(x['val'] for x in out if x['net'] is not None),100*under/n))
