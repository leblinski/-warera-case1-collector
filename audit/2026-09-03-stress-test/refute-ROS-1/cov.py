exec(open('indep.py').read().split("res={}")[0])
cov=sp=0
for t in range(1,7):
    for slot in SLOTW:
        out,_,_=rows(slot,t);cov+=sum(1 for x in out if x['net'] is not None);sp+=len(out)
print('Cases-tab foot would print: covered %d of %d rolls (%d%%)'%(cov,sp,round(cov/sp*100)))
# knife: contribution of unpriced share to the case gross under each fill, in gross units
for m in ['scrap','worse','fillquiet']:
    print(m,'knife delta to gross %.4f'%(ODDS[0]*SLOTW['weapon']*(slot_net('weapon',1,m)-slot_net('weapon',1,'page'))))
