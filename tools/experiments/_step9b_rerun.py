# -*- coding: utf-8 -*-
import pathlib
import sys

# 归档后位置：tools/experiments/ —— 把仓库根加回 sys.path，脚本仍按仓库根为工作目录运行
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# 第9步补跑：重跑 Full R3 vs Traditional（当前冻结代码，统一 metrics），替换旧 FINAL
import csv
import hashlib
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator

OUT = 'eval/final/r3_vs_traditional'
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
SEED = 42
BUDGET = simulator.DEFAULT_SIM_BUDGET


def sha(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()[:16]


data_ver = {'products_csv': sha('data/shopmind_products_50sku.csv'),
            'sales_csv': sha('data/shopmind_180days_50sku.csv')}
metrics_ver = sha('core/metrics.py')

gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
res = {}
for key in ('diannao', 'baseline'):
    r = simulator._simulate_strategy(specs[key], gt, BUDGET, SEED, keep_daily=True)
    res[key] = {'summary': r['summary'], 'daily_logs': r['daily_logs']}
print('runs done')

os.makedirs(OUT, exist_ok=True)
for k in res:
    rows = res[k]['daily_logs']
    with open(os.path.join(OUT, 'daily_%s.csv' % k), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

summaries = {k: res[k]['summary'] for k in res}
payload = {'name': 'r3_vs_traditional', 'frozen': 'FINAL / FROZEN', 'status': 'FINAL',
           'generated_at': NOW, 'seed': SEED, 'budget': BUDGET,
           'metric_module': 'core.metrics', 'metrics_version': metrics_ver,
           'data_version': data_ver,
           'initial_condition': 'initial_inventory = ceil(base_daily_demand * 3)',
           'config': {'class': 'C-rerun-fresh', 'strategies': [{'key': k, 'mode': specs[k]['mode'], 'use_memory': specs[k]['use_memory'], 'use_events': specs[k]['use_events'], 'protect_livelihood': specs[k]['protect_livelihood']} for k in ('diannao', 'baseline')]},
           'summaries': summaries}
with open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print('saved summary; GM:', {k: summaries[k]['cumulative_gross_margin'] for k in summaries})

fp = 'eval/final/final_experiment_summary.json'
d = json.load(open(fp, encoding='utf-8'))
d['results']['r3_vs_traditional'] = summaries
d['generated_at'] = NOW
json.dump(d, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

fz = 'eval/final/FROZEN.json'
z = json.load(open(fz, encoding='utf-8'))
z['r3_vs_traditional_rerun_at'] = NOW
json.dump(z, open(fz, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('REPLACED frozen r3_vs_traditional')
