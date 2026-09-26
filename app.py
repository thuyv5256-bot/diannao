# -*- coding: utf-8 -*-
"""
店脑 · 网页交互界面（Gradio）

设计原则：店主年龄偏大、没有数据分析基础。
所以界面必须做到三件事 ——
  1. 打开就知道看哪：一屏之内给出"今天进什么货"
  2. 数字说人话：不出现"安全库存系数"，只说"够卖几天"
  3. 决策可追问：点一下能看到"为什么建议进这么多"

运行：python app.py   →  浏览器打开 http://127.0.0.1:7861
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import analysis, evolution, forecast, memory, policy
    from core.config import (
        CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
    )
else:
    from .core import analysis, evolution, forecast, memory, policy
    from .core.config import (
        CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
    )

import gradio as gr

GR_MAJOR = int(gr.__version__.split(".")[0])

# 决策日：默认演示"今晚为明天中秋备货"
DEFAULT_PLAN_DATE = "2026-09-25"
LAST_DAY = "2026-09-24"

CSS = """
.gradio-container { max-width: 1280px !important; }
.dn-card { background:#fff; border:1px solid #e3e6eb; border-radius:12px;
           padding:18px 20px; margin-bottom:14px; }
.dn-hero { background:linear-gradient(135deg,#1f4e79,#2e7d5b); color:#fff;
           border-radius:14px; padding:22px 26px; margin-bottom:18px; }
.dn-hero h1 { margin:0 0 6px; font-size:26px; }
.dn-hero p  { margin:0; opacity:.9; font-size:15px; }
table.dn { width:100%; border-collapse:collapse; font-size:15px; }
table.dn th { background:#f2f4f7; color:#2c3e50; text-align:left;
              padding:10px 12px; font-weight:600; border-bottom:2px solid #dfe4ea; }
table.dn td { padding:10px 12px; border-bottom:1px solid #eef1f4; color:#2c3e50; }
table.dn tr.liv td:first-child { border-left:4px solid #c0392b; }
table.dn tr.nor td:first-child { border-left:4px solid #2c7a4b; }
table.dn tr:hover td { background:#fafbfc; }
.badge { display:inline-block; padding:2px 8px; border-radius:10px;
         font-size:12px; font-weight:600; }
.b-liv { background:#fdecea; color:#c0392b; }
.b-hi  { background:#e8f5e9; color:#2c7a4b; }
.b-warn{ background:#fff3e0; color:#e67e22; }
.b-ok  { background:#e8f5e9; color:#2c7a4b; }
.b-bad { background:#fdecea; color:#c0392b; }
.kpi { display:inline-block; min-width:150px; margin-right:14px; padding:12px 16px;
       background:#f8f9fb; border-radius:10px; border:1px solid #e8ebef; }
.kpi .v { font-size:24px; font-weight:700; color:#1f4e79; }
.kpi .l { font-size:13px; color:#6b7a8d; margin-top:2px; }
.note { background:#fffdf5; border-left:4px solid #f0b429; padding:12px 16px;
        border-radius:6px; font-size:15px; color:#5a4a1f; line-height:1.7; }
.good { background:#f3fbf5; border-left:4px solid #2c7a4b; padding:12px 16px;
        border-radius:6px; font-size:15px; color:#1f4a30; line-height:1.7; }
h3 { color:#1f4e79 !important; }
"""

# Gradio 6.0 起 css/theme 从 Blocks() 挪到了 launch()，这里做版本兼容
_BLOCKS_KW = {"title": "店脑 · 智能补货助手"}
_LAUNCH_KW = {}
if GR_MAJOR < 6:
    _BLOCKS_KW.update(css=CSS, theme=gr.themes.Soft(primary_hue="blue"))
else:
    _LAUNCH_KW.update(css=CSS, theme=gr.themes.Soft(primary_hue="blue"))

# Gradio 5+ 的 SSR 首屏渲染依赖 Node.js，云沙箱里未必有，关掉更稳
if GR_MAJOR >= 5:
    _LAUNCH_KW["ssr_mode"] = False


# ════════════════════════════════════════════════════════════
# 通用渲染
# ════════════════════════════════════════════════════════════
def _cover_badge(days: float) -> str:
    if days < 2:
        return f'<span class="badge b-bad">仅够 {days:.1f} 天</span>'
    if days < 4:
        return f'<span class="badge b-warn">够 {days:.1f} 天</span>'
    return f'<span class="badge b-ok">够 {days:.1f} 天</span>'


def _hero(sub: str) -> str:
    return f"""
    <div class="dn-hero">
      <h1>🏪 店脑 · 社区小店智能补货助手</h1>
      <p>{sub}</p>
    </div>"""


def render_plan_html(plan: dict) -> str:
    """渲染补货建议单 —— 店主打开就要看懂的那一屏。"""
    items = [it for it in plan["items"] if it["reorder_qty"] > 0 or it["daily_demand"] > 0]
    items.sort(key=lambda x: (-x["is_livelihood"], -x["reorder_qty"]))

    holiday_notes = sorted({it["holiday_note"] for it in plan["items"] if it["holiday_note"]})
    m = plan["metrics"]

    rows = []
    for it in items:
        cls = "liv" if it["is_livelihood"] else "nor"
        badge = ('<span class="badge b-liv">民生</span>' if it["is_livelihood"]
                 else '<span class="badge b-hi">高毛利</span>')
        qty_txt = (f"<b style='font-size:17px;color:#1f4e79'>{it['reorder_qty']:.0f}</b> "
                   f"<span style='color:#8b98a8'>{it['unit']}</span>")
        if it["reorder_qty"] <= 0:
            qty_txt = "<span style='color:#adb5bd'>暂不进货</span>"
        flag = ""
        if it["trimmed"]:
            flag = f"<br><span style='font-size:12px;color:#e67e22'>⚠ {it['trim_note']}</span>"
        rows.append(f"""
        <tr class="{cls}">
          <td>{badge} {it['name']}</td>
          <td>{it['on_hand']:.0f} {it['unit']}</td>
          <td>约 {it['daily_demand']:.1f} {it['unit']}</td>
          <td>{qty_txt}{flag}</td>
          <td>{_cover_badge(it.get('final_cover_days', 0))}</td>
        </tr>""")

    holiday_html = ""
    if holiday_notes:
        holiday_html = (f'<div class="note" style="margin-bottom:14px">'
                        f'🎑 <b>节日提醒</b>：{("、".join(holiday_notes))}，'
                        f'已自动上调相关品类备货量。</div>')

    floor_rate = m.get("livelihood_floor_secured") or 1.0
    liv_note = (
        f'街坊天天要的 {sum(1 for it in plan["items"] if it["is_livelihood"] and it["reorder_qty"] > 0)} '
        f'样民生货品已优先锁定，保障率 {floor_rate:.0%}。'
        '这部分不参与利润排队 —— 再省也不能让街坊买不到米面油盐。'
    )

    return f"""
    {_hero(f"决策日期 {plan['date']}　预算 {CURRENCY}{plan['budget']:.0f}　"
           f"|　{plan['mode_label']}")}
    {holiday_html}
    <div class="dn-card">
      <div class="kpi"><div class="v">{CURRENCY}{m['total_cost']:.0f}</div>
        <div class="l">本次进货花费</div></div>
      <div class="kpi"><div class="v">{CURRENCY}{m['gross_margin']:.0f}</div>
        <div class="l">预计可赚毛利</div></div>
      <div class="kpi"><div class="v">{m['livelihood_index']:.0%}</div>
        <div class="l">街坊民生保障度</div></div>
      <div class="kpi"><div class="v">{m['stockout_risk_count']}</div>
        <div class="l">可能断货的商品</div></div>
      <div style="clear:both"></div>
    </div>
    <div class="good">{liv_note}</div>
    <div class="dn-card" style="margin-top:14px">
      <h3 style="margin-top:0">📋 建议进货单</h3>
      <table class="dn">
        <tr><th>商品</th><th>货架还剩</th><th>明天预计卖</th>
            <th>建议进货</th><th>进货后能卖</th></tr>
        {''.join(rows)}
      </table>
      <div style="margin-top:12px;font-size:13px;color:#8b98a8">
        ★ 民生商品：毛利低但是街坊刚需，也是引客流的招牌
      </div>
    </div>"""


def render_compare_html(cmp: dict) -> str:
    """店脑 vs 传统纯利润算法的对比 —— 答辩现场的王牌。"""
    rows = []
    for d in sorted(cmp["diff"], key=lambda x: (-x["is_livelihood"], -abs(x["delta"]))):
        if d["diannao_qty"] <= 0 and d["baseline_qty"] <= 0:
            continue
        cls = "liv" if d["is_livelihood"] else "nor"
        delta = d["delta"]
        if abs(delta) < 1e-9:
            d_html = "<span style='color:#adb5bd'>一致</span>"
        elif delta > 0:
            d_html = f"<b style='color:#c0392b'>店脑多 {delta:.0f}</b>"
        else:
            d_html = f"<b style='color:#2c7a4b'>店脑少 {abs(delta):.0f}</b>"
        rows.append(f"""
        <tr class="{cls}">
          <td>{d['name']}</td>
          <td>{d['diannao_qty']:.0f} {d['unit']}</td>
          <td>{d['baseline_qty']:.0f} {d['unit']}</td>
          <td>{d_html}</td>
        </tr>""")

    md, mb = cmp["diannao"]["metrics"], cmp["baseline"]["metrics"]
    delta = cmp["delta"]

    return f"""
    {_hero(f"同一天 · 同一笔预算 {CURRENCY}{cmp['budget']:.0f} · 两种算法给出的不同答案")}
    <div class="dn-card">
      <h3 style="margin-top:0">两种算法，两种活法</h3>
      <table class="dn">
        <tr><th>商品</th><th>店脑（惠民约束）</th><th>传统算法（纯利润）</th><th>差异</th></tr>
        {''.join(rows)}
      </table>
    </div>
    <div class="dn-card">
      <table class="dn">
        <tr><th>指标</th><th>店脑</th><th>传统算法</th></tr>
        <tr><td>预计可赚毛利</td>
            <td><b>{CURRENCY}{md['gross_margin']:.0f}</b></td>
            <td>{CURRENCY}{mb['gross_margin']:.0f}</td></tr>
        <tr><td>街坊民生保障度</td>
            <td><b style="color:#c0392b">{md['livelihood_index']:.1%}</b></td>
            <td><b style="color:#2c7a4b">{mb['livelihood_index']:.1%}</b></td></tr>
        <tr><td>可能断货的商品数</td>
            <td>{md['stockout_risk_count']}</td><td>{mb['stockout_risk_count']}</td></tr>
      </table>
    </div>
    <div class="note">
      <b>怎么读这张表：</b>传统算法按"一块钱本钱能赚回多少"排队，
      高毛利的零食饮料永远排在前面；预算一紧，被砍掉的必然是大米、鸡蛋、牛奶
      这类低毛利刚需。<br>
      店脑先用惠民约束把民生兜底量锁住（<b>至少备够 {LIVELIHOOD_MIN_COVER_DAYS:.0f} 天</b>），
      剩下才按利润分配。<br>
      <b>代价摆在明面上：</b>店脑的直接毛利比传统算法少
      {CURRENCY}{delta['margin_cost_of_livelihood']:.0f}。
      但这笔钱并没有白花 —— 看下面第四页的数据。
    </div>"""


# ════════════════════════════════════════════════════════════
# 交互逻辑
# ════════════════════════════════════════════════════════════
def do_plan(date_str: str, budget: float):
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        return "<div class='note'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
    budget = float(budget or DEFAULT_BUDGET)
    cmp = policy.compare_plans(d, budget, persist=False)
    return render_plan_html(cmp["diannao"])


def do_compare(date_str: str, budget: float):
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        return "<div class='note'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
    budget = float(budget or DEFAULT_BUDGET)
    cmp = policy.compare_plans(d, budget, persist=False)
    return render_compare_html(cmp)


def load_feedback_template():
    """载入昨日经营数据作为反馈录入的初值，省得店主从零填。"""
    products = memory.get_products()
    rows = []
    for p in products:
        recs = memory.get_sales_range(p["sku"], LAST_DAY, LAST_DAY)
        r = recs[0] if recs else None
        rows.append([
            p["sku"], p["name"],
            int(round(r["qty_sold"])) if r else 0,
            int(round(r["qty_stockout"])) if r else 0,
            int(round(r["qty_spoilage"])) if r else 0,
        ])
    return pd.DataFrame(rows, columns=["编号", "商品", "昨天卖出", "没买到（断货）", "坏掉/报废"])


def submit_feedback(day_str: str, df: pd.DataFrame):
    if df is None or len(df) == 0:
        return "<div class='note'>还没有填写内容。</div>", render_evolution_html()
    try:
        d = str(day_str).strip()
        date.fromisoformat(d)
    except Exception:
        return "<div class='note'>日期格式不对。</div>", render_evolution_html()

    feedback = []
    for _, row in df.iterrows():
        try:
            feedback.append({
                "sku": str(row["编号"]).strip(),
                "qty_sold": float(row["昨天卖出"] or 0),
                "qty_stockout": float(row["没买到（断货）"] or 0),
                "qty_spoilage": float(row["坏掉/报废"] or 0),
            })
        except Exception:
            continue

    result = evolution.process_feedback(d, feedback)
    changes = result["changes"]
    summary = result["summary"]

    if not changes:
        body = (f"<div class='good'>📭 本次没有需要调整的地方。"
                f"其中断货 {summary['stockout_days']} 项、损耗 {summary['spoilage_days']} 项，"
                f"都在正常波动范围内 —— 系统不会为了一天的偶然起伏就改策略。</div>")
    else:
        rows = []
        for ch in changes:
            o_s, n_s = ch["safety_factor"]
            o_b, n_b = ch["base_days"]
            arrow = "↑ 上调" if n_s > o_s else "↓ 下调"
            if n_b > o_b:
                arrow = "↑ 上调"
            elif n_b < o_b:
                arrow = "↓ 下调"
            cls = "liv" if ch["is_livelihood"] else "nor"
            tag = ('<span class="badge b-liv">断货</span>' if ch["trigger"] == "断货"
                   else '<span class="badge b-warn">积压损耗</span>')
            rows.append(f"""
            <tr class="{cls}">
              <td>{ch['name']}</td>
              <td>{tag}</td>
              <td>{arrow}</td>
              <td style="font-size:13px;color:#5a6b7d">{ch['reason']}</td>
            </tr>""")
        body = f"""
        <div class="dn-card">
          <h3 style="margin-top:0">🧠 店脑从今天的生意里学到了什么</h3>
          <table class="dn">
            <tr><th>商品</th><th>发生了什么</th><th>怎么调整</th><th>为什么</th></tr>
            {''.join(rows)}
          </table>
        </div>
        <div class="good">
          ✅ 调整已写进门店记忆库，<b>明天出的补货建议就会按新策略来</b>。
          这就是"越用越懂你的店"。
        </div>"""

    return body, render_evolution_html()


def render_evolution_html() -> str:
    logs = memory.get_evolution_log(limit=40)
    if not logs:
        return ("<div class='note'>还没有学习记录。到「今天生意怎么样」录一次反馈，"
                "这里就会显示店脑是怎么自己调整的。</div>")

    products = {p["sku"]: p for p in memory.get_products()}
    rows = []
    for lg in logs:
        p = products.get(lg["sku"], {})
        nm = p.get("name", lg["sku"])
        star = "★ " if p.get("is_livelihood") else ""
        param_cn = {"safety_factor": "安全库存（备货宽裕度）",
                    "base_days": "备货天数"}.get(lg["param"], lg["param"])
        arrow = "↑" if (lg["new_value"] or 0) > (lg["old_value"] or 0) else "↓"
        tag = ('<span class="badge b-bad">断货</span>' if lg["trigger"] == "断货"
               else '<span class="badge b-warn">积压损耗</span>')
        rows.append(f"""
        <tr class="{'liv' if p.get('is_livelihood') else 'nor'}">
          <td>{lg['day']}</td><td>{star}{nm}</td><td>{tag}</td>
          <td>{param_cn}</td>
          <td><b style="color:{'#c0392b' if arrow == '↑' else '#2c7a4b'}">{arrow}
              {lg['old_value']:.3f} → {lg['new_value']:.3f}</b></td>
        </tr>""")

    n_up = sum(1 for lg in logs if (lg["new_value"] or 0) > (lg["old_value"] or 0))
    n_down = len(logs) - n_up

    return f"""
    <div class="dn-card">
      <div class="kpi"><div class="v">{len(logs)}</div><div class="l">累计学习次数</div></div>
      <div class="kpi"><div class="v">{n_up}</div><div class="l">为避免断货上调</div></div>
      <div class="kpi"><div class="v">{n_down}</div><div class="l">为减少积压下下调</div></div>
      <div style="clear:both"></div>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">策略自进化轨迹</h3>
      <table class="dn">
        <tr><th>日期</th><th>商品</th><th>触发原因</th><th>调整了什么</th><th>变化</th></tr>
        {''.join(rows)}
      </table>
    </div>"""


def evolution_chart(sku: str):
    """画某商品的策略参数演进曲线。"""
    products = memory.get_products()
    name_map = {p["name"]: p["sku"] for p in products}
    sku = name_map.get(sku, sku)

    fig = go.Figure()
    series_s = memory.evolution_series(sku, "safety_factor")
    series_b = memory.evolution_series(sku, "base_days")

    if not series_s and not series_b:
        fig.add_annotation(text="该商品还没有进化记录", showarrow=False,
                           font=dict(size=16, color="#8b98a8"))
        fig.update_layout(height=340, template="plotly_white",
                          paper_bgcolor="#fff", plot_bgcolor="#fff")
        return fig

    # 横轴用「第几次调整」而不是日期 —— 同一天可能发生多次调整，
    # 用日期做横轴会被压缩到毫秒级，看不出演进过程。
    # 第 0 个点用首次调整的 old_value，即店主原始经验值，
    # 这样即使只有一条记录也能看出"从哪来、到哪去"。
    def _xy(series):
        if not series:
            return [], [], []
        xs = list(range(0, len(series) + 1))
        ys = [series[0][1]] + [s[2] for s in series]
        labels = ["初始值"] + [f"{s[0]}" for s in series]
        return xs, ys, labels

    if series_s:
        xs, ys, labels = _xy(series_s)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, customdata=labels,
            mode="lines+markers", name="备货宽裕度",
            line=dict(color="#c0392b", width=3),
            marker=dict(size=10), connectgaps=True,
            hovertemplate="%{customdata}<br>备货宽裕度 %{y:.3f}<extra></extra>",
        ))
    if series_b:
        xs, ys, labels = _xy(series_b)
        fig.add_trace(go.Scatter(
            x=xs, y=ys, customdata=labels,
            mode="lines+markers", name="备货天数", yaxis="y2",
            line=dict(color="#1f4e79", width=3, dash="dot"),
            marker=dict(size=9), connectgaps=True,
            hovertemplate="%{customdata}<br>备货天数 %{y:.2f}<extra></extra>",
        ))
    fig.update_layout(
        height=380, template="plotly_white",
        paper_bgcolor="#fff", plot_bgcolor="#fff",
        title=dict(text="策略参数随经营反馈的变化", font=dict(size=17, color="#1f4e79")),
        xaxis=dict(title="0 = 初始值，其后为第 N 次调整",
                   gridcolor="#eef1f4", dtick=1),
        # 注意：plotly 6+ 起轴的字体要用 title.font，旧的 titlefont 已移除
        yaxis=dict(
            title=dict(text="备货宽裕度", font=dict(color="#c0392b")),
            gridcolor="#eef1f4", tickfont=dict(color="#c0392b"),
        ),
        yaxis2=dict(
            title=dict(text="备货天数", font=dict(color="#1f4e79")),
            overlaying="y", side="right", tickfont=dict(color="#1f4e79"),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=70, b=60),
    )
    return fig


def submit_feedback_full(day_str: str, df: pd.DataFrame):
    """
    提交反馈的完整联动：更新「学到了什么」+ 自动刷新「它学会了什么」页，
    并让图表对准最近发生调整的商品。避免用户提交完还要手动翻页刷新。
    """
    body, evo = submit_feedback(day_str, df)
    logs = memory.get_evolution_log(limit=1)
    sku = logs[0]["sku"] if logs else ""
    return body, evo, evo, evolution_chart(sku), sku


def refresh_evolution(sku: str):
    """刷新自进化页：参数演进曲线 + 调整日志。"""
    return evolution_chart(sku or ""), render_evolution_html()


def render_memory_html() -> str:
    stats = memory.memory_stats()
    health = analysis.sku_health_report()

    kpis = f"""
      <div class="kpi"><div class="v">{stats['累计覆盖天数']}</div><div class="l">天经营记录</div></div>
      <div class="kpi"><div class="v">{stats['销量记录条数']}</div><div class="l">条销量明细</div></div>
      <div class="kpi"><div class="v">{stats['商品数']}</div><div class="l">种商品档案</div></div>
      <div class="kpi"><div class="v">{stats['民生商品数']}</div><div class="l">种民生商品</div></div>
    """

    rows = []
    for h in health:
        star = "★ " if h["is_livelihood"] else ""
        cover = h["cover_days"]
        if cover < 2:
            cb = f'<span class="badge b-bad">{cover:.1f} 天</span>'
        elif cover < 4:
            cb = f'<span class="badge b-warn">{cover:.1f} 天</span>'
        else:
            cb = f'<span class="badge b-ok">{cover:.1f} 天</span>'
        so = (f'<span class="badge b-bad">{h["stockout_days"]} 天</span>'
              if h["stockout_days"] > 0 else "<span style='color:#adb5bd'>—</span>")
        sp = (f'<span class="badge b-warn">{h["spoilage_days"]} 天</span>'
              if h["spoilage_days"] > 0 else "<span style='color:#adb5bd'>—</span>")
        rows.append(f"""
        <tr class="{'liv' if h['is_livelihood'] else 'nor'}">
          <td>{star}{h['name']}</td><td>{h['category']}</td>
          <td>{h['avg_daily']:.1f}</td><td>{h['on_hand']:.0f}</td>
          <td>{cb}</td><td>{so}</td><td>{sp}</td>
          <td>{h['stockout_qty']:.0f} / {h['spoilage_qty']:.0f}</td>
        </tr>""")

    return f"""
    {_hero("门店长期记忆库 —— 店脑对这家店的全部认知都沉淀在这里")}
    <div class="dn-card">{kpis}<div style="clear:both"></div></div>
    <div class="dn-card">
      <h3 style="margin-top:0">商品经营健康度</h3>
      <table class="dn">
        <tr><th>商品</th><th>品类</th><th>日均销量</th><th>现有库存</th>
            <th>可支撑</th><th>断过货</th><th>报损过</th><th>缺货量/损耗量</th></tr>
        {''.join(rows)}
      </table>
    </div>"""


def render_analysis_html() -> str:
    ev = analysis.traffic_pull_evidence()
    if "error" in ev:
        return f"<div class='note'>{ev['error']}</div>"

    cat_rows = []
    for c in ev["category_table"]:
        cat_rows.append(f"""
        <tr><td>{c['category']}</td>
            <td><b style="color:#c0392b">{c['high_dev']*100:+.2f}%</b></td>
            <td>{c['low_dev']*100:+.2f}%</td>
            <td><b style="color:#c0392b">{c['gap']*100:+.2f}%</b></td></tr>""")

    return f"""
    {_hero("用这家店自己的历史数据，算清楚一件事：民生商品到底有多重要")}
    <div class="dn-card">
      <h3 style="margin-top:0">为什么不能砍民生商品的货？</h3>
      <p style="font-size:15px;color:#42546b;line-height:1.8">
      民生商品毛利薄，但它有一个传统算法看不见的作用：<b>它是客流入口</b>。
      街坊为了一袋米、一提奶进店，顺手就带走了零食和饮料。
      店脑把这家店 {ev['total_days']} 天的经营记录翻出来做了对比 ——
      </p>
      <table class="dn">
        <tr><th>日子</th><th>非民生商品销量</th><th>天数</th></tr>
        <tr><td>民生商品<b>缺了货</b>的日子</td>
            <td><b style="color:#c0392b">{ev['high_group_deviation']*100:+.2f}%</b>
                （低于平时）</td>
            <td>{ev['high_loss_days']} 天</td></tr>
        <tr><td>民生商品<b>货齐</b>的日子</td>
            <td><b style="color:#2c7a4b">{ev['low_group_deviation']*100:+.2f}%</b>
                （略高于平时）</td>
            <td>{ev['low_loss_days']} 天</td></tr>
        <tr><td><b>两者差距</b></td>
            <td colspan="2"><b style="font-size:17px;color:#c0392b">
                {abs(ev['gap'])*100:.2f} 个百分点</b></td></tr>
      </table>
      <div class="good" style="margin-top:14px">
        📊 <b>结论：</b>民生商品一断货，零食饮料酒水就跟着少卖
        {abs(ev['gap'])*100:.1f}%。样本为 {ev['high_loss_days']} 个缺货日
        对比 {ev['low_loss_days']} 个货齐日。<br>
        传统算法为了省下粮油那点低毛利，砍掉的其实是整家店的客流 ——
        <b>省下的进货钱，在别的品类上亏回去了。</b>
      </div>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">哪些品类最吃客流？</h3>
      <table class="dn">
        <tr><th>品类</th><th>民生缺货日</th><th>民生货齐日</th><th>差距</th></tr>
        {''.join(cat_rows)}
      </table>
      <div style="margin-top:12px;font-size:13px;color:#8b98a8">
        口径说明：已用"同星期几均值"消除周末效应的影响。
      </div>
    </div>"""


def render_about_html() -> str:
    return f"""
    {_hero("面向社区夫妻小店的兼顾抗风险与惠民导向的智能补货决策 Agent")}
    <div class="dn-card">
      <h3 style="margin-top:0">要解决的问题</h3>
      <p style="font-size:15px;color:#42546b;line-height:1.9">
      社区夫妻小店是城市重要的便民基础设施。但店主大多没有数据分析能力，
      全凭个人经验进货，结果两头吃亏：<b>要么商品积压损耗，要么刚需日用品断货</b>。
      市面上的进销存、智能补货系统几乎都面向大型商超，部署复杂、收费高昂，
      小店主用不上、也用不起。
      </p>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">三个创新点</h3>
      <p style="font-size:15px;color:#42546b;line-height:1.9">
      <b>① 带惠民约束的决策逻辑。</b>
      区别于只追求利润最大化的库存算法，本 Agent 增设民生商品约束模块：
      对低毛利刚需日用品设置备货优先级，避免店主单纯逐利砍掉便民货品，
      兼顾商户收益与社区公共便民价值。见「今日该进什么货 → 两种算法对比」。
      </p>
      <p style="font-size:15px;color:#42546b;line-height:1.9">
      <b>② 可落地的长期记忆与策略自进化闭环。</b>
      搭建门店专属长期记忆库，完整留存历史经营事件、商品特性、门店习惯。
      自进化不依赖大模型微调 —— 基于补货后真实的销售、积压、断货反馈，
      动态迭代补货权重参数：断货则上调安全库存，积压损耗则下调进货建议量，
      形成"方案输出 → 业务反馈 → 策略修正"的完整闭环。见「它学会了什么」。
      </p>
      <p style="font-size:15px;color:#42546b;line-height:1.9">
      <b>③ 面向弱势群体小商户的轻量化普惠方案。</b>
      无需专业硬件、无需数据分析基础，浏览器打开即用，
      降低小微企业使用人工智能的门槛。
      </p>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">技术实现</h3>
      <table class="dn">
        <tr><th>模块</th><th>做法</th></tr>
        <tr><td>长期记忆库</td><td>SQLite 持久化商品档案 / 销量事件 / 策略参数 / 进化轨迹</td></tr>
        <tr><td>需求预测</td><td>指数衰减加权移动平均 × 星期效应 × 节日因子；
            关键细节：把断货日的销量还原为<b>潜在需求</b>再学习</td></tr>
        <tr><td>惠民约束</td><td>三层分配：民生兜底锁定 → 剩余预算按资金效率竞争 → 极端不足时按客流价值保底</td></tr>
        <tr><td>策略自进化</td><td>断货↑安全库存 / 积压↓进货量；带硬边界、步长上限、阈值触发，防震荡</td></tr>
        <tr><td>交互界面</td><td>Gradio 网页端，普通浏览器即可使用</td></tr>
      </table>
    </div>"""


# ════════════════════════════════════════════════════════════
# 界面组装
# ════════════════════════════════════════════════════════════
def build_app():
    memory.init_db()
    if not memory.get_products():
        from seed_data import generate_history
        generate_history()

    products = memory.get_products()
    sku_choices = [(f"{'★ ' if p['is_livelihood'] else ''}{p['name']}", p["sku"])
                   for p in products]
    default_sku = sku_choices[0][1] if sku_choices else ""

    with gr.Blocks(**_BLOCKS_KW) as demo:

        with gr.Tabs():
            # ── Tab 1 ──
            with gr.Tab("📋 今天该进什么货"):
                with gr.Row():
                    date_in = gr.Textbox(value=DEFAULT_PLAN_DATE, label="进货日期",
                                         scale=2, info="格式：2026-09-25")
                    budget_in = gr.Number(value=DEFAULT_BUDGET, label="进货预算（元）",
                                          scale=2)
                    btn_plan = gr.Button("🔍 帮我算算", variant="primary", scale=1)
                    btn_cmp = gr.Button("⚖️ 和传统算法比一比", scale=1)
                plan_out = gr.HTML(render_plan_html(
                    policy.build_plan(DEFAULT_PLAN_DATE, DEFAULT_BUDGET,
                                      policy.MODE_DIANNAO, persist=False)))

            # ── Tab 2 ──
            with gr.Tab("✍️ 今天生意怎么样"):
                gr.Markdown(
                    "把今天实际卖了多少、有没有断货、有没有坏货填进来。"
                    "店脑会据此调整明天的进货建议 —— **这一步是它变聪明的关键**。"
                )
                with gr.Row():
                    fb_date = gr.Textbox(value=LAST_DAY, label="填写的是哪一天",
                                         scale=2, info="格式：2026-09-24")
                    btn_tpl = gr.Button("↻ 载入昨日实际数据", scale=1)
                    btn_submit = gr.Button("✅ 提交，让店脑学习", variant="primary", scale=1)

                fb_df = gr.Dataframe(
                    value=load_feedback_template(),
                    headers=["编号", "商品", "昨天卖出", "没买到（断货）", "坏掉/报废"],
                    datatype=["str", "str", "number", "number", "number"],
                    interactive=True, wrap=True, row_count=(16, "fixed"),
                )
                fb_out = gr.HTML()
                evo_out = gr.HTML(render_evolution_html())

            # ── Tab 3 ──
            with gr.Tab("🧠 它学会了什么"):
                gr.Markdown("这里能看到店脑每一次自我调整的来龙去脉 —— "
                            "**为什么改、改了多少、改成什么样**。"
                            "提交反馈后本页会自动刷新；也可手动选择商品查看。")
                with gr.Row():
                    sku_dd = gr.Dropdown(
                        choices=sku_choices,
                        value=default_sku,
                        label="选择商品查看它的策略演进", scale=3,
                    )
                    btn_evo_refresh = gr.Button("↻ 刷新", scale=1)
                evo_chart = gr.Plot(evolution_chart(default_sku))
                evo_log = gr.HTML(render_evolution_html())

            # ── Tab 4 ──
            with gr.Tab("📚 店里的老账本"):
                mem_html = gr.HTML(render_memory_html())
                btn_mem_refresh = gr.Button("↻ 刷新")
                gr.Markdown("---")
                gr.HTML(render_analysis_html())

            # ── Tab 5 ──
            with gr.Tab("ℹ️ 项目说明"):
                gr.HTML(render_about_html())

        # ── 事件绑定统一放在末尾，便于跨标签页联动 ──
        btn_plan.click(do_plan, [date_in, budget_in], plan_out)
        btn_cmp.click(do_compare, [date_in, budget_in], plan_out)
        btn_tpl.click(load_feedback_template, None, fb_df)
        btn_submit.click(
            submit_feedback_full, [fb_date, fb_df],
            [fb_out, evo_out, evo_log, evo_chart, sku_dd],
        )
        sku_dd.change(evolution_chart, sku_dd, evo_chart)
        btn_evo_refresh.click(refresh_evolution, sku_dd, [evo_chart, evo_log])
        btn_mem_refresh.click(render_memory_html, None, mem_html)

    return demo


if __name__ == "__main__":
    import os

    # 本地运行绑回环地址，只有自己电脑能访问；
    # 发布到云端时平台会注入 PORT，此时必须绑 0.0.0.0 才能被反向代理转发。
    _port_env = os.environ.get("PORT")
    if _port_env:
        _host, _port = "0.0.0.0", int(_port_env)
    else:
        _host, _port = "127.0.0.1", int(os.environ.get("HOST_PORT", "7861"))

    app = build_app()
    app.launch(server_name=_host, server_port=_port,
               inbrowser=False, show_error=True, **_LAUNCH_KW)
