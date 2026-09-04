"""Independent check of ROS-4: even vs as-traded (all slots, as ev_ref) vs weapon-only as-traded
(what the removed page option 69ace98 actually did: byCount=slot==='weapon')."""
import json,sys,statistics
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
cost=m.case(1)['cost']['unit']
def slot_net(slot,t,mode):
    cat=m.cats.get(ev_ref.item_code(slot,t))
    seen={}
    for key,row in cat['rolls'].items():
        k=ev_ref.roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
        if k is not None:seen[k]=row
    dis=m.dismantle(t);need=m.need(t);ws=vs=0.0;cnt={}
    for k in ev_ref.roll_space(slot,t):
        row=seen.get(k)
        if not row:continue
        st=row['selected'] or row['fallback_48h']
        if not st or st.get('median') is None:continue
        n=(row.get('fallback_48h') or {}).get('count') or 0
        w=n if (mode=='all' or (mode=='weapon' and slot=='weapon')) else 1
        sale=st['median']*m.taxMul;best=sale if sale>need else dis
        ws+=w;vs+=w*best;cnt[k]=n
    return (vs/ws if ws else None),cnt
res={}
for mode in ['even','weapon','all']:
    gross=0;per={}
    for t in range(1,7):
        wsum=net=0
        for slot in ev_ref.SLOTS:
            v,cnt=slot_net(slot,t,mode)
            if v is None:continue
            w=ev_ref.CRAFT_SLOT_WEIGHT[slot];wsum+=w;net+=w*v;per[(slot,t)]=v
        gross+=ev_ref.CASE_TIER_ODDS[t-1]*net/wsum
    res[mode]={'gross':gross,'pct':(gross-cost)/cost*100,'per':per}
    print('%-7s gross %.4f edge %+.4f pct %+.2f%%'%(mode,gross,gross-cost,(gross-cost)/cost*100))
e,w,a=res['even'],res['weapon'],res['all']
print('gap weapon-only %.4f  gap all-slots %.4f'%(w['gross']-e['gross'],a['gross']-e['gross']))
kd=ev_ref.CASE_TIER_ODDS[0]*ev_ref.CRAFT_SLOT_WEIGHT['weapon']*(a['per'][('weapon',1)]-e['per'][('weapon',1)])
print('knife contribution %.4f = %.0f%% of all-slot gap, %.0f%% of weapon-only gap'%(kd,kd/(a['gross']-e['gross'])*100,kd/(w['gross']-e['gross'])*100))
for slot,t in [('weapon',1),('weapon',3),('weapon',4),('helmet',4),('chest',4)]:
    print(' %s%d even %.4f traded %.4f'%(slot,t,e['per'][(slot,t)],a['per'][(slot,t)]))
# knife 40/5 weight
_,cnt=slot_net('weapon',1,'all');tot=sum(cnt.values())
print('knife 48h counts total %d, 40/5=%d (%.1f%%), even weight 1/%d=%.1f%%; max/median count x%.1f'%(tot,cnt['40/5'],cnt['40/5']/tot*100,len(cnt),100/len(cnt),cnt['40/5']/statistics.median(cnt.values())))
_,cs=slot_net('weapon',4,'all');print('sniper 48h count max/median x%.2f'%(max(cs.values())/statistics.median(cs.values())))
json.dump({k:{'gross':v['gross'],'pct':v['pct']} for k,v in res.items()},open('check.json','w'),indent=1)
