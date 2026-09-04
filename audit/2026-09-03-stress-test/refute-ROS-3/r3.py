"""Independent re-derivation of ROS-3's time-to-sell populations. SNAP=<snapshot> selects the file."""
import json,os,sys,statistics,datetime,collections
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
SNAP=os.environ.get('SNAP','/home/user/-warera-case1-collector/data/warera_case1_market.json')
TIERS=['basic','reinforced','advanced','elite','legendary','mythic']
def ts(s): return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def med(v): return statistics.median(v)/60 if v else None
def f(v): return '-' if v is None else '%.1f'%v
p=json.load(open(SNAP)); now=ts(p['generated_at'])
print('snapshot',p['generated_at'])
# --- per-roll figures the page displays
rollsel={}   # (code,rollkey) -> selected stats (what factsFor / sortRolls read)
sales=[]     # comps-eligible, non-stale, retained sales
for code,cat in p['categories'].items():
    slot=cat['slot']; t=TIERS.index(cat['tier'])+1; space=set(ev_ref.roll_space(slot,t))
    for key,row in cat['rolls'].items():
        k=ev_ref.roll_key(slot,(row.get('exact_roll') or {}).get('skills'))
        st=row.get('selected') or row.get('fallback_48h')
        rollsel[(code,k)]=(t,slot,st,row.get('retained_window'))
    for tx in cat['transactions']:
        k=ev_ref.roll_key(slot,tx.get('skills') or {})
        q=tx.get('quantity'); money=tx.get('money')
        elig=tx.get('state') is not None and tx.get('state')==tx.get('max_state') and (tx.get('max_state') or 0)>0 and k in space and q==1 and money and money>0
        if not elig: continue
        sold=ts(tx['sold_at']); oc=tx.get('offer_created_at')
        tts=(sold-ts(oc)) if oc else None
        if tts is not None and tts<0: tts=None
        if tts is not None and tts>48*3600: continue   # stale_listing
        if sold<now-168*3600 or sold>now: continue
        sales.append((code,t,k,money/q,sold,tts))
priced=[(c,v) for c,v in rollsel.items() if v[2] and v[2]['median'] is not None]
secs=[v[2]['median_time_to_sell_seconds'] for c,v in priced if v[2]['median_time_to_sell_seconds'] is not None]
wsecs=[]
for c,v in priced:
    s=v[2]['median_time_to_sell_seconds']
    if s is not None: wsecs+=[s]*v[2]['count']
print('A priced rolls %d; median of selected.tts over rolls %s min; count-weighted %s'%(len(priced),f(med(secs)),f(med(wsecs))))
# sanity: recompute one roll's selected median tts from raw sales and compare with the field
mism=0;chk=0
byroll=collections.defaultdict(list)
for code,t,k,pr,sold,tts in sales: byroll[(code,k)].append((pr,sold,tts))
for c,v in priced:
    st=v[2]; win=48 if st is rollsel[c][2] and v[2] is not None and (v[2].get('count')==(rollsel[c][2] or {}).get('count')) else 48
    # figure out which window 'selected' was: compare count with primary/fallback
    rows=byroll.get(c,[])
    for hours in (24,48):
        sub=[r for r in rows if r[1]>=now-hours*3600]
        if len(sub)==st['count'] and abs(statistics.median([r[0] for r in sub])-st['median'])<1e-9:
            d=[r[2] for r in sub if r[2] is not None]
            chk+=1
            if d and abs(statistics.median(d)-st['median_time_to_sell_seconds'])>1: mism+=1
            break
print('   selected.tts re-derived from raw sales: %d rolls matched a window, %d tts mismatches'%(chk,mism))
allt=[s[5] for s in sales if s[5] is not None]
w48=[s[5] for s in sales if s[5] is not None and s[4]>=now-48*3600]
w24=[s[5] for s in sales if s[5] is not None and s[4]>=now-24*3600]
print('B sale-weighted median tts: all retained %s (n=%d); 48h %s (n=%d); 24h %s (n=%d)'%(f(med(allt)),len(allt),f(med(w48)),len(w48),f(med(w24)),len(w24)))
# C: at/below vs above the roll's selected median
lo=[];hi=[];lo_t=collections.defaultdict(list);hi_t=collections.defaultdict(list);eq_t=collections.defaultdict(list)
for code,t,k,pr,sold,tts in sales:
    v=rollsel.get((code,k))
    if not v or not v[2] or v[2]['median'] is None or tts is None: continue
    m=v[2]['median']
    (lo if pr<=m else hi).append(tts); (lo_t if pr<=m else hi_t)[t].append(tts)
    if abs(pr-m)<1e-9: eq_t[t].append(tts)
print('C overall: <=roll median %s (n=%d); >median %s (n=%d)'%(f(med(lo)),len(lo),f(med(hi)),len(hi)))
# D: sell-verdict rolls (page rule, tax 1%, bar 0.10)
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
sellset={}
for t in range(1,7):
    for slot in ev_ref.SLOTS:
        v=m.slot_value(slot,t)
        if not v: continue
        for k,pr,sale,sells in v['rows']:
            if sells: sellset[(ev_ref.item_code(slot,t),k)]=(slot,len(ev_ref.roll_space(slot,t)))
print('   sell-verdict rolls total',len(sellset))
print('D per tier: rolls-med | sales-all | <=med | ==med | >med | sell-verdict rolls unweighted (n) | sell-verdict draw-weighted')
out={}
for t in range(1,7):
    rs=[v[2]['median_time_to_sell_seconds'] for c,v in priced if v[0]==t and v[2]['median_time_to_sell_seconds'] is not None]
    sa=[s[5] for s in sales if s[1]==t and s[5] is not None]
    sr=[];wl=[]
    for c,v in priced:
        if v[0]!=t or c not in sellset: continue
        s=v[2]['median_time_to_sell_seconds']
        if s is None: continue
        sr.append(s); slot,sp=sellset[c]; wl.append((s,ev_ref.CRAFT_SLOT_WEIGHT[slot]/sp))
    wl.sort(); tot=sum(w for _,w in wl); cum=0; dw=None
    for s,w in wl:
        cum+=w
        if cum>=tot/2: dw=s/60; break
    print('  %-10s %s | %s | %s (n=%d) | %s (n=%d) | %s (n=%d) | %s (n=%d) | %s'%(TIERS[t-1],f(med(rs)),f(med(sa)),f(med(lo_t[t])),len(lo_t[t]),f(med(eq_t[t])),len(eq_t[t]),f(med(hi_t[t])),len(hi_t[t]),f(med(sr)),len(sr),f(dw)))
    out[TIERS[t-1]]={'roll_med':med(rs),'sales':med(sa),'le':med(lo_t[t]),'n_le':len(lo_t[t]),'eq':med(eq_t[t]),'gt':med(hi_t[t]),'n_gt':len(hi_t[t]),'sell_rolls':med(sr),'n_sell':len(sr),'sell_rolls_draw_wtd':dw}
srall=[v[2]['median_time_to_sell_seconds'] for c,v in priced if c in sellset and v[2]['median_time_to_sell_seconds'] is not None]
print('   sell-verdict rolls all tiers, unweighted median of roll medians %s (n=%d)'%(f(med(srall)),len(srall)))
# E: the brief's split test: 48h window, rolls with >=N sales, sales <=median vs >=Q3
def q3(v):
    v=sorted(v); n=len(v); pos=0.75*(n-1); i=int(pos); fr=pos-i
    return v[i] if i+1>=n else v[i]+(v[i+1]-v[i])*fr
for N in (6,7,10):
    g=collections.defaultdict(list)
    for code,t,k,pr,sold,tts in sales:
        if sold>=now-48*3600: g[(code,k)].append((pr,tts))
    le=[];ge=[];eq=[];nroll=0;ns=0
    for c,rows in g.items():
        if len(rows)<N: continue
        nroll+=1; ns+=len(rows); pr=[r[0] for r in rows]; mm=statistics.median(pr); qq=q3(pr)
        for r in rows:
            if r[1] is None: continue
            if r[0]<=mm: le.append(r[1])
            if r[0]>=qq: ge.append(r[1])
            if abs(r[0]-mm)<1e-9: eq.append(r[1])
    print('E split test N>=%d: %d rolls, %d sales; <=median %s min (n=%d), ==median %s (n=%d), >=Q3 %s (n=%d), ratio %.1fx'%(N,nroll,ns,f(med(le)),len(le),f(med(eq)),len(eq),f(med(ge)),len(ge),med(ge)/med(le)))
    out['split_N%d'%N]={'rolls':nroll,'sales':ns,'le':med(le),'eq':med(eq),'ge_q3':med(ge)}
out['A']={'rolls':len(priced),'roll_med':med(secs),'count_wtd':med(wsecs)};out['B']={'all':med(allt),'h48':med(w48),'h24':med(w24)};out['C']={'le':med(lo),'gt':med(hi),'n_le':len(lo),'n_gt':len(hi)};out['sell_all']=med(srall)
json.dump(out,open(os.environ.get('OUT','r3_current.json'),'w'),indent=1)
