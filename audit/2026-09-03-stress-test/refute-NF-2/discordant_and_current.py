"""(1) McNemar discordant pairs A vs D on the D subset, MIN_FWD=1, fixed bid; (2) neighbour-guessed verdicts on the CURRENT committed snapshot rolls (not rebuilt)."""
import sys, json, statistics, collections
from datetime import timedelta
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit'); sys.path.insert(0,'/home/user/-warera-case1-collector')
import collector as C
from ev_ref import SCRAP_YIELDS, SLOTS, roll_space, roll_key, item_code
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
gen=C.parse_time(snap['generated_at']); bid=snap['commodities']['scraps']['order_book']['best_bid']; TAX=0.99; BAR=0.10
def pos(slot,k): return int(k.split('/')[0]) if slot=='weapon' else int(k)
def band(slot,k): return k.split('/')[1] if slot=='weapon' else ''
def verdicts(rollrows,slot,t,dis):
    seen={}
    for r in rollrows.values():
        k=roll_key(slot,r['exact_roll']['skills'])
        if k: seen[k]=r
    V={}
    for k in roll_space(slot,t):
        r=seen.get(k); sel=r and r['selected']['median']; wide=r and r['retained_window']['median']
        V[k]=('own',sel*TAX>dis) if sel is not None else (('wide',wide*TAX>dis) if wide is not None else ('none',None))
    return V
def lower(V,slot,k):
    best=None
    for y in V:
        if y==k or V[y][0]=='none' or band(slot,y)!=band(slot,k) or pos(slot,y)>=pos(slot,k): continue
        if best is None or pos(slot,y)>pos(slot,best): best=y
    return best
# (2) current snapshot
g=collections.Counter()
for t in range(1,7):
    dis=SCRAP_YIELDS[t-1]*bid+BAR
    for slot in SLOTS:
        cat=snap['categories'].get(item_code(slot,t))
        if not cat: continue
        V=verdicts(cat['rolls'],slot,t,dis)
        for k in V:
            if V[k][0]=='none':
                b=lower(V,slot,k)
                if b: g[(item_code(slot,t),'sell' if V[b][1] else 'break')]+=1
                else: g[(item_code(slot,t),'dash')]+=1
print('CURRENT snapshot quiet rolls with no wide, default bar: neighbour verdicts', dict(g))
# (1) discordant pairs
rows_by={code:[C.unpack_transaction(r,code) for r in cat['transactions']] for code,cat in snap['categories'].items()}
disc=collections.Counter()
for back in (72,48,24):
    T0=gen-timedelta(hours=back); T1=T0+timedelta(hours=24)
    for t in range(1,7):
        dis=SCRAP_YIELDS[t-1]*bid+BAR
        for slot in SLOTS:
            code=item_code(slot,t); rows=rows_by.get(code)
            if rows is None: continue
            V=verdicts(C.aggregate(rows,T0),slot,t,dis)
            fwd=collections.defaultdict(list)
            for tx in rows:
                if not tx['eligible_for_comps'] or C.stale_listing(tx): continue
                s=C.parse_time(tx['sold_at'])
                if T0<s<=T1: fwd[roll_key(slot,tx['skills'])].append(tx['unit_price'])
            for k,f in fwd.items():
                if k not in V or V[k][0]!='own': continue
                b=lower(V,slot,k)
                if not b: continue
                truth=statistics.median(f)*TAX>dis
                disc[(V[k][1]==truth, V[b][1]==truth)]+=1
print('D subset (n=%d): (A right,D right)=%d (A right,D wrong)=%d (A wrong,D right)=%d (both wrong)=%d'%(sum(disc.values()),disc[(True,True)],disc[(True,False)],disc[(False,True)],disc[(False,False)]))
