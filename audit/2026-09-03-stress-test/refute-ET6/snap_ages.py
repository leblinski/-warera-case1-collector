"""Ages (h before generated_at) of the retained comps behind the snapshot's quiet rolls (in roll space,
no 48h comp, retained median present), from categories[code].transactions, stale (tts>48h) dropped."""
import json,sys,statistics,datetime
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
from ev_ref import *
s=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
P=lambda x:datetime.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()
NOW=P(s['generated_at']); ages=[]; nq=0; counts=[]
for t in range(1,7):
    for slot in SLOTS:
        cat=s['categories'].get(item_code(slot,t))
        if not cat: continue
        seen={}
        for key,row in cat['rolls'].items():
            k=roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
            if k is not None: seen[k]=row
        tx={}
        for x in cat['transactions']:
            if x.get('state')!=x.get('max_state') or x.get('quantity')!=1: continue
            tts=P(x['sold_at'])-P(x['offer_created_at'])
            if tts>48*3600: continue
            tx.setdefault(roll_key(slot,x['skills']),[]).append((NOW-P(x['sold_at']))/3600)
        for k in roll_space(slot,t):
            row=seen.get(k)
            if not row: continue
            st=row['selected'] or row['fallback_48h']
            if st and st.get('median') is not None: continue
            w=row.get('retained_window') or {}
            if w.get('median') is None: continue
            nq+=1; a=tx.get(k,[]); ages+=a; counts.append((w['count'],len(a)))
ages.sort()
print('quiet rolls in space',nq,'comps',len(ages),'age h: median %.0f p10 %.0f p25 %.0f p75 %.0f p90 %.0f'%(statistics.median(ages),ages[int(.1*len(ages))],ages[int(.25*len(ages))],ages[int(.75*len(ages))],ages[int(.9*len(ages))]))
print('retained count agrees with my comp count on %d of %d rolls'%(sum(1 for a,b in counts if a==b),len(counts)))
