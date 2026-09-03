"""(b),(c),(f) checks against the committed snapshot. Run: python3 analysis_snapshot.py"""
import sys, json, statistics, collections
from datetime import timedelta
sys.path.insert(0,'/home/user/-warera-case1-collector')
import collector as c
SNAP='/home/user/-warera-case1-collector/data/warera_case1_market.json'
p=json.load(open(SNAP)); now=c.parse_time(p['generated_at'])
tier_of={r['item_code']:r['tier'] for r in c.categories()}
print('generated_at',p['generated_at'])

# ---- (b) weighted_median is the lower median on even counts ----
lo=hi=eq=0; ex=None
for code,cat in p['categories'].items():
    for k,r in cat['rolls'].items():
        s=r['selected']
        if s['count']%2==0 and s['count']>0:
            if s['weighted_median']<s['median']: lo+=1; ex=ex or (code,k,s['count'],s['median'],s['weighted_median'])
            elif s['weighted_median']>s['median']: hi+=1
            else: eq+=1
print(f'(b) even-count selected windows: weighted_median<median {lo}, > {hi}, == {eq}; example {ex}')
# synthetic: two equal-weight sales at 1 and 3 -> weighted_median?
rows=[c.derive_transaction({'id':i,'item_code':'x','sold_at':c.stamp(now),'money':m,'quantity':1,'skills':{'a':1},'state':100,'max_state':100}) for i,m in (('a',1),('b',3))]
print('   synthetic equal weights prices 1,3 -> median',c.summarize(rows,now)['median'],'weighted_median',c.summarize(rows,now)['weighted_median'])

# ---- (b) censoring of median_time_to_sell by the stale filter, per tier, 48h window ----
by_tier=collections.defaultdict(lambda: {'all':[], 'kept':[]})
per_roll=[]  # (tier, published tts median, uncensored median, n_all, n_dropped)
for code,cat in p['categories'].items():
    txs=[c.unpack_transaction(r,code) for r in cat['transactions']]
    groups=collections.defaultdict(list)
    for t in txs:
        if not t['eligible_for_comps']: continue
        sold=c.parse_time(t['sold_at'])
        if sold < now-timedelta(hours=48): continue
        groups[t['roll_key']].append(t)
    for k,g in groups.items():
        d_all=[t['time_to_sell_seconds'] for t in g if t['time_to_sell_seconds'] is not None]
        d_kept=[d for d in d_all if d<=48*3600]
        by_tier[tier_of[code]]['all']+=d_all; by_tier[tier_of[code]]['kept']+=d_kept
        pub=cat['rolls'].get(k,{}).get('fallback_48h',{}).get('median_time_to_sell_seconds')
        if d_all and d_kept:
            per_roll.append((tier_of[code],pub,statistics.median(d_all),statistics.median(d_kept),len(d_all),len(d_all)-len(d_kept)))
print('(b) time-to-sell censoring, 48h window, eligible rows:')
print('   tier  n_all  dropped  share  median_kept(h)  median_all(h)  p90_kept(h) p90_all(h)')
def q(v,f):
    v=sorted(v); return v[min(len(v)-1,int(f*len(v)))]
for tier in ('basic','reinforced','advanced','elite','legendary','mythic'):
    a=by_tier[tier]['all']; k=by_tier[tier]['kept']
    print(f'   {tier:10s} {len(a):6d} {len(a)-len(k):7d} {(len(a)-len(k))/len(a):6.3%} {statistics.median(k)/3600:9.2f} {statistics.median(a)/3600:9.2f} {q(k,.9)/3600:9.1f} {q(a,.9)/3600:9.1f}')
alla=[d for t in by_tier.values() for d in t['all']]; allk=[d for t in by_tier.values() for d in t['kept']]
print(f'   {"all":10s} {len(alla):6d} {len(alla)-len(allk):7d} {(len(alla)-len(allk))/len(alla):6.3%} {statistics.median(allk)/3600:9.2f} {statistics.median(alla)/3600:9.2f} {q(allk,.9)/3600:9.1f} {q(alla,.9)/3600:9.1f}')
mism=sum(1 for r in per_roll if r[1] is not None and abs(r[1]-r[3])>1e-9)
print(f'   published fallback_48h.median_time_to_sell == median of kept rows for {len(per_roll)-mism}/{len(per_roll)} rolls (mismatch {mism})')
diff=[r for r in per_roll if r[5]>0]
print(f'   rolls with >=1 dropped sale: {len(diff)}; rolls where uncensored median > censored median: {sum(1 for r in diff if r[2]>r[3])}, ratio uncensored/censored median (median over rolls): {statistics.median(r[2]/r[3] for r in diff if r[3]>0):.3f}')
big=[r for r in diff if r[2]>2*r[3]]
print(f'   rolls where uncensored tts median is >2x the published one: {len(big)} (by tier {collections.Counter(r[0] for r in big)})')

# ---- (c) stale filter direction and magnitude, independent recomputation ----
print('(c) stale filter: recompute selected.median with and without stale_listing, per roll')
chg=[]; excl_above=excl_below=excl_eq=0; n_excl=0
for code,cat in p['categories'].items():
    txs=[c.unpack_transaction(r,code) for r in cat['transactions']]
    with_f=c.aggregate(txs,now)
    # monkeypatch: no stale filter
    orig=c.stale_listing; c.stale_listing=lambda tx,max_hours=None: False
    try: no_f=c.aggregate(txs,now)
    finally: c.stale_listing=orig
    for k in with_f:
        a=with_f[k]['selected']['median']; b=no_f[k]['selected']['median']
        if a is None or b is None: continue
        chg.append((tier_of[code],a,b,with_f[k]['selected']['count'],no_f[k]['selected']['count']))
        if a!=b:
            pass
    # excluded sales relative to filtered median
    for t in txs:
        if t['eligible_for_comps'] and c.stale_listing(t) and c.parse_time(t['sold_at'])>=now-timedelta(hours=48):
            m=with_f.get(t['roll_key'],{}).get('selected',{}).get('median')
            if m is None: continue
            n_excl+=1
            if t['unit_price']>m: excl_above+=1
            elif t['unit_price']<m: excl_below+=1
            else: excl_eq+=1
rel=[(b-a)/b for _,a,b,_,_ in chg if b]
changed=[r for r in chg if r[1]!=r[2]]
print(f'   rolls compared {len(chg)}, median changed on {len(changed)}; filtered lower on {sum(1 for r in changed if r[1]<r[2])}, higher on {sum(1 for r in changed if r[1]>r[2])}')
print(f'   (no_filter - filtered)/no_filter: mean {statistics.mean(rel):.4%}, median {statistics.median(rel):.4%}, p10 {q(rel,.1):.4%}, p90 {q(rel,.9):.4%}, max {max(rel):.3%}, min {min(rel):.3%}')
print(f'   excluded (48h, eligible, stale) {n_excl}: above filtered median {excl_above}, below {excl_below}, equal {excl_eq}')
for tier in ('basic','reinforced','advanced','elite','legendary','mythic'):
    r=[(b-a)/b for t,a,b,_,_ in chg if t==tier and b]
    print(f'   {tier:10s} n={len(r):4d} mean {statistics.mean(r):.4%} median {statistics.median(r):.4%} p10 {q(r,.1):.4%}')
# windows selected switching due to filter
sw=sum(1 for t,a,b,ca,cb in chg if (ca>=3)!=(cb>=3))
print(f'   rolls whose selected window flips (24h vs 48h) because of the filter: {sw}')

# ---- (f) live-vs-shard dedupe: floor vs round ----
n=0; bad=0
for code,cat in p['categories'].items():
    for r in cat['transactions']:
        dt=c.parse_time(r['sold_at']); ms=dt.microsecond//1000
        n+=1
        if ms>=500: bad+=1   # Math.round(ms/1000) != floor
print(f'(f) sales whose live key second (round) != shard second (floor): {bad}/{n} = {bad/n:.2%}')
# simulate mergeSales on the newest 100 rows of the busiest item as if they came live
code=max(p['categories'],key=lambda k:len(p['categories'][k]['transactions']))
rows=p['categories'][code]['transactions'][:100]
def shard_key(r): return (r['money'], int(c.parse_time(r['sold_at']).timestamp()))
def live_key(r): return (r['money'], round(c.parse_time(r['sold_at']).timestamp()))
seen={shard_key(r) for r in p['categories'][code]['transactions']}
dup=sum(1 for r in rows if live_key(r) not in seen)
print(f'   {code}: of its newest 100 sales replayed as a live page, {dup} would be added as new rows on top of their shard copies')
