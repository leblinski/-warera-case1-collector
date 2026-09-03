"""(e) cont.: sweep the 50 committed snapshots for the brief's 3.7114 case gross, and report the
time-to-sell populations on that snapshot."""
import json, subprocess, sys, os, statistics, collections
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
REPO='/home/user/-warera-case1-collector'
commits=[l.split()[0] for l in open('commits.txt')]
res=[]
best=None
for h in commits:
    raw=subprocess.run(['git','-C',REPO,'show',h+':data/warera_case1_market.json'],capture_output=True).stdout
    try: p=json.loads(raw)
    except Exception as e: print(h,'no snapshot');continue
    m=ev_ref.Model(p,tax=1.0,bar_abs=0.10);c=m.case(1)
    n=sum(cat['transaction_count'] for cat in p['categories'].values())
    res.append((h,p['generated_at'],c['gross'],c['cost']['unit'],c['pct'],n))
    if best is None or abs(c['gross']-3.7114)<abs(best[2]-3.7114):best=(h,p['generated_at'],c['gross'],c['cost']['unit'],c['pct'],n,p)
for r in res: print(r[0][:8],r[1],'gross %.4f cost %.3f pct %+.2f%% tx %d'%r[2:])
h,gen,g,cost,pct,n,p=best
print('\nclosest to 3.7114:',h[:8],gen,'gross %.4f cost %.3f pct %+.2f%%'%(g,cost,pct))
open('brief_snapshot.json','w').write(json.dumps(p))
json.dump([r[:6] for r in res],open('e2_commits.json','w'),indent=1)
