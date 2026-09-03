import json,sys
for f in sys.argv[1:]:
    j=json.load(open(f)); print('########',f)
    print(' STAMP:',j['dataStamp'])
    p=j['price']; print(' PRICE: scrapNote=%s scrapPrice=%s floor=%s | cutCard=%s | rollFacts=%s | figure=%s hint=%s flip=%s/%s scrapDetail=%s'%(p['scrapNote'],p['scrapPrice'],p['scrapVerdict'],p['cutCard'] if not p['cutCardHidden'] else '(hidden)',p['rollFacts'],p['figure'],p['docketHint'],p['flipFigure'],p['flipDetail'],p['scrapDetail']))
    c=j['cases']; print(' CASES: %s | %s | %s | tab=%s'%(c['verdict'],c['detail'],c['rows'],c['tab'])); print('   foot:',c['foot'])
    c=j['craft']; print(' CRAFT: %s | %s | %s | scrapIn=%s'%(c['verdict'],c['detail'],c['rows'],c['scrapIn'])); print('   foot:',c['foot'])
    for k,v in j['sort'].items():
        if k.startswith('tier'): print(' SORT %s: %s || detail: %s'%(k,v['rows'],v['detail']))
    print(' SORT gate:',j['sort']['gate']); print(' SORT foot:',j['sort']['foot'])
    if 'extra' in j: print(' EXTRA:',json.dumps(j['extra']))
    print(' ERR:',j['_errors'],'REQ:',j['_requests'])
