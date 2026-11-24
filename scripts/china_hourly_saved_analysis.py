"""Deterministic hourly diagnostics from frozen evidence. No WB, Telegram or models."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from china_cloud_cost_control import Cache, stamp
from china_hourly_sales_read import ROOT, POLICY, MSK, complete_slot, analysis_ready, saved_slot, aggregate, comparison

ANALYSIS = 'china_agent:hourly_saved_analysis:v1:'


def ratio(numerator, denominator):
    return round(numerator / denominator * 100, 4) if denominator else None


def funnel_metrics(row):
    return dict(openings=row.get('clicks'), carts=row.get('cart_count'), orders=row.get('orders'),
                order_amount_cny=row.get('order_amount_cny'),
                open_cart_pct=ratio(row['cart_count'], row['clicks']),
                cart_order_pct=ratio(row['orders'], row['cart_count']),
                open_order_pct=ratio(row['orders'], row['clicks']))


def build(cache, key, source):
    cut = datetime.fromisoformat(source['slot_msk'])
    if not analysis_ready(source):
        raise ValueError('Incomplete hourly source; no invented analysis')
    orders = {}
    for offset in (0, 1, 7):
        part = source['orders'][str(offset)]
        totals = aggregate(part['rows'])
        if len({r['id'] for r in part['rows']}) != len(part['rows']) or totals != part['totals']:
            raise ValueError('Frozen order totals mismatch')
        orders[str(offset)] = totals
    sales = {str(n): comparison(orders['0'], orders[str(n)]) for n in (1, 7)}
    current = source.get('general_funnel', {})
    funnels = {}
    for offset in (1, 7):
        oldkey, old = saved_slot(cache, cut - timedelta(days=offset))
        prior = (old or {}).get('general_funnel', {})
        result = dict(status='unavailable_no_saved_same_clock_funnel', source_key=oldkey)
        if current.get('status') == prior.get('status') == 'complete':
            delta = abs((datetime.fromisoformat(current['observed_at']) -
                         datetime.fromisoformat(prior['observed_at']) - timedelta(days=offset)).total_seconds())
            have = {r['nm_id']: r['selected'] for r in prior['rows']}
            wanted = {r['nm_id']: r['selected'] for r in current['rows']}
            result.update(clock_difference_seconds=delta)
            if delta > 600:
                result['status'] = 'unavailable_clock_mismatch'
            elif have.keys() != wanted.keys():
                result['status'] = 'unavailable_product_scope_changed'
            else:
                result.update(status='comparable_snapshot', rows=[dict(nm_id=nm,
                    current=funnel_metrics(wanted[nm]), baseline=funnel_metrics(have[nm])) for nm in sorted(wanted)])
        funnels[str(offset)] = result
    return dict(status='complete' if complete_slot(source) else 'partial',
                source_status=source['status'], coverage_complete=complete_slot(source),
                method='deterministic_saved_evidence', source_key=key,
                slot_msk=source['slot_msk'], observed_at=source['observed_at'], completed_at=stamp(),
                cabinet='token_3', orders=orders, sales_comparisons=sales,
                funnel_current=[dict(nm_id=r['nm_id'], **funnel_metrics(r['selected'])) for r in current.get('rows', [])],
                funnel_same_clock=funnels, advertising=dict(status=source['advertising']['status'], totals=source['advertising']['totals']),
                advertising_coverage={k:source['advertising'].get(k) for k in
                    ('missing_ids', 'missing_live_ids', 'omitted_archived_ids', 'historical_coverage_complete', 'totals_scope')},
                ad_comparisons=source.get('ad_comparisons', {}),
                budgets=dict(status=source['budgets']['status'], count=len(source['budgets']['rows']),
                    zero_balance_ids=[r['advertId'] for r in source['budgets']['rows'] if r.get('total') == 0]),
                budget_audit=source.get('budget_audit'),
                warning='Funnel is a delayed observed snapshot, not an exact order cutoff; API past full-day counters are never used as same-clock baseline. No price/bid/economic action is inferred from hourly noise.',
                wb_writes=0, telegram_calls=0, model_calls=0, grants_action_permission=False)


def run(cache=None):
    c = cache or Cache()
    policy = c.get(POLICY) or {}
    if policy.get('enabled') is not True or policy.get('cabinet') != 'token_3' or policy.get('wb_writes') != 0:
        raise ValueError('Read-only collector policy unavailable')
    pointer = c.get(ROOT + ':latest') or {}
    key = pointer.get('source_key')
    if not isinstance(key, str) or not key.startswith(ROOT + ':snapshot:'):
        raise ValueError('Exact source pointer missing')
    source = c.get(key) or {}
    if source.get('slot_msk') != pointer.get('slot_msk'):
        raise ValueError('Source pointer mismatch')
    at = datetime.fromisoformat(source['observed_at'])
    if not 0 <= (datetime.now(timezone.utc) - at).total_seconds() <= 4800:
        raise ValueError('Hourly source stale')
    digest = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result_key = ANALYSIS + source['slot_msk'] + ':' + digest[:16]
    previous = c.get(result_key)
    if previous:
        if previous.get('status') not in ('complete', 'partial') or previous.get('source_key') != key or previous.get('source_sha256') != digest:
            raise ValueError('Prior analysis unresolved; no overwrite')
        print('Saved hourly analysis already complete; no repeated calculation or API calls')
        return previous
    value = build(c, key, source)
    value['source_sha256'] = digest
    if not c.create(result_key, value) or c.get(result_key) != value:
        raise RuntimeError('Analysis readback conflict')
    c.put(ANALYSIS + 'latest', dict(status=value['status'], source_key=result_key,
          hourly_source_key=key, slot_msk=source['slot_msk'], source_sha256=digest))
    print(json.dumps(dict(status=value['status'], source_key=result_key, wb_writes=0, telegram_calls=0, model_calls=0)))
    return value


if __name__ == '__main__':
    run()

