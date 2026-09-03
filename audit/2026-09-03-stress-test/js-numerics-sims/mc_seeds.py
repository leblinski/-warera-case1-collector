"""Re-check simPick bias: tier-6 and whole-case MC across seeds, 1e6 each. Run: python3 mc_seeds.py"""
import json,sys,random,math
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import *
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=Model(snap,tax=1.0,bar_abs=0.10);card=m.case(1);gross=card['gross']
def sim_pick(weights):
    total=0.0
    for w in weights: total+=w
    r=random.random()*total
    for i,w in enumerate(weights):
        r-=w
        if r<=0: return i
    return len(weights)-1
SLOT_W=[CRAFT_SLOT_WEIGHT[s] for s in SLOTS]
tables={t:{s:[(sale if sells else m.dismantle(t)) for (k,p,sale,sells) in m.slot_value(s,t)['rows']] for s in SLOTS} for t in range(1,7)}
def draw(t):
    rows=tables[t][SLOTS[sim_pick(SLOT_W)]];return rows[sim_pick([1]*len(rows))]
N=1000000;net6=m.craft_expected(6)['net']
zs=[];zc=[]
for seed in range(2,7):
    random.seed(seed);tot=tot2=0.0
    for _ in range(N):v=draw(6);tot+=v;tot2+=v*v
    mean=tot/N;se=math.sqrt((tot2/N-mean*mean)/N);zs.append((mean-net6)/se)
    random.seed(seed+100);tot=tot2=0.0
    for _ in range(N):v=draw(sim_pick(CASE_TIER_ODDS)+1);tot+=v;tot2+=v*v
    mean=tot/N;se=math.sqrt((tot2/N-mean*mean)/N);zc.append((mean-gross)/se)
    print('seed %d: tier6 z=%+.2f   whole-case mean %.4f z=%+.2f'%(seed,zs[-1],mean,zc[-1]))
print('mean z tier6 %+.2f, whole-case %+.2f (5 seeds of 1e6; |mean z| should be < ~0.9)'%(sum(zs)/5,sum(zc)/5))
# slot pick frequencies with the exact float weights
random.seed(9);c=[0]*6
for _ in range(N):c[sim_pick(SLOT_W)]+=1
print('slot pick freq',[round(x/N,4) for x in c],'expected',SLOT_W)
random.seed(10);c=[0]*6
for _ in range(N*5):c[sim_pick(CASE_TIER_ODDS)]+=1
print('tier pick freq (5e6)',[x/(N*5) for x in c],'expected',CASE_TIER_ODDS,' mythic count',c[5],'expected',N*5*0.0001)
