# -*- coding: utf-8 -*-
import pathlib
import sys

# 归档后位置：tools/experiments/ —— 把仓库根加回 sys.path，脚本仍按仓库根为工作目录运行
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

# 第6.2步：R³ 极端预算压力测试（固定同一天/同商品/同预测/同库存，只变预算）
import copy
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core import dataset, policy, r3_optimizer

products = dataset.read_products()
# 固定预测与库存（全 SKU 日需求 10、库存 0），使唯一变量 = 预算
policy.forecast.forecast_all = lambda plan_date, restore_potential=True, risks=None: {
    p['sku']: {'daily_demand': 10.0, 'risk_factor': 1.0, 'holiday_note': '',
               'risk_note': '', 'promo_note': ''} for p in products}
policy.memory.get_inventory = lambda: {p['sku']: 0.0 for p in products}
policies = {p['sku']: {'base_days': 3.0, 'safety_factor': 0.15} for p in products}
items0, _ = policy._prepare_items('2026-07-14', policies, products, risks=[], use_memory=False)

FLOOR = round(sum(it['floor_cost'] for it in items0 if it['is_livelihood']), 2)
print('民生最低需求成本 FLOOR =', FLOOR)
SCEN = [('A 充足', 1_000_000.0), ('B 底线+少量', FLOOR + 200.0),
        ('C ~50%底线', FLOOR * 0.5), ('D 接近0', 0.0)]


def run(base, budget):
    items = [copy.deepcopy(it) for it in base]
    r3_optimizer.solve(items, budget, protect_livelihood=True)
    liv = round(sum(it['cost'] for it in items if it['is_livelihood']), 2)
    nonliv = round(sum(it['cost'] for it in items if not it['is_livelihood']), 2)
    total = round(sum(it['cost'] for it in items), 2)
    cov = policy.calculate_essential_coverage(items)
    return {'liv': liv, 'nonliv': nonliv, 'total': total,
            'rate': cov['rate'], 'short': cov['shortfall_cost'],
            'neg': any(it['reorder_qty'] < 0 or it['cost'] < 0 for it in items)}


print('%-12s %10s %10s %10s %8s %10s %10s %10s' % (
    '场景', '预算', '民生需求成本', '民生采购', '保障率', '缺口金额', '非民生采购', '总采购'))
for name, b in SCEN:
    r = run(items0, b)
    print('%-12s %10.0f %10.0f %10.0f %7.1f%% %10.1f %10.0f %10.0f  超预算=%s 负值=%s' % (
        name, b, FLOOR, r['liv'], r['rate'] * 100, r['short'], r['nonliv'], r['total'],
        r['total'] > b + 1e-6, r['neg']))

print('--- SKU 顺序无关性复测 ---')
for name, b in SCEN:
    r1 = run(items0, b)
    r2 = run(list(reversed(items0)), b)
    same = (abs(r1['liv'] - r2['liv']) < 1e-6 and abs(r1['nonliv'] - r2['nonliv']) < 1e-6
            and abs(r1['total'] - r2['total']) < 1e-6 and r1['rate'] == r2['rate'])
    print('%-12s 顺序一致=%s  (正序 liv=%.0f nonliv=%.0f total=%.0f | 反序 liv=%.0f nonliv=%.0f total=%.0f)'
          % (name, same, r1['liv'], r1['nonliv'], r1['total'], r2['liv'], r2['nonliv'], r2['total']))
