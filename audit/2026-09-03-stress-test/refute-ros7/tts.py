"""Displayed 'Sells in' (selected window, stale excluded => censored at 48h) vs uncensored median tts per roll."""
import sys,json,statistics
sys.path.insert(0,'/home/user/-warera-case1-collector'); sys.path.insert(0,'/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/audit')
import collector as c, ev_ref
p=json.load(open('/home/user/-warera-case1-collector/data/warera_case1_market.json')); now=c.parse_time(p['generated_at'])
for code,slot in [('knife','weapon'),('helmet1','helmet'),('jet','weapon'),('tank','weapon')]:
    txs=[c.unpack_transaction(r,code) for r in p['categories'][code]['transactions']]
    rolls=p['categories'][code]['rolls']
    byk={}
    for t in txs:
        if not t['eligible_for_comps']: continue
        k=ev_ref.roll_key(slot,t['skills']); byk.setdefault(k,[]).append(t)
    rows=[]
    for rk,r in rolls.items():
        k=ev_ref.roll_key(slot,r['exact_roll']['skills']); st=r['selected']
        if st['median'] is None: continue
        w=st['selected_window_hours'] if 'selected_window_hours' in st else r['selected_window_hours']
        win=[t for t in byk[k] if (now-c.parse_time(t['sold_at'])).total_seconds()<=w*3600 and t['time_to_sell_seconds'] is not None]
        unc=statistics.median([t['time_to_sell_seconds'] for t in win])
        rows.append((k,st['count'],st['median_time_to_sell_seconds']/3600,unc/3600,sum(c.stale_listing(t) for t in win),len(win)))
    rows.sort()
    big=[r for r in rows if r[3]>r[2]*1.5]
    print('%s: priced rolls %d; rolls where uncensored median tts >1.5x displayed: %d; displayed median-of-medians %.1fh vs uncensored %.1fh'%(code,len(rows),len(big),statistics.median(r[2] for r in rows),statistics.median(r[3] for r in rows)))
    for r in big[:12]: print('   %s n=%d shown %.1fh actual %.1fh (stale %d of %d in window)'%r)
