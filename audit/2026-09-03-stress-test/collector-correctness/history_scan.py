"""Walk every commit of the collector repo and dump per-run header fields of the rolling cache.
Usage: python3 history_scan.py > history.tsv"""
import json, subprocess, sys
REPO='/home/user/-warera-case1-collector'
shas=subprocess.run(['git','-C',REPO,'log','--format=%H %ct','--reverse'],capture_output=True,text=True).stdout.split('\n')
print('\t'.join(['sha','commit_ts','schema','generated_at','updated_at','status','tx_count','requests','stop','pages','full_scan','hist_complete','last_full_scan','oldest_sold','newest_sold','min_last_success','failed']))
for line in shas:
    if not line.strip(): continue
    sha,ct=line.split()
    raw=subprocess.run(['git','-C',REPO,'show',f'{sha}:data/warera_case1_market.json'],capture_output=True)
    if raw.returncode!=0 or not raw.stdout.strip():
        print('\t'.join([sha[:7],ct,'nofile']+['']*15)); continue
    try:
        p=json.loads(raw.stdout)
    except Exception as e:
        print('\t'.join([sha[:7],ct,'noparse']+['']*15)); continue
    cats=p.get('categories',{})
    c=cats.get('sniper',{})
    olds=[t['sold_at'] for cc in cats.values() for t in cc.get('transactions',[])]
    print('\t'.join(str(x) for x in [sha[:7],ct,p.get('schema_version'),p.get('generated_at'),p.get('updated_at'),p.get('status'),
        p.get('health',{}).get('transaction_count'),p.get('health',{}).get('request_count'),
        c.get('stop_reason'),c.get('pages_fetched'),c.get('full_scan'),c.get('history_complete'),c.get('last_full_scan_at'),
        min(olds) if olds else '',max(olds) if olds else '',
        min((cc.get('last_success_at') or '') for cc in cats.values()),
        ','.join(p.get('health',{}).get('failed_categories',[]))]))
    sys.stdout.flush()
