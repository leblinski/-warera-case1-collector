"""Find committed snapshots nearest each T0 and dump scrap bid / oldest sale / generated_at."""
import subprocess, json, sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0,'/home/user/-warera-case1-collector'); import collector as C
REPO='/home/user/-warera-case1-collector'
log=subprocess.run(['git','-C',REPO,'log','--format=%H %cI'],capture_output=True,text=True).stdout.split('\n')
commits=[]
for l in log:
    if not l.strip(): continue
    h,d=l.split(); commits.append((h,datetime.fromisoformat(d).astimezone(timezone.utc)))
gen=C.parse_time('2026-09-03T15:30:50.113Z')
out={}
for back in (72,48,24):
    T0=gen-timedelta(hours=back)
    cands=[c for c in commits if c[1]<=T0+timedelta(minutes=10)]
    h,d=max(cands,key=lambda c:c[1])
    raw=subprocess.run(['git','-C',REPO,'show',f'{h}:data/warera_case1_market.json'],capture_output=True,text=True).stdout
    p=json.loads(raw)
    oldest=min(C.parse_time(C.unpack_transaction(r,code)['sold_at']) for code,cat in p['categories'].items() for r in cat['transactions'])
    bid=p['commodities']['scraps']['order_book']['best_bid']
    nroll=sum(len(cat['rolls']) for cat in p['categories'].values())
    nsel=sum(1 for cat in p['categories'].values() for r in cat['rolls'].values() if r['selected']['median'] is not None)
    print(f'T0-{back}h={T0.isoformat()} commit {h[:8]} committed {d.isoformat()} generated_at={p["generated_at"]} schema={p.get("schema_version")} scrap_bid={bid} oldest_sale={oldest.isoformat()} rolls={nroll} with_selected={nsel} retained_sales={sum(len(c["transactions"]) for c in p["categories"].values())}')
    out[back]=h
json.dump(out,open(sys.argv[1],'w'))
