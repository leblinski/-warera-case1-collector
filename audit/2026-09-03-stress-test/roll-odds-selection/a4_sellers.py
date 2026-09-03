"""(a) cont.: is the max-roll excess concentrated in a few sellers (selection/dumping) or spread
like the rest (as an RNG bias would be)?  Unique-seller and capped counts per attack value.
(d) cont.: per-roll median resale/purchase ratio for strict flips."""
import json, collections, statistics, math
from load import load, TIERS
p,now,rows=load()
def med(v): return statistics.median(v) if v else None
out={}
for code,(a0,a1),(c0,c1) in [('sniper',(101,130),(16,20)),('tank',(141,170),(26,35)),('gun',(51,60),(6,10)),('rifle',(71,90),(11,15))]:
    rs=[r for r in rows if r['code']==code and r['ri']>=0]
    byA=collections.defaultdict(list)
    for r in rs: byA[int(r['roll'].split('/')[0])].append(r)
    def stats(a):
        v=byA[a];sellers=collections.Counter(r['seller'] for r in v);buyers=collections.Counter(r['buyer'] for r in v)
        return len(v),len(sellers),sum(min(c,2) for c in sellers.values()),len(buyers),sellers.most_common(3)
    rest=[stats(a) for a in range(a0,a1)];mx=stats(a1)
    m=lambda i:statistics.mean(x[i] for x in rest)
    print('%s attack %d: sales %d (rest %.0f, x%.2f) | unique sellers %d (rest %.0f, x%.2f) | seller-capped@2 %d (rest %.0f, x%.2f) | unique buyers %d (rest %.0f, x%.2f) | top sellers %s'%(
        code,a1,mx[0],m(0),mx[0]/m(0),mx[1],m(1),mx[1]/m(1),mx[2],m(2),mx[2]/m(2),mx[3],m(3),mx[3]/m(3),[c for _,c in mx[4]]))
    out[code]={'sales_x':mx[0]/m(0),'unique_sellers_x':mx[1]/m(1),'capped2_x':mx[2]/m(2),'unique_buyers_x':mx[3]/m(3),'top_sellers_max':[c for _,c in mx[4]]}
    # who sells max rolls: sellers' share of max-roll sales vs their share of all sales
    tot=collections.Counter(r['seller'] for r in rs);mxs=collections.Counter(r['seller'] for r in byA[a1])
    big=[(s,tot[s],mxs[s]) for s in tot if tot[s]>=30]
    ratio=[(s[2]/s[1])/(mx[0]/len(rs)) for s in big]
    print('   sellers with >=30 %s sales: %d; their max-roll share relative to market: median x%.2f, max x%.2f; excess sales attributable to sellers with >2x: %d of %d excess'%(code,len(big),med(ratio) or 0,max(ratio) if ratio else 0,sum(s[2]-s[1]*mx[0]/len(rs) for s in big if (s[2]/s[1])/(mx[0]/len(rs))>2),mx[0]-m(0)))
    # crit
    byC=collections.defaultdict(list)
    for r in rs: byC[int(r['roll'].split('/')[1])].append(r)
    cu=[len(set(r['seller'] for r in byC[c])) for c in range(c0,c1+1)]
    print('   crit %d unique sellers %d vs rest mean %.0f (x%.2f)'%(c1,cu[-1],statistics.mean(cu[:-1]),cu[-1]/statistics.mean(cu[:-1])))
# per-roll flip ratios (strict, weapons)
big={'knife','gun','rifle','sniper','tank','jet'}
by=sorted([r for r in rows if r['ri']>=0],key=lambda r:r['sold'])
ob=collections.defaultdict(list);pair={}
for r in by:
    k=(r['code'],r['roll'],r['seller'])
    if ob[k]:pair[r['id']]=ob[k].pop(0)
    ob[(r['code'],r['roll'],r['buyer'])].append(r)
print('\nper-roll median resale/purchase ratio (strict flips, rolls with >=5 flips):')
for code in ['knife','gun','rifle','sniper','tank','jet']:
    byroll=collections.defaultdict(list)
    for r in by:
        if r['code']==code and r['id'] in pair:byroll[r['roll']].append(r['price']/pair[r['id']]['price'])
    rr=[med(v) for v in byroll.values() if len(v)>=5]
    print('  %-7s rolls with >=5 flips %3d; median of per-roll medians %.3f; share of rolls with median ratio>1: %.0f%%'%(code,len(rr),med(rr) or 0,100*sum(x>1 for x in rr)/len(rr) if rr else 0))
    out[code+'_flip_roll']={'rolls':len(rr),'median':med(rr)}
json.dump(out,open('a4_sellers.json','w'),indent=1)
