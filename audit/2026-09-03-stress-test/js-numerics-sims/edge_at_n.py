"""Edge per case when the swing line's own n (12,100) is actually bought off the visible book. Run: python3 edge_at_n.py"""
import json,sys,math
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import *
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=Model(snap,tax=1.0,bar_abs=0.10);c=m.case(1);gross=c['gross'];sd=c['sd'];edge=c['edge']
ob=snap['commodities']['case1']['order_book']
for n in (1,100,1000,4766,12100,12500,24000,50000):
    w=craft_walk(ob,n);e=gross-w['unit'];need=(2*sd/e)**2 if e>0 else float('inf')
    print('n=%6d unit %.5f (thin=%s) edge/case %+.4f -> (2sd/edge)^2 = %s'%(n,w['unit'],w['thin'],e,('%.0f'%need) if need<1e9 else 'inf'))
# fixed point: n such that n == (2 sd / (gross - unit(n)))^2
n=12100
for _ in range(50):
    w=craft_walk(ob,n);e=gross-w['unit'];n2=(2*sd/e)**2 if e>0 else float('inf')
    if not math.isfinite(n2):print('no fixed point: edge <= 0 at n=%d'%n);break
    if abs(n2-n)<1:break
    n=n2
else:pass
if math.isfinite(n2):print('self-consistent n = %.0f (unit %.5f, edge %.4f) -- floor, since only 100 asks are visible'%(n2,craft_walk(ob,int(n2))['unit'],gross-craft_walk(ob,int(n2))['unit']))
# resale pressure at that n spread over 7 days
cats=snap['categories']
import datetime
def ptime(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
for code,t,s in (('knife',1,'weapon'),('helmet1',1,'helmet'),('rifle',3,'weapon'),('sniper',4,'weapon')):
    tx=cats[code]['transactions'];times=[ptime(x['sold_at']) for x in tx];days=(max(times)-min(times)).total_seconds()/86400;daily=len(tx)/days
    v=m.craft_expected(t)['per'][s];listed=1-v['broken']/v['weight']
    per_day=12100/7*CASE_TIER_ODDS[t-1]*CRAFT_SLOT_WEIGHT[s]*listed
    print('%-8s daily sales %.0f; 12,100 cases over 7 days lists %.0f/day = %.0f%% of daily volume'%(code,daily,per_day,per_day/daily*100))
