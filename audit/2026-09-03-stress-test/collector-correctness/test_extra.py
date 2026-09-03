"""Adversarial tests for collector.collect_market / publish / validate. Never edits the repo.
Run: cd <this dir> && python3 -m unittest test_extra -v"""
import sys, json, copy, io, contextlib, tempfile, unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0,'/home/user/-warera-case1-collector')
import collector as c

NOW=datetime(2026,9,3,12,tzinfo=timezone.utc)
CAT=next(r for r in c.categories() if r['item_code']=='sniper')

def raw(txid,hours,price=50,code='sniper',on_market=timedelta(minutes=10)):
    sold=NOW-timedelta(hours=hours)
    return {'_id':txid,'transactionType':'itemMarket','itemCode':code,'money':price,'quantity':1,
            'sellerId':'s','buyerId':'b','createdAt':c.stamp(sold),'offerCreatedAt':c.stamp(sold-on_market),
            'item':{'code':code,'state':100,'maxState':100,'skills':{'attack':121,'criticalChance':17}}}

class Stream:
    """A newest-first stream of sales, paged 100 at a time, like the Gateway."""
    base_url=c.GATEWAY; requests=0
    def __init__(self,rows,per_page=100,fail_after=None):
        self.rows=sorted(rows,key=lambda r:r['createdAt'],reverse=True); self.per=per_page; self.calls=0; self.fail_after=fail_after
    def call(self,proc,params=None):
        self.calls+=1; self.requests+=1
        if self.fail_after is not None and self.calls>self.fail_after: raise c.ApiError('outage',503)
        start=int(params.get('cursor','0') or 0)
        chunk=self.rows[start:start+self.per]
        nxt=str(start+self.per) if start+self.per<len(self.rows) else None
        return {'items':chunk,'nextCursor':nxt}

def one(client,previous,now=NOW,max_pages=1000):
    return c.collect_market(client,[CAT],{'sniper':previous},now,max_pages)['sniper']

def sales_every(minutes,hours_back,prefix='s'):
    n=int(hours_back*60/minutes)
    return [raw(f'{prefix}{i}',hours=i*minutes/60) for i in range(n)]

class StopLogic(unittest.TestCase):
    def test_backstop_ignores_checkpoint_after_long_outage(self):
        """Collector down 5h; the 6-hourly backstop is due; the scan stops at 3h and the
        sales between 3h and 5.5h ago are never fetched, and never will be."""
        base=one(Stream(sales_every(10,2,'old')),{})           # cache built 5h ago ...
        base['last_success_at']=c.stamp(NOW-timedelta(hours=5))
        base['last_full_scan_at']=c.stamp(NOW-timedelta(hours=7))  # ... backstop due
        for r in base['transactions']: r['sold_at']=c.stamp(c.parse_time(r['sold_at'])-timedelta(hours=5))
        stream=sales_every(1,8,'n')                              # 60 sales/h for 8h
        res=one(Stream(stream,per_page=100),base)
        self.assertEqual(res['stop_reason'],'backstop_3h'); self.assertEqual(res['status'],'ok')
        got={r['id'] for r in res['transactions']}
        missing=[r for r in stream if r['_id'] not in got and c.parse_time(r['createdAt'])>NOW-timedelta(hours=5.5)]
        hrs=sorted((NOW-c.parse_time(r['createdAt'])).total_seconds()/3600 for r in missing)
        print(f'\n  [backstop-outage] missed {len(missing)} of {len(stream)} sales; missed span {hrs[0]:.2f}h..{hrs[-1]:.2f}h ago; checkpoint advanced to {res["last_success_at"]}')
        self.assertGreater(len(missing),100)
        # next incremental run cannot recover them either: checkpoint is now NOW
        again=one(Stream(stream+[raw('newer',hours=0.01)]),res,now=NOW+timedelta(minutes=15))
        got2={r['id'] for r in again['transactions']}
        self.assertTrue(all(r['_id'] not in got2 for r in missing))

    def test_outage_without_backstop_is_recovered(self):
        oldraw=[raw(f'old{i}',hours=5+i/6) for i in range(12)]
        base=one(Stream(oldraw),{},now=NOW)
        base['last_success_at']=c.stamp(NOW-timedelta(hours=5)); base['last_full_scan_at']=c.stamp(NOW-timedelta(hours=5))
        stream=sales_every(1,12,'n')+oldraw
        res=one(Stream(stream),base)
        self.assertEqual(res['stop_reason'],'known_history_with_0.5h_overlap')
        got={r['id'] for r in res['transactions']}
        missing=[r for r in stream if r['_id'] not in got and c.parse_time(r['createdAt'])>NOW-timedelta(hours=5.5)]
        self.assertEqual(missing,[])

    def test_delayed_ingestion_older_than_overlap_is_only_caught_by_backstop(self):
        base=one(Stream(sales_every(0.1,3,'k')),{})   # 10 sales/min: one page spans 10 min
        base['last_success_at']=c.stamp(NOW-timedelta(minutes=15))
        late=raw('late',hours=1.0)      # ingested late, 1h old > 0.5h overlap
        res=one(Stream(sales_every(0.1,3,'k')+[late]),base)
        self.assertEqual(res['stop_reason'],'known_history_with_0.5h_overlap')
        self.assertNotIn('late',{r['id'] for r in res['transactions']})
        base['last_full_scan_at']=c.stamp(NOW-timedelta(hours=7))
        res=one(Stream(sales_every(0.1,3,'k')+[late]),base)
        self.assertIn('late',{r['id'] for r in res['transactions']})

    def test_late_sale_older_than_backstop_is_lost_forever(self):
        base=one(Stream(sales_every(1,4,'k')),{})
        base['last_success_at']=c.stamp(NOW-timedelta(minutes=15)); base['last_full_scan_at']=c.stamp(NOW-timedelta(hours=7))
        late=raw('late',hours=3.5)
        res=one(Stream(sales_every(1,4,'k')+[late]),base)
        self.assertEqual(res['stop_reason'],'backstop_3h')
        self.assertNotIn('late',{r['id'] for r in res['transactions']})

    def test_failed_run_midway_then_recovery(self):
        base=one(Stream(sales_every(1,2,'k')),{}); base['last_success_at']=c.stamp(NOW-timedelta(hours=2))
        for r in base['transactions']: r['sold_at']=c.stamp(c.parse_time(r['sold_at'])-timedelta(hours=2))
        stream=sales_every(1,5,'n')
        failed=one(Stream(stream,fail_after=1),base)     # one page then outage
        self.assertEqual(failed['status'],'error'); self.assertEqual(failed['last_success_at'],base['last_success_at'])
        self.assertEqual(len(failed['transactions']),100+len(base['transactions']))
        rec=one(Stream(stream),failed,now=NOW+timedelta(minutes=15))
        self.assertEqual(rec['status'],'ok')
        got={r['id'] for r in rec['transactions']}
        self.assertTrue(all(r['_id'] in got for r in stream if c.parse_time(r['createdAt'])>NOW-timedelta(hours=2.5)))

    def test_none_checkpoint_on_one_category_pages_to_the_boundary(self):
        """A category with last_success_at None (new manifest entry) makes checkpoint None
        and history_complete False -> full scan to the retention boundary -> page cap -> error for all."""
        manifest=c.categories()
        prev=c.collect_market(Stream(sales_every(30,2,'k')),manifest,{},NOW)
        prev['jet']['last_success_at']=None; prev['jet']['history_complete']=False
        stream=sales_every(1,200,'n')   # 200h of sales at 60/h = 12,000 rows = 120 pages
        res=c.collect_market(Stream(stream),manifest,prev,NOW,max_pages=50)
        self.assertTrue(all(r['status']=='error' for r in res.values()))
        self.assertIn('Reached 50 pages',res['sniper']['error'])
        self.assertIsNone(res['jet']['last_success_at'])
        # sniper's checkpoint is not advanced either, although its own data was complete
        self.assertEqual(res['sniper']['last_success_at'],prev['sniper']['last_success_at'])

    def test_fresh_cache_cannot_complete_history_at_real_volume(self):
        """At 60 Case-I sales/h plus non-Case-I traffic the stream is ~62 pages/h (README);
        168h = ~10,400 pages > max_pages=1000. Model 20 pages/h: still > 1000."""
        rows=[]
        for i in range(168*20*100//2):   # 20 pages/h, half of each page is non-Case-I
            h=i/(20*100/2); rows.append(raw(f'a{i}',hours=h)); rows.append(dict(raw(f'b{i}',hours=h,code='rock'),itemCode='rock'))
        res=one(Stream(rows),{},max_pages=1000)
        self.assertEqual(res['status'],'error'); self.assertFalse(res['history_complete'])
        self.assertIn('Reached 1000 pages',res['error'])
        self.assertEqual(res['pages_fetched'],1000)
        depth=(NOW-c.parse_time(res['transactions'][-1]['sold_at'])).total_seconds()/3600
        print(f'\n  [fresh-cache] 1000 pages reached {depth:.0f}h back at 20 pages/h; retained {res["transaction_count"]} rows, status error, checkpoint None')
        # and the next run does exactly the same again (never_complete stays True)
        res2=one(Stream(rows),res,now=NOW+timedelta(minutes=15),max_pages=1000)
        self.assertEqual(res2['pages_fetched'],1000); self.assertEqual(res2['status'],'error')

    def test_history_complete_survives_retention_extension(self):
        """history_complete set by a 48h scan stays True after RETENTION_HOURS grows; the
        deeper window is never paged (this is what the committed cache did on 2026-08-31)."""
        base=one(Stream(sales_every(0.1,3,'k')),{})
        self.assertTrue(base['history_complete'])
        stream=sales_every(0.1,200,'n')+sales_every(0.1,3,'k')
        res=one(Stream(stream),base,now=NOW+timedelta(minutes=15))
        self.assertEqual(res['stop_reason'],'known_history_with_0.5h_overlap'); self.assertTrue(res['history_complete'])
        oldest=min(c.parse_time(r['sold_at']) for r in res['transactions'])
        self.assertGreater(oldest,NOW-timedelta(hours=4))

    def test_sale_stamped_after_now_is_dropped_then_recovered_by_overlap(self):
        base=one(Stream(sales_every(10,2,'k')),{}); base['last_success_at']=c.stamp(NOW-timedelta(minutes=15))
        fut=raw('fut',hours=-0.01)   # 36s after `now`: ingested while the run was paging
        res=one(Stream(sales_every(10,2,'k')+[fut]),base)
        self.assertNotIn('fut',{r['id'] for r in res['transactions']})
        res2=one(Stream(sales_every(10,2,'k')+[fut]),res,now=NOW+timedelta(minutes=15))
        self.assertIn('fut',{r['id'] for r in res2['transactions']})

class Summaries(unittest.TestCase):
    def tx(self,txid,price,hours=1,on_market=timedelta(minutes=10)):
        return c.normalize_transaction(raw(txid,hours,price,on_market=on_market),'sniper')
    def test_weighted_median_is_lower_median_on_even_equal_weights(self):
        rows=[self.tx('a',1),self.tx('b',3)]
        s=c.summarize(rows,NOW)
        self.assertEqual(s['median'],2); self.assertEqual(s['weighted_median'],1)
        rows=[self.tx('a',1),self.tx('b',3),self.tx('c',3),self.tx('d',9)]
        self.assertEqual(c.summarize(rows,NOW)['weighted_median'],3)
    def test_tts_median_is_censored_at_48h(self):
        rows=[self.tx(f'q{i}',10,on_market=timedelta(hours=h)) for i,h in enumerate((1,2,60,70,80))]
        agg=c.aggregate(rows,NOW); r=next(iter(agg.values()))
        self.assertEqual(r['selected']['count'],2)
        self.assertEqual(r['selected']['median_time_to_sell_seconds'],1.5*3600)   # true median 60h
    def test_window_boundaries_inclusive(self):
        rows=[self.tx('edge',10,hours=24),self.tx('edge48',10,hours=48),self.tx('in',10,hours=1)]
        r=next(iter(c.aggregate(rows,NOW).values()))
        self.assertEqual(r['primary_24h']['count'],2); self.assertEqual(r['fallback_48h']['count'],3)
    def test_stale_filter_changes_selected_window(self):
        rows=[self.tx('a',10,hours=1),self.tx('b',10,hours=2),self.tx('c',10,hours=3,on_market=timedelta(hours=49)),self.tx('d',20,hours=30)]
        r=next(iter(c.aggregate(rows,NOW).values()))
        self.assertEqual(r['selected_window_hours'],48); self.assertEqual(r['selected']['median'],10)

class Publish(unittest.TestCase):
    def build(self,now=NOW):
        class Full(Stream):
            def call(self,proc,params=None):
                if proc=='transaction.getPaginatedTransactions': return Stream.call(self,proc,params)
                if proc=='itemTrading.getPrices': return {'case1':3.5,'scraps':0.22,'steel':1.68}
                return {'buyOrders':[],'sellOrders':[]}
        rows=[raw(f's{i}',hours=h) for i,h in enumerate((1,2,20,30,50))]
        with contextlib.redirect_stdout(io.StringIO()):
            return c.collect(Full(rows),now=now)
    def test_late_sale_rewrites_a_completed_day_file(self):
        out=self.build()
        with tempfile.TemporaryDirectory() as tmp:
            pub,arc=Path(tmp)/'p',Path(tmp)/'a'
            c.publish(out,pub,arc,NOW)
            day=(NOW-timedelta(hours=30)).date().isoformat()
            before=json.loads((arc/f'{day}.json').read_text())
            out['categories']['sniper']['transactions'].append(c.pack_transaction(c.normalize_transaction(raw('late',hours=31),'sniper')))
            out['categories']['sniper']['transaction_count']+=1
            c.publish(out,pub,arc,NOW+timedelta(minutes=15))
            after=json.loads((arc/f'{day}.json').read_text())
            self.assertEqual(after['sale_count'],before['sale_count']+1)
    def test_schema_bump_rewrites_every_day_file(self):
        out=self.build()
        with tempfile.TemporaryDirectory() as tmp:
            pub,arc=Path(tmp)/'p',Path(tmp)/'a'
            c.publish(out,pub,arc,NOW)
            m={f.name:f.stat().st_mtime_ns for f in arc.glob('*.json')}
            old=c.SCHEMA_VERSION
            try:
                c.SCHEMA_VERSION+=1
                c.publish(out,pub,arc,NOW)
            finally: c.SCHEMA_VERSION=old
            self.assertTrue(all(f.stat().st_mtime_ns!=m[f.name] for f in arc.glob('*.json')))
    def test_shard_epoch_floors(self):
        out=self.build(now=NOW.replace(microsecond=0))
        cat=out['categories']['sniper']; cat['transactions'][0]['sold_at']=cat['transactions'][0]['sold_at'][:-5]+'.900Z'
        rows,_=c.shard_rows('sniper',cat)
        sec=[r[1] for r in rows]; ts=c.parse_time(cat['transactions'][0]['sold_at']).timestamp()
        self.assertIn(int(ts),sec); self.assertNotIn(round(ts),sec)

class Validation(unittest.TestCase):
    def test_validate_accepts_error_status_cache_and_workflow_commits_it(self):
        base=one(Stream(sales_every(10,2,'k')),{})
        failed=one(Stream(sales_every(10,2,'k'),fail_after=0),base)
        self.assertEqual(failed['status'],'error')
        # emulate collect() wrapping
        payload={'schema_version':c.SCHEMA_VERSION,'generated_at':c.stamp(NOW),'categories':{cc['item_code']:{**failed,**cc,'transactions':failed['transactions'] if cc['item_code']=='sniper' else [],'transaction_count':failed['transaction_count'] if cc['item_code']=='sniper' else 0,'quality_issue_count':0,'rolls':failed['rolls'] if cc['item_code']=='sniper' else {}} for cc in c.categories()},'commodities':{k:{} for k in c.COMMODITIES}}
        self.assertEqual(c.validate(json.loads(json.dumps(payload))),len(failed['transactions']))
    def test_tolerance_rejects_summary_recomputed_by_changed_aggregate(self):
        base=one(Stream(sales_every(10,2,'k')),{})
        payload={'schema_version':c.SCHEMA_VERSION,'generated_at':c.stamp(NOW),'categories':{cc['item_code']:{**base,**cc,'transactions':base['transactions'] if cc['item_code']=='sniper' else [],'transaction_count':base['transaction_count'] if cc['item_code']=='sniper' else 0,'quality_issue_count':0,'rolls':base['rolls'] if cc['item_code']=='sniper' else {}} for cc in c.categories()},'commodities':{k:{} for k in c.COMMODITIES}}
        old=c.MAX_TIME_ON_MARKET_HOURS
        try:
            c.MAX_TIME_ON_MARKET_HOURS=1   # a policy change without a schema bump
            rows=[c.unpack_transaction(r,'sniper') for r in base['transactions']]
            self.assertTrue(c.summaries_match(c.aggregate(rows,NOW),base['rolls']))  # fixture sits 10 min so unaffected
        finally: c.MAX_TIME_ON_MARKET_HOURS=old

class ClientTests(unittest.TestCase):
    def test_deadline_makes_timeout_tiny_not_an_error(self):
        cl=c.Client(api_key='k',max_seconds=1)
        import time; cl.deadline=time.monotonic()-5
        with self.assertRaises(c.ApiError) as cm: cl.call('x')
        self.assertIn('budget',str(cm.exception))
    def test_redirect_refused(self):
        h=c.NoRedirect()
        with self.assertRaises(c.ApiError): h.redirect_request(None,None,302,'Found',{},'https://evil/')
    def test_retry_after_header_parsing(self):
        self.assertEqual(c.retry_delay('7'),7.0); self.assertEqual(c.retry_delay(None),0); self.assertEqual(c.retry_delay('garbage'),0)

if __name__=='__main__': unittest.main()
