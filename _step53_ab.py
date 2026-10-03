# -*- coding: utf-8 -*-
# 第5.3步 A/B 实验：Full R³(启用Memory) vs R³ - Memory(禁用Memory)
import sys
import collections

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator

gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
A = simulator._simulate_strategy(specs['diannao'], gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)
B = simulator._simulate_strategy(specs['diannao_no_memory'], gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)

KEYS = ['cumulative_gross_margin', 'stockout_rate', 'livelihood_stockout_rate',
        'livelihood_secured_rate', 'spoilage_rate', 'spoilage_cost', 'spoilage_units',
        'avg_inventory_capital', 'inventory_turnover', 'memory_experiences']
print('=== A Full R3 ===')
print({k: A['summary'][k] for k in KEYS})
print('=== B R3 - Memory ===')
print({k: B['summary'][k] for k in KEYS})


def mape(res):
    num = den = 0.0
    for r in res['daily_logs']:
        a, f = r['actual_demand'], r['forecast_demand']
        if a > 0:
            num += abs(a - f)
            den += a
    return num / den if den > 0 else 0.0


print('MAPE A', round(mape(A), 4), 'MAPE B', round(mape(B), 4))

logs = A['daily_logs']
hits = [r for r in logs if r['memory_adjustment_factor'] != 1.0]
deltas = [abs(r['memory_delta']) for r in hits]
print('HIT_ROWS', len(hits), 'HIT_SKUS', len(set(r['sku'] for r in hits)))
print('AVG_ABS_DELTA', round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
      'MAX_ABS_DELTA', round(max(deltas), 4) if deltas else 0.0)

bmap = {(r['day'], r['sku']): r['reorder_qty'] for r in B['daily_logs']}
changed = [r for r in logs if abs(r['reorder_qty'] - bmap.get((r['day'], r['sku']), 0.0)) > 1e-9]
print('CHANGED_REORDER_ROWS', len(changed), 'CHANGED_SKUS', len(set(r['sku'] for r in changed)))
c = collections.Counter(r['sku'] for r in changed)
print('TOP_CHANGED_SKUS', c.most_common(8))

print('--- CASES ---')
for sku, _n in c.most_common(3):
    rows = [r for r in logs if r['sku'] == sku]
    nm = rows[0]['name'] if rows else sku
    print('CASE', sku, nm)
    learns = [r for r in rows if (r['stockout_qty'] / max(r['sold_qty'] + r['stockout_qty'], 1e-9) > 0.1)
              or (r['spoilage_qty'] / max(r['sold_qty'] + r['spoilage_qty'], 1e-9) > 0.1)]
    for r in learns[:2]:
        print('   LEARN', r['day'], 'fc=%.1f' % r['forecast_demand'], 'sold=%.0f' % r['sold_qty'],
              'stockout=%.0f' % r['stockout_qty'], 'spoilage=%.0f' % r['spoilage_qty'])
    shown = 0
    for r in rows:
        if abs(r['reorder_qty'] - bmap.get((r['day'], sku), 0.0)) > 1e-9:
            print('  ', r['day'], 'factor=%.3f' % r['memory_adjustment_factor'],
                  'fc=%.1f' % r['forecast_demand'], 'dem=%.1f' % r['actual_demand'],
                  'A_reorder=%.0f' % r['reorder_qty'], 'B_reorder=%.0f' % bmap.get((r['day'], sku), 0.0),
                  'sold=%.0f' % r['sold_qty'], 'stockout=%.0f' % r['stockout_qty'])
            shown += 1
            if shown >= 5:
                break
