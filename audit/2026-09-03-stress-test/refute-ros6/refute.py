"""Independent check of ROS-6: strict flip pairing, resale price, per-roll 'sells in' impact."""
import json, statistics, collections, datetime, math
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
p=json.load(open(SNAP))
def ts(s): return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
now=ts(p['generated_at'])
TIERS=['basic','reinforced','advanced','elite','legendary','mythic']
def med(v): return statistics.median(v) if v else None
def sellsIn(secs):
    if secs is None or not secs>0: return '-'
    m=secs/60
    if m<1: return '<1m'
    if m<90: return '%dm'%round(m)
    h=m/60
    return (('%.1fh'%h) if h<10 else ('%dh'%round(h))) if h<48 else '%dd'%round(h/24)
rows=[]; ids=collections.Counter()
for code,cat in p['categories'].items():
    for tx in cat['transactions']:
        ids[tx['id']]+=1
        sold=ts(tx['sold_at']); off=ts(tx['offer_created_at'])
        tts=sold-off
        rows.append(dict(code=code,tier=cat['tier'],roll=json.dumps(tx.get('skills'),sort_keys=True),price=tx['money']/tx['quantity'],
                         sold=sold,tts=tts,seller=tx['seller_id'],buyer=tx['buyer_id'],id=tx['id'],elig=(tx['state']==tx['max_state'] and tx['quantity']==1 and tx['money']>0 and tx.get('skills')),rk=json.dumps({'skills':tx.get('skills')},separators=(',',':'),sort_keys=True)))
print('rows',len(rows),'dup ids',sum(1 for c in ids.values() if c>1),'elig',sum(bool(r['elig']) for r in rows),'neg tts',sum(r['tts']<0 for r in rows))
rows=[r for r in rows if r['elig'] and r['rk']]
rows.sort(key=lambda r:r['sold'])
# strict pairing: seller of later sale == buyer of an earlier sale of same (code, roll_key), each purchase used once
openb=collections.defaultdict(collections.deque); pair={}
for r in rows:
    q=openb[(r['code'],r['rk'],r['seller'])]
    if q: pair[r['id']]=q.popleft()
    openb[(r['code'],r['rk'],r['buyer'])].append(r)
# README-style: seller was ever an earlier buyer of same roll
seen=set(); ever=0
for r in rows:
    if (r['code'],r['rk'],r['seller']) in seen: ever+=1
    seen.add((r['code'],r['rk'],r['buyer']))
print('README-style ever-buyer:',ever,'(%.1f%%)'%(100*ever/len(rows)),'| one-to-one pairs:',len(pair),'(%.1f%%)'%(100*len(pair)/len(rows)))
print('\nweapons (strict):')
for code in ['knife','gun','rifle','sniper','tank','jet']:
    rs=[r for r in rows if r['code']==code]; fl=[r for r in rs if r['id'] in pair]
    ratio=[r['price']/pair[r['id']]['price'] for r in fl]; hold=[(r['sold']-pair[r['id']]['sold'])/3600 for r in fl]
    print('  %-7s sales %6d flips %4d (%.1f%%) resale/purchase med %.3f  hold med %.1fh  purchase below nonflip roll median: %s'%(code,len(rs),len(fl),100*len(fl)/len(rs),med(ratio),med(hold),''))
# per-roll selected tts and median with/without flips; count rolls whose displayed 'Sells in' string changes
stale=lambda r: r['tts']>48*3600
byroll=collections.defaultdict(list)
for r in rows:
    if not stale(r) and r['sold']>=now-168*3600: byroll[(r['code'],r['rk'])].append(r)
def selected(rs):
    w48=[r for r in rs if r['sold']>=now-48*3600]; w24=[r for r in w48 if r['sold']>=now-24*3600]
    use=w24 if len(w24)>=3 else w48
    if not use: return None
    return dict(n=len(use),median=med([r['price'] for r in use]),tts=med([r['tts'] for r in use]))
mism=0; tot=0
res=collections.defaultdict(lambda:dict(rolls=0,str_changed=0,tts_a=[],tts_b=[],price_changed=0,price_rel=[],flips_rolls=0))
for code,cat in p['categories'].items():
    for k,row in cat['rolls'].items():
        st=row['selected']
        if st['median'] is None: continue
        rs=byroll[(code,k)]; a=selected(rs); tot+=1
        if abs(a['median']-st['median'])>1e-9 or abs(a['tts']-st['median_time_to_sell_seconds'])>1: mism+=1
        b=selected([r for r in rs if r['id'] not in pair])
        t=cat['tier']; R=res[t]; R['rolls']+=1; R['tts_a'].append(a['tts'])
        if any(r['id'] in pair for r in rs): R['flips_rolls']+=1
        if b is None: R['str_changed']+=1; continue
        R['tts_b'].append(b['tts'])
        if sellsIn(a['tts'])!=sellsIn(b['tts']): R['str_changed']+=1
        if abs(a['median']-b['median'])>1e-9: R['price_changed']+=1; R['price_rel'].append(b['median']/a['median']-1)
print('\nreplication of selected median/tts vs collector: %d rolls, %d mismatches'%(tot,mism))
print('\n%-10s rolls rolls_with_flip  sellsIn_string_changes  medOfRollMed(min) with/without  price_median_changed  median rel price change'%'tier')
for t in TIERS:
    R=res[t]
    print('%-10s %5d %5d %5d (%.0f%%)   %6.1f / %6.1f   %4d   %+.2f%% (max abs %.2f%%)'%(t,R['rolls'],R['flips_rolls'],R['str_changed'],100*R['str_changed']/R['rolls'],med(R['tts_a'])/60,med(R['tts_b'])/60,R['price_changed'],100*(med(R['price_rel']) if R['price_rel'] else 0),100*max(map(abs,R['price_rel'])) if R['price_rel'] else 0))
# mythic detail: which rolls drive 213->168
my=[]
for code,cat in p['categories'].items():
    if cat['tier']!='mythic': continue
    for k,row in cat['rolls'].items():
        if row['selected']['median'] is None: continue
        rs=byroll[(code,k)]; a=selected(rs); b=selected([r for r in rs if r['id'] not in pair])
        if b and abs(a['tts']-b['tts'])>1: my.append((code,k,a['n'],a['tts']/60,b['tts']/60,sellsIn(a['tts']),sellsIn(b['tts'])))
print('\nmythic rolls whose selected tts changes when flips removed (%d):'%len(my))
for m in my: print('  ',m)
# magnitude of per-roll changes: tts ratio without/with, direction counts; price rel quantiles
print('\nper-roll tts ratio (noflip/with) among changed rolls; direction; price |rel| > 2%')
for t in TIERS:
    rat=[];up=dn=0;big=0;pr=[]
    for code,cat in p['categories'].items():
        if cat['tier']!=t: continue
        for k,row in cat['rolls'].items():
            if row['selected']['median'] is None: continue
            rs=byroll[(code,k)]; a=selected(rs); b=selected([r for r in rs if r['id'] not in pair])
            if b is None: continue
            if abs(a['tts']-b['tts'])>1:
                rat.append(b['tts']/max(a['tts'],1)); up+=b['tts']>a['tts']; dn+=b['tts']<a['tts']
            if abs(a['median']-b['median'])>1e-9:
                pr.append(abs(b['median']/a['median']-1)); big+=abs(b['median']/a['median']-1)>0.02
    rat.sort()
    q=lambda v,f: v[int(f*(len(v)-1))] if v else None
    print('  %-10s tts changed %3d (up %3d / down %3d) ratio p10 %.2f p50 %.2f p90 %.2f | price changed %3d, >2%%: %d, median |rel| %.2f%%'%(t,len(rat),up,dn,q(rat,.1) or 0,q(rat,.5) or 0,q(rat,.9) or 0,len(pr),big,100*(med(pr) or 0)))
