"""For consecutive distinct snapshots in git history: which ids are new in N+1 but have sold_at
older than generated_at(N)? Those arrived after run N. Bucket their lateness: <=0.5h (overlap
catches), 0.5h..3h (only the 6-hourly backstop catches), >3h (lost unless something else).
Run: python3 late_arrivals.py > late_arrivals.txt"""
import json, subprocess, collections
from datetime import datetime, timedelta
REPO='/home/user/-warera-case1-collector'
def pt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
shas=subprocess.run(['git','-C',REPO,'log','--format=%H','--reverse'],capture_output=True,text=True).stdout.split()
prev=None; prev_gen=None
buckets=collections.Counter(); examples=[]; total_new=0; per_run=[]
for sha in shas:
    raw=subprocess.run(['git','-C',REPO,'show',f'{sha}:data/warera_case1_market.json'],capture_output=True)
    if raw.returncode!=0 or not raw.stdout.strip(): continue
    try: p=json.loads(raw.stdout)
    except Exception: continue
    gen=p['generated_at']
    if gen==prev_gen: continue
    cur={t['id']:(code,t['sold_at']) for code,c in p['categories'].items() for t in c['transactions']}
    if prev is not None:
        stop=p['categories']['sniper'].get('stop_reason'); full=p['categories']['sniper'].get('full_scan')
        new=[(i,v) for i,v in cur.items() if i not in prev]
        late=[(i,code,s,(pt(prev_gen)-pt(s)).total_seconds()/3600) for i,(code,s) in new if pt(s)<pt(prev_gen)]
        b=collections.Counter('<=0.5h' if h<=0.5 else '0.5-3h' if h<=3 else '>3h' for *_,h in late)
        buckets.update(b); total_new+=len(new)
        per_run.append((gen,stop,full,len(new),dict(b)))
        if b['0.5-3h'] or b['>3h']:
            worst=max(late,key=lambda x:x[3])
            examples.append((prev_gen,gen,stop,full,dict(b),worst))
    prev=cur; prev_gen=gen
print('total new ids across consecutive runs',total_new)
print('late relative to previous generated_at:',dict(buckets))
print('runs with late sales beyond the 0.5h overlap:')
for e in examples: print('  ',e)
