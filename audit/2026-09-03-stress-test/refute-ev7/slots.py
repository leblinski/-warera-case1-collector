import json,sys,os
AUD=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,AUD)
import ev_ref as E
snap=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=E.Model(snap,tax=1,bar_abs=0.10)
for t in (1,2,3):
    e=m.craft_expected(t); print('tier',t,'brokenShare(page) %.4f'%e['brokenShare'])
    for slot in E.SLOTS:
        v=m.slot_value(slot,t); 
        if not v: print('  ',slot,'none'); continue
        sells=sum(1 for r in v['rows'] if r[3])
        print('   %-7s covered %3d/%3d sells %3d broken %3d  frac_sells %.3f'%(slot,v['covered'],v['space'],sells,v['broken'],sells/v['covered']))
