# -*- coding: utf-8 -*-
"""小满 · 「为什么这样进」决策详情页（产品化表达，遵循 DESIGN.md）。

只回答一个问题：为什么小满建议这样进货？
只用当前真实决策结果（decision basis 字段）生成结论与证据，不写死、不暴露内部推理。
"""

WHY_CSS = """
/* 「为什么这样进」页 —— 只消费 --xm-* token（颜色定义见 core/themes.py） */
.yw-concl { background: var(--xm-canvas); border: var(--xm-border-w) solid var(--xm-card-border);
  border-left: 4px solid var(--xm-primary); border-radius: var(--xm-radius-lg);
  padding: var(--xm-space-lg); box-shadow: var(--xm-card-shadow); }
.yw-name { font-size:16px; font-weight:600; color: var(--xm-ink); }
.yw-headline { font-size:26px; font-weight:700; color: var(--xm-primary); margin:8px 0 4px; }
.yw-meta { font-size:14px; color: var(--xm-slate); }
.yw-concl-text { font-size:14px; color: var(--xm-charcoal); margin-top:10px; line-height:1.9; }
.yw-ev-title { font-size:18px; font-weight:600; color: var(--xm-ink); margin:22px 0 12px; }
.ev-step { display:flex; gap:12px; margin-bottom:14px; }
.ev-num { flex:0 0 22px; height:22px; line-height:22px; text-align:center;
  border-radius: var(--xm-radius-full); background: var(--xm-info-soft);
  color: var(--xm-primary); font-size:12px; font-weight:600; }
.ev-t { font-size:15px; font-weight:600; color: var(--xm-ink); }
.ev-l { font-size:13px; color: var(--xm-slate); margin-top:3px; line-height:1.8; }
.ev-r3 { display:flex; gap:10px; margin-top:6px; }
.ev-r3 > div { flex:1; background: var(--xm-surface-soft);
  border: var(--xm-border-w) solid var(--xm-hairline); border-radius: var(--xm-radius-md);
  padding:10px 12px; }
.ev-r3 b { font-size:14px; color: var(--xm-ink); }
.ev-r3 span { font-size:12px; color: var(--xm-slate); display:block; margin-top:3px; line-height:1.7; }
.yw-foot { font-size:12px; color: var(--xm-steel); margin-top:16px; }
"""


def _conclusion(it):
    unit = it['unit']
    daily = float(it.get('daily_demand') or 0)
    qty = float(it.get('reorder_qty') or 0)
    cov = float(it.get('supply_cover_days') or 0)
    parts = ['预计明日需求约 %.1f %s' % (daily, unit),
             ('现有库存充足' if cov >= 1.5 else '现有库存偏紧')]
    if abs(float(it.get('memory_delta') or 0)) > 1e-9:
        parts.append('参考了过去一次类似经营情况')
    if it.get('is_livelihood'):
        parts.append('属民生商品，优先保障')
    return '；'.join(parts) + '，因此建议进货 %.0f %s。' % (qty, unit)


def render_head() -> str:
    """页面头部（Direction A：页头 + 副信息）。"""
    return ('<div class="xm-page-head"><div>'
            '<div class="xm-h1">为什么这样进</div>'
            '<div class="xm-page-sub">挑一个商品，看这单建议背后的六步依据</div>'
            '</div></div>')


def _kpi(label, value, sub=None):
    sub_html = ('<div class="xm-kpi-sub">%s</div>' % sub) if sub else ''
    return ('<div class="xm-kpi"><div class="xm-kpi-k">%s</div>'
            '<div class="xm-kpi-v">%s</div>%s</div>' % (label, value, sub_html))


def render_why_page(it: dict) -> str:
    """三段式：KPI 条 + 2/3 依据链 + 1/3 结论与口径（Direction A）。"""
    unit = it['unit']
    daily = float(it.get('daily_demand') or 0)
    on_hand = float(it.get('on_hand') or 0)
    qty = float(it.get('reorder_qty') or 0)
    cov = float(it.get('final_cover_days') or 0)
    tag = '<span class="xm-badge xm-badge-green">民生</span>' if it.get('is_livelihood') else ''
    kpi = ('<div class="xm-kpi-row">'
           + _kpi('建议进货', '%.0f %s' % (qty, unit), sub='为明天备货')
           + _kpi('当前库存', '%.0f %s' % (on_hand, unit),
                  sub='预计需求 %.1f %s / 天' % (daily, unit))
           + _kpi('进货后约够', '%.1f 天' % cov, sub='覆盖到下次补货')
           + '</div>')
    concl = ('<div class="yw-concl"><div class="yw-name">%s%s</div>'
             '<div class="yw-meta">小满的结论</div>'
             '<div class="yw-concl-text">%s</div></div>'
             % (it['name'], tag, _conclusion(it)))
    left = ('<div class="xm-card"><div class="xm-h3" style="margin:0 0 10px">小满参考了这些信息</div>' + _evidence(it) + '</div>')
    right = concl + '<div class="xm-card" style="margin-top:12px">' + _foot() + '</div>'
    return (kpi + '<div class="xm-split"><div class="xm-main-col">%s</div>'
            '<div class="xm-rail">%s</div></div>' % (left, right))

def _step(n, title, lines):
    body = ''.join('<div class="ev-l">%s</div>' % l for l in lines)
    return ('<div class="ev-step"><div class="ev-num">%s</div>'
            '<div><div class="ev-t">%s</div>%s</div></div>' % (n, title, body))


def _foot():
    return '<div class="yw-foot">背后由 R³ 多目标决策机制共同权衡（收益 / 韧性 / 民生）。</div>'


def _evidence(it):
    unit = it['unit']
    daily = float(it.get('daily_demand') or 0)
    on_hand = float(it.get('on_hand') or 0)
    elig = float(it.get('eligible_in_transit') or 0)
    intransit = float(it.get('in_transit') or 0)
    lead = float(it.get('lead_time_days') or 0)
    target = float(it.get('target_stock') or 0)
    raw = float(it.get('raw_reorder') or 0)
    qty = float(it.get('reorder_qty') or 0)
    cov = float(it.get('supply_cover_days') or 0)
    rf = float(it.get('risk_factor') or 1.0)
    md = float(it.get('memory_delta') or 0)
    env = []
    if it.get('holiday_note'):
        env.append('节假日：%s' % it['holiday_note'])
    if abs(rf - 1.0) > 1e-9:
        env.append('决策日情况：%s' % (it.get('risk_note') or '存在天气/事件影响'))
    env.append('供应商：%s%s' % (it.get('supplier', ''), '（决策日断供）' if it.get('supplier_down') else '（正常）'))
    has_ev = bool(abs(rf - 1.0) > 1e-9 or it.get('holiday_note') or it.get('supplier_down'))
    env.append('对建议的影响：%s' % ('有影响，已计入下面的预计需求与备货' if has_ev else '无特殊影响，按正常情况'))
    s1 = _step(1, '看环境', env)
    if abs(rf - 1.0) > 1e-9 and rf > 0:
        s2 = _step(2, '算需求', ['基础预计 %.1f %s，调整后预计需求 %.1f %s' % (daily / rf, unit, daily, unit)])
    else:
        s2 = _step(2, '算需求', ['预计需求 %.1f %s（基于历史销量）' % (daily, unit)])
    if abs(md) > 1e-9:
        s3 = _step(3, '翻老账', ['参考了过去一次类似经营情况（%s）' % (it.get('memory_scene') or '普通日')])
    else:
        s3 = _step(3, '翻老账', ['这次没有参考到相关历史经验'])
    inv = ['当前库存 %.0f %s，有效在途 %.0f %s，供应商交期 %.0f 天' % (on_hand, unit, elig, unit, lead)]
    if intransit > 0:
        inv.append('另有在途 %.0f %s' % (intransit, unit))
    inv.append('现有库存约可支撑 %.1f 天' % cov)
    s4 = _step(4, '查库存', inv)
    margin = float(it.get('unit_margin') or 0)
    gap = max(0.0, target - on_hand - elig)
    fq = float(it.get('floor_qty') or 0)
    resp = ('已满足最低保障量 %.0f %s' % (fq, unit)) if (it.get('is_livelihood') and qty >= fq - 1e-9) else ('民生商品，保障量 %.0f %s' % (fq, unit) if it.get('is_livelihood') else '非民生商品，不占用民生兜底额')
    r3 = ('<div class="ev-r3">'
          '<div><b>赚钱</b><span>这批货预计带来约 ¥%.0f 经营收益</span></div>'
          '<div><b>抗风险</b><span>相对目标库存缺口约 %.0f %s</span></div>'
          '<div><b>保民生</b><span>%s</span></div></div>' % (margin * qty, gap, unit, resp))
    s5 = ('<div class="ev-step"><div class="ev-num">5</div><div><div class="ev-t">做权衡</div>'
          '<div class="ev-l">在「赚钱 · 抗风险 · 保民生」之间综合权衡：</div>' + r3 + '</div></div>')
    if qty < raw - 1e-9:
        adj = '原始建议 %.0f → 压缩 %.0f → 最终建议进货 %.0f %s' % (raw, raw - qty, qty, unit)
    else:
        adj = '原始建议 %.0f → 最终建议进货 %.0f %s' % (raw, qty, unit)
    s6 = _step(6, '给结论', [adj])
    return s1 + s2 + s3 + s4 + s5 + s6

