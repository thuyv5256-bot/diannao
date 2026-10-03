# -*- coding: utf-8 -*-
import pathlib
import sys

# 归档后位置：tools/experiments/ —— 把仓库根加回 sys.path，脚本仍按仓库根为工作目录运行
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# 第9.2步：FINAL 最终复现验收（只读，不覆盖 FINAL）
import hashlib
import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator


def sha(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()[:16]


frozen = json.load(open('eval/final/r3_vs_traditional/summary.json', encoding='utf-8'))
cur_data = {'products_csv': sha('data/shopmind_products_50sku.csv'),
            'sales_csv': sha('data/shopmind_180days_50sku.csv')}
print('data_version match:', frozen['data_version'] == cur_data, cur_data)
print('metrics_version match:', frozen['metrics_version'] == sha('core/metrics.py'))

gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
new = {}
for key in ('diannao', 'baseline'):
    new[key] = simulator._simulate_strategy(specs[key], gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=False)['summary']
print('rerun done')

KEYS = ['cumulative_gross_margin', 'stockout_rate', 'livelihood_stockout_rate',
        'livelihood_fill_rate', 'spoilage_rate', 'spoilage_cost', 'spoilage_qty',
        'avg_inventory_capital', 'inventory_turnover']
allok = True
for k in ('diannao', 'baseline'):
    print('###', k)
    for m in KEYS:
        a = new[k].get(m)
        b = frozen['summaries'][k].get(m)
        diff = round(a - b, 6) if (isinstance(a, (int, float)) and isinstance(b, (int, float))) else None
        same = (diff == 0)
        if not same:
            allok = False
        print('  %-26s new=%s  frozen=%s  diff=%s  same=%s' % (m, a, b, diff, same))
print('ALL_EXACT_MATCH:', allok)
