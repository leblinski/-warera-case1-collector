"""Independent re-derivation of ET-1 (own loader, own estimators). Rolling origins as in the
finding (every 6h from first_sale+48h to now-24h), plus a phase-shifted origin grid (+3h) and
sale-weighted aggregation, plus a sign test rwmed vs med48."""
import json, os, glob, statistics, bisect, datetime, random, sys
P='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
H=3600; STALE=48*H
idx=json.load(open(P+'/index.json'))
NOW=int(datetime.datetime.fromisoformat(idx['generated_at'].replace('Z','+00:00')).timestamp())
rolls={}; tier={}
for f in glob.glob(P+'/prices/*.json'):
    d=json.load(open(f)); tier[d['item_code']]=d['tier']
    for p,t,tts,ri in d['sales']:
        if tts is not None and tts>STALE: continue
        rolls.setdefault((d['item_code'],ri),[]).append((t,p))
for k in rolls: rolls[k].sort()
first=min(v[0][0] for v in rolls.values())
def wmed(pw):
    half=sum(w for _,w in pw)/2; c=0
    for p,w in sorted(pw):
        c+=w
        if c>=half: return p
def q(xs,f):
    s=sorted(xs); pos=(len(s)-1)*f; lo=int(pos); hi=min(lo+1,len(s)-1); return s[lo]+(s[hi]-s[lo])*(pos-lo)
def run(phase_h, hor=24, step=6, label=''):
    origins=list(range(first+48*H+phase_h*H, NOW-hor*H+1, step*H))
    recs=[]
    for key,v in rolls.items():
        ts=[t for t,_ in v]
        for T in origins:
            i=bisect.bisect_right(ts,T); j=bisect.bisect_right(ts,T+hor*H)
            fut=[p for _,p in v[i:j]]
            if not fut: continue
            w48=[(t,p) for t,p in v[:i] if t>T-48*H]
            if not w48: continue
            w24=[p for t,p in w48 if t>T-24*H]
            p48=[p for _,p in w48]
            est={'med48':statistics.median(p48),
                 'selected':statistics.median(w24) if len(w24)>=3 else statistics.median(p48),
                 'rwmed':wmed([(p,2**(-(T-t)/(12*H))) for t,p in w48]),
                 'mean48':sum(p48)/len(p48),'q75':q(p48,.75),'q25':q(p48,.25)}
            recs.append((key,len(p48),len(fut),{n:[abs(e-p)/p for p in fut] for n,e in est.items()},
                         {n:sum(1 for p in fut if p>=e)/len(fut) for n,e in est.items()}))
    print('\n== %s origins=%d hor=%dh roll-origins=%d rolls=%d sales=%d ==' % (label,len(origins),hor,len(recs),len(set(r[0] for r in recs)),sum(r[2] for r in recs)))
    for n in ['med48','selected','rwmed','mean48','q75','q25']:
        ro=statistics.mean(statistics.mean(r[3][n]) for r in recs)*100          # equal weight per roll-origin
        sw=sum(sum(r[3][n]) for r in recs)/sum(r[2] for r in recs)*100         # equal weight per sale
        sold=statistics.mean(r[4][n] for r in recs)*100
        d=[statistics.mean(r[3][n])-statistics.mean(r[3]['med48']) for r in recs]
        wins=sum(1 for x in d if x<0); ties=sum(1 for x in d if x==0)
        # cluster bootstrap by roll
        by={}
        for r,x in zip(recs,d): by.setdefault(r[0],[]).append(x)
        keys=list(by); random.seed(7); b=[]
        for _ in range(300):
            s=[x for k in random.choices(keys,k=len(keys)) for x in by[k]]; b.append(statistics.mean(s)*100)
        b.sort()
        print('%-9s relMAE(ro) %.2f  relMAE(sale-wtd) %.2f  sold %.1f  d vs med48 %+.3f [%+.3f,%+.3f]  wins/ties/losses %d/%d/%d' % (
            n,ro,sw,sold,statistics.mean(d)*100,b[7],b[292],wins,ties,len(d)-wins-ties))
    for lo,hi in [(1,4),(5,29),(30,10**9)]:
        sub=[r for r in recs if lo<=r[1]<=hi]
        print('  n48 in [%d,%s] ro=%d: '%(lo,hi if hi<10**9 else 'inf',len(sub))+'  '.join('%s %.2f'%(n,statistics.mean(statistics.mean(r[3][n]) for r in sub)*100) for n in ['med48','selected','rwmed','mean48','q75']))
run(0,label='same grid as finding')
run(3,label='phase +3h')
run(0,hor=6,label='6h horizon')
run(0,step=1,label='1h step (dense origins)')
