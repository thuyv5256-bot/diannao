# -*- coding: utf-8 -*-
# 第7.2步：R³(店脑) vs Traditional(Baseline) 180天正式公平对照
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import simulator

gt = simulator.load_ground_truth()
specs = simulator._strategy_specs()
A = simulator._simulate_strategy(specs['diannao'], gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)
B = simulator._simulate_strategy(specs['baseline'], gt, simulator.DEFAULT_SIM_BUDGET, 42, keep_daily=True)

KEYS = ['cumulative_gross_margin', 'stockout_rate', 'livelihood_stockout_rate',
        'livelihood_secured_rate', 'spoilage_qty', 'spoilage_cost', 'spoilage_rate',
        'avg_inventory_capital', 'inventory_turnover']
LABEL = {'cumulative_gross_margin': '累计毛利', 'stockout_rate': '总体缺货率',
         'livelihood_stockout_rate': '民生缺货率', 'livelihood_secured_rate': '民生保障率',
         'spoilage_qty': '损耗件数', 'spoilage_cost': '损耗成本', 'spoilage_rate': '损耗率',
         'avg_inventory_capital': '平均库存资金', 'inventory_turnover': '库存周转率'}

print('%-18s %18s %18s %16s %12s' % ('指标', 'A Full R³', 'B Traditional', '绝对变化', '百分比'))
for k in KEYS:
    a = A['summary'][k]
    b = B['summary'][k]
    d = a - b
    p = (d / b * 100) if b else 0.0
    print('%-18s %18.4f %18.4f %+16.4f %+11.2f%%' % (LABEL[k], a, b, d, p))


def day_agg(res, day):
    rows = [r for r in res['daily_logs'] if r['day'] == day]
    liv = [r for r in rows if r['is_livelihood'] == 1]
    return {
        'reorder': sum(r['reorder_qty'] for r in rows),
        'liv_reorder': sum(r['reorder_qty'] for r in liv),
        'demand': sum(r['actual_demand'] for r in rows),
        'sold': sum(r['sold_qty'] for r in rows),
        'stockout': sum(r['stockout_qty'] for r in rows),
        'liv_stockout': sum(r['stockout_qty'] for r in liv),
        'spoil': sum(r['spoilage_qty'] for r in rows),
        'event': rows[0]['event'] if rows else '',
    }


days = gt['day_list']
ev = gt['event_by_day']
normal_day = next(d for d in days if ev.get(d, '正常') == '正常')
event_day = next((d for d in days if ev.get(d, '正常') != '正常'), normal_day)


def liv_gap(d):
    ra = [r for r in A['daily_logs'] if r['day'] == d and r['is_livelihood'] == 1]
    rb = [r for r in B['daily_logs'] if r['day'] == d and r['is_livelihood'] == 1]
    return sum(r['reorder_qty'] for r in ra) - sum(r['reorder_qty'] for r in rb)


liv_day = max(days, key=lambda d: abs(liv_gap(d)))
for tag, d in [('① 普通经营日', normal_day), ('② 风险事件日', event_day), ('③ 民生/预算作用日', liv_day)]:
    aa, bb = day_agg(A, d), day_agg(B, d)
    print('\n=== %s  %s  事件=%s ===' % (tag, d, aa['event']))
    print('  %-14s %12s %12s' % ('当日合计', 'A R3', 'B Trad'))
    METRICS = [('reorder', '补货件数'), ('liv_reorder', '其中民生补货'), ('demand', '实际需求'), ('sold', '实际售出'), ('stockout', '缺货'), ('liv_stockout', '民生缺货'), ('spoil', '报损')]
    for key, name in METRICS:
        print('  %-14s %12.0f %12.0f' % (name, aa[key], bb[key]))
    ra = {r['sku']: r for r in A['daily_logs'] if r['day'] == d}
    rb = {r['sku']: r for r in B['daily_logs'] if r['day'] == d}
    diffs = sorted(ra, key=lambda s: -abs(ra[s]['reorder_qty'] - rb[s]['reorder_qty']))[:3]
    for s in diffs:
        x, y = ra[s], rb[s]
        print('    SKU %-5s %-8s 补货 A=%.0f B=%.0f | 需求=%.0f 售出 A=%.0f B=%.0f 缺货 A=%.0f B=%.0f'
              % (s, x['name'][:8], x['reorder_qty'], y['reorder_qty'], x['actual_demand'],
                 x['sold_qty'], y['sold_qty'], x['stockout_qty'], y['stockout_qty']))
