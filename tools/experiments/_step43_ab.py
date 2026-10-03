# -*- coding: utf-8 -*-
import pathlib
import sys

# 归档后位置：tools/experiments/ —— 把仓库根加回 sys.path，脚本仍按仓库根为工作目录运行
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# 第4.3步 A/B 实验：R³ 完整版(损耗控制开) vs R³-SpoilageControl(关)
import json
import sys
import collections

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator

gt = simulator.load_ground_truth()
base = simulator._strategy_specs()['diannao']
specA = dict(base); specA['key'] = 'A_on'; specA['spoilage_control'] = True
specB = dict(base); specB['key'] = 'B_off'; specB['spoilage_control'] = False
resA = simulator._simulate_strategy(specA, gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)
resB = simulator._simulate_strategy(specB, gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)
KEYS = ['spoilage_units', 'spoilage_cost', 'spoilage_rate', 'cumulative_gross_margin',
        'stockout_rate', 'livelihood_stockout_rate', 'livelihood_secured_rate',
        'avg_inventory_capital', 'inventory_turnover']
print('=== A 损耗控制开 ==='); print({k: resA['summary'][k] for k in KEYS})
print('=== B 损耗控制关 ==='); print({k: resB['summary'][k] for k in KEYS})
json.dump({'A': resA['summary'], 'B': resB['summary']}, open('eval/_step43_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

logs = resA['daily_logs']
trig = [r for r in logs if r.get('spoilage_capped')]
print('TRIGGERED_ROWS', len(trig))
print('TRIGGERED_SKUS', len(set(r['sku'] for r in trig)))
print('TOTAL_REDUCED_UNITS', round(sum(r['raw_reorder_uncapped'] - r['reorder_qty'] for r in trig), 1))
by_sku = collections.Counter(r['sku'] for r in trig)
print('TOP_SKUS', by_sku.most_common(10))

for sku, n in by_sku.most_common(3):
    rows = [r for r in logs if r['sku'] == sku]
    hits = [r for r in rows if r.get('spoilage_capped')][:2]
    for h in hits:
        print('CASE', sku, h['name'], h['day'], 'min_rem', h['min_remaining_shelf'],
              'near_exp', h['near_expiry_qty'], 'uncap', h['raw_reorder_uncapped'],
              'after', h['reorder_qty'], 'demand', h['actual_demand'])
    if hits:
        tail = [r for r in rows if r['day'] >= hits[0]['day']][:6]
        print('  spoil_after', [(r['day'], r['spoilage_qty']) for r in tail])

