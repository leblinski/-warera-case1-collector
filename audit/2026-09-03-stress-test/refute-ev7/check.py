"""Independent check of EV-7: 24h volume per tier/item straight from transactions, listings per case
(two conventions), 2-sigma arithmetic, and the within-tier variance the page ignores."""
import json,sys,math,os
from datetime import datetime,timedelta,timezone
AUD=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,AUD)
import ev_ref as E
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
now=datetime.fromisoformat(snap['generated_at'].replace('Z','+00:00'))
ODDS=[0.62,0.30,0.071,0.0085,0.0004,0.0001]; YIELD=[6,18,54,162,486,1458]
def tier(code): return E.WEAPON_CODES.index(code)+1 if code in E.WEAPON_CODES else int(code[-1])
n24={};g24={};q_not1=0
for code,cat in snap['categories'].items():
    c=g=0
    for tx in cat['transactions']:
        t=datetime.fromisoformat(tx['sold_at'].replace('Z','+00:00'))
        if tx.get('quantity',1)!=1: q_not1+=1
        if now-t<=timedelta(hours=24): c+=1; g+=tx['money']*tx.get('quantity',1)
    n24[code]=c; g24[code]=g
T=[0]*7; G=[0]*7
for code in n24: T[tier(code)]+=n24[code]; G[tier(code)]+=g24[code]
print('quantity!=1 rows:',q_not1)
print('24h sales per tier:',T[1:]); print('24h gold per tier:',[round(x) for x in G[1:]])
m=E.Model(snap,tax=1,bar_abs=0.10); c=m.case(1); edge=c['edge']; sd=c['sd']; cost=c['cost']['unit']; gross=c['gross']
print('page mirror: gross %.4f cost %.4f edge %.4f (%.2f%%) sd %.3f'%(gross,cost,edge,edge/cost*100,sd))
# listings per case, two conventions: (A) priced rolls only, renormalised (page's assumption); (B) uncovered rolls count as not listed
print('\ntier: broken(page)  listings/case A (renorm)  B (uncovered=not listed)  cap10%A cap10%B')
lpcA=[0]*7; lpcB=[0]*7; scr=0
for t in range(1,7):
    a=b=0.0
    for slot in E.SLOTS:
        v=m.slot_value(slot,t); w=E.CRAFT_SLOT_WEIGHT[slot]
        if not v: continue
        sells=sum(1 for r in v['rows'] if r[3])
        a+=w*sells/v['covered']; b+=w*sells/v['space']
    lpcA[t]=ODDS[t-1]*a; lpcB[t]=ODDS[t-1]*b; scr+=ODDS[t-1]*YIELD[t-1]*c['parts'][t-1]['broken']
    print(' %d  %5.1f%%  %.4f  %.4f   %8.0f %8.0f'%(t,c['parts'][t-1]['broken']*100,lpcA[t],lpcB[t],0.1*T[t]/lpcA[t] if lpcA[t] else float('inf'),0.1*T[t]/lpcB[t] if lpcB[t] else float('inf')))
print('total listings/case A %.3f B %.3f; scraps/case %.2f'%(sum(lpcA),sum(lpcB),scr))
# per-item share at N cases/day
for N in (100,300,1000):
    out=[]
    for t in range(1,7):
        for slot in E.SLOTS:
            code=E.item_code(slot,t); v=m.slot_value(slot,t)
            if not v or not n24.get(code): continue
            sells=sum(1 for r in v['rows'] if r[3])
            lA=N*ODDS[t-1]*E.CRAFT_SLOT_WEIGHT[slot]*sells/v['covered']; lB=N*ODDS[t-1]*E.CRAFT_SLOT_WEIGHT[slot]*sells/v['space']
            out.append((lA/n24[code]*100,lB/n24[code]*100,code,n24[code]))
    out.sort(reverse=True)
    print(' N=%d: '%N+', '.join('%s %.0f%%(A)/%.0f%%(B) of %d'%(cd,a,b,n) for a,b,cd,n in out[:3]))
# 2-sigma
print('\n2-sigma cases (2sd/edge)^2, page sd %.3f:'%sd)
for lab,e in (('+3.61%',edge),('+4.3%',cost*0.043),('+9.47%',cost*0.0947),('+2%',cost*0.02)):
    n=(2*sd/e)**2; capA=0.1*T[1]/lpcA[1]; capB=0.1*T[1]/lpcB[1]
    print('  %-7s n=%7.0f capital %7.0f days@capA(%.0f/d) %6.1f days@capB(%.0f/d) %6.1f profit %6.0f gold/day@capA %.1f @capB %.1f @100%%common %.1f'%(lab,n,n*cost,capA,n/capA,capB,n/capB,n*e,capA*e,capB*e,10*capA*e))
# full per-roll variance (within-tier included) vs page's between-tier sd
var=0.0
for t in range(1,7):
    for slot in E.SLOTS:
        v=m.slot_value(slot,t)
        if not v: continue
        w=E.CRAFT_SLOT_WEIGHT[slot]; e=m.craft_expected(t)
        # renormalise slot weights over slots present, as craft_expected does
        for k,price,sale,sells in v['rows']:
            best=sale if sells else m.dismantle(t)
            var+=ODDS[t-1]*(w/e['rollw'] if 'rollw' in e else w)*(1/v['covered'])*(best-gross)**2
print('full per-roll sd %.3f (page between-tier sd %.3f); 2sigma cases at +3.61%% with full sd: %.0f'%(math.sqrt(var),sd,(2*math.sqrt(var)/edge)**2))
# case book depth within 1% of best ask
so=snap['commodities']['case1']['order_book']['sell_orders']; ba=min(o['price'] for o in so)
print('case best ask %.3f; depth within 1%%: %d; total shown %d rows %d'%(ba,sum(o['quantity'] for o in so if o['price']<=ba*1.01),sum(o['quantity'] for o in so),len(so)))
print('case transactions in snapshot:', 'transactions' in snap['commodities']['case1'], list(snap['commodities']['case1'].keys()))
