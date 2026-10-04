# -*- coding: utf-8 -*-
import pathlib
import sys

# 归档后位置：tools/experiments/ —— 把仓库根加回 sys.path，脚本仍按仓库根为工作目录运行
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# 第8.3步：生成并冻结最终实验结果（统一 core.metrics 口径）
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import metrics, r3_optimizer, simulator

OUT = 'eval/final'
os.makedirs(OUT, exist_ok=True)
NOW = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
SEED = 42
BUDGET = simulator.DEFAULT_SIM_BUDGET
gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
prod_map = gt['prod_map']


def save(name, config, results):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    payload = {'name': name, 'frozen': 'FINAL / FROZEN', 'generated_at': NOW,
               'seed': SEED, 'budget': BUDGET, 'metric_module': 'core.metrics',
               'config': config,
               'summaries': {k: v['summary'] for k, v in results.items()}}
    with open(os.path.join(d, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    for k, v in results.items():
        rows = v.get('daily_logs') or []
        if rows:
            with open(os.path.join(d, 'daily_%s.csv' % k), 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    return d


def run_one(spec, key, label):
    s = dict(spec)
    s['key'] = key
    s['label'] = label
    r = simulator._simulate_strategy(s, gt, BUDGET, SEED, keep_daily=True)
    return {'summary': r['summary'], 'daily_logs': r['daily_logs']}


def recompute_r3_vs_trad(daily_path):
    """B 类：用统一 metrics 从原始经营流水重算指标（不重新模拟）。"""
    rows_by = defaultdict(list)
    with open(daily_path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows_by[r['strategy']].append(r)

    def F(x):
        return float(x or 0)

    out = {}
    for key, rows in rows_by.items():
        sold = sum(F(r['sold_qty']) for r in rows)
        dem = sum(F(r['actual_demand']) for r in rows)
        so = sum(F(r['stockout_qty']) for r in rows)
        spoil = sum(F(r['spoilage_qty']) for r in rows)
        gross = sum(F(r['gross_margin']) for r in rows)
        cogs = sum(F(r['sold_qty']) * prod_map[r['sku']]['cost_price'] for r in rows)
        liv = [r for r in rows if r['is_livelihood'] == '1']
        l_sold = sum(F(r['sold_qty']) for r in liv)
        l_dem = sum(F(r['actual_demand']) for r in liv)
        l_so = sum(F(r['stockout_qty']) for r in liv)
        dayval = defaultdict(float)
        for r in rows:
            dayval[r['day']] += F(r['closing_inventory']) * prod_map[r['sku']]['cost_price']
        avg_inv = metrics.avg_inventory_capital([dayval[d] for d in sorted(dayval)])
        out[key] = {'cumulative_gross_margin': round(gross, 2),
                    'stockout_rate': round(metrics.stockout_rate(so, dem), 6),
                    'livelihood_stockout_rate': round(metrics.livelihood_stockout_rate(l_so, l_dem), 6),
                    'livelihood_fill_rate': round(metrics.livelihood_fill_rate(l_sold, l_dem), 6),
                    'spoilage_rate': round(metrics.spoilage_rate(spoil, sold), 6),
                    'spoilage_qty': round(spoil, 1),
                    'avg_inventory_capital': round(avg_inv, 2),
                    'inventory_turnover': round(metrics.inventory_turnover(cogs, avg_inv), 4)}
    return out


# 1) R³ vs Traditional（B：从旧流水重算，不重跑）
r3v = recompute_r3_vs_trad(os.path.join('eval', 'digital_store_daily.csv'))
save('r3_vs_traditional', {'source': 'recomputed from eval/digital_store_daily.csv', 'class': 'B'},
     {k: {'summary': v} for k, v in r3v.items()})
print('R3 vs Trad (B recomputed):', r3v)


# 2) Memory A/B（C：重跑）
mem = {'memory_on': run_one(specs['diannao'], 'memory_on', '小满 R³（Memory 开）'),
       'memory_off': run_one(specs['diannao_no_memory'], 'memory_off', '小满 − Memory')}
save('memory_ab', {'variable': 'use_memory', 'class': 'C'}, mem)
print('Memory A/B done')


# 3) Spoilage Control A/B（C：重跑）
sp_on = dict(specs['diannao'])
sp_on['spoilage_control'] = True
sp_off = dict(specs['diannao'])
sp_off['spoilage_control'] = False
spoil_ab = {'control_on': run_one(sp_on, 'spoil_on', '损耗控制开'),
            'control_off': run_one(sp_off, 'spoil_off', '损耗控制关')}
save('spoilage_ab', {'variable': 'spoilage_control', 'class': 'C'}, spoil_ab)
print('Spoilage A/B done')


# 4) R³三目标消融（C：重跑，运行时包装关闭单个目标）
_orig_solve = r3_optimizer.solve
_orig_lambda = r3_optimizer.RESILIENCE_SHORTFALL_PENALTY


def _install(ablate):
    def _solve(items, budget, protect_livelihood=True):
        if ablate != 'revenue':
            return _orig_solve(items, budget, protect_livelihood=protect_livelihood)
        saved = [it.get('unit_margin') for it in items]
        for it in items:
            it['unit_margin'] = 0.0
        try:
            return _orig_solve(items, budget, protect_livelihood=protect_livelihood)
        finally:
            for it, m in zip(items, saved):
                it['unit_margin'] = m
    r3_optimizer.solve = _solve
    r3_optimizer.RESILIENCE_SHORTFALL_PENALTY = 0.0 if ablate == 'resilience' else _orig_lambda


def run_abl(spec, key, label, ablate):
    _install(ablate)
    try:
        return run_one(spec, key, label)
    finally:
        r3_optimizer.solve = _orig_solve
        r3_optimizer.RESILIENCE_SHORTFALL_PENALTY = _orig_lambda


abl = {'full': run_abl(specs['diannao'], 'full', 'Full R3', None),
       'no_revenue': run_abl(specs['diannao'], 'no_revenue', 'R3 - Revenue', 'revenue'),
       'no_resilience': run_abl(specs['diannao'], 'no_resilience', 'R3 - Resilience', 'resilience'),
       'no_responsibility': run_abl(specs['diannao_no_responsibility'], 'no_responsibility', 'R3 - Responsibility', None)}
save('ablation_3obj', {'variable': 'revenue/resilience/responsibility', 'class': 'C'}, abl)
print('3-objective ablation done')


agg = {}
for name in ('r3_vs_traditional', 'memory_ab', 'spoilage_ab', 'ablation_3obj'):
    with open(os.path.join(OUT, name, 'summary.json'), encoding='utf-8') as f:
        agg[name] = json.load(f)['summaries']

final = {'title': '小满 · 最终实验结果（FINAL / FROZEN）', 'generated_at': NOW,
         'seed': SEED, 'budget': BUDGET, 'metric_module': 'core.metrics',
         'experiments': list(agg.keys()), 'results': agg}
with open(os.path.join(OUT, 'final_experiment_summary.json'), 'w', encoding='utf-8') as f:
    json.dump(final, f, ensure_ascii=False, indent=2)
with open(os.path.join(OUT, 'FROZEN.json'), 'w', encoding='utf-8') as f:
    json.dump({'status': 'FINAL / FROZEN', 'generated_at': NOW, 'seed': SEED,
               'budget': BUDGET, 'metric_module': 'core.metrics',
               'experiments': list(agg.keys())}, f, ensure_ascii=False, indent=2)
print('FINAL FROZEN at', OUT)
