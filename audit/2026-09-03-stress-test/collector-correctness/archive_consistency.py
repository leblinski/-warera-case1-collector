"""Archive vs rolling cache: id uniqueness across day files, per-day counts rolling vs archive,
sales the rolling cache has for a completed day that the archive lacks (late arrivals not yet merged) and vice versa.
Run: python3 archive_consistency.py"""
import json, glob, collections
from datetime import datetime
A='/home/user/-warera-case1-collector/data/archive/'
def pt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
arch={}; ids=collections.Counter()
for f in sorted(glob.glob(A+'*.json')):
    d=json.load(open(f)); day=d['date']
    arch[day]={r['id']:r for r in d['sales']}
    for r in d['sales']:
        ids[r['id']]+=1
        assert pt(r['sold_at']).date().isoformat()==day, (day,r['sold_at'])
    assert d['sale_count']==len(d['sales'])
print('ids appearing in >1 day file:',sum(1 for v in ids.values() if v>1))
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
roll=collections.defaultdict(dict)
for code,c in p['categories'].items():
    for t in c['transactions']: roll[pt(t['sold_at']).date().isoformat()][t['id']]={**t,'item_code':code}
print('day        archive  rolling  rolling-only  archive-only')
for day in sorted(set(arch)|set(roll)):
    a=arch.get(day,{}); r=roll.get(day,{})
    ro=set(r)-set(a); ao=set(a)-set(r)
    print(f'{day} {len(a):8d} {len(r):8d} {len(ro):13d} {len(ao):13d}')
    if ro:
        ex=sorted(ro,key=lambda i:r[i]['sold_at'])[:3]; print('   rolling-only examples:',[(r[i]['item_code'],r[i]['sold_at']) for i in ex])
    if a and r:
        diff=[i for i in set(a)&set(r) if {k:v for k,v in a[i].items()}!={k:v for k,v in r[i].items()}]
        if diff: print('   rows differing between archive and rolling:',len(diff))
