"""Synthetic transaction fixtures model the documented API; no live key needed."""
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import collector as c

NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
CAT = next(row for row in c.categories() if row['item_code'] == 'sniper')


def raw(txid='test-1', hours=1, price=50, code='sniper', state=100, skills=None):
    sold = NOW - timedelta(hours=hours)
    return {'_id': txid, 'transactionType': 'itemMarket', 'itemCode': code,
            'money': price, 'quantity': 1, 'sellerId': 'fixture-seller', 'buyerId': 'fixture-buyer',
            'createdAt': c.stamp(sold), 'offerCreatedAt': c.stamp(sold - timedelta(minutes=10)),
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
                        + [raw('expired', hours=49)])
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

    def test_exact_equipment_and_unknown_fields_retained(self):
        original = raw()
        original['item']['futureField'] = {'value': 2}
        original['sellerCountryId'] = 'fixture-country'
        tx = c.normalize_transaction(original, 'sniper')
        self.assertEqual(tx['raw'], original)
        self.assertEqual(tx['equipment'], original['item'])
        self.assertEqual(tx['skills'], {'attack': 121, 'criticalChance': 17})
        self.assertEqual(tx['time_to_sell_seconds'], 600)
        self.assertTrue(tx['eligible_for_comps'])

    def test_submillisecond_run_clock_survives_json_validation(self):
        now = NOW.replace(microsecond=123456)
        with contextlib.redirect_stdout(io.StringIO()):
            output = c.collect(FullClient(), now=now)
        loaded = json.loads(json.dumps(output))
        self.assertEqual(c.validate(loaded, True, now), 36)

    def test_shared_market_scan_distributes_and_filters_categories(self):
        client = SequenceClient([page([raw('knife-sale', code='knife'), raw('outside', code='other-case-equipment')], 'next'),
                                 page([raw('knife-sale', code='knife'), raw('jet-sale', code='jet'), raw('old', hours=49)])])
        result = c.collect_market(client, c.categories(), {}, NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertNotIn('itemCode', client.calls[0][1])
        self.assertEqual(sum(row['transaction_count'] for row in result.values()), 2)
        self.assertEqual(result['knife']['transactions'][0]['item_code'], 'knife')
        self.assertEqual(result['jet']['transactions'][0]['item_code'], 'jet')
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

    def test_sparse_24h_uses_48h_and_prunes_old_data(self):
        rows = [self.normalized('a', hours=1, price=10), self.normalized('b', hours=30, price=20),
                self.normalized('expired', hours=49, price=100)]
        roll = next(iter(c.aggregate(rows, NOW).values()))
        self.assertEqual(roll['selected_window_hours'], 48)
        self.assertEqual(roll['selected']['median'], 15)
        self.assertTrue(roll['low_sample'])

    def test_paginated_backfill_deduplicates_and_prunes(self):
        client = SequenceClient([page([raw('a'), raw('b', hours=2)], 'cursor-a'),
                                 page([raw('b', hours=2), raw('c', hours=30), raw('old', hours=49)], 'unused')])
        result = collect_category(client, CAT, {}, NOW)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual({tx['id'] for tx in result['transactions']}, {'a', 'b', 'c'})
        self.assertEqual(client.calls[1][1]['cursor'], 'cursor-a')
        self.assertEqual(client.calls[0][1]['limit'], 100)
        self.assertEqual(result['stop_reason'], '48h_boundary')

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
        self.assertEqual(result['stop_reason'], 'known_history_with_1h_overlap')
        self.assertIn('late', {row['id'] for row in result['transactions']})

    def test_periodic_full_rescan_does_not_stop_at_known_id(self):
        previous = collect_category(SequenceClient([page([raw('known', hours=2)])]), CAT, {}, NOW)
        previous['last_full_scan_at'] = c.stamp(NOW - timedelta(hours=7))
        client = SequenceClient([page([raw('known', hours=2)], 'next'), page([raw('late', hours=40)])])
        result = collect_category(client, CAT, previous, NOW)
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(result['full_scan'])
        self.assertEqual(result['transaction_count'], 2)

    def test_failed_call_preserves_good_cache_but_expires_49h_row(self):
        previous = {'transactions': [self.normalized('fresh'), self.normalized('old', hours=49)],
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
        previous = {'case1': {'price': 3.5, 'price_fetched_at': c.stamp(NOW - timedelta(hours=49))}}
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


if __name__ == '__main__':
    unittest.main()
