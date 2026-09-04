"""Independent forward re-score of NF-2. Rebuilds roll stats at T0 from raw sales WITHOUT collector.aggregate,
applies the page's verdict rule (sortRolls/fillQuiet 4445-4512), scores vs the roll's own next-24h median.
usage: python3 my_forward.py MIN_FWD [bid_mode: fixed|hist]"""
import sys, json, statistics, collections, subprocess
from datetime import timedelta
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
sys.path.insert(0,'/home/user/-warera-case1-collector')
import collector as C
from ev_ref import SCRAP_YIELDS, SLOTS, roll_space, roll_key, item_code
MIN_FWD=int(sys.argv[1]) if len(sys.argv)>1 else 1
BID_MODE=sys.argv[2] if len(sys.argv)>2 else 'fixed'
HIST_BID={72:0.223,48:0.224,24:0.225}   # from git_snaps.out (committed snapshots nearest each T0)
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
gen=C.parse_time(snap['generated_at']); cur_bid=snap['commodities']['scraps']['order_book']['best_bid']
TAX=0.99; BAR=0.10
rows_by={code:[C.unpack_transaction(r,code) for r in cat['transactions']] for code,cat in snap['categories'].items()}
def pos(slot,k): return int(k.split('/')[0]) if slot=='weapon' else int(k)
def band(slot,k): return k.split('/')[1] if slot=='weapon' else ''

def stats_at(rows,slot,T0):
    """my own rebuild: per roll key -> (selected_median, retained_median) or None entries"""
    w168=collections.defaultdict(list); w48=collections.defaultdict(list); w24=collections.defaultdict(list)
    for tx in rows:
        if not tx['eligible_for_comps'] or C.stale_listing(tx): continue
        s=C.parse_time(tx['sold_at'])
        if s>T0 or s<T0-timedelta(hours=168): continue
        k=roll_key(slot,tx['skills'])
        if k is None: continue
        w168[k].append(tx['unit_price'])
        if s>=T0-timedelta(hours=48): w48[k].append(tx['unit_price'])
        if s>=T0-timedelta(hours=24): w24[k].append(tx['unit_price'])
    out={}
    for k in w168:
        sel=statistics.median(w24[k]) if len(w24[k])>=3 else (statistics.median(w48[k]) if w48[k] else None)
        out[k]=(sel,statistics.median(w168[k]))
    return out

class Acc:
    def __init__(s): s.cm=collections.Counter()
    def add(s,truth,pred): s.cm[(truth,pred)]+=1
    @property
    def n(s): return sum(s.cm.values())
    def line(s):
        n=s.n; ok=s.cm[(True,True)]+s.cm[(False,False)]
        return 'n=%d acc=%.1f%% sell->break=%d break->sell=%d truesell=%d'%(n,100*ok/max(1,n),s.cm[(True,False)],s.cm[(False,True)],s.cm[(True,True)]+s.cm[(True,False)])

tot=collections.defaultdict(Acc); vind=collections.Counter(); near=collections.defaultdict(list); guessed=collections.Counter()
for back in (72,48,24):
    T0=gen-timedelta(hours=back); T1=T0+timedelta(hours=24)
    bid=HIST_BID[back] if BID_MODE=='hist' else cur_bid
    for t in range(1,7):
        scrap=SCRAP_YIELDS[t-1]*bid; dis=scrap+BAR
        for slot in SLOTS:
            code=item_code(slot,t); rows=rows_by.get(code)
            if rows is None: continue
            st=stats_at(rows,slot,T0)
            # cross-check against collector.aggregate at T0
            agg=C.aggregate(rows,T0)
            aggk={roll_key(slot,r['exact_roll']['skills']):r for r in agg.values()}
            for k,(sel,wide) in st.items():
                a=aggk[k]; assert a['selected']['median']==sel and a['retained_window']['median']==wide,(code,k)
            space=roll_space(slot,t)
            # verdicts as the page computes them
            V={}
            for k in space:
                sel,wide=st.get(k,(None,None))
                if sel is not None: V[k]=('own',sel*TAX>dis)
                elif wide is not None: V[k]=('wide',wide*TAX>dis)
                else: V[k]=('none',None)
            def lower_neighbour(k,exclude=None):
                best=None
                for y in space:
                    if y==k or y==exclude: continue
                    if V[y][0]=='none' or band(slot,y)!=band(slot,k) or pos(slot,y)>=pos(slot,k): continue
                    if best is None or pos(slot,y)>pos(slot,best): best=y
                return best
            for k in space:
                if V[k][0]=='none':
                    b=lower_neighbour(k)
                    if b: guessed[(code,'break' if not V[b][1] else 'sell')]+=1 if back==24 else 0
            fwd=collections.defaultdict(list)
            for tx in rows:
                if not tx['eligible_for_comps'] or C.stale_listing(tx): continue
                s=C.parse_time(tx['sold_at'])
                if T0<s<=T1: fwd[roll_key(slot,tx['skills'])].append(tx['unit_price'])
            for k in space:
                f=fwd.get(k)
                if not f or len(f)<MIN_FWD: continue
                tm=statistics.median(f); truth=tm*TAX>dis
                kind,v=V[k]
                if kind=='own':
                    tot['A own selected'].add(truth,v)
                    wv=st[k][1]*TAX>dis; tot['B own retained'].add(truth,wv)
                    if wv!=v: vind['selected right' if v==truth else 'retained right']+=1
                    b=lower_neighbour(k)
                    if b:
                        pred=V[b][1]; tot['D neighbour held-one-out'].add(truth,pred); tot['A on D subset'].add(truth,v)
                        if pred!=truth: near['D err'].append((tm*TAX-dis)/dis)
                    if v!=truth: near['A err'].append((tm*TAX-dis)/dis)
                elif kind=='wide':
                    tot['E quiet-48h wide verdict'].add(truth,v)
                else:
                    b=lower_neighbour(k)
                    if b: tot['C quiet no-wide neighbour'].add(truth,V[b][1]); tot['C tier%d'%t].add(truth,V[b][1])
print('MIN_FWD',MIN_FWD,'bid_mode',BID_MODE,'cur_bid',cur_bid)
for k in sorted(tot): print('  %-32s %s'%(k,tot[k].line()))
print('  disagreements vindicated:',dict(vind))
for k,e in near.items():
    ab=sorted(abs(x) for x in e)
    print('  %s: n=%d |truth_net-bar|/bar median=%.2f%% share<1%%=%d share<2%%=%d'%(k,len(ab),100*ab[len(ab)//2],sum(x<0.01 for x in ab),sum(x<0.02 for x in ab)))
print('  neighbour-guessed rolls at T0-24h by item/verdict:',dict(guessed))
