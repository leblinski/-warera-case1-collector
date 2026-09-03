"""Case edge over every committed snapshot of the collector's rolling cache."""
import subprocess, json, sys, io
sys.path.insert(0,'/home/user/-warera-case1-collector'); sys.path.insert(0,'.')
import collector as c
from ev_ref import Model
repo='/home/user/-warera-case1-collector'
shas=subprocess.check_output(['git','-C',repo,'rev-list','--reverse','HEAD'],text=True).split()
print('%-8s %-24s %6s %6s %7s %7s %7s  %s'%('sha','generated_at','scrap','ask','gross','edge','edge%','schema/txns'))
for sha in shas:
    try:
        raw=subprocess.check_output(['git','-C',repo,'show',f'{sha}:data/warera_case1_market.json'],text=True)
    except subprocess.CalledProcessError:
        print(sha[:8],'no cache file');continue
    p=json.loads(raw); v=p.get('schema_version')
    try:
        p=c.migrate(p) if v!=c.SCHEMA_VERSION else p
    except Exception as e:
        print(sha[:8],p.get('generated_at'),'migrate failed:',e);continue
    try:
        m=Model(p,tax=1.0,bar_abs=0.10); r=m.case(1)
        print('%-8s %-24s %6.4f %6.3f %7.4f %+7.4f %+6.2f%%  v%s/%d'%(sha[:8],p['generated_at'],m.scrap_bid,r['cost']['unit'],r['gross'],r['edge'],r['pct'],v,p['health']['transaction_count']))
    except Exception as e:
        print(sha[:8],p.get('generated_at'),'model failed:',e)
