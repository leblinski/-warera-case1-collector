import json
P='/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public'
S=json.load(open(P+'/summary.json'))
n24=n48=0; tankmax=None
for code,cat in S['categories'].items():
    for key,row in cat['rolls'].items():
        st=row['selected'] or row['fallback_48h']
        if not st or st.get('median') is None: continue
        if row['selected_window_hours']==24: n24+=1
        else: n48+=1
        fb=row['fallback_48h']
        if (st['count'] or 0)<5 and (fb['count'] or 0)>=5:
            d=abs(fb['median']-st['median'])/st['median']
            if tankmax is None or d>tankmax[0]: tankmax=(d,code,key,st['count'],st['median'],fb['count'],fb['median'])
print('priced rolls with selected_window 24h (Price tab labels Sales "last 48h"):',n24,' 48h:',n48)
print('largest 24h-vs-48h median gap among the 50:',tankmax)
