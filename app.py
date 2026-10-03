# -*- coding: utf-8 -*-
"""
小满 · 网页交互界面（Gradio）

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
    from core import agent, analysis, decision_basis, decision_trace, eval_core, events, evolution, final_view, forecast, home_view, learn_view, ledger_view, llm, memory, policy, risk, simulator, ui_theme, why_view, about_view
    from core.config import (
        CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
        MEMORY_SAFETY_MAX_DELTA, SAFETY_FACTOR_MAX, SAFETY_FACTOR_MIN,
    )
else:
    from .core import agent, analysis, decision_basis, decision_trace, eval_core, events, evolution, final_view, forecast, home_view, learn_view, ledger_view, llm, memory, policy, risk, simulator, ui_theme, why_view, about_view
    from .core.config import (
        CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
        MEMORY_SAFETY_MAX_DELTA, SAFETY_FACTOR_MAX, SAFETY_FACTOR_MIN,
    )

import gradio as gr

GR_MAJOR = int(gr.__version__.split(".")[0])

# 决策日：默认演示"今晚为明天备货"（CSV 经营数据末日后一天）
DEFAULT_PLAN_DATE = "2026-08-28"
LAST_DAY = "2026-08-27"

CSS = """
.gradio-container { max-width: 1600px !important; }

/* —— 简约商务蓝主题 —— */
.dn-hero { background:#fff; border:1px solid #e6eaf0; border-left:6px solid #2c5f8a;
           border-radius:14px; padding:36px 34px; margin-bottom:22px; }
.dn-hero h1 { margin:0 0 10px; font-size:34px; font-weight:800; letter-spacing:.5px;
              color:#1f4e79; }
.dn-hero p  { margin:0; font-size:16px; color:#5a6b7d; }

.dn-card { background:#fff; border:1px solid #e6eaf0; border-radius:14px;
           padding:20px 22px; margin-bottom:16px; }

/* 指标卡片：圆角 + 柔和阴影 + 大数字 */
.kpi-row { display:flex; flex-wrap:wrap; gap:16px; }
.kpi { flex:1 1 200px; min-width:180px; padding:18px 20px; background:#fff;
       border:1px solid #e6eaf0; border-radius:12px;
       box-shadow:0 2px 8px rgba(44,95,138,.06); }
.kpi .v { font-size:30px; font-weight:700; color:#1f4e79; line-height:1.2; }
.kpi .l { font-size:13px; color:#5a6b7d; margin-top:4px; }

/* 表格：蓝色表头 + 隔行浅灰 + 文字居中 */
table.dn { width:100%; border-collapse:collapse; font-size:15px; }
table.dn th { background:#2c5f8a; color:#fff; text-align:center;
              padding:12px 14px; font-weight:600; }
table.dn td { padding:12px 14px; border-bottom:1px solid #eef1f5; color:#2c3e50;
              text-align:center; }
table.dn tr:nth-child(even) td { background:#f7f9fb; }
table.dn td:first-child, table.dn th:first-child { text-align:left; }
table.dn td.dn-left { text-align:left; }
table.dn tr.liv td:first-child { border-left:4px solid #3f8f6b; }
table.dn tr.nor td:first-child { border-left:4px solid #2c5f8a; }
table.dn tr:hover td { background:#eef4f9; }

/* 徽章 */
.badge { display:inline-block; padding:3px 10px; border-radius:12px;
         font-size:12px; font-weight:600; }
.b-liv { background:#edf7f1; color:#2f7d57; }
.b-hi  { background:#eef4f9; color:#1f4e79; }
.b-warn{ background:#fdf4e5; color:#d98a2b; }
.b-ok  { background:#edf7f1; color:#2f7d57; }
.b-bad { background:#fbf0ee; color:#c0564f; }

/* 补货依据（为什么进这么多） */
details.why { margin-top:8px; text-align:left; font-size:13px; }
details.why summary { cursor:pointer; color:#1f4e79; font-weight:600;
                      font-size:13px; user-select:none; }
details.why .basis { background:#f6f8fb; border:1px solid #e6eaf0; border-radius:8px;
                     padding:10px 12px; margin-top:6px; line-height:1.9;
                     color:#2c3e50; text-align:left; }

/* 提示 / 说明区块：更多边距，排版舒展 */
.note { background:#fffbf0; border-left:4px solid #d98a2b; padding:16px 20px;
        border-radius:8px; font-size:15px; color:#6b5320; line-height:1.8;
        margin:16px 0; }
.good { background:#edf7f1; border-left:4px solid #3f8f6b; padding:16px 20px;
        border-radius:8px; font-size:15px; color:#2f7d57; line-height:1.8;
        margin:16px 0; }

/* 明天有没有特殊情况？面板 */
.dn-risk-panel { background:#fff; border:1px solid #e6eaf0; border-left:6px solid #d98a2b;
                 border-radius:14px; padding:18px 22px; margin-bottom:16px; }
.dn-risk-head { font-size:16px; font-weight:700; color:#1f4e79; margin-bottom:2px; }
.dn-risk-sub { font-size:13px; color:#5a6b7d; margin-bottom:12px; }

/* 生效风险提醒（页面顶部，与节日/促销提醒同区） */
.risk-note { background:#fdf4e5; border-left:4px solid #d98a2b; padding:14px 18px;
             border-radius:8px; font-size:15px; color:#7a5a1f; line-height:1.8;
             margin:0 0 14px; }

h3 { color:#1f4e79 !important; }

/* 输入控件行：加大横向间距 */
.dn-row { --layout-gap: 22px !important; gap: 22px !important; }

/* 隐藏 Gradio 默认框架信息（展示层弱化） */
footer { display: none !important; }
.gradio-container footer { display: none !important; }

/* 顶部导航：图标与文字颜色统一（默认低强调，激活为品牌蓝） */
[role="tab"] { color: #66737F !important; }
[role="tab"][aria-selected="true"] { color: #234E70 !important; font-weight: 600; }
""" + home_view.HOME_CSS + why_view.WHY_CSS + learn_view.LEARN_CSS + ledger_view.LEDGER_CSS + about_view.ABOUT_CSS + ui_theme.THEME_CSS

# Gradio 6.0 起 css/theme 从 Blocks() 挪到了 launch()，这里做版本兼容
_BLOCKS_KW = {"title": "小满 · 自进化智能补货 Agent"}
_LAUNCH_KW = {}
if GR_MAJOR < 6:
    _BLOCKS_KW.update(css=CSS, theme=gr.themes.Soft(primary_hue="blue"))
else:
    _LAUNCH_KW.update(css=CSS, theme=gr.themes.Soft(primary_hue="blue"), footer_links=[])

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


def _reorder_basis(it: dict) -> str:
    """「为什么这样进货」—— 委托 core.decision_basis 输出真实 6 阶段决策链。"""
    return decision_basis.render_reorder_basis(it)


def _reorder_reason(it: dict) -> str:
    """一句人话说明为什么这样进货 —— 全部来自当前真实字段。"""
    if it.get("supplier_down"):
        return "供应商断供，本次不可采购"
    if float(it.get("reorder_qty") or 0.0) <= 0:
        return "现有库存约可支撑 %.1f 天，暂无需补货" % float(it.get("supply_cover_days") or 0.0)
    parts = []
    if it.get("is_livelihood"):
        parts.append("民生商品优先保障")
    if it.get("trimmed"):
        parts.append("预算/多目标权衡后部分满足")
    if abs(float(it.get("memory_delta") or 0.0)) > 1e-9:
        parts.append("参考历史经验微调")
    if it.get("risk_note"):
        parts.append("已计入风险事件")
    return "；".join(parts) if parts else "按目标库存补足"


def _trim_flag(it: dict) -> str:
    """商品行内的「裁剪说明」标签——按 R³ 实际裁剪原因给出更准确的提示。

    只会在 it["trimmed"] 为真（实际采购 < 理论目标）时被调用，因此这里只区分
    「部分满足 / 民生已兜底 / 非民生取舍 / 民生仍有缺口」四种真实情形。
    """
    qty = float(it.get("reorder_qty") or 0.0)
    cover_now = float(it.get("supply_cover_days") or 0.0)
    min_cover = float(LIVELIHOOD_MIN_COVER_DAYS)

    if qty > 1e-9:
        text = "⚠ 预算受限，R³优化后部分满足"
    elif it.get("is_livelihood") and cover_now >= min_cover - 1e-9:
        text = "🛡️ 已满足民生最低保障，本次预算优先分配至其他缺口商品"
    elif not it.get("is_livelihood"):
        text = "⚖️ 预算受限，R³根据收益与库存风险进行取舍"
    else:
        text = "⚠ 当前存在民生保障缺口，R³优先补足最低保障库存"
    return f"<br><span style='font-size:12px;color:#d98a2b'>{text}</span>"


def _hero(sub: str) -> str:
    return f"""
    <div class="dn-hero">
      <h1>🏪 小满 · 面向社区小店的自进化智能补货 Agent</h1>
      <p>{sub}</p>
    </div>"""


def _home_hero(plan: dict) -> str:
    risk = plan.get("risk_summary") or "无特殊风险事件"
    return ('<div class="dn-hero"><h1>小满 · 社区小店智能补货 Agent</h1>'
            '<p>让小店既算经济账，也守住街坊的米袋子和菜篮子</p>'
            '<p style="font-size:13px;color:#5a6b7d;margin-top:6px">决策日期 %s　预算 %s　生效风险：%s</p></div>'
            % (plan["date"], CURRENCY + "%.0f" % float(plan["budget"]), risk))


def _agent_judgement(plan: dict) -> str:
    items = plan["items"]
    m = plan["metrics"]
    risk = plan.get("risk_summary") or "今日无特殊风险事件，按正常经营环境判断"
    n_risk = sum(1 for it in items if it.get("stockout_risk"))
    n_trim = sum(1 for it in items if it.get("trimmed"))
    gap = float(m.get("livelihood_floor_shortfall", 0.0) or 0.0)
    worry = ("有 %d 种商品现有库存可能不足以覆盖明天需求" % n_risk) if n_risk else "暂无商品出现明显缺货风险"
    if gap > 0:
        worry += "；民生最低保障仍有约 %s%.0f 缺口" % (CURRENCY, gap)
    act = "R³ 先在预算内锁定民生兜底，再按毛利分配剩余预算"
    if n_trim:
        act += "；受预算约束，共 %d 种商品的采购量被压缩" % n_trim
    return ('<div class="dn-card" style="border-left:6px solid #2c5f8a;margin-top:14px">'
            '<h3 style="margin-top:0">小满 · 今日判断</h3>'
            '<div style="line-height:2;color:#33414f;font-size:14px">'
            '① 今天发生什么：%s<br>② 小满重点担心：%s<br>③ 因此采取的策略：%s</div></div>'
            % (risk, worry, act))


def render_plan_html(plan: dict) -> str:
    """「今天该进什么货」首页 — 委托 core.home_view（经营工作台，遵循 DESIGN.md）。"""
    return home_view.render_home_html(plan)


def render_why_html(sku: str) -> str:
    """「为什么这样进」页 —— 所选商品的真实 6 阶段决策链（只读决策结果，不改 order_qty）。"""
    plan = policy.build_plan(DEFAULT_PLAN_DATE, DEFAULT_BUDGET, policy.MODE_DIANNAO, persist=False)
    items = plan.get("items") or []
    if not items:
        return "<div class='note'>暂无商品数据。</div>"
    it = next((x for x in items if x["sku"] == sku), items[0])
    return why_view.render_why_page(it)


def render_decision_trace(trace: dict) -> str:
    """渲染「小满 Agent 决策过程」—— 每一步的数据都来自真实执行结果。"""
    rows = []
    for i, s in enumerate(trace["steps"], start=1):
        # 最后一步：最终补货方案，用独立高亮块展示
        if s.get("done"):
            mark = "✓" if s.get("ok", True) else "✗"
            color = "#3f8f6b" if s.get("ok", True) else "#c0564f"
            rows.append(f"""
            <div style="margin-top:6px;padding:14px 16px;background:#edf7f1;border-left:4px solid {color};border-radius:8px;">
              <div style="font-weight:800;color:#1f4e79;font-size:16px;">{mark} {s['tool']}</div>
              <div style="color:#2f7d57;font-size:14px;margin-top:6px;line-height:1.7;">{s['detail']}</div>
            </div>""")
            continue

        ok = s.get("ok", True)
        tool = s.get("tool", "")
        if ok:
            mark, color, title = "✓", "#3f8f6b", tool
        else:
            mark, color, title = "✗", "#c0564f", f"{tool}：执行失败"
        rows.append(f"""
        <div style="padding:10px 0;border-bottom:1px solid #eef1f5;">
          <div style="font-weight:700;color:#1f4e79;font-size:15px;">
            <span style="color:{color};font-weight:800;margin-right:6px;">{mark}</span>
            {i}. {title}
          </div>
          <div style="color:#5a6b7d;font-size:14px;margin-top:3px;padding-left:28px;line-height:1.6;">
            {s['detail']}
          </div>
        </div>""")
    return f"""
    <div class="dn-card" style="border-left:6px solid #2c5f8a; margin-bottom:16px;">
      <h3 style="margin-top:0">小满 Agent 决策过程</h3>
      {''.join(rows)}
    </div>"""


def _compare_verdict(cmp: dict) -> str:
    """根据两种算法的真实指标动态生成结果解读，不写死「小满更好」。

    各指标用「显示精度」作阈值，避免出现「从 3 件降到 3 件」这类舍入假差异。
    """
    md = cmp["diannao"]["metrics"]
    mb = cmp["baseline"]["metrics"]
    dg = md["gross_margin"] - mb["gross_margin"]
    dl = md["livelihood_secured_rate"] - mb["livelihood_secured_rate"]
    ds = md["stockout_units"] - mb["stockout_units"]

    if dg < -0.5:
        margin_part = (f"纯利润策略获得更高的预计毛利（¥{mb['gross_margin']:.0f} 对 "
                       f"¥{md['gross_margin']:.0f}）")
    elif dg > 0.5:
        margin_part = (f"R³策略获得更高的预计毛利（¥{md['gross_margin']:.0f} 对 "
                       f"¥{mb['gross_margin']:.0f}）")
    else:
        margin_part = f"两种策略的预计毛利基本一致（约 ¥{md['gross_margin']:.0f}）"

    if dl > 0.0005:
        live_part = (f"R³策略把民生最低保障达标率从 {mb['livelihood_secured_rate']:.1%} "
                     f"提高到 {md['livelihood_secured_rate']:.1%}")
    elif dl < -0.0005:
        live_part = (f"R³策略的民生最低保障达标率为 {md['livelihood_secured_rate']:.1%}，"
                     f"略低于纯利润策略的 {mb['livelihood_secured_rate']:.1%}")
    else:
        live_part = f"两种策略的民生最低保障达标率一致（{md['livelihood_secured_rate']:.1%}）"

    if ds < -0.5:
        stock_part = (f"预计缺货数量从 {mb['stockout_units']:.1f} 件降到 "
                      f"{md['stockout_units']:.1f} 件")
    elif ds > 0.5:
        stock_part = (f"预计缺货数量为 {md['stockout_units']:.1f} 件，"
                      f"高于纯利润策略的 {mb['stockout_units']:.1f} 件")
    else:
        stock_part = f"两种策略的预计缺货数量基本一致（约 {md['stockout_units']:.0f} 件）"

    return (f"本次决策中，{margin_part}；{live_part}；{stock_part}。"
            f"这体现小满并非单纯追求利润最大化，而是在收益、库存韧性与社区责任之间"
            f"进行多目标权衡。")


def render_compare_html(cmp: dict) -> str:
    """小满 vs 传统纯利润算法的对比 —— 答辩现场的王牌。"""
    rows = []
    for d in sorted(cmp["diff"], key=lambda x: (-x["is_livelihood"], -abs(x["delta"]))):
        if d["diannao_qty"] <= 0 and d["baseline_qty"] <= 0:
            continue
        cls = "liv" if d["is_livelihood"] else "nor"
        delta = d["delta"]
        if abs(delta) < 1e-9:
            d_html = "<span style='color:#adb5bd'>一致</span>"
        elif delta > 0:
            d_html = f"<b style='color:#c0564f'>小满多 {delta:.0f}</b>"
        else:
            d_html = f"<b style='color:#3f8f6b'>小满少 {abs(delta):.0f}</b>"
        rows.append(f"""
        <tr class="{cls}">
          <td>{d['name']}</td>
          <td>{d['diannao_qty']:.0f} {d['unit']}</td>
          <td>{d['baseline_qty']:.0f} {d['unit']}</td>
          <td>{d_html}</td>
        </tr>""")

    md, mb = cmp["diannao"]["metrics"], cmp["baseline"]["metrics"]

    risk_summary = cmp.get("risk_summary", "")
    risk_html = ""
    if risk_summary:
        risk_html = (f'<div class="risk-note">⚠️ <b>当前生效的风险事件</b>：{risk_summary}。'
                     f'两种算法均已按上述风险调整销量预测与补货数量。</div>')

    return f"""
    {_hero(f"同一天 · 同一笔预算 {CURRENCY}{cmp['budget']:.0f} · 两种算法给出的不同答案")}
    {risk_html}
    <div class="dn-card">
      <h3 style="margin-top:0">两种算法，两种活法</h3>
      <table class="dn">
        <tr><th>商品</th><th>小满（惠民约束）</th><th>传统算法（纯利润）</th><th>差异</th></tr>
        {''.join(rows)}
      </table>
    </div>
    <div class="dn-card">
      <table class="dn">
        <tr><th>指标</th><th>小满</th><th>传统算法</th></tr>
        <tr><td>预计毛利</td>
            <td><b>{CURRENCY}{md['gross_margin']:.0f}</b></td>
            <td>{CURRENCY}{mb['gross_margin']:.0f}</td></tr>
        <tr><td>民生最低保障达标率</td>
            <td><b style="color:#3f8f6b">{md['livelihood_secured_rate']:.1%}</b></td>
            <td><b style="color:#8b98a8">{mb['livelihood_secured_rate']:.1%}</b></td></tr>
        <tr><td>库存资金占用（采购金额）</td>
            <td>{CURRENCY}{md['total_cost']:.0f}</td>
            <td>{CURRENCY}{mb['total_cost']:.0f}</td></tr>
        <tr><td>预计缺货数量</td>
            <td>{md['stockout_units']:.1f} 件</td>
            <td>{mb['stockout_units']:.1f} 件</td></tr>
        <tr><td>预计缺货率（覆盖期）</td>
            <td>{md['stockout_rate']:.1%}</td>
            <td>{mb['stockout_rate']:.1%}</td></tr>
        <tr><td>可能断货商品数</td>
            <td>{md['stockout_risk_count']}</td><td>{mb['stockout_risk_count']}</td></tr>
        <tr><td>预计损耗金额（短保商品）</td>
            <td>{CURRENCY}{md['spoilage_cost']:.0f}</td>
            <td>{CURRENCY}{mb['spoilage_cost']:.0f}</td></tr>
      </table>
      <p style="color:#8b98a8;font-size:12px;margin:8px 0 0">
        注：缺货数量 = 补货周期内预期需求 − 补货后可用库存（不足部分求和）；
        缺货率 = 缺货数量 ÷ 补货周期内预期总需求；损耗金额仅统计保质期 ≤ 30 天的短保商品。
      </p>
    </div>
    <div class="note">
      <b>怎么读这张表：</b>传统算法按「单位资金毛利」从高到低分配预算，高毛利商品通常排在前面；
      在预算紧张时，纯利润策略可能优先压缩部分低毛利民生商品的补货量。<br>
      小满先用惠民约束把民生兜底量锁住（<b>至少备够 {LIVELIHOOD_MIN_COVER_DAYS:.0f} 天</b>），
      剩下才按利润分配。
    </div>
    <div class="note">
      <b>结果解读：</b>{_compare_verdict(cmp)}
    </div>"""


# ════════════════════════════════════════════════════════════
# 交互逻辑
# ════════════════════════════════════════════════════════════
def _active_risks(rain: bool, heat: bool, holiday: bool, supplier: bool) -> list[str]:
    """把四个复选框的状态规整成 risk 模块认识的键列表。"""
    active = []
    if rain:
        active.append("rain")
    if heat:
        active.append("heat")
    if holiday:
        active.append("holiday")
    if supplier:
        active.append("supplier")
    return active


_EVENT_LABEL_TO_KEY = {v: k for k, v in events.EVENT_KEY_TO_LABEL.items()}


def _day_risks(day_str: str) -> list[str]:
    """把某天的经营事件（来自 day_events / CSV）映射成补货时的风险键。"""
    info = events.day_info(day_str)
    key = _EVENT_LABEL_TO_KEY.get((info or {}).get("event", "正常"))
    return [key] if key else []


def do_plan(date_str: str, budget: float, rain: bool, heat: bool,
            holiday: bool, supplier: bool):
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        return ("<div class='note'>日期格式不对，请填写类似 2026-08-28 的格式。</div>", "")
    budget = float(budget or DEFAULT_BUDGET)
    risks = _active_risks(rain, heat, holiday, supplier)
    plan = policy.build_plan(d, budget, policy.MODE_DIANNAO, persist=False, risks=risks)
    return (home_view.render_home_html(plan, 'top'), home_view.render_home_html(plan, 'result'))


def do_compare(date_str: str, budget: float, rain: bool, heat: bool,
               holiday: bool, supplier: bool):
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        return "<div class='note'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
    budget = float(budget or DEFAULT_BUDGET)
    risks = _active_risks(rain, heat, holiday, supplier)
    cmp = policy.compare_plans(d, budget, persist=False, risks=risks)
    return render_compare_html(cmp)


def do_explain(date_str: str, budget: float, rain: bool, heat: bool,
               holiday: bool, supplier: bool):
    """用大白话解释当前补货方案（LLM 可用时走 AI，否则走规则模板）。"""
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        return "<div class='note'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
    budget = float(budget or DEFAULT_BUDGET)
    risks = _active_risks(rain, heat, holiday, supplier)
    plan = policy.build_plan(d, budget, policy.MODE_DIANNAO, persist=False, risks=risks)
    text = llm.explain_plan(plan)
    html_text = text.replace("\n", "<br>")
    if llm.is_enabled():
        head = "🤖 大模型解读"
    else:
        head = "📋 规则模板解读（未配置 LLM Key，配置后自动切换为 AI 讲解）"
    return f"<div class='good'><b>{head}</b><br><br>{html_text}</div>"


def do_agent(request_text: str):
    """Agent 智能补货入口：解析自然语言请求 → 走完整数据决策流程。

    例如输入「预算600元，明天高温」—— Agent 会读历史数据、找历史高温事件、
    分析高温期间的销量变化、检查商品与民生属性、生成方案并解释。
    """
    import re
    text = (request_text or "").strip()
    req = agent.parse_request(text)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    plan_date = m.group(1) if m else DEFAULT_PLAN_DATE

    try:
        date.fromisoformat(plan_date)
    except Exception:
        return "<div class='note'>日期格式不对，请填写类似 2026-08-28 的格式。</div>"

    result = agent.plan_and_explain(plan_date, req["budget"], req["risks"])
    explanation = result["explanation"].replace("\n", "<br>")
    plan_html = render_plan_html(result["plan"])
    return f"""
    <div class="dn-card">
      <h3 style="margin-top:0">🤖 Agent 的推理过程</h3>
      <div class="note" style="margin:8px 0">{explanation}</div>
    </div>
    {plan_html}"""


_EVENT_ICON = {
    "高温": "🔥", "暴雨": "☔", "节假日": "📅", "供应商D断供": "📦", "正常": "🏪",
}


def render_experiences_html() -> str:
    """「它学会了什么」页优先展示的经营经验（来自真实反馈，非随机参数）。"""
    rows = memory.get_experiences(limit=40)
    if not rows:
        return "<div class='note'>暂无学习记录，请先提交一次经营反馈。</div>"

    products = {p["sku"]: p for p in memory.get_products()}
    items = []
    for r in rows:
        p = products.get(r["sku"], {})
        nm = p.get("name", r["sku"])
        unit = p.get("unit", "件")
        icon = _EVENT_ICON.get(r["event_type"], "🏪")
        ev_label = r["event_type"] if r["event_type"] != "正常" else "普通日"
        sig_badge = ('<span class="badge b-bad">断货</span>' if r["signal"] == "断货"
                     else '<span class="badge b-warn">积压损耗</span>')
        items.append(f"""
        <div style="padding:14px 0;border-bottom:1px solid #eef1f5;">
          <div style="font-size:15px;font-weight:700;color:#1f4e79;">
            <span>{icon} {ev_label}</span> · {nm} {sig_badge}
            <span style="font-weight:400;font-size:12px;color:#8b98a8;margin-left:10px;">{r['day']}</span>
          </div>
          <div style="color:#5a6b7d;font-size:14px;margin-top:6px;padding-left:4px;line-height:1.9;">
            原计划：预计卖 <b>{r['forecast_qty']:.1f}</b> {unit}，建议补货 <b>{r['reorder_qty']:.0f}</b> {unit}<br>
            实际结果：卖出 <b>{r['qty_sold']:.0f}</b> {unit}，断货 <b>{r['qty_stockout']:.0f}</b> {unit}，报损 <b>{r['qty_spoilage']:.0f}</b> {unit}<br>
            → 学到：{r['lesson']}<br>
            → 下次：{r['adjustment']}
          </div>
        </div>""")

    return f"""
    <div class="dn-card" style="border-left:6px solid #2c5f8a;">
      <h3 style="margin-top:0">📌 最近学到的经营经验</h3>
      {''.join(items)}
    </div>"""


def render_eval_figure():
    """在隔离临时库上跑一轮快速评测，返回 Plotly 对比图（不动在线记忆库）。"""
    import tempfile

    tmp_db = Path(tempfile.gettempdir()) / "diannao_eval_tmp.db"
    try:
        results = eval_core.run_eval(seeds=[42], days=eval_core.DAYS, db_path=tmp_db)
        return eval_core.build_figure(results, eval_core.DAYS, 1)
    finally:
        try:
            tmp_db.unlink(missing_ok=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# 📊 180 天数字小店长期实验（小满 vs 传统纯利润）
# ════════════════════════════════════════════════════════════
def _fmt_money(v) -> str:
    return f"{CURRENCY}{v:,.0f}"


def render_digital_store_html(results: dict, gt: dict, budget: float) -> str:
    """把 180 天长期仿真的真实结果渲染成指标卡 + 对照表 + 客观结论。"""
    d = results["diannao"]["summary"]
    b = results["baseline"]["summary"]
    d0, d1 = gt["day_list"][0], gt["day_list"][-1]

    def kpi(name, unit, dv, bv, better_low=False):
        # 谁更优就在哪一侧标绿
        d_better = (dv < bv) if better_low else (dv > bv)
        b_better = (bv < dv) if better_low else (bv > dv)
        d_color = "#2c7a4b" if d_better else "#1f4e79"
        b_color = "#c0392b" if b_better else "#8b98a8"
        return f"""
        <div class="kpi">
          <div style="font-size:13px;color:#5a6b7d;margin-bottom:6px">{name}</div>
          <div style="font-size:13px;color:#8b98a8">小满</div>
          <div style="font-size:24px;font-weight:800;color:{d_color}">{dv}{unit}</div>
          <div style="font-size:12px;color:#8b98a8;margin-top:4px">传统</div>
          <div style="font-size:18px;font-weight:700;color:{b_color}">{bv}{unit}</div>
        </div>"""

    cards = (
        kpi("累计毛利", "", _fmt_money(d["cumulative_gross_margin"]),
            _fmt_money(b["cumulative_gross_margin"]))
        + kpi("总体缺货率", "", f"{d['stockout_rate']:.2%}", f"{b['stockout_rate']:.2%}",
              better_low=True)
        + kpi("民生最低保障达标率", "", f"{d['livelihood_secured_rate']:.1%}",
              f"{b['livelihood_secured_rate']:.1%}")
        + kpi("民生实际缺货率", "", f"{d['livelihood_stockout_rate']:.2%}",
              f"{b['livelihood_stockout_rate']:.2%}", better_low=True)
        + kpi("民生实际缺货件数", "", f"{d['livelihood_stockout_qty']:,.0f}",
              f"{b['livelihood_stockout_qty']:,.0f}", better_low=True)
        + kpi("损耗/报废率", "", f"{d['spoilage_rate']:.3%}", f"{b['spoilage_rate']:.3%}",
              better_low=True)
        + kpi("平均库存资金占用", "", _fmt_money(d["avg_inventory_capital"]),
              _fmt_money(b["avg_inventory_capital"]), better_low=True)
    )

    table = f"""
    <table class="dn">
      <tr><th>指标</th><th>小满 R³</th><th>传统纯利润</th><th>口径 / 公式</th></tr>
      <tr><td>累计毛利</td><td><b>{_fmt_money(d['cumulative_gross_margin'])}</b></td>
          <td>{_fmt_money(b['cumulative_gross_margin'])}</td>
          <td>Σ 实销×毛利额 − Σ 损耗×进价</td></tr>
      <tr><td>总体缺货率</td><td>{d['stockout_rate']:.2%}</td><td>{b['stockout_rate']:.2%}</td>
          <td>全部商品缺货件数 ÷ 全部商品真实需求件数</td></tr>
      <tr><td>民生最低保障达标率</td><td><b style="color:#2c7a4b">{d['livelihood_secured_rate']:.1%}</b></td>
          <td>{b['livelihood_secured_rate']:.1%}</td>
          <td>180 天平均的每日「补货量 ≥ 民生最低保障量」达标比例</td></tr>
      <tr><td>民生商品实际缺货率</td><td><b style="color:#2c7a4b">{d['livelihood_stockout_rate']:.2%}</b></td>
          <td>{b['livelihood_stockout_rate']:.2%}</td>
          <td>19 种民生商品缺货件数 ÷ 其真实需求件数</td></tr>
      <tr><td>民生商品实际缺货件数</td><td><b style="color:#2c7a4b">{d['livelihood_stockout_qty']:,.0f}</b></td>
          <td>{b['livelihood_stockout_qty']:,.0f}</td>
          <td>19 种民生商品 Σ(需求 − 销量) 中缺货部分</td></tr>
      <tr><td>缺货件数（全部商品）</td><td>{d['stockout_qty']:,.1f}</td><td>{b['stockout_qty']:,.1f}</td>
          <td>Σ(需求 − 销量) 中缺货部分</td></tr>
      <tr><td>缺货 SKU 数 / 次数</td>
          <td>{d['stockout_sku_count']} / {d['stockout_occurrences']}</td>
          <td>{b['stockout_sku_count']} / {b['stockout_occurrences']}</td>
          <td>缺过货的商品数 / SKU×日 缺货次数</td></tr>
      <tr><td>损耗率</td><td>{d['spoilage_rate']:.3%}</td><td>{b['spoilage_rate']:.3%}</td>
          <td>损耗件数 ÷ (销量 + 损耗件数)</td></tr>
      <tr><td>损耗/报废件数</td><td>{d['spoilage_qty']:,.1f}</td><td>{b['spoilage_qty']:,.1f}</td>
          <td>短保/易损商品的过期报废量</td></tr>
      <tr><td>平均库存资金占用</td>
          <td>{_fmt_money(d['avg_inventory_capital'])}</td>
          <td>{_fmt_money(b['avg_inventory_capital'])}</td>
          <td>180 天平均的每日期初库存货值</td></tr>
      <tr><td>库存周转（180 天内）</td>
          <td>{d['inventory_turnover']:.1f} 次</td><td>{b['inventory_turnover']:.1f} 次</td>
          <td>销售成本 ÷ 平均库存资金占用</td></tr>
    </table>"""

    return f"""
    {_hero(f"180 天数字小店长期实验：同一条街、同样的 180 天，两种补货思路的最终成绩单")}
    <div class="note">
      仿真区间 <b>{d0} ~ {d1}</b>（{len(gt['day_list'])} 天 × {len(gt['products'])} 个 SKU）·
      每日进货预算 <b>{_fmt_money(budget)}</b> · 两种策略面对<b>完全相同</b>的需求序列、价格、交期、
      天气/节假日/断供事件，差别只在<b>补货决策策略</b>。
    </div>
    <div class="kpi-row">{cards}</div>
    <div class="dn-card">
      <h3 style="margin-top:0">长期指标对照（全部由仿真日志真实计算）</h3>
      {table}
    </div>
    <div class="note">
      <b>📖 指标说明：</b><br>
      · <b>总体缺货率</b>：全部商品（50 SKU）未满足需求件数占其总需求件数的比例；<br>
      · <b>民生最低保障达标率</b>：补货决策满足民生商品最低保障库存约束的比例（计划层面），
      不代表经营过程中完全不会发生实际缺货；<br>
      · <b>民生商品实际缺货率</b>：19 种民生商品在真实经营中未被满足的需求件数
      占其总需求件数的比例（结算层面）。
    </div>
    <div class="note">
      <b>📌 客观结论：</b>{simulator.conclusion_text(results)}
    </div>
    <div class="note">
      <b>无未来数据泄漏：</b>第 t 天补货时，决策层只读「t 天以前」的经营记录与当天已知的
      天气/节假日/断供状态；真实需求仅保存在仿真结算层（上帝视角），不喂给决策。
      因此两个策略看到的未来信息完全相同，结论可比。
    </div>"""


def do_digital_store(budget):
    """运行 180 天长期仿真。返回 (指标卡 HTML, 累计毛利曲线, 总体缺货率/民生最低保障达标率变化)。"""
    budget = float(budget) if budget else simulator.DEFAULT_SIM_BUDGET
    results = simulator.run_strategies(simulator.MAIN_STRATEGIES, budget=budget,
                                       seed=simulator.DEFAULT_SEED, keep_daily=True)
    gt = simulator.load_ground_truth()
    html = render_digital_store_html(results, gt, budget)
    fig1 = simulator.build_cumulative_figure(results)
    fig2 = simulator.build_rates_figure(results)
    return html, fig1, fig2


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
            sold = float(row["昨天卖出"] or 0)
            stockout = float(row["没买到（断货）"] or 0)
            spoilage = float(row["坏掉/报废"] or 0)
        except (TypeError, ValueError):
            continue
        # 输入限制：必须为大于等于 0 的数字，不能出现负数（NaN 也会在此被拦截）
        if not (sold >= 0 and stockout >= 0 and spoilage >= 0):
            return ("<div class='note'>❌ 输入有误：昨天卖出 / 没买到（断货）/ 坏掉报废 "
                    "都必须填大于等于 0 的数字，不能出现负数，请检查后再提交。</div>",
                    render_evolution_html())
        feedback.append({
            "sku": str(row["编号"]).strip(),
            "qty_sold": sold,
            "qty_stockout": stockout,
            "qty_spoilage": spoilage,
        })

    # 还原"当时的补货决策"：按当天经营事件重算预测销量与建议补货量，
    # 连同日期 / 商品 / 场景一起写进反馈记录，供 Memory 复盘。
    risks = _day_risks(d)
    plan = policy.build_plan(d, DEFAULT_BUDGET, policy.MODE_DIANNAO,
                             persist=False, risks=risks)
    plan_context = {
        it["sku"]: {"forecast_qty": it["daily_demand"], "reorder_qty": it["reorder_qty"]}
        for it in plan["items"]
    }

    result = evolution.process_feedback(d, feedback, plan_context=plan_context)
    changes = result["changes"]
    summary = result["summary"]
    skipped = summary.get("skipped", 0)

    # 提交成功提示（无论是否触发策略校准都显示）
    success = "<div class='good'>今天的经营情况已记下</div>"


    if not changes:
        if skipped > 0:
            # 幂等去重：完全相同的反馈已经学习过，本次不重复调整策略
            body = ("<div class='good'>今天的经营情况已记下（此前已记录过）。</div>"
                    f"<div class='note'>已跳过 {skipped} 条与历史完全一致的经营反馈"
                    "（同一天、同一商品、同一销量/断货/报损），小满不会把同一结果重复学习两次。</div>")
        elif summary.get("updated", 0) > 0:
            body = success + ("<div class='note'>本次为经营数据修正：已更新原记录并重算"
                              "策略影响，策略参数保持不变（未累计学习两次）。</div>")
        elif summary.get("removed", 0) > 0:
            body = success + ("<div class='note'>本次为经营数据修正：原异常已消除，"
                              "已撤销对应的策略调整。</div>")
        else:
            body = success + (f"<div class='note'>已记录。本次没有触发新的策略调整。"
                              f"今天断货 {summary['stockout_days']} 项、损耗 {summary['spoilage_days']} 项，"
                              f"都在正常波动范围内，不需要调整策略。</div>")
    else:
        rows = []
        for ch in changes:
            o_s, n_s = ch["safety_factor"]
            arrow = "↑ 上调" if n_s > o_s else "↓ 下调"
            cls = "liv" if ch["is_livelihood"] else "nor"
            tag = ('<span class="badge b-liv">断货</span>' if ch["trigger"] == "断货"
                   else '<span class="badge b-warn">积压损耗</span>')
            scene = ch.get("scene", "")
            rows.append(f"""
            <tr class="{cls}">
              <td>{ch['name']}</td>
              <td>{tag}</td>
              <td>{arrow}（下次{scene}：{o_s:.2f} → {n_s:.2f}）</td>
              <td class="dn-left" style="font-size:13px;color:#5a6b7d">{ch['reason']}</td>
            </tr>""")
        body = success + f"""
        <div class="dn-card">
          <h3 style="margin-top:0">这次记录让小满更新了 {len(changes)} 个商品的经营经验</h3>
          <table class="dn">
            <tr><th>商品</th><th>发生了什么</th><th>怎么调整</th><th>为什么</th></tr>
            {''.join(rows)}
          </table>
        </div>
        <div class="good">
          下次再遇到类似情况时，小满会参考这条经验，
          对之后的补货建议做小幅调整。
        </div>"""

    return body, render_evolution_html()


def render_evolution_html() -> str:
    logs = memory.get_evolution_log(limit=40)
    if not logs:
        return ("<div class='note'>还没有学习记录。到「今天生意怎么样」录一次反馈，"
                "这里就会显示小满是怎么自己调整的。</div>")

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
          <td><b style="color:{'#c0564f' if arrow == '↑' else '#3f8f6b'}">{arrow}
              {lg['old_value']:.3f} → {lg['new_value']:.3f}</b></td>
        </tr>""")

    n_up = sum(1 for lg in logs if (lg["new_value"] or 0) > (lg["old_value"] or 0))
    n_down = len(logs) - n_up

    return f"""
    <div class="dn-card">
      <div class="kpi-row">
      <div class="kpi"><div class="v">{len(logs)}</div><div class="l">累计学习次数</div></div>
      <div class="kpi"><div class="v">{n_up}</div><div class="l">为避免断货上调</div></div>
      <div class="kpi"><div class="v">{n_down}</div><div class="l">为减少积压下下调</div></div>
      </div>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">策略自进化轨迹</h3>
      <table class="dn">
        <tr><th>日期</th><th>商品</th><th>触发原因</th><th>调整了什么</th><th>变化</th></tr>
        {''.join(rows)}
      </table>
    </div>"""


def _scene_label(event_type) -> str:
    """把事件类型翻译成页面上的场景名（普通日/高温/暴雨/节假日/供应商D断供）。"""
    return "普通日" if not event_type or event_type == "正常" else event_type


def render_sku_strategy_html(sku: str) -> str:
    """选中商品的「当前策略状态」：基础/当前安全系数、有效学习次数、最近一次调整。"""
    products = {p["sku"]: p for p in memory.get_products()}
    p = products.get(sku) if sku else None
    if not p:
        return "<div class='note'>请先在上方选择一个商品。</div>"

    pol = memory.get_policy(sku) or {}
    base = float(pol.get("safety_factor", 0.15))
    details = memory.evolution_details(sku)
    current = float(details[-1]["new_value"]) if details else base
    n_learn = len(details)
    star = "★ " if p.get("is_livelihood") else ""

    # 边界提示：达到系统硬上下限，或单商品累计校准 ±0.06（自适应边界）
    boundary = ""
    if current >= SAFETY_FACTOR_MAX - 1e-9:
        boundary = ("<div class='note' style='border-left-color:#c0564f;background:#fbf0ee;color:#8a3d37;'>"
                    "🛑 已达到策略安全边界（系统上限），本次不再继续调整。</div>")
    elif current <= SAFETY_FACTOR_MIN + 1e-9:
        boundary = ("<div class='note' style='border-left-color:#c0564f;background:#fbf0ee;color:#8a3d37;'>"
                    "🛑 已达到策略安全边界（系统下限），本次不再继续调整。</div>")
    elif abs(current - base) >= MEMORY_SAFETY_MAX_DELTA - 1e-9:
        boundary = ("<div class='note' style='border-left-color:#c0564f;background:#fbf0ee;color:#8a3d37;'>"
                    f"🛑 该商品累计校准已达 ±{MEMORY_SAFETY_MAX_DELTA:.2f} 的自适应边界，"
                    "后续同类反馈不再继续调整安全系数。</div>")

    if not details:
        last_reason = "—"
        change_line = ("<span style='color:#8b98a8'>暂未形成有效调整 —— "
                       "提交一次真正触发阈值的经营反馈后，这里会出现变化。</span>")
    else:
        last = details[-1]
        signal = "发生断货" if last["trigger"] == "断货" else "发生报损"
        last_reason = f"{last['day']} {_scene_label(last['event_type'])}{signal}"
        change_line = (f"<b style='color:#c0564f'>{base:.2f} → {current:.2f}</b>"
                       f"<span style='color:#8b98a8;font-size:13px;margin-left:8px'>"
                       f"（累计 {n_learn} 次有效调整）</span>")

    return f"""
    <div class="dn-card" style="border-left:6px solid #2c5f8a;">
      <h3 style="margin-top:0">📊 当前策略状态 · {star}{p['name']}</h3>
      <div class="kpi-row">
        <div class="kpi"><div class="v">{base:.2f}</div><div class="l">基础安全库存系数</div></div>
        <div class="kpi"><div class="v" style="color:#c0564f">{current:.2f}</div><div class="l">当前安全库存系数</div></div>
        <div class="kpi"><div class="v">{n_learn}</div><div class="l">累计有效学习</div></div>
      </div>
      <div style="margin-top:14px;font-size:15px;color:#2c3e50;line-height:1.9;">
        <div><b>最近一次调整原因：</b>{last_reason}</div>
        <div><b>策略变化：</b>{change_line}</div>
      </div>
      {boundary}
    </div>"""


def evolution_chart(sku: str):
    """画某商品的安全库存系数演进曲线（只取真实有效的调整记录，重复/被去重不算节点）。"""
    products = {p["sku"]: p for p in memory.get_products()}
    p = products.get(sku, {})
    nm = p.get("name", sku or "未选择商品")
    details = memory.evolution_details(sku) if sku else []

    fig = go.Figure()

    if not details:
        fig.add_annotation(text=f"{nm} 还没有有效的策略调整记录", showarrow=False,
                           font=dict(size=16, color="#8b98a8"))
        fig.update_layout(height=360, template="plotly_white",
                          paper_bgcolor="#fff", plot_bgcolor="#fff",
                          title=dict(text=f"{nm} · 安全库存系数演进",
                                     font=dict(size=17, color="#1f4e79")))
        return fig

    # 第 0 个点是初始值（首次调整的 old_value，即基础安全系数），
    # 其后每个点是「真正改变策略」的有效调整的 new_value。
    base = float(details[0]["old_value"])
    xs = list(range(0, len(details) + 1))
    ys = [base] + [float(d["new_value"]) for d in details]

    # 悬停详情：每个点都讲清楚哪天 / 什么场景 / 卖多少 / 断货多少 / 报损多少 / 为何调整
    hover = [f"初始值<br>安全库存系数 <b>{base:.3f}</b>"]
    for d in details:
        trigger = d["trigger"] or ""
        signal = ("断货" if trigger == "断货"
                  else "积压损耗" if trigger == "积压损耗" else trigger)
        hover.append(
            f"<b>日期：{d['day']}</b><br>"
            f"经营场景：{_scene_label(d['event_type'])}<br>"
            f"实际销量：{float(d['qty_sold'] or 0):.0f} 件<br>"
            f"断货数量：{float(d['qty_stockout'] or 0):.0f} 件<br>"
            f"报损数量：{float(d['qty_spoilage'] or 0):.0f} 件<br>"
            f"调整前参数：{float(d['old_value']):.3f}<br>"
            f"调整后参数：{float(d['new_value']):.3f}<br>"
            f"调整原因：{signal}"
        )

    fig.add_trace(go.Scatter(
        x=xs, y=ys, text=hover,
        mode="lines+markers", name="安全库存系数",
        line=dict(color="#c0392b", width=3),
        marker=dict(size=11, color="#c0392b", line=dict(color="#fff", width=1.5)),
        connectgaps=True,
        hovertemplate="%{text}<extra></extra>",
    ))

    # 横轴：0 = 初始值，其后标注每次有效调整的日期（MM-DD）
    tick_vals = list(range(len(xs)))
    tick_text = ["初始"] + [str(d["day"])[5:] for d in details]

    fig.update_layout(
        height=380, template="plotly_white",
        paper_bgcolor="#fff", plot_bgcolor="#fff",
        title=dict(text=f"{nm} · 安全库存系数随经营反馈的变化",
                   font=dict(size=17, color="#1f4e79")),
        xaxis=dict(
            title=dict(text="经营反馈（0 = 初始值，其后为每次有效调整的日期）",
                       font=dict(size=12, color="#5a6b7d")),
            gridcolor="#eef1f4", tickvals=tick_vals, ticktext=tick_text,
        ),
        yaxis=dict(
            title=dict(text="安全库存系数", font=dict(color="#c0392b")),
            gridcolor="#eef1f4", tickfont=dict(color="#c0392b"),
        ),
        margin=dict(l=60, r=30, t=70, b=70),
    )
    return fig


def submit_feedback_full(day_str: str, df: pd.DataFrame):
    """
    提交反馈的完整联动：更新「学到了什么」+ 自动刷新「它学会了什么」页，
    并让图表对准最近发生调整的商品。避免用户提交完还要手动翻页刷新。
    """
    body, evo = submit_feedback(day_str, df)
    products = {p["sku"]: p for p in memory.get_products()}
    logs = memory.get_evolution_log(limit=1)
    # 最近发生调整的商品优先；若本次没有沉淀经验（无进化记录），则退回第一个商品，
    # 确保返回给 sku_dd 下拉框的值始终是真实存在的 SKU，避免空串触发
    # "Value: is not in the list of choices" 的组件报错。
    sku = logs[0]["sku"] if logs else ""
    if sku not in products:
        sku = next(iter(products), "")
    return (body, evo, render_sku_strategy_html(sku), evo,
            evolution_chart(sku), sku, learn_view.render_learn_page())


def refresh_evolution(sku: str):
    """刷新自进化页：当前策略状态 + 参数演进曲线 + 调整日志。"""
    return render_sku_strategy_html(sku or ""), evolution_chart(sku or ""), render_evolution_html()


def render_memory_html() -> str:
    """「店里的老账本」— 委托 core.ledger_view（经营档案，遵循 DESIGN.md）。"""
    return ledger_view.render_ledger()


def render_analysis_html() -> str:
    """用 180 天 CSV 经营数据，算清楚高温 / 暴雨 / 节假日把销量抬/压了多少。

    原来的「客流带动效应」分析依赖仿真里埋入的「民生缺货量」信号；
    CSV 只记录实际销量、不记录缺货量，因此这里改为 CSV 真正支持的
    「事件对销量的影响」分析 —— 数据直接来自天气/事件列。
    """
    summary = events.events_summary()
    impact_table = events.event_impact_table()

    ev_rows = []
    for k in events.EVENT_KEY_TO_LABEL:
        days = summary.get(k, [])
        if days:
            ev_rows.append(f"""
            <tr><td>{events.EVENT_KEY_TO_LABEL[k]}</td><td>{len(days)} 天</td>
                <td>{days[0]} ~ {days[-1]}</td></tr>""")

    def _fmt(v):
        return f"{v*100:+.1f}%" if v is not None else "—"

    cat_rows = []
    for r in impact_table:
        cat_rows.append(f"""
        <tr><td>{r['category']}</td>
            <td><b style="color:#c0564f">{_fmt(r['heat'])}</b></td>
            <td><b style="color:#1f4e79">{_fmt(r['rain'])}</b></td>
            <td><b style="color:#3f8f6b">{_fmt(r['holiday'])}</b></td></tr>""")

    return f"""
    {_hero("用 180 天经营数据，算清楚高温 / 暴雨 / 节假日到底把销量抬了多少")}
    <div class="dn-card">
      <h3 style="margin-top:0">📅 历史事件日历</h3>
      <table class="dn">
        <tr><th>事件</th><th>天数</th><th>发生时段</th></tr>
        {''.join(ev_rows)}
      </table>
      <div style="margin-top:12px;font-size:13px;color:#8b98a8">
        这些事件直接来自经营仿真数据 CSV 的天气 / 事件列，不是写死的数字。
      </div>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">事件对销量的影响（数据驱动）</h3>
      <table class="dn">
        <tr><th>品类</th><th>高温</th><th>暴雨</th><th>节假日</th></tr>
        {''.join(cat_rows)}
      </table>
      <div style="margin-top:12px;font-size:13px;color:#8b98a8">
        口径：事件日销量 ÷ 同星期几非事件日均值（已消除星期效应）；
        勾选风险事件时，预测模块优先用这里的真实乘数，数据缺失再回退先验系数。
      </div>
    </div>"""


def render_about_html() -> str:
    """「项目说明」— 委托 core.about_view（产品叙事）。"""
    return about_view.render_about()


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

        with gr.Tabs() as main_tabs:
            # ── Tab 1 ──
            with gr.Tab("今天该进什么货"):
                with gr.Group(elem_classes=["xm-flow"]):
                    plan_top_out = gr.HTML(home_view.render_home_html(policy.build_plan(DEFAULT_PLAN_DATE, DEFAULT_BUDGET, policy.MODE_DIANNAO, persist=False), 'top'))
                    with gr.Accordion('明天按什么情况进货？　%s · 预算 ¥%.0f · 暂无特殊情况' % (DEFAULT_PLAN_DATE[5:].replace('-', '/'), DEFAULT_BUDGET), open=False):
                        with gr.Row(elem_classes=["dn-row"]):
                            date_in = gr.Textbox(value=DEFAULT_PLAN_DATE, label="目标经营日",
                                                 scale=2, info="为这一天的经营备货，默认=明天")
                            budget_in = gr.Number(value=DEFAULT_BUDGET, label="这次最多花多少（元）",
                                                  scale=2)
                            btn_plan = gr.Button("重新生成进货建议", variant="primary", scale=1)
                            btn_cmp = gr.Button("与传统算法对比（实验）", scale=1)
    
                        with gr.Group(elem_classes=["dn-risk-panel"]):
                            gr.HTML("<div class='dn-risk-head'>明天有没有特殊情况？</div>"
                                    "<div class='dn-risk-sub'>勾选后小满会把它纳入销量预计与补货计算；"
                                    "不勾选则按正常情况计算。</div>")
                            with gr.Row(elem_classes=["dn-row"]):
                                rain_cb = gr.Checkbox(value=False, label="暴雨",
                                                      info="客流可能下降")
                                heat_cb = gr.Checkbox(value=False, label="高温",
                                                      info="冷饮需求可能上升")
                                holiday_cb = gr.Checkbox(value=False, label="节假日",
                                                         info="整体备货需求可能增加")
                                supplier_cb = gr.Checkbox(value=False, label="供应商断货",
                                                          info="需要增加安全库存缓冲")

                    plan_out = gr.HTML(home_view.render_home_html(policy.build_plan(DEFAULT_PLAN_DATE, DEFAULT_BUDGET, policy.MODE_DIANNAO, persist=False), 'result'))
                with gr.Row():
                    btn_explain = gr.Button("用大白话解释", scale=1)
                    btn_goto_exp = gr.Button("查看实验验证 ›", scale=1)
                explain_out = gr.HTML()

                gr.Markdown("---")
                gr.Markdown("### 🤖 Agent 智能补货\n"
                            "直接说需求，例如「预算600元，明天高温」。"
                            "Agent 会读历史数据 → 找历史事件 → 分析销量影响 → 出方案并解释。")
                with gr.Row(elem_classes=["dn-row"]):
                    agent_in = gr.Textbox(label="你的需求", scale=4,
                                          placeholder="例如：预算600元，明天高温，帮我算算")
                    btn_agent = gr.Button("🤖 让 Agent 来算", variant="primary", scale=1)
                agent_out = gr.HTML()

                gr.Markdown("---")
                with gr.Accordion('高级实验工具 · 180 天长期仿真（现场无需运行）', open=False):
                    with gr.Row(elem_classes=["dn-row"]):
                        sim_budget = gr.Number(value=simulator.DEFAULT_SIM_BUDGET,
                                               label="每日进货预算（元）", scale=2,
                                               info="默认 ¥1800，两种策略使用同一预算")
                        btn_sim = gr.Button("🚀 运行180天仿真", variant="primary", scale=1)
                    gr.Markdown("⏳ 约需 2 分钟（其中完整小满每次约 100 秒，传统算法约 20 秒）。"
                                "完整消融实验请运行 `python run_digital_store.py`。")
                    sim_out = gr.HTML()
                    with gr.Row():
                        sim_plot1 = gr.Plot(scale=1)
                        sim_plot2 = gr.Plot(scale=1)

            # ── Tab 2 ── 为什么这样进
            with gr.Tab("为什么这样进"):
                gr.Markdown("## 为什么这样进\n看看每一笔补货建议背后的依据")
                with gr.Row(elem_classes=["dn-row"]):
                    why_sku = gr.Dropdown(choices=sku_choices, value=default_sku, label="正在查看", scale=3)
                    btn_why = gr.Button("查看", variant="primary", scale=1)
                why_out = gr.HTML(render_why_html(default_sku))

            # ── Tab 3 ──
            with gr.Tab("今天生意怎么样", id="feedback"):
                gr.Markdown("## 今天生意怎么样")
                gr.Markdown("记录今天真实卖货情况，小满会据此调整之后的建议。")
                with gr.Row(elem_classes=["dn-row"]):
                    fb_date = gr.Textbox(value=LAST_DAY, label="记录日期",
                                         scale=2, info="格式：2026-09-24")
                    btn_tpl = gr.Button("载入昨日实际数据", scale=1)
                    btn_submit = gr.Button("保存今日经营情况", variant="primary", scale=1)

                fb_df = gr.Dataframe(
                    value=load_feedback_template(),
                    headers=["编号", "商品", "昨天卖出", "没买到（断货）", "坏掉/报废"],
                    datatype=["str", "str", "number", "number", "number"],
                    interactive=True, wrap=True, row_count=(16, "fixed"),
                )
                gr.Markdown("「没买到（断货）」= 有顾客想买，但店里已经没有；「坏掉/报废」= 过期、破损或无法继续销售。")
                gr.Markdown("这些真实经营结果会帮助小满调整之后的补货建议。")
                fb_out = gr.HTML()
                evo_out = gr.HTML(render_evolution_html())

            # ── Tab 3 ──
            with gr.Tab("它学会了什么", id="learn"):
                gr.Markdown("## 它学会了什么")
                gr.Markdown("从每天真实经营结果里，慢慢记住这家店的规律。")
                exp_log = gr.HTML(learn_view.render_learn_page())
                btn_goto_feedback = gr.Button("去记录今天的经营情况 →", scale=1)
                with gr.Accordion("查看策略变化详情 · 当前策略参数与变化曲线", open=False):
                    with gr.Row(elem_classes=["dn-row"]):
                        sku_dd = gr.Dropdown(
                            choices=sku_choices,
                            value=default_sku,
                            label="选择商品", scale=3,
                        )
                        btn_evo_refresh = gr.Button("↻ 刷新", scale=1)
                    evo_status = gr.HTML(render_sku_strategy_html(default_sku))
                    evo_chart = gr.Plot(evolution_chart(default_sku))
                    gr.Markdown(
                        "**小满不会重新训练大模型**，而是根据实际经营结果持续校准补货策略参数。\n\n"
                        "· 发生**断货**时，在安全范围内适当**提高安全库存**；\n"
                        "· 发生**持续报损**时，则适当**降低备货强度**。\n\n"
                        "曲线只保留**真正导致策略变化的有效反馈**节点 —— 重复提交、被去重的反馈不会形成新的节点。"
                    )
                    evo_log = gr.HTML(render_evolution_html())

            # ── Tab 4 ──
            with gr.Tab("店里的老账本") as tab_mem:
                mem_html = gr.HTML(render_memory_html())
                btn_mem_refresh = gr.Button("刷新", scale=1)
                btn_goto_learn = gr.Button("看看小满学会了什么 →", scale=1)
                gr.Markdown("---")
                gr.HTML(render_analysis_html())

            # ── Tab 5 ──（FINAL 实验对比）
            with gr.Tab("实验验证", id="experiment"):
                gr.HTML(final_view.render_html())

            # ── Tab 6 ──
            with gr.Tab("项目说明"):
                gr.HTML(render_about_html())
                gr.Markdown("---")
                gr.Markdown("### 📊 离线评测对比\n"
                            "点击下方按钮，在**隔离临时库**上跑一轮快速评测（2 个随机种子 × 60 天），"
                            "不影响当前门店记忆，评委无需命令行即可看到对比柱状图。")
                with gr.Row(elem_classes=["dn-row"]):
                    btn_eval = gr.Button("🔬 生成评测对比图", scale=1)
                eval_plot = gr.Plot()

        # ── 事件绑定统一放在末尾，便于跨标签页联动 ──
        risk_inputs = [rain_cb, heat_cb, holiday_cb, supplier_cb]
        plan_inputs = [date_in, budget_in, rain_cb, heat_cb, holiday_cb, supplier_cb]
        btn_plan.click(do_plan, plan_inputs, [plan_top_out, plan_out])
        btn_goto_exp.click(lambda: gr.Tabs(selected="experiment"), None, main_tabs)
        btn_why.click(render_why_html, why_sku, why_out)
        why_sku.change(render_why_html, why_sku, why_out)
        btn_cmp.click(do_compare, plan_inputs, plan_out)
        btn_explain.click(do_explain, plan_inputs, explain_out)
        btn_agent.click(do_agent, agent_in, agent_out)
        # 勾选/取消风险事件时，自动重算并同步顶部提醒
        for cb in risk_inputs:
            cb.change(do_plan, plan_inputs, [plan_top_out, plan_out])
        btn_tpl.click(load_feedback_template, None, fb_df)
        btn_submit.click(
            submit_feedback_full, [fb_date, fb_df],
            [fb_out, evo_out, evo_status, evo_log, evo_chart, sku_dd, exp_log],
        )
        sku_dd.change(refresh_evolution, sku_dd, [evo_status, evo_chart, evo_log])
        btn_evo_refresh.click(refresh_evolution, sku_dd, [evo_status, evo_chart, evo_log])
        btn_goto_feedback.click(lambda: gr.Tabs(selected="feedback"), None, main_tabs)
        btn_mem_refresh.click(render_memory_html, None, mem_html)
        btn_goto_learn.click(lambda: gr.Tabs(selected="learn"), None, main_tabs)
        # 进入「店里的老账本」时自动刷新，确保刚沉淀的经营经验立即可见
        tab_mem.select(render_memory_html, None, mem_html)
        btn_eval.click(render_eval_figure, None, eval_plot)
        btn_sim.click(do_digital_store, sim_budget, [sim_out, sim_plot1, sim_plot2])

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
