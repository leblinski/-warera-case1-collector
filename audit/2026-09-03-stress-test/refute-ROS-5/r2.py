"""Sensitivity: case gross if top rolls are drawn more often than uniform. Mirrors ev_ref.Model
(rows carry (key,price,sale,sells); best = sale if sells else dismantle) but reweights rolls."""
import json,sys
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
from ev_ref import Model,CASE_TIER_ODDS,CRAFT_SLOT_WEIGHT,SLOTS,item_code,WEAPON_STATS
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=Model(p,tax=1.0,bar_abs=0.10)
base=m.case(1)
def gross(weightfn):
    g=0.0
    for t in range(1,7):
        wsum=net=0.0
        for slot in SLOTS:
            v=m.slot_value(slot,t)
            if not v: continue
            dis=m.dismantle(t); ws=vs=0.0
            for (k,price,sale,sells) in v['rows']:
                w=weightfn(slot,t,k); best=sale if sells else dis
                ws+=w; vs+=w*best
            wsum+=CRAFT_SLOT_WEIGHT[slot]; net+=CRAFT_SLOT_WEIGHT[slot]*vs/ws
        g+=CASE_TIER_ODDS[t-1]*net/wsum
    return g
def is_top_attack(slot,t,k):
    return slot=='weapon' and int(k.split('/')[0])==WEAPON_STATS[t-1][0][1]
def is_top_crit(slot,t,k):
    return slot=='weapon' and int(k.split('/')[1])==WEAPON_STATS[t-1][1][1]
def is_top_armour(slot,t,k):
    return slot!='weapon' and k==ev_ref.roll_space(slot,t)[-1]
uni=gross(lambda s,t,k:1.0)
print('base gross (ev_ref) %.4f ; reweighted uniform %.4f'%(base['gross'],uni))
s1=gross(lambda s,t,k:1.16 if (s=='weapon' and t==4 and is_top_attack(s,t,k)) else 1.0)
s2=gross(lambda s,t,k:(1.16 if is_top_attack(s,t,k) else 1.0)*(1.09 if is_top_crit(s,t,k) else 1.0) if (s=='weapon' and t==4) else 1.0)
s3=gross(lambda s,t,k:1.16 if (is_top_attack(s,t,k) or is_top_armour(s,t,k)) else 1.0)
s4=gross(lambda s,t,k:(1.16 if is_top_attack(s,t,k) else 1.0)*(1.09 if is_top_crit(s,t,k) else 1.0)*(1.16 if is_top_armour(s,t,k) else 1.0))
for lab,v in [('sniper attack130 x1.16',s1),('sniper att130 x1.16 & crit20 x1.09',s2),('every item top attack/top armour roll x1.16',s3),('all items top attack x1.16, top crit x1.09, top armour x1.16',s4)]:
    print('%-55s gross %.4f  delta %+.5f  (edge %.4f -> %.4f, %+.2f%% -> %+.2f%%)'%(lab,v,v-uni,uni-base['cost']['unit'],v-base['cost']['unit'],(uni/base['cost']['unit']-1)*100,(v/base['cost']['unit']-1)*100))
# power calc check
n=(3/0.16)**2*30; print('draws for 3 sigma on 16%% excess in 1/30 cell: %.0f ; case openings at %.4f*%.2f: %.2fM'%(n,CASE_TIER_ODDS[3],CRAFT_SLOT_WEIGHT['weapon'],n/(CASE_TIER_ODDS[3]*CRAFT_SLOT_WEIGHT['weapon'])/1e6))
