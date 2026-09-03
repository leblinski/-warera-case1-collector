"""(a) simDraw vs card, (b) full per-case sd, (c) order-book impact, (e) per-1,000 vanish, (f) float.
Run: python3 sims.py [--mc 1000000] [--batches 1000]"""
import json, sys, random, math, argparse, time
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import *
ap=argparse.ArgumentParser();ap.add_argument('--mc',type=int,default=1000000);ap.add_argument('--batches',type=int,default=1000)
ap.add_argument('--seed',type=int,default=1)
a=ap.parse_args();random.seed(a.seed)
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=Model(snap,tax=1.0,bar_abs=0.10)
card=m.case(1);gross=card['gross'];unit1=card['cost']['unit'];edge=card['edge']
print('CARD gross %.4f unit %.5f edge %.4f sd(between) %.4f'%(gross,unit1,edge,card['sd']))

# --- simPick replica ---
def sim_pick(weights):
    total=0.0
    for w in weights: total+=w
    r=random.random()*total
    for i,w in enumerate(weights):
        r-=w
        if r<=0: return i
    return len(weights)-1
SLOT_W=[CRAFT_SLOT_WEIGHT[s] for s in SLOTS]
print('sum SLOT_W = %r, sum CASE_TIER_ODDS = %r'%(sum(SLOT_W),sum(CASE_TIER_ODDS)))
# per tier per slot: list of 'best' values for priced rolls (identical rule to card: sale>need ? sale : dis)
tables={}
for t in range(1,7):
    tables[t]={}
    for s in SLOTS:
        v=m.slot_value(s,t)
        tables[t][s]=[ (sale if sells else m.dismantle(t)) for (k,price,sale,sells) in v['rows']] if v else []
def sim_draw(t):
    s=SLOTS[sim_pick(SLOT_W)]
    rows=tables[t][s]
    if not rows: return 0.0,True
    return rows[sim_pick([1]*len(rows))],False   # uniform among priced rolls (w=1 each)

print('\n(a) per-tier: card net (renormalised over slots with data) vs simulator expectation')
print('tier  card_net   sim_exact  sim_MC(1e6)   MC_se    diff(exact-card)  slots_without_data')
sim_exact={};within_var={};within_var_sim={}
for t in range(1,7):
    e=m.craft_expected(t)
    have=[s for s in SLOTS if tables[t][s]]
    wsum=sum(CRAFT_SLOT_WEIGHT[s] for s in have)
    ex=sum(CRAFT_SLOT_WEIGHT[s]*(sum(tables[t][s])/len(tables[t][s])) for s in have)   # sim: missing slot -> 0, no renormalisation
    sim_exact[t]=ex
    # within-tier variance under the card's own distribution (slots renormalised, rolls uniform among priced)
    ex2=sum(CRAFT_SLOT_WEIGHT[s]/wsum*(sum(x*x for x in tables[t][s])/len(tables[t][s])) for s in have)
    within_var[t]=ex2-e['net']**2
    ex2s=sum(CRAFT_SLOT_WEIGHT[s]*(sum(x*x for x in tables[t][s])/len(tables[t][s])) for s in have)
    within_var_sim[t]=ex2s-ex**2
    tot=0.0;tot2=0.0;unp=0
    for _ in range(a.mc):
        v,u=sim_draw(t);tot+=v;tot2+=v*v;unp+=u
    mean=tot/a.mc;se=math.sqrt(max(tot2/a.mc-mean*mean,0)/a.mc)
    print('%d   %9.4f  %9.4f   %9.4f   %7.4f   %+9.4f          %s  (unpriced draws %.2f%%)'%(t,e['net'],ex,mean,se,ex-e['net'],[s for s in SLOTS if not tables[t][s]] or '-',unp/a.mc*100))
gross_sim=sum(CASE_TIER_ODDS[t-1]*sim_exact[t] for t in range(1,7))
print('case gross: card %.4f  simulator long-run %.4f  diff %+.5f (%.3f%% of gross; %.2f%% of edge %.4f)'%(gross,gross_sim,gross_sim-gross,(gross_sim-gross)/gross*100,(gross_sim-gross)/edge*100,edge))

# whole-case MC: 1e6 cases
tot=0;tot2=0;t0=time.time()
for _ in range(a.mc):
    t=sim_pick(CASE_TIER_ODDS)+1;v,_u=sim_draw(t);tot+=v;tot2+=v*v
mean=tot/a.mc;var=tot2/a.mc-mean*mean
print('simOpenOne MC 1e6: mean %.4f (se %.4f), sd %.3f  [%.1fs]'%(mean,math.sqrt(var/a.mc),math.sqrt(var),time.time()-t0))

print('\n(b) variance')
between=sum(CASE_TIER_ODDS[t-1]*(m.craft_expected(t)['net']-gross)**2 for t in range(1,7))
within=sum(CASE_TIER_ODDS[t-1]*within_var[t] for t in range(1,7))
sd_b=math.sqrt(between);sd_full=math.sqrt(between+within)
for t in range(1,7):
    print('  tier %d within-tier sd %.3f (net %.3f)'%(t,math.sqrt(max(within_var[t],0)),m.craft_expected(t)['net']))
print('between-tier sd %.4f (page)   full sd %.4f   within share of variance %.1f%%'%(sd_b,sd_full,within/(between+within)*100))
need_b=(2*sd_b/edge)**2;need_f=(2*sd_full/edge)**2
print('cases (2sd/edge)^2: page %.0f -> shown %d ; full %.0f -> shown %d'%(need_b,round(need_b/100)*100,need_f,round(need_f/100)*100))
# what does "reliably" mean at that n: MC of batches
for label,nb in (('page',round(need_b/100)*100),('full',round(need_f/100)*100)):
    wins=0;t0=time.time();profits=[]
    for b in range(a.batches):
        got=0.0
        for _ in range(nb):
            t=sim_pick(CASE_TIER_ODDS)+1;v,_u=sim_draw(t);got+=v
        cost=craft_walk(snap['commodities']['case1']['order_book'],1)['unit']*nb  # unit price held at best-ask walk for 1, as the card's edge assumes
        p=got-cost;profits.append(p);wins+=p>0
    profits.sort()
    print('  batches of %d (%s sd): P(profit>0) = %.1f%% over %d batches; median profit %.1f, p10 %.1f  [%.0fs]'%(nb,label,wins/a.batches*100,a.batches,profits[len(profits)//2],profits[len(profits)//10],time.time()-t0))
print('normal-approx at n=(2sd/edge)^2: P(profit>0)=Phi(2)=97.7%%; at n with edge=1 SE: 84.1%%')

print('\n(c) order books')
ob=snap['commodities']['case1']['order_book']
so=sorted(ob['sell_orders'],key=lambda o:o['price']);depth=sum(o['quantity'] for o in so)
print('case1 sell book: %d orders, %d cases, best %.3f deepest %.3f'%(len(so),depth,so[0]['price'],so[-1]['price']))
for n in (1,10,100,1000,depth,9999):
    w=craft_walk(ob,n);ex_line=edge*n;true=gross*n-w['cost']
    print('  n=%5d unit %.5f thin=%s  card-style edge*n (caseCount=1) %+9.3f  vs gross*n-walk(n) %+9.3f  gap %+8.3f'%(n,w['unit'],w['thin'],ex_line,true,ex_line-true))
# levels at same price: bookLevels dedup
from collections import Counter
lv=Counter();[lv.__setitem__(o['price'],lv[o['price']]+o['quantity']) for o in so]
print('  distinct ask levels %d; top5 %s'%(len(lv),sorted(lv.items())[:5]))
sb=snap['commodities']['scraps']['order_book'];bo=sorted(sb['buy_orders'],key=lambda o:-o['price'])
best=bo[0]['price'];atbest=sum(o['quantity'] for o in bo if o['price']==best);allbid=sum(o['quantity'] for o in bo)
scr_per_case=sum(CASE_TIER_ODDS[t-1]*SCRAP_YIELDS[t-1]*m.craft_expected(t)['brokenShare'] for t in range(1,7))
scr_all=sum(CASE_TIER_ODDS[t-1]*SCRAP_YIELDS[t-1] for t in range(1,7))
print('scraps bid book: best %.3f with %d resting at best, %d in 100 visible bids; scraps dumped per case (broken only) %.2f, per 100 cases %.0f, if everything broken %.0f/100 cases'%(best,atbest,allbid,scr_per_case,scr_per_case*100,scr_all*100))
# sale volume per item vs 100 cases/day
cats=snap['categories'];tx0=None
print('daily sale volume per item (retained window) vs pieces 100 cases/day would add to listings:')
import datetime
def ptime(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
tot_add=0;rows=[]
for t in range(1,7):
    e=m.craft_expected(t)
    for s in SLOTS:
        code=item_code(s,t);cat=cats.get(code)
        if not cat:continue
        tx=cat.get('transactions') or []
        if tx0 is None:tx0=tx[0]
        times=[ptime(x['sold_at'] if 'sold_at' in x else x.get('soldAt') or x.get('time')) for x in tx] if tx else []
        days=((max(times)-min(times)).total_seconds()/86400) if times else 0
        daily=len(tx)/days if days else 0
        v=e['per'].get(s);listed_frac=(1-v['broken']/v['weight']) if v else 0
        add=100*CASE_TIER_ODDS[t-1]*CRAFT_SLOT_WEIGHT[s]
        addl=add*listed_frac
        rows.append((code,len(tx),days,daily,add,addl,addl/daily*100 if daily else float('inf')))
for r in rows:print('  %-8s sales %6d over %.2f d = %7.1f/day; 100 cases/day yield %6.2f pieces, %6.2f listed = %6.1f%% of daily volume'%r)
print('  sample transaction keys:',list(tx0.keys()) if isinstance(tx0,dict) else tx0)

print('\n(e) Per 1,000 column: shown total (keep+drop over priced rolls) vs tier odds x 1000')
for t in range(1,7):
    shown=0;full=CASE_TIER_ODDS[t-1]*1000;lost=[]
    for s in SLOTS:
        v=m.slot_value(s,t)
        space=len(roll_space(s,t));known=v['covered'] if v else 0
        each=CASE_TIER_ODDS[t-1]*CRAFT_SLOT_WEIGHT[s]/space
        shown+=each*known*1000
        if known<space:lost.append('%s %d/%d (%.2f)'%(s,known,space,each*(space-known)*1000))
    print('  tier %d: shown %.3f of %.3f per 1,000 cases; vanished %.3f -> %s'%(t,shown,full,full-shown,', '.join(lost) or 'none'))
# Uncommon on-screen check
t=2
for s,keep_rolls in (('helmet',1),('chest',1)):
    space=len(roll_space(s,t));print('  Uncommon %s: each=%.4f per case -> %d roll kept = %.1f per 1,000'%(s,CASE_TIER_ODDS[1]*0.14/space,keep_rolls,CASE_TIER_ODDS[1]*0.14/space*1000*keep_rolls))
print('  Uncommon rest = 300 - 2.8 - 8.4 = %.1f'%(300-2.8-8.4))

print('\n(f) float accumulation: naive sum vs fsum over every priced roll best-value')
allv=[x for t in tables for s in tables[t] for x in tables[t][s]]
sn=0.0
for x in allv:sn+=x
print('  n=%d naive %.15f fsum %.15f rel diff %.2e'%(len(allv),sn,math.fsum(allv),abs(sn-math.fsum(allv))/math.fsum(allv)))
