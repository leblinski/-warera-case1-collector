"""Does the finding's 'rwmed' (48h window) match what the page would actually get from
selected.weighted_median (24h window when n24>=3, else 48h)? Score both OOS on the same grid."""
import json,glob,statistics,bisect,datetime,random
P='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'; H=3600
NOW=int(datetime.datetime.fromisoformat(json.load(open(P+'/index.json'))['generated_at'].replace('Z','+00:00')).timestamp())
rolls={}
for f in glob.glob(P+'/prices/*.json'):
    d=json.load(open(f))
    for p,t,tts,ri in d['sales']:
        if tts is not None and tts>48*H: continue
        rolls.setdefault((d['item_code'],ri),[]).append((t,p))
for k in rolls: rolls[k].sort()
first=min(v[0][0] for v in rolls.values()); origins=list(range(first+48*H,NOW-24*H+1,6*H))
def wmed(pw):
    half=sum(w for _,w in pw)/2; c=0
    for p,w in sorted(pw):
        c+=w
        if c>=half: return p
recs=[]
for key,v in rolls.items():
    ts=[t for t,_ in v]
    for T in origins:
        i=bisect.bisect_right(ts,T); j=bisect.bisect_right(ts,T+24*H); fut=[p for _,p in v[i:j]]
        if not fut: continue
        w48=[(t,p) for t,p in v[:i] if t>T-48*H]
        if not w48: continue
        w24=[(t,p) for t,p in w48 if t>T-24*H]; sel=w24 if len(w24)>=3 else w48
        W=lambda ws:[(p,2**(-(T-t)/(12*H))) for t,p in ws]
        est={'med48':statistics.median([p for _,p in w48]),'sel_med':statistics.median([p for _,p in sel]),
             'rwmed48':wmed(W(w48)),'sel_wmed':wmed(W(sel)),'sel_rwmean':sum(p*w for p,w in W(sel))/sum(w for _,w in W(sel))}
        recs.append((key,len(w48),{n:statistics.mean(abs(e-p)/p for p in fut) for n,e in est.items()}))
print('roll-origins',len(recs))
for n in ['med48','sel_med','rwmed48','sel_wmed','sel_rwmean']:
    d=[r[2][n]-r[2]['med48'] for r in recs]; by={}
    for r,x in zip(recs,d): by.setdefault(r[0],[]).append(x)
    keys=list(by); random.seed(7); b=sorted(statistics.mean([x for k in random.choices(keys,k=len(keys)) for x in by[k]])*100 for _ in range(300))
    print('%-10s relMAE %.3f  d %+.3f [%+.3f,%+.3f]  thin(n48<5) %.3f  n48>=5 %.3f'%(n,statistics.mean(r[2][n] for r in recs)*100,statistics.mean(d)*100,b[7],b[292],
          statistics.mean(r[2][n] for r in recs if r[1]<5)*100,statistics.mean(r[2][n] for r in recs if r[1]>=5)*100))
