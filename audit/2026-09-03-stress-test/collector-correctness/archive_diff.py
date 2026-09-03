"""For every commit that touched data/archive, show per-day sale_count and, for modified files,
what changed (schema_version, ids added/removed and how late the added sales were vs the run)."""
import json, subprocess, collections
REPO='/home/user/-warera-case1-collector'
def show(sha,path):
    r=subprocess.run(['git','-C',REPO,'show',f'{sha}:{path}'],capture_output=True)
    return json.loads(r.stdout) if r.returncode==0 and r.stdout.strip() else None
log=subprocess.run(['git','-C',REPO,'log','--format=%H','--reverse','--','data/archive'],capture_output=True,text=True).stdout.split()
for sha in log:
    files=subprocess.run(['git','-C',REPO,'show','--format=','--name-status',sha],capture_output=True,text=True).stdout.split('\n')
    snap=show(sha,'data/warera_case1_market.json')
    gen=snap['generated_at'] if snap else '?'
    print(f'== {sha[:7]} generated_at={gen}')
    for line in files:
        if not line.strip() or 'data/archive' not in line: continue
        status,path=line.split('\t')
        new=show(sha,path)
        if status=='A':
            print(f'  A {path} schema={new.get("schema_version")} sale_count={new["sale_count"]}')
            continue
        old=show(sha+'^',path)
        oi={r['id']:r for r in old['sales']}; ni={r['id']:r for r in new['sales']}
        added=[ni[i] for i in ni if i not in oi]; removed=[i for i in oi if i not in ni]
        changed=[i for i in ni if i in oi and ni[i]!=oi[i]]
        meta_changed={k:(old.get(k),new.get(k)) for k in set(old)|set(new) if k!='sales' and old.get(k)!=new.get(k)}
        print(f'  M {path} schema {old.get("schema_version")}->{new.get("schema_version")} sale_count {old["sale_count"]}->{new["sale_count"]} added={len(added)} removed={len(removed)} changed_rows={len(changed)} meta={meta_changed}')
        if changed:
            i=changed[0]; print('    example changed row keys:', {k:(oi[i].get(k),ni[i].get(k)) for k in set(oi[i])|set(ni[i]) if oi[i].get(k)!=ni[i].get(k)})
        if added:
            by=collections.Counter(r['item_code'] for r in added)
            print('    added by item:',dict(by.most_common(8)))
            print('    added sold_at range:',min(r['sold_at'] for r in added),max(r['sold_at'] for r in added))
