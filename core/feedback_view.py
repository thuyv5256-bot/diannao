# -*- coding: utf-8 -*-
"""小满 · 「今天生意怎么样」每日经营反馈页（产品化表达，遵循 DESIGN.md）。

用户心智：这一天实际卖得怎么样 → 补充断货/损耗 → 保存 → 小满把真实结果记下来，
供后续经营经验与策略调整使用。

本模块只负责**页面表达**，不碰任何业务逻辑：
  · 字段口径、触发阈值、Memory/evolution 调用全部仍由 app.submit_feedback 与
    core.evolution 决定；
  · 所有文案只描述代码当前真实具备的能力 —— 页面不会宣称「自动采集 POS 数据」：
    载入动作确实只是从历史经营记录（sales 表）读初值，且只有实际销量有历史值，
    断货/损耗两列在历史里恒为 0，仍然必须由店主当天自己填。
"""

FEEDBACK_CSS = """
/* 可编辑经营记录表：与 .xm-table 对齐的表头、字号与聚焦反馈 */
.fb-table table th { font-size:13px; font-weight:600; color:var(--xm-steel);
  background:var(--xm-surface); }
.fb-table table td { font-size:14px; }
.fb-table table input, .fb-table table textarea { font-size:14px !important;
  border-radius:var(--xm-radius-xs) !important; }
.fb-table table input:focus, .fb-table table textarea:focus {
  outline:2px solid var(--xm-primary) !important; outline-offset:-1px; }
.fb-table table td:nth-child(2) { font-weight:600; color:var(--xm-ink); }

/* 操作区：主按钮独占一行，次级操作退居一侧，不与主按钮抢主视觉 */
.fb-actions { display:flex; gap:12px; align-items:center; margin-top:16px; flex-wrap:wrap; }
.fb-date { max-width:300px; }
.fb-date .xm-hint { margin:6px 0 0; }
"""

# 表格列名：店主语言；与 core 层字段（name / qty_sold / qty_stockout / qty_spoilage / sku）
# 一一对应，未做任何增删或语义改动。
COL_ITEM = "商品"
COL_SOLD = "实际卖出"
COL_STOCKOUT = "没买到（断货）"
COL_SPOILAGE = "损耗（报废）"
COL_SKU = "商品编号"
FB_COLUMNS = [COL_ITEM, COL_SOLD, COL_STOCKOUT, COL_SPOILAGE, COL_SKU]
FB_DATATYPES = ["str", "number", "number", "number", "str"]


def _day_cn(day_str) -> str:
    """2026-08-27 → 8月27日 · 周四（不合法时原样返回）。"""
    import datetime as _dt
    _w = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    try:
        d = _dt.date.fromisoformat(str(day_str)[:10])
        return "%d月%d日 · %s" % (d.month, d.day, _w[d.weekday()])
    except Exception:
        return str(day_str)


def render_head() -> str:
    """页头：这一步在做什么、为什么值得花一分钟。"""
    return ('<div class="xm-page">'
            '<div class="xm-h1">今天生意怎么样</div>'
            '<div class="xm-sm" style="margin-top:6px">'
            '把真实经营结果告诉小满，之后的补货建议会参考这些记录。</div>'
            '</div>')


def render_date_hint(day) -> str:
    """经营日期区说明：日期的真实语义 + 载入动作的真实来源。"""
    return ('<div class="xm-hint">这里要记的是<strong>已经卖完货的那一天</strong>（%s）。'
            '小满会把这一天的实际结果，和当天本来给出的补货建议放在一起复盘，'
            '所以日期请填实际卖货的那天。</div>' % _day_cn(day))


def render_table_hint(loaded_day) -> str:
    """表格区说明：如实交代哪一列自动载入、哪一列必须店主自己填。"""
    return ('<div class="xm-hint">'
            '「实际卖出」已按 %s 的历史经营记录填好，核对一下即可；'
            '<br>「没买到（断货）」＝ 有顾客想买但店里已经没货，'
            '「损耗（报废）」＝ 过期、破损或无法继续销售 —— '
            '这两项目前没有历史记录，<strong>需要你按当天的实际情况填写</strong>。'
            '<br>填得越准，小满越能分清是备货不足，还是进得太多。'
            '</div>' % _day_cn(loaded_day))


def render_result(result: dict, day) -> str:
    """保存结果反馈 —— 严格按 evolution.process_feedback 的真实返回值表达。

    只有 `changes` 非空（真实触发了策略校准）才讲「记住了什么 / 下次怎么调整」；
    其余情况一律只说「已保存」，不伪造 Memory 命中或策略调整。
    """
    summary = result.get("summary") or {}
    changes = result.get("changes") or []
    skipped = int(summary.get("skipped", 0) or 0)
    updated = int(summary.get("updated", 0) or 0)
    removed = int(summary.get("removed", 0) or 0)
    stockout_n = int(summary.get("stockout_days", 0) or 0)
    spoilage_n = int(summary.get("spoilage_days", 0) or 0)

    saved = ('<div class="xm-brief"><span class="xm-badge xm-badge-green">已保存</span>'
             '<div><div class="xm-brief-t">%s 的经营情况已记下</div>'
             '<div class="xm-brief-sub">真实结果已存进店里的老账本，供以后复盘和调整参考。</div>'
             '</div></div>' % _day_cn(day))

    if not changes:
        if skipped > 0:
            # 幂等去重：完全一致的反馈已经学过，不重复调整策略
            return (saved +
                    '<div class="xm-card xm-card-tint"><div class="xm-sm">'
                    '这次的内容此前已经记录过，小满不会把同一个结果学两遍，'
                    '所以补货建议保持不变。</div></div>')
        if updated > 0:
            return (saved +
                    '<div class="xm-card xm-card-tint"><div class="xm-sm">'
                    '这次是对之前记录的修正，小满已更新原来的记录并重算影响，'
                    '不会重复累加一次调整。</div></div>')
        if removed > 0:
            return (saved +
                    '<div class="xm-card xm-card-tint"><div class="xm-sm">'
                    '这次的数字和之前不一样，原先记下的异常已经消除，'
                    '小满已撤销那次调整，补货建议回到调整前的样子。</div></div>')
        # 未触发任何阈值：只说保存成功，并如实给出当天异常项数
        return (saved +
                '<div class="xm-card xm-card-tint"><div class="xm-sm">'
                '已记录。这次没有触发新的策略调整 —— 当天断货 %d 项、损耗 %d 项，'
                '都在正常波动范围内。</div></div>' % (stockout_n, spoilage_n))

    # 真实形成了经营经验 / 策略校准，才展示明细
    rows = []
    for ch in changes:
        o_s, n_s = ch["safety_factor"]
        arrow = ('<span style="color:var(--xm-error)">↑ 上调</span>' if n_s > o_s
                 else '<span style="color:var(--xm-success)">↓ 下调</span>')
        trigger = ch.get("trigger") or ""
        if trigger == "断货":
            tag = '<span class="xm-badge xm-badge-red">断货</span>'
        elif trigger == "积压损耗":
            tag = '<span class="xm-badge xm-badge-orange">积压损耗</span>'
        else:
            tag = '<span class="xm-badge xm-badge-neutral">预测偏差</span>'
        live = (' <span class="xm-badge xm-badge-green">民生</span>'
                if ch.get("is_livelihood") else '')
        rows.append('<tr><td><div class="xm-name">%s%s</div></td><td>%s</td>'
                    '<td>%s<br><span class="xm-cap">安全库存系数 %.2f → %.2f</span></td>'
                    '<td class="xm-sm">%s</td></tr>'
                    % (ch["name"], live, tag, arrow, o_s, n_s, ch.get("reason") or "—"))
    table = ('<table class="xm-table"><tr><th>商品</th><th>发生了什么</th>'
             '<th>下次怎么调整</th><th>依据</th></tr>' + ''.join(rows) + '</table>')
    return (saved +
            '<div class="xm-sec"><div class="xm-sec-title">这次记录让小满更新了 %d 个商品的经营经验</div>'
            '%s'
            '<div class="xm-card xm-card-tint" style="margin-top:12px"><div class="xm-sm">'
            '下次再遇到类似情况时，小满会参考这条经验，对之后的补货建议做小幅调整。'
            '基础策略参数本身不变。</div></div>'
            '</div>' % (len(changes), table))


def render_invalid(msg: str) -> str:
    """输入校验失败提示（沿用 v2 语义色，不使用旧版 .note）。"""
    return ('<div class="xm-brief"><span class="xm-badge xm-badge-red">无法保存</span>'
            '<div><div class="xm-brief-t">%s</div></div></div>' % msg)


def render_empty() -> str:
    return render_invalid("表格里还没有内容，先载入或填写再保存。")
