# -*- coding: utf-8 -*-
# 第9步：从干净状态复现 Full R³ vs Traditional，与冻结结果对比
import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator

gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
new = {}
for key in ('diannao', 'baseline'):
    r = simulator._simulate_strategy(specs[key], gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=False)
    new[key] = r['summary']

frozen = json.load(open('eval/final/r3_vs_traditional/summary.json', encoding='utf-8'))['summaries']
mem = json.load(open('eval/final/memory_ab/summary.json', encoding='utf-8'))['summaries']
KEYS = ['cumulative_gross_margin', 'stockout_rate', 'livelihood_stockout_rate',
        'livelihood_fill_rate', 'spoilage_rate', 'avg_inventory_capital', 'inventory_turnover']
for k in ('diannao', 'baseline'):
    print('###', k)
    for m in KEYS:
        print('  %-26s new=%s  frozen_r3v=%s  memory_ab_memon=%s' % (
            m, new[k].get(m), frozen[k].get(m),
            mem['memory_on'].get(m) if k == 'diannao' else '-'))
