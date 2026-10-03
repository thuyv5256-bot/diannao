# -*- coding: utf-8 -*-
# 第6.3步：R³ 三目标消融（A全 / B-R / C-R2 / D-Responsibility），同一180天环境
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator, r3_optimizer

_orig_solve = r3_optimizer.solve
_orig_lambda = r3_optimizer.RESILIENCE_SHORTFALL_PENALTY


def _install(ablate):
    def _solve(items, budget, protect_livelihood=True):
        if ablate == 'revenue':
            saved = [it.get('unit_margin') for it in items]
            for it in items:
                it['unit_margin'] = 0.0
            try:
                return _orig_solve(items, budget, protect_livelihood=protect_livelihood)
            finally:
                for it, m in zip(items, saved):
                    it['unit_margin'] = m
        return _orig_solve(items, budget, protect_livelihood=protect_livelihood)
    r3_optimizer.solve = _solve
    r3_optimizer.RESILIENCE_SHORTFALL_PENALTY = 0.0 if ablate == 'resilience' else _orig_lambda


def run(spec, ablate):
    _install(ablate)
    try:
        return simulator._simulate_strategy(spec, gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)
    finally:
        r3_optimizer.solve = _orig_solve
        r3_optimizer.RESILIENCE_SHORTFALL_PENALTY = _orig_lambda


gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
A = run(specs['diannao'], None)
B = run(specs['diannao'], 'revenue')
C = run(specs['diannao'], 'resilience')
D = run(specs['diannao_no_responsibility'], None)

KEYS = ['cumulative_gross_margin', 'stockout_rate', 'livelihood_stockout_rate',
        'livelihood_secured_rate', 'spoilage_rate', 'spoilage_cost',
        'avg_inventory_capital', 'inventory_turnover']

GROUPS = [('A Full R3', A), ('B -Revenue', B), ('C -Resilience', C), ('D -Responsibility', D)]
print('%-24s' % '指标', end='')
for name, _ in GROUPS:
    print('%18s' % name, end='')
print()
for k in KEYS:
    print('%-24s' % k, end='')
    for _name, r in GROUPS:
        print('%18s' % r['summary'][k], end='')
    print()

print('--- 相对 Full R3 的变化（绝对 / 百分比）---')
for name, r in GROUPS[1:]:
    print(name)
    for k in KEYS:
        a = A['summary'][k]
        x = r['summary'][k]
        d = x - a
        p = (d / a * 100) if a else 0.0
        print('   %-26s %+12.4f  %+8.2f%%' % (k, d, p))
