"""Cadence, page cost and scan-mode statistics from history.tsv. Run: python3 history_analyze.py"""
import csv, statistics, collections
from datetime import datetime, timezone
rows=[r for r in csv.DictReader(open('history.tsv'),delimiter='\t') if r['schema'] not in ('nofile','noparse','')]
def pt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
# dedupe by generated_at (merge commits repeat a snapshot)
uniq={}
for r in rows: uniq.setdefault(r['generated_at'],r)
runs=sorted(uniq.values(),key=lambda r:r['generated_at'])
print('distinct runs',len(runs),'first',runs[0]['generated_at'],'last',runs[-1]['generated_at'])
gaps=[(pt(b['generated_at'])-pt(a['generated_at'])).total_seconds()/60 for a,b in zip(runs,runs[1:])]
print(f'gap minutes: median {statistics.median(gaps):.1f} p90 {sorted(gaps)[int(.9*len(gaps))]:.1f} max {max(gaps):.1f}; gaps>30min: {sum(g>30 for g in gaps)}, >60: {sum(g>60 for g in gaps)}, >180: {sum(g>180 for g in gaps)}')
for a,b,g in zip(runs,runs[1:],gaps):
    if g>45: print(f'   gap {g:6.1f} min  {a["generated_at"]} -> {b["generated_at"]}  next run: stop={b["stop"]} pages={b["pages"]} full_scan={b["full_scan"]} status={b["status"]} min_last_success={b["min_last_success"]} last_full_scan={b["last_full_scan"]}')
print('stop reasons',collections.Counter(r['stop'] for r in runs))
print('status',collections.Counter(r['status'] for r in runs),'failed',[ (r['generated_at'],r['failed']) for r in runs if r['failed']])
print('schema',collections.Counter(r['schema'] for r in runs))
print('history_complete',collections.Counter(r['hist_complete'] for r in runs))
fs=[r for r in runs if r['full_scan']=='True']
print('full_scan runs',len(fs))
for r in fs: print('   ',r['generated_at'],r['stop'],'pages',r['pages'],'requests',r['requests'],'tx',r['tx_count'],'oldest',r['oldest_sold'])
inc=[r for r in runs if r['stop']=='known_history_with_0.5h_overlap']
pg=[int(r['pages']) for r in inc]
print(f'incremental runs {len(inc)}: pages median {statistics.median(pg)} max {max(pg)}; requests median {statistics.median(int(r["requests"]) for r in inc)}')
# pages per hour of stream: for backstop_3h runs: pages/3h; for incremental: pages/(gap+0.5h)
for r in fs:
    if r['stop'].startswith('backstop'): print(f'   backstop run {r["generated_at"]}: {int(r["pages"])/3:.1f} pages/hour of stream')
ph=[]
for a,b,g in zip(runs,runs[1:],gaps):
    if b['stop']=='known_history_with_0.5h_overlap': ph.append(int(b['pages'])/((g+30)/60))
print(f'incremental pages per stream-hour: median {statistics.median(ph):.1f} p90 {sorted(ph)[int(.9*len(ph))]:.1f} max {max(ph):.1f}')
print('oldest retained over time (first/last):',runs[0]['oldest_sold'],runs[-1]['oldest_sold'])
print('tx_count first/last',runs[0]['tx_count'],runs[-1]['tx_count'])
# retention cutoff vs oldest for last run
last=runs[-1]; from datetime import timedelta
print('last run 168h cutoff',(pt(last['generated_at'])-timedelta(hours=168)).isoformat(),'oldest',last['oldest_sold'])
