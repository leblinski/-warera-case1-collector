"""Knife 40/5 'Sells in' as the page shows it, and how thin the basic sell-verdict rolls are."""
import json,sys,statistics
sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import ev_ref
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json'))
m=ev_ref.Model(p,tax=1.0,bar_abs=0.10)
def sellsIn(secs):
    if secs is None or not secs>0: return '—'
    mm=secs/60
    if mm<1: return '<1m'
    if mm<90: return '%dm'%round(mm)
    h=mm/60
    return ('%.1fh'%h if h<10 else '%.0fh'%h) if h<48 else '%dd'%round(h/24)
cat=p['categories'][ev_ref.item_code('weapon',1)]
for key,row in cat['rolls'].items():
    k=ev_ref.roll_key('weapon',row['exact_roll']['skills'])
    if k=='40/5':
        st=row['selected'] or row['fallback_48h']
        print('knife 40/5: selected window',row['selected_window_hours'],'count',st['count'],'median',st['median'],'tts',st['median_time_to_sell_seconds'],'-> page cell',sellsIn(st['median_time_to_sell_seconds']))
# thin share among basic sell-verdict rolls
n=thin=0;secs=[];secs_fat=[]
for slot in ev_ref.SLOTS:
    v=m.slot_value(slot,1); code=ev_ref.item_code(slot,1)
    rows={ev_ref.roll_key(slot,r['exact_roll']['skills']):r for r in p['categories'][code]['rolls'].values()}
    for k,pr,sale,sells in v['rows']:
        if not sells: continue
        st=rows[k]['selected'] or rows[k]['fallback_48h']; n+=1
        if st['count']<5: thin+=1
        if st['median_time_to_sell_seconds'] is not None:
            secs.append(st['median_time_to_sell_seconds'])
            if st['count']>=5: secs_fat.append(st['median_time_to_sell_seconds'])
print('basic sell-verdict rolls %d, thin(<5 sales) %d; median tts all %.1f min, non-thin only %.1f min (n=%d)'%(n,thin,statistics.median(secs)/60,statistics.median(secs_fat)/60,len(secs_fat)))
