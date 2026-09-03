"""Sale density around the windows the backstop bug should have skipped, from the archive + rolling cache.
Run: python3 holes.py"""
import json, collections
from datetime import datetime, timedelta, timezone
A='/home/user/-warera-case1-collector/data/archive/'
def pt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def load(day): return json.load(open(A+day+'.json'))['sales']
def density(day, start, end, step=10):
    rows=load(day); cnt=collections.Counter()
    for r in rows:
        t=pt(r['sold_at'])
        if start<=t<end: cnt[int((t-start).total_seconds()//(step*60))]+=1
    n=int((end-start).total_seconds()//(step*60))
    return [cnt[i] for i in range(n)]
cases=[('2026-09-01',datetime(2026,9,1,0,30,tzinfo=timezone.utc),datetime(2026,9,1,4,0,tzinfo=timezone.utc),'01:46:38','02:35:41'),
       ('2026-09-02',datetime(2026,9,2,3,30,tzinfo=timezone.utc),datetime(2026,9,2,6,0,tzinfo=timezone.utc),'04:30:43','04:51:26')]
for day,s,e,h0,h1 in cases:
    print(f'== {day} predicted hole {h0}..{h1} (10-min buckets from {s.time()})')
    d=density(day,s,e)
    print('   this day :',d)
    for off in (-1,1,2):
        dd=(s+timedelta(days=off)).date().isoformat()
        try: print(f'   day {off:+d}   :',density(dd,s+timedelta(days=off),e+timedelta(days=off)))
        except FileNotFoundError: pass
    # exact count inside the predicted hole vs the same-length windows before/after
    hs=datetime.fromisoformat(f'{day}T{h0}+00:00'); he=datetime.fromisoformat(f'{day}T{h1}+00:00'); L=he-hs
    rows=load(day)
    def cnt(a,b): return sum(1 for r in rows if a<=pt(r['sold_at'])<b)
    print(f'   sales in hole {cnt(hs,he)}; same length before {cnt(hs-L,hs)}; after {cnt(he,he+L)}; hole length {L}')
