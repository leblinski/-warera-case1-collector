"""Synthetic transaction fixtures model the documented API; no live key needed."""
import contextlib
import copy
import io
import json
import math
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import collector as c

NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
# Just past the retention window, for fixtures that must be pruned.
RETAINED_PAST = c.RETENTION_HOURS + 1
CAT = next(row for row in c.categories() if row['item_code'] == 'sniper')


def raw(txid='test-1', hours=1, price=50, code='sniper', state=100, skills=None,
        on_market=timedelta(minutes=10)):
    sold = NOW - timedelta(hours=hours)
    return {'_id': txid, 'transactionType': 'itemMarket', 'itemCode': code,
            'money': price, 'quantity': 1, 'sellerId': 'fixture-seller', 'buyerId': 'fixture-buyer',
            'createdAt': c.stamp(sold), 'offerCreatedAt': c.stamp(sold - on_market),
            'item': {'_id': 'equipment-' + txid, 'code': code, 'state': state, 'maxState': 100,
                     'skills': skills if skills is not None else {'attack': 121, 'criticalChance': 17}}}


def page(rows, cursor=None):
    return {'items': rows, 'nextCursor': cursor}


def collect_category(client, category, previous, now, max_pages=1000):
    code = category['item_code']
    return c.collect_market(client, [category], {code: previous}, now, max_pages)[code]


class SequenceClient:
    base_url = c.GATEWAY
    requests = 0

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def call(self, procedure, params=None):
        self.calls.append((procedure, params))
        self.requests += 1
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


class FullClient:
    base_url = c.GATEWAY
    requests = 0

    def call(self, procedure, params=None):
        self.requests += 1
        if procedure == 'transaction.getPaginatedTransactions':
            return page([raw(cat['item_code'] + '-new', code=cat['item_code']) for cat in c.categories()]
                        + [raw('expired', hours=RETAINED_PAST)])
        if procedure == 'itemTrading.getPrices':
            return {'case1': 3.5, 'scraps': 0.22, 'steel': 1.68}
        return {'buyOrders': [], 'sellOrders': []}


class CollectorTests(unittest.TestCase):
    def normalized(self, *args, **kwargs):
        return c.normalize_transaction(raw(*args, **kwargs), 'sniper')

    def test_all_categories_end_to_end_atomic_roundtrip(self):
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=NOW)
        self.assertEqual(output['health']['category_count'], 36)
        self.assertEqual(output['health']['transaction_count'], 36)
        self.assertEqual(output['status'], 'ok')
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'market.json'
            c.atomic_write(target, output)
            loaded = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(c.validate(loaded, True, NOW), 36)
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_exact_roll_retained_and_every_derived_field_recomputable(self):
        original = raw()
        original['item']['futureField'] = {'value': 2}
        original['sellerCountryId'] = 'fixture-country'
        tx = c.normalize_transaction(original, 'sniper')
        # Exact rolls are kept verbatim; the original payload and the wider equipment object
        # are not, because every field the collector publishes is recomputed from what is.
        self.assertEqual(tx['skills'], {'attack': 121, 'criticalChance': 17})
        self.assertEqual(tx['time_to_sell_seconds'], 600)
        self.assertTrue(tx['eligible_for_comps'])
        self.assertNotIn('raw', tx)
        self.assertNotIn('equipment', tx)
        self.assertEqual(c.derive_transaction(tx), tx)

    def test_tampered_derived_field_is_rejected_without_the_raw_payload(self):
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=NOW)
        loaded = json.loads(json.dumps(output))
        loaded['categories']['sniper']['transactions'][0]['unit_price'] = 999.0
        with self.assertRaises(c.CollectionError):
            c.validate(loaded)

    def test_retention_exceeds_comparison_window(self):
        # Rows older than the comparison window stay retained but stop being comparables.
        rows = [self.normalized('fresh', hours=1), self.normalized('kept', hours=c.COMPS_WINDOW_HOURS + 10)]
        self.assertGreater(c.RETENTION_HOURS, c.COMPS_WINDOW_HOURS)
        self.assertEqual(next(iter(c.aggregate(rows, NOW).values()))['fallback_48h']['count'], 1)

    def test_submillisecond_run_clock_survives_json_validation(self):
        now = NOW.replace(microsecond=123456)
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=now)
        loaded = json.loads(json.dumps(output))
        self.assertEqual(c.validate(loaded, True, now), 36)

    def test_platform_rounding_tolerance_still_rejects_changed_summary(self):
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=NOW)
        loaded = json.loads(json.dumps(output))
        roll = next(iter(loaded['categories']['pants4']['rolls'].values()))
        for window in ('primary_24h', 'fallback_48h', 'selected'):
            value = roll[window]['recency_weighted_price']
            roll[window]['recency_weighted_price'] = math.nextafter(value, math.inf)
        self.assertEqual(c.validate(loaded, True, NOW), 36)
        roll['selected']['recency_weighted_price'] += 0.01
        with self.assertRaises(c.CollectionError):
            c.validate(loaded, True, NOW)

    def test_shared_market_scan_distributes_and_filters_categories(self):
        client = SequenceClient([page([raw('knife-sale', code='knife'), raw('outside', code='other-case-equipment')], 'next'),
                                 page([raw('knife-sale', code='knife'), raw('jet-sale', code='jet'), raw('old', hours=RETAINED_PAST)])])
        result = c.collect_market(client, c.categories(), {}, NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertNotIn('itemCode', client.calls[0][1])
        self.assertEqual(sum(row['transaction_count'] for row in result.values()), 2)
        # item_code is not stored per row; a record's category is its position in the output.
        self.assertEqual(result['knife']['transactions'][0]['id'], 'knife-sale')
        self.assertEqual(result['jet']['transactions'][0]['id'], 'jet-sale')
        self.assertEqual(c.unpack_transaction(result['knife']['transactions'][0], 'knife')['item_code'], 'knife')
        self.assertTrue(all(row['history_complete'] for row in result.values()))
        self.assertEqual(result['sniper']['transaction_count'], 0)

    def test_one_incomplete_category_forces_complete_market_backfill(self):
        previous = c.collect_market(SequenceClient([page([raw('known', hours=2)])]), c.categories(), {}, NOW)
        previous['jet']['history_complete'] = False
        client = SequenceClient([page([raw('known', hours=2)], 'next'), page([raw('late-jet', code='jet', hours=40)])])
        result = c.collect_market(client, c.categories(), previous, NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result['jet']['transaction_count'], 1)
        self.assertTrue(all(row['full_scan'] for row in result.values()))

    def test_market_failure_keeps_commodity_observations(self):
        class BrokenMarket(FullClient):
            def call(self, procedure, params=None):
                if procedure == 'transaction.getPaginatedTransactions':
                    raise c.ApiError('Run time budget reached')
                return super().call(procedure, params)
        with contextlib.redirect_stdout(io.StringIO()):
            result = c.collect(BrokenMarket(), now=NOW)
        self.assertTrue(all(row['status'] == 'ok' for row in result['commodities'].values()))
        self.assertEqual(result['status'], 'degraded')

    def test_condition_unknown_or_used_excluded_but_retained(self):
        rows = [self.normalized('full'), self.normalized('used', state=99), self.normalized('unknown', state=None)]
        self.assertEqual(len(rows), 3)
        self.assertEqual(next(iter(c.aggregate(rows, NOW).values()))['selected']['count'], 1)
        self.assertFalse(rows[2]['full_condition'])

    def test_invalid_roll_or_price_not_used(self):
        for value in (raw(skills={}), raw(price=0), raw(price=float('nan'))):
            self.assertFalse(c.normalize_transaction(value, 'sniper')['eligible_for_comps'])

    def test_distinct_rolls_never_collapsed(self):
        rows = [self.normalized('a'), self.normalized('b', skills={'attack': 121, 'criticalChance': 18})]
        self.assertEqual(len(c.aggregate(rows, NOW)), 2)

    def test_24h_primary_excludes_older_outlier_and_recency_weights(self):
        rows = [self.normalized('a', hours=1, price=10), self.normalized('b', hours=12, price=20),
                self.normalized('c', hours=23, price=30), self.normalized('old', hours=30, price=1000)]
        roll = next(iter(c.aggregate(rows, NOW).values()))
        self.assertEqual(roll['selected_window_hours'], 24)
        self.assertEqual(roll['selected']['median'], 20)
        self.assertLess(roll['selected']['recency_weighted_price'], 20)
        self.assertEqual(roll['fallback_48h']['count'], 4)

    def test_a_sale_off_a_long_standing_listing_is_not_a_comparable(self):
        # The listing was posted under price rules that have since moved; that it happened to
        # clear inside the window says nothing about what the item is worth now.
        rows = [self.normalized('fresh-a', hours=1, price=25),
                self.normalized('fresh-b', hours=2, price=25),
                self.normalized('fresh-c', hours=3, price=25),
                self.normalized('backlog', hours=1, price=1,
                                on_market=timedelta(hours=c.MAX_TIME_ON_MARKET_HOURS + 1))]
        roll = next(iter(c.aggregate(rows, NOW).values()))
        self.assertEqual(roll['selected']['count'], 3)
        self.assertEqual(roll['selected']['median'], 25)
        self.assertEqual(roll['fallback_48h']['count'], 3)

    def test_a_listing_inside_the_window_still_counts_and_unknown_age_is_kept(self):
        rows = [self.normalized('slow', hours=1, price=10,
                                on_market=timedelta(hours=c.MAX_TIME_ON_MARKET_HOURS - 1)),
                self.normalized('quick', hours=1, price=20)]
        self.assertEqual(next(iter(c.aggregate(rows, NOW).values()))['selected']['count'], 2)
        unknown = self.normalized('unknown', hours=1, price=30)
        unknown['time_to_sell_seconds'] = None
        self.assertFalse(c.stale_listing(unknown))

    def test_a_stale_listing_is_dropped_from_the_price_but_kept_on_the_clock(self):
        """The staleness filter only ever removes slow sales, so timing with it biases low."""
        slow = timedelta(hours=c.MAX_TIME_ON_MARKET_HOURS + 4)
        rows = [self.normalized('quick', hours=1, price=20, on_market=timedelta(minutes=10)),
                self.normalized('crawler', hours=2, price=99, on_market=slow)]
        roll = next(iter(c.aggregate(rows, NOW).values()))['selected']
        # The clock counts it, so the median sits between ten minutes and four days.
        # Old behaviour reported a flat 600: the ten-minute sale, alone.
        self.assertEqual(roll['median_time_to_sell_seconds'],
                         (600 + slow.total_seconds()) / 2)
        # The price still ignores it: one comparable, and not the 99.
        self.assertEqual(roll['count'], 1)
        self.assertEqual(roll['median'], 20)
        self.assertEqual(roll['stale_excluded'], 1)

    def test_book_history_records_full_depth_and_does_not_double_a_rerun(self):
        """Intent is unrecoverable: a book not captured this run is gone for good."""
        payload = {'generated_at': c.stamp(NOW), 'commodities': {
            'case1': {'status': 'ok', 'order_book': {
                'buy_orders': [{'price': 3.5, 'quantity': 10}, {'price': 3.5, 'quantity': 5},
                               {'price': 3.4, 'quantity': 7}],
                'sell_orders': [{'price': 3.6, 'quantity': 2}]}},
            'steel': {'status': 'error'}}}
        with tempfile.TemporaryDirectory() as tmp:
            books = Path(tmp) / 'books'
            self.assertEqual(c.append_book_history(payload, books, NOW), 1)
            path = books / (NOW.date().isoformat() + '.jsonl')
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 1)
            # Orders at one price become one rung, best first, and a failed book is skipped.
            self.assertEqual(rows[0]['case1']['b'], [[3.5, 15], [3.4, 7]])
            self.assertEqual(rows[0]['case1']['a'], [[3.6, 2]])
            self.assertNotIn('steel', rows[0])
            # The same run again replaces its line rather than sampling twice.
            c.append_book_history(payload, books, NOW)
            self.assertEqual(len(path.read_text(encoding='utf-8').splitlines()), 1)
            # A later run appends, and the file stays in time order.
            later = dict(payload, generated_at=c.stamp(NOW + timedelta(minutes=15)))
            c.append_book_history(later, books, NOW)
            stamps = [json.loads(line)['t'] for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(stamps, sorted(stamps))
            self.assertEqual(len(stamps), 2)

    def test_book_history_is_skipped_when_no_commodity_reported_a_book(self):
        payload = {'generated_at': c.stamp(NOW), 'commodities': {'case1': {'status': 'error'}}}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(c.append_book_history(payload, Path(tmp) / 'books', NOW), 0)
            self.assertFalse(list((Path(tmp) / 'books').glob('*'))) if (Path(tmp) / 'books').exists() else None

    def test_raw_sale_rows_keep_the_backlog_the_statistics_drop(self):
        # Consumers that want the wider view still get every retained row.
        category = {'item_code': 'sniper', 'name': 'Sniper', 'tier': 'elite', 'rarity': 'epic',
                    'slot': 'weapon', 'status': 'ok', 'last_success_at': c.stamp(NOW),
                    'transactions': []}
        backlog = self.normalized('backlog', hours=1, price=1,
                                  on_market=timedelta(hours=c.MAX_TIME_ON_MARKET_HOURS + 1))
        category['transactions'] = [c.pack_transaction(backlog)]
        category['rolls'] = c.aggregate([backlog], NOW)
        rows, _ = c.shard_rows('sniper', category)
        self.assertEqual(category['rolls'], {})
        self.assertEqual(len(rows), 1)

    def test_sparse_24h_uses_48h_and_prunes_old_data(self):
        rows = [self.normalized('a', hours=1, price=10), self.normalized('b', hours=30, price=20),
                self.normalized('expired', hours=49, price=100)]
        roll = next(iter(c.aggregate(rows, NOW).values()))
        self.assertEqual(roll['selected_window_hours'], 48)
        self.assertEqual(roll['selected']['median'], 15)
        self.assertTrue(roll['low_sample'])

    def test_paginated_backfill_deduplicates_and_prunes(self):
        client = SequenceClient([page([raw('a'), raw('b', hours=2)], 'cursor-a'),
                                 page([raw('b', hours=2), raw('c', hours=30), raw('old', hours=RETAINED_PAST)], 'unused')])
        result = collect_category(client, CAT, {}, NOW)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual({tx['id'] for tx in result['transactions']}, {'a', 'b', 'c'})
        self.assertEqual(client.calls[1][1]['cursor'], 'cursor-a')
        self.assertEqual(client.calls[0][1]['limit'], 100)
        self.assertEqual(result['stop_reason'], 'retention_boundary')

    def test_partial_failure_does_not_poison_initial_backfill_checkpoint(self):
        first = collect_category(SequenceClient([page([raw('a')], 'next'), c.ApiError('outage')]), CAT, {}, NOW)
        self.assertFalse(first['history_complete'])
        self.assertIsNone(first['last_success_at'])
        self.assertEqual(first['transaction_count'], 1)
        retry = SequenceClient([page([raw('a')], 'next'), page([raw('b', hours=35)])])
        result = collect_category(retry, CAT, first, NOW)
        self.assertEqual(len(retry.calls), 2)
        self.assertTrue(result['history_complete'])
        self.assertEqual(result['transaction_count'], 2)

    def test_incremental_overlap_collects_delayed_transactions(self):
        previous = collect_category(SequenceClient([page([raw('known', hours=0.5), raw('older', hours=2)])]), CAT, {}, NOW)
        previous['last_success_at'] = c.stamp(NOW - timedelta(minutes=15))
        client = SequenceClient([page([raw('new', hours=0.1), raw('known', hours=0.5)], 'next'),
                                 page([raw('late', hours=1), raw('older', hours=2)], 'unneeded')])
        result = collect_category(client, CAT, previous, NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result['stop_reason'], f'known_history_with_{c.OVERLAP_HOURS:g}h_overlap')
        self.assertIn('late', {row['id'] for row in result['transactions']})

    def test_periodic_full_rescan_does_not_stop_at_known_id(self):
        previous = collect_category(SequenceClient([page([raw('known', hours=2)])]), CAT, {}, NOW)
        previous['last_full_scan_at'] = c.stamp(NOW - timedelta(hours=7))
        client = SequenceClient([page([raw('known', hours=2)], 'next'), page([raw('late', hours=40)])])
        result = collect_category(client, CAT, previous, NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(result['full_scan'])
        self.assertEqual(result['transaction_count'], 2)

    def test_periodic_backstop_does_not_repage_the_whole_retention_window(self):
        previous = collect_category(SequenceClient([page([raw('known', hours=1)])]), CAT, {}, NOW)
        self.assertTrue(previous['history_complete'])
        previous['last_full_scan_at'] = c.stamp(NOW - timedelta(hours=7))
        client = SequenceClient([page([raw('known', hours=1)], 'n1'),
                                 page([raw('deep', hours=c.BACKSTOP_HOURS + 2)], 'n2'),
                                 page([raw('deeper', hours=100)], 'n3')])
        result = collect_category(client, CAT, previous, NOW)
        self.assertTrue(result['full_scan'])
        self.assertEqual(result['stop_reason'], f'backstop_{c.BACKSTOP_HOURS:g}h')
        self.assertEqual(len(client.calls), 2)

    def test_backstop_still_reaches_a_checkpoint_older_than_it(self):
        """An outage longer than the backstop must not leave a hole in the cache."""
        previous = collect_category(SequenceClient([page([raw('known', hours=1)])]), CAT, {}, NOW)
        self.assertTrue(previous['history_complete'])
        # Four hours since the last success, against a three hour backstop, and a full scan due.
        gap = c.BACKSTOP_HOURS + 1
        previous['last_success_at'] = c.stamp(NOW - timedelta(hours=gap))
        previous['last_full_scan_at'] = c.stamp(NOW - timedelta(hours=7))
        client = SequenceClient([page([raw('recent', hours=1)], 'n1'),
                                 page([raw('in-the-gap', hours=c.BACKSTOP_HOURS + 0.5)], 'n2'),
                                 page([raw('past-the-checkpoint', hours=gap + 1)], 'n3')])
        result = collect_category(client, CAT, previous, NOW)
        self.assertTrue(result['full_scan'])
        # It keeps paging past the backstop until the checkpoint's overlap is covered.
        self.assertEqual(len(client.calls), 3)
        ids = {row['id'] for row in result['transactions']}
        self.assertIn('in-the-gap', ids)

    def test_first_run_stops_at_the_initial_depth_and_counts_as_complete(self):
        """A fresh cache cannot page the whole retention window inside the page budget."""
        client = SequenceClient([page([raw('a', hours=1)], 'n1'),
                                 page([raw('b', hours=c.INITIAL_DEPTH_HOURS + 2)], 'n2'),
                                 page([raw('c', hours=RETAINED_PAST)], 'n3')])
        result = collect_category(client, CAT, {}, NOW)
        self.assertEqual(result['stop_reason'], f'initial_depth_{c.INITIAL_DEPTH_HOURS:g}h')
        self.assertEqual(len(client.calls), 2)
        # Complete at the depth it set out to reach; retention accumulates forward from here.
        self.assertTrue(result['history_complete'])

    def test_cache_that_never_completed_history_still_pages_to_the_boundary(self):
        first = collect_category(SequenceClient([page([raw('a')], 'next'), c.ApiError('outage')]), CAT, {}, NOW)
        self.assertFalse(first['history_complete'])
        client = SequenceClient([page([raw('a')], 'n1'),
                                 page([raw('mid', hours=c.BACKSTOP_HOURS + 2)], 'n2'),
                                 page([raw('old', hours=RETAINED_PAST)], 'n3')])
        result = collect_category(client, CAT, first, NOW)
        self.assertEqual(result['stop_reason'], 'retention_boundary')
        self.assertEqual(len(client.calls), 3)
        self.assertTrue(result['history_complete'])

    def test_failed_call_preserves_good_cache_but_expires_stale_row(self):
        previous = {'transactions': [self.normalized('fresh'), self.normalized('old', hours=RETAINED_PAST)],
                    'history_complete': True, 'last_full_scan_at': c.stamp(NOW), 'last_success_at': c.stamp(NOW)}
        result = collect_category(SequenceClient([c.ApiError('outage')]), CAT, previous, NOW)
        self.assertEqual(result['status'], 'error')
        self.assertEqual([row['id'] for row in result['transactions']], ['fresh'])
        self.assertEqual(result['last_success_at'], previous['last_success_at'])

    def test_cursor_loop_and_page_cap_are_errors(self):
        for client, cap in ((SequenceClient([page([raw()], 'same'), page([raw()], 'same')]), 10),
                            (SequenceClient([page([raw()], 'next')]), 1)):
            result = collect_category(client, CAT, {}, NOW, cap)
            self.assertEqual(result['status'], 'error')
            self.assertFalse(result['history_complete'])

    def test_malformed_page_not_silently_treated_as_empty(self):
        for payload in ({}, {'items': []}, {'items': None, 'nextCursor': None}, page([], 'bad')):
            result = collect_category(SequenceClient([payload]), CAT, {}, NOW)
            self.assertEqual(result['status'], 'error')

    def test_missing_id_timestamp_and_cross_category_fail(self):
        wrong_id, wrong_time, wrong_code = raw(), raw(), raw(code='tank')
        del wrong_id['_id']
        del wrong_time['createdAt']
        for tx in (wrong_id, wrong_time, wrong_code):
            with self.assertRaises(c.CollectionError):
                c.normalize_transaction(tx, 'sniper')

    def test_real_order_book_shape_sorted_and_preserved(self):
        payload = {'buyOrders': [{'itemCode': 'case1', 'price': 3.4, 'quantity': 4}, {'price': 3.5, 'quantity': 2}],
                   'sellOrders': [{'price': 3.7, 'quantity': 5}, {'price': 3.6, 'quantity': 2}, {'price': 3.55, 'quantity': 0}]}
        result = c.normalize_book(payload, 'case1')
        self.assertEqual((result['best_bid'], result['best_ask']), (3.5, 3.6))
        self.assertEqual(result['raw'], payload)
        with self.assertRaises(c.CollectionError):
            c.normalize_book({'changedSchema': []}, 'case1')

    def test_commodity_failure_retains_price_and_timestamp(self):
        previous = {'case1': {'price': 3.5, 'price_fetched_at': c.stamp(NOW - timedelta(hours=1))}}
        client = SequenceClient([c.ApiError('prices down')] + [c.ApiError('books down')] * 3)
        result = c.collect_commodities(client, previous, NOW)
        self.assertEqual(result['case1']['price'], 3.5)
        self.assertEqual(result['case1']['price_fetched_at'], previous['case1']['price_fetched_at'])
        self.assertEqual(result['case1']['status'], 'error')

    def test_expired_commodity_price_not_carried_forward(self):
        previous = {'case1': {'price': 3.5, 'price_fetched_at': c.stamp(NOW - timedelta(hours=RETAINED_PAST))}}
        client = SequenceClient([c.ApiError('prices down')] + [c.ApiError('books down')] * 3)
        self.assertNotIn('price', c.collect_commodities(client, previous, NOW)['case1'])

    def test_failed_category_makes_whole_output_degraded(self):
        class BrokenClient(FullClient):
            def call(self, procedure, params=None):
                if procedure == 'transaction.getPaginatedTransactions':
                    raise c.ApiError('outage')
                return super().call(procedure, params)
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(BrokenClient(), now=NOW)
        self.assertEqual(output['status'], 'degraded')
        self.assertIsNone(output['updated_at'])
        self.assertEqual(len(output['health']['failed_categories']), 36)
        c.validate(output)
        with self.assertRaises(c.CollectionError):
            c.validate(output, True, NOW)

    def test_missing_key_leaves_existing_file_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'market.json'
            path.write_text('existing data', encoding='utf-8')
            with patch.dict(os.environ, {'WARERA_API_KEY': ''}), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(c.main(['--output', str(path)]), 1)
            self.assertEqual(path.read_text(), 'existing data')

    def test_corrupt_cache_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'market.json'
            path.write_text('{bad', encoding='utf-8')
            with patch.dict(os.environ, {'WARERA_API_KEY': 'test-only'}), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(c.main(['--output', str(path)]), 1)
            self.assertEqual(path.read_text(), '{bad')

    def test_trpc_envelopes_and_embedded_errors(self):
        value = page([])
        self.assertEqual(c.unwrap({'result': {'data': value}}), value)
        self.assertEqual(c.unwrap([{'result': {'data': {'json': value}}}]), value)
        with self.assertRaises(c.ApiError) as error:
            c.unwrap({'error': {'data': {'httpStatus': 401}}})
        self.assertEqual(error.exception.status, 401)

    def test_http_401_does_not_retry_or_expose_key(self):
        client = c.Client(api_key='test-secret-never-log', interval=0)
        error = HTTPError('https://example.invalid', 401, 'Unauthorized', {}, io.BytesIO(b'private response'))
        with patch('collector.build_opener') as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(c.ApiError) as raised:
                client.call('transaction.getPaginatedTransactions', {'limit': 100})
            self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertNotIn(client.api_key, str(raised.exception))

    def test_publish_emits_index_summary_and_one_shard_per_item(self):
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            public, archive = Path(tmp) / 'public', Path(tmp) / 'archive'
            c.publish(output, public, archive, NOW)
            self.assertEqual(len(list((public / 'prices').glob('*.json'))), 36)
            index = json.loads((public / 'index.json').read_text(encoding='utf-8'))
            self.assertEqual(set(index['items']), {row['item_code'] for row in c.categories()})
            summary = json.loads((public / 'summary.json').read_text(encoding='utf-8'))
            # The on-load bundle answers any price without carrying a single sale row.
            self.assertNotIn('sales', json.dumps(summary))
            self.assertTrue(summary['categories']['sniper']['rolls'])
            # Full order books ship separately: a crafting cost must walk the book, but the
            # depth is far too large to carry in the file every visitor loads.
            books = json.loads((public / 'commodities.json').read_text(encoding='utf-8'))
            self.assertEqual(set(books['commodities']), set(c.COMMODITIES))
            self.assertIn('buy_orders', books['commodities']['scraps']['order_book'])
            self.assertNotIn('raw', books['commodities']['scraps']['order_book'])
            self.assertNotIn('order_book', json.dumps(summary))
            shard = json.loads((public / 'prices' / 'sniper.json').read_text(encoding='utf-8'))
            price, sold_at, time_to_sell, roll_index = shard['sales'][0]
            self.assertEqual(price, 50)
            self.assertEqual(time_to_sell, 600)
            self.assertEqual(shard['rolls'][roll_index], {'skills': {'attack': 121, 'criticalChance': 17}})
            self.assertEqual(shard['coverage_start'], sold_at)

    def test_archive_covers_whole_days_only_and_is_written_once(self):
        client, day_before = FullClient(), NOW - timedelta(days=1)
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(client, now=NOW)
        # Backdate one sale into a completed day; today is still accumulating and is skipped.
        rows = output['categories']['sniper']['transactions']
        rows[0]['sold_at'] = c.stamp(day_before)
        with tempfile.TemporaryDirectory() as tmp:
            public, archive = Path(tmp) / 'public', Path(tmp) / 'archive'
            c.publish(output, public, archive, NOW)
            files = sorted(p.name for p in archive.glob('*.json'))
            self.assertEqual(files, [day_before.date().isoformat() + '.json'])
            target = archive / files[0]
            record = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(record['sale_count'], 1)
            self.assertEqual(record['sales'][0]['item_code'], 'sniper')
            before = target.stat().st_mtime_ns
            c.publish(output, public, archive, NOW)
            self.assertEqual(target.stat().st_mtime_ns, before)

    def test_schema_1_cache_migrates_without_a_refetch(self):
        legacy = {'schema_version': 1, 'categories': {'sniper': {'transactions': [
            dict(self.normalized('legacy'), raw=raw(), equipment={'gone': True},
                 exact_roll={'skills': {'attack': 121}})]}}}
        migrated = c.migrate(legacy)
        row = migrated['categories']['sniper']['transactions'][0]
        self.assertEqual(migrated['schema_version'], c.SCHEMA_VERSION)
        self.assertEqual(set(row), set(c.STORED_FIELDS) - {'stats'})
        self.assertEqual(c.unpack_transaction(row, 'sniper')['unit_price'], 50)
        with self.assertRaises(c.CollectionError):
            c.migrate({'schema_version': 99})

    def test_every_older_schema_migrates_into_a_cache_that_validates(self):
        # The failure this guards against took the collector down for three hours: a change to
        # aggregate() left every existing cache failing validate()'s tamper check, so the
        # collector rejected its own cache on load. Any future change to aggregate() does the
        # same, so the invariant is checked for every version migrate() claims to accept.
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=NOW)
        for version in range(1, c.SCHEMA_VERSION):
            aged = json.loads(json.dumps(output))
            aged['schema_version'] = version
            with contextlib.redirect_stdout(io.StringIO()):
                migrated = c.migrate(aged)
            self.assertEqual(migrated['schema_version'], c.SCHEMA_VERSION, f'from schema {version}')
            self.assertEqual(c.validate(migrated, True, NOW), 36, f'from schema {version}')

    def test_a_roll_silent_in_the_comps_window_still_reports_the_retained_one(self):
        # A roll is about one percent of its slot, so most are quiet on any given day. Without
        # the wider window a reader cannot tell "nobody wants this" from "none since Tuesday".
        rows = [self.normalized('recent', hours=1, price=25),
                self.normalized('older', hours=c.COMPS_WINDOW_HOURS + 20, price=20,
                                skills={'attack': 122, 'criticalChance': 17})]
        rolls = c.aggregate(rows, NOW)
        quiet = rolls[c.canonical({'skills': {'attack': 122, 'criticalChance': 17}})]
        self.assertIsNone(quiet['selected']['median'])
        self.assertEqual(quiet['selected']['count'], 0)
        self.assertEqual(quiet['retained_window']['median'], 20)
        self.assertEqual(quiet['retained_window']['count'], 1)
        self.assertEqual(quiet['retained_window_hours'], c.RETENTION_HOURS)
        # and a roll that did trade recently is unaffected
        loud = rolls[c.canonical({'skills': {'attack': 121, 'criticalChance': 17}})]
        self.assertEqual(loud['selected']['median'], 25)

    def test_schema_2_cache_has_its_summaries_rebuilt_not_trusted(self):
        # A cache written before the time-on-market filter carries summaries the current
        # aggregate() would not produce. validate() recomputes them as a tamper check, so
        # unless the migration rebuilds them the collector rejects its own cache on load.
        backlog = self.normalized('backlog', hours=1, price=1,
                                  on_market=timedelta(hours=c.MAX_TIME_ON_MARKET_HOURS + 1))
        fresh = self.normalized('fresh', hours=1, price=25)
        legacy = {'schema_version': 2, 'generated_at': c.stamp(NOW), 'categories': {'sniper': {
            'transactions': [c.pack_transaction(backlog), c.pack_transaction(fresh)],
            'rolls': {'stale-summary-the-old-code-produced': {}}}}}
        migrated = c.migrate(legacy)
        self.assertEqual(migrated['schema_version'], c.SCHEMA_VERSION)
        rolls = migrated['categories']['sniper']['rolls']
        self.assertTrue(c.summaries_match(
            c.aggregate([backlog, fresh], NOW), rolls))
        self.assertEqual(next(iter(rolls.values()))['selected']['count'], 1)
        self.assertEqual(next(iter(rolls.values()))['selected']['median'], 25)


if __name__ == '__main__':
    unittest.main()
