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
from html import escape as _esc
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import agent, decision_basis, eval_core, events, evolution, feedback_view, final_view, forecast, home_view, learn_view, ledger_view, llm, memory, policy, risk, settings_store, settings_view, simulator, themes, ui_theme, why_view, about_view
    from core.config import (
        APP_NAME, APP_SUBTITLE, CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
        MEMORY_SAFETY_MAX_DELTA, SAFETY_FACTOR_MAX, SAFETY_FACTOR_MIN,
    )
else:
    from .core import agent, decision_basis, eval_core, events, evolution, feedback_view, final_view, forecast, home_view, learn_view, ledger_view, llm, memory, policy, risk, settings_store, settings_view, simulator, themes, ui_theme, why_view, about_view
    from .core.config import (
        APP_NAME, APP_SUBTITLE, CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
        MEMORY_SAFETY_MAX_DELTA, SAFETY_FACTOR_MAX, SAFETY_FACTOR_MIN,
    )

import gradio as gr

GR_MAJOR = int(gr.__version__.split(".")[0])

# 决策日：默认演示"今晚为明天备货"（CSV 经营数据末日后一天）
DEFAULT_PLAN_DATE = "2026-08-28"
LAST_DAY = "2026-08-27"

# 界面主题：启动时读本地设置（data/ui_settings.json，读不到回退默认主题）
ACTIVE_THEME = settings_store.current_theme()
NAV_BRAND = APP_NAME + " · 智能补货"

# 左侧边栏导航项：(显示名, gr.Tabs 里对应 Tab 的 id)
NAV_CHOICES = [
    ("今天该进什么货", "home"),
    ("为什么这样进", "why"),
    ("今天生意怎么样", "feedback"),
    ("它学会了什么", "learn"),
    ("店里的老账本", "ledger"),
    ("实验验证", "experiment"),
    ("项目说明", "about"),
    ("设置", "settings"),
]


def sidebar_brand_html(theme_id=None) -> str:
    """左侧栏顶部品牌区：应用名 + 当前主题（真实读取；换主题时一并刷新）。"""
    th = themes.get(theme_id if theme_id is not None else settings_store.current_theme())
    return ('<div class="xm-side-brand">'
            '<div class="xm-side-name">%s · 智能补货</div>'
            '<div class="xm-side-sub">当前主题：%s</div></div>'
            % (_esc(APP_NAME), _esc(th["name"])))

CSS = themes.theme_css(ACTIVE_THEME) + """
/* 应用级补充：组件样式统一在 core/ui_theme.py，颜色一律走 --xm-* token */
/* Direction A：外壳更宽、左右留 24px，主区吃满剩余宽度（不再窄列居中） */
.gradio-container { max-width: 1560px !important; padding-left: 24px !important; padding-right: 24px !important; }
/* Gradio 自己的 main 默认只有 960px，会把主区压成窄列 —— 放开它 */
.gradio-container main, .gradio-container .main { max-width: none !important; }
footer { display: none !important; }
.gradio-container footer { display: none !important; }
""" + home_view.HOME_CSS + why_view.WHY_CSS + feedback_view.FEEDBACK_CSS + learn_view.LEARN_CSS + ledger_view.LEDGER_CSS + about_view.ABOUT_CSS + settings_view.SETTINGS_CSS + ui_theme.THEME_CSS

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








def _hero(sub: str) -> str:
    """页面头部（v2）：应用名 + 副标题 + 一句话说明；颜色字号全部走 token。"""
    return ('<div class="xm-page"><div class="xm-h1">%s · %s</div>'
            '<div class="xm-sm" style="margin-top:6px">%s</div></div>'
            % (APP_NAME, APP_SUBTITLE, sub))


def render_plan_html(plan: dict) -> str:
    """「今天该进什么货」首页 — 委托 core.home_view（经营工作台，遵循 DESIGN.md）。"""
    return home_view.render_home_html(plan)


def render_why_html(sku: str) -> str:
    """「为什么这样进」页 —— 所选商品的真实 6 阶段决策链（只读决策结果，不改 order_qty）。"""
    plan = policy.build_plan(DEFAULT_PLAN_DATE, DEFAULT_BUDGET, policy.MODE_DIANNAO, persist=False)
    items = plan.get("items") or []
    if not items:
        return "<div class='xm-callout'>暂无商品数据。</div>"
    it = next((x for x in items if x["sku"] == sku), items[0])
    return why_view.render_why_page(it)




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
            d_html = "<span style='color:var(--xm-steel)'>一致</span>"
        elif delta > 0:
            d_html = f"<b style='color:var(--xm-error)'>小满多 {delta:.0f}</b>"
        else:
            d_html = f"<b style='color:var(--xm-success)'>小满少 {abs(delta):.0f}</b>"
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
        risk_html = ("<div class='xm-callout'><b>当前生效的风险事件</b>：%s。"
                     "两种算法均已按上述风险调整销量预测与补货数量。</div>" % risk_summary)

    return f"""
    {_hero(f"同一天 · 同一笔预算 {CURRENCY}{cmp['budget']:.0f} · 两种算法给出的不同答案")}
    {risk_html}
    <div class="xm-card">
      <div class="xm-h3" style="margin:0 0 8px">两种算法，两种活法</div>
      <table class="xm-table">
        <tr><th>商品</th><th>小满（惠民约束）</th><th>传统算法（纯利润）</th><th>差异</th></tr>
        {''.join(rows)}
      </table>
    </div>
    <div class="xm-card">
      <table class="xm-table">
        <tr><th>指标</th><th>小满</th><th>传统算法</th></tr>
        <tr><td>预计毛利</td>
            <td><b>{CURRENCY}{md['gross_margin']:.0f}</b></td>
            <td>{CURRENCY}{mb['gross_margin']:.0f}</td></tr>
        <tr><td>民生最低保障达标率</td>
            <td><b style="color:var(--xm-success)">{md['livelihood_secured_rate']:.1%}</b></td>
            <td><b style="color:var(--xm-steel)">{mb['livelihood_secured_rate']:.1%}</b></td></tr>
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
      <p style="color:var(--xm-steel);font-size:12px;margin:8px 0 0">
        注：缺货数量 = 补货周期内预期需求 − 补货后可用库存（不足部分求和）；
        缺货率 = 缺货数量 ÷ 补货周期内预期总需求；损耗金额仅统计保质期 ≤ 30 天的短保商品。
      </p>
    </div>
    <div class="xm-callout">
      <b>怎么读这张表：</b>传统算法按「单位资金毛利」从高到低分配预算，高毛利商品通常排在前面；
      在预算紧张时，纯利润策略可能优先压缩部分低毛利民生商品的补货量。<br>
      小满先用惠民约束把民生兜底量锁住（<b>至少备够 {LIVELIHOOD_MIN_COVER_DAYS:.0f} 天</b>），
      剩下才按利润分配。
    </div>
    <div class="xm-callout">
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
        return ("<div class='xm-callout'>日期格式不对，请填写类似 2026-08-28 的格式。</div>", "")
    budget = float(budget or DEFAULT_BUDGET)
    risks = _active_risks(rain, heat, holiday, supplier)
    plan = policy.build_plan(d, budget, policy.MODE_DIANNAO, persist=False, risks=risks)
    return (home_view.render_home_html(plan, 'top'),
            home_view.render_home_html(plan, 'rail'),
            home_view.render_home_html(plan, 'result'))


def do_compare(date_str: str, budget: float, rain: bool, heat: bool,
               holiday: bool, supplier: bool):
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        return "<div class='xm-callout'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
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
        return "<div class='xm-callout'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
    budget = float(budget or DEFAULT_BUDGET)
    risks = _active_risks(rain, heat, holiday, supplier)
    plan = policy.build_plan(d, budget, policy.MODE_DIANNAO, persist=False, risks=risks)
    text = llm.explain_plan(plan)
    html_text = text.replace("\n", "<br>")
    if llm.is_enabled():
        head = "大模型解读"
    else:
        head = "规则模板解读（未配置 LLM Key，配置后自动切换为 AI 讲解）"
    return f"<div class='xm-callout xm-callout-ok'><b>{head}</b><br><br>{html_text}</div>"


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
        return "<div class='xm-callout'>日期格式不对，请填写类似 2026-08-28 的格式。</div>"

    result = agent.plan_and_explain(plan_date, req["budget"], req["risks"])
    explanation = result["explanation"].replace("\n", "<br>")
    plan_html = render_plan_html(result["plan"])
    return f"""
    <div class="xm-card">
      <div class="xm-h3" style="margin:0 0 8px">Agent 的推理过程</div>
      <div class="xm-callout" style="margin:8px 0">{explanation}</div>
    </div>
    {plan_html}"""


def apply_theme(theme_id: str, sku: str = ""):
    """设置页「应用主题」：落盘 + 就地换肤（含图表重渲染）。

    不刷新页面：主题变量注入 <style> 后立即生效；选择写入 data/ui_settings.json，
    下次启动由 ACTIVE_THEME 直接读回。

    图表为什么要跟着重渲染：plotly 的底色/字色是**服务端渲染时**烘进图里的，
    改 CSS 变量不会影响已生成的图。所以换主题时一并重画「安全库存系数演进」曲线
    （按需生成的评测图 / 180 天仿真图在生成时就取当前主题，无需额外处理）。
    """
    tid = settings_store.set_theme(theme_id)["theme"]
    th = themes.get(tid)
    tag = themes.theme_style_tag(tid, brand=NAV_BRAND, theme_label=th["name"])
    try:  # 提示条失败不影响换肤
        gr.Info("已应用主题：%s" % th["name"])
    except Exception:
        pass
    return (tag, settings_view.render_status(tid), settings_view.render_env_panel(tid),
            sidebar_brand_html(tid), evolution_chart(sku or ""))


# 事件 → 徽标语气（替代旧 emoji 图标；DESIGN.md §5 明确禁用彩色 Emoji）
_EVENT_TONE = {
    "高温": "orange", "暴雨": "orange", "节假日": "neutral",
    "供应商D断供": "red", "正常": "green",
}


def _event_badge(event_type: str) -> str:
    """事件徽标：语气色 + 中文名，页面里不再出现 emoji 图标。"""
    tone = _EVENT_TONE.get(event_type, "neutral")
    label = event_type if event_type != "正常" else "普通日"
    return '<span class="xm-badge xm-badge-%s">%s</span>' % (tone, label)




def render_eval_figure():
    """在隔离临时库上跑一轮快速评测，返回 Plotly 对比图（不动在线记忆库）。"""
    import tempfile

    tmp_db = Path(tempfile.gettempdir()) / "diannao_eval_tmp.db"
    try:
        results = eval_core.run_eval(seeds=[42], days=eval_core.DAYS, db_path=tmp_db)
        fig = eval_core.build_figure(results, eval_core.DAYS, 1)
        fig.update_layout(**themes.plotly_layout(ACTIVE_THEME))
        return fig
    finally:
        try:
            tmp_db.unlink(missing_ok=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# 180 天数字小店长期实验（小满 vs 传统纯利润）
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
        d_color = "var(--xm-success)" if d_better else "var(--xm-ink)"
        b_color = "var(--xm-error)" if b_better else "var(--xm-steel)"
        return f"""
        <div style="min-width:216px">
          <div class="st-kv-k">{name}</div>
          <div style="font-size:20px;font-weight:600;color:{d_color};margin-top:2px">小满 {dv}{unit}</div>
          <div style="font-size:14px;color:{b_color}">传统 {bv}{unit}</div>
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
    <table class="xm-table">
      <tr><th>指标</th><th>小满 R³</th><th>传统纯利润</th><th>口径 / 公式</th></tr>
      <tr><td>累计毛利</td><td><b>{_fmt_money(d['cumulative_gross_margin'])}</b></td>
          <td>{_fmt_money(b['cumulative_gross_margin'])}</td>
          <td>Σ 实销×毛利额 − Σ 损耗×进价</td></tr>
      <tr><td>总体缺货率</td><td>{d['stockout_rate']:.2%}</td><td>{b['stockout_rate']:.2%}</td>
          <td>全部商品缺货件数 ÷ 全部商品真实需求件数</td></tr>
      <tr><td>民生最低保障达标率</td><td><b style="color:var(--xm-success)">{d['livelihood_secured_rate']:.1%}</b></td>
          <td>{b['livelihood_secured_rate']:.1%}</td>
          <td>180 天平均的每日「补货量 ≥ 民生最低保障量」达标比例</td></tr>
      <tr><td>民生商品实际缺货率</td><td><b style="color:var(--xm-success)">{d['livelihood_stockout_rate']:.2%}</b></td>
          <td>{b['livelihood_stockout_rate']:.2%}</td>
          <td>19 种民生商品缺货件数 ÷ 其真实需求件数</td></tr>
      <tr><td>民生商品实际缺货件数</td><td><b style="color:var(--xm-success)">{d['livelihood_stockout_qty']:,.0f}</b></td>
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
    <div class="xm-callout">
      仿真区间 <b>{d0} ~ {d1}</b>（{len(gt['day_list'])} 天 × {len(gt['products'])} 个 SKU）·
      每日进货预算 <b>{_fmt_money(budget)}</b> · 两种策略面对<b>完全相同</b>的需求序列、价格、交期、
      天气/节假日/断供事件，差别只在<b>补货决策策略</b>。
    </div>
    <div class="xm-card"><div style="display:flex;flex-wrap:wrap;gap:var(--xm-space-xl)">{cards}</div></div>
    <div class="xm-card">
      <div class="xm-h3" style="margin:0 0 8px">长期指标对照（全部由仿真日志真实计算）</div>
      {table}
    </div>
    <div class="xm-callout">
      <b>指标说明：</b><br>
      · <b>总体缺货率</b>：全部商品（50 SKU）未满足需求件数占其总需求件数的比例；<br>
      · <b>民生最低保障达标率</b>：补货决策满足民生商品最低保障库存约束的比例（计划层面），
      不代表经营过程中完全不会发生实际缺货；<br>
      · <b>民生商品实际缺货率</b>：19 种民生商品在真实经营中未被满足的需求件数
      占其总需求件数的比例（结算层面）。
    </div>
    <div class="xm-callout">
      <b>客观结论：</b>{simulator.conclusion_text(results)}
    </div>
    <div class="xm-callout">
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
    # 图表套用当前主题（simulator 只负责数据，样式在这里统一，深色主题下不再是白底）
    lay = themes.plotly_layout(ACTIVE_THEME)
    ink = themes.palette(ACTIVE_THEME)["ink"]
    fig1 = simulator.build_cumulative_figure(results)
    fig2 = simulator.build_rates_figure(results)
    for fig in (fig1, fig2):
        fig.update_layout(**lay)
        fig.update_layout(title_font_color=ink)   # 覆盖 simulator 里写死的标题色
    return html, fig1, fig2


def load_feedback_template(day_str: str = LAST_DAY):
    """载入某一天已有的历史经营数据作为录入初值，省得店主从零填。

    数据来源是 memory 里的历史经营记录（sales 表），**不是 POS 自动采集**：
    实际销量有历史值可直接载入；断货/损耗两列在历史记录中恒为 0，
    仍必须由店主按当天实际情况填写。day_str 只用于校验，不改变任何数据源。
    """
    day = str(day_str or LAST_DAY).strip()
    try:
        date.fromisoformat(day)
    except Exception:
        day = LAST_DAY
    products = memory.get_products()
    rows = []
    for p in products:
        recs = memory.get_sales_range(p["sku"], day, day)
        r = recs[0] if recs else None
        rows.append([
            p["name"],
            int(round(r["qty_sold"])) if r else 0,
            int(round(r["qty_stockout"])) if r else 0,
            int(round(r["qty_spoilage"])) if r else 0,
            p["sku"],
        ])
    df = pd.DataFrame(rows, columns=feedback_view.FB_COLUMNS)
    return df, feedback_view.render_table_hint(day)


def submit_feedback(day_str: str, df: pd.DataFrame):
    if df is None or len(df) == 0:
        return feedback_view.render_empty(), render_evolution_html()
    try:
        d = str(day_str).strip()
        date.fromisoformat(d)
    except Exception:
        return feedback_view.render_invalid("日期格式不对，请填 2026-08-27 这样的日期。"), render_evolution_html()

    feedback = []
    for _, row in df.iterrows():
        try:
            sold = float(row[feedback_view.COL_SOLD] or 0)
            stockout = float(row[feedback_view.COL_STOCKOUT] or 0)
            spoilage = float(row[feedback_view.COL_SPOILAGE] or 0)
        except (TypeError, ValueError):
            continue
        # 输入限制：必须为大于等于 0 的数字，不能出现负数（NaN 也会在此被拦截）
        if not (sold >= 0 and stockout >= 0 and spoilage >= 0):
            return (feedback_view.render_invalid(
                        "%s / %s / %s 都必须填大于等于 0 的数字，不能出现负数，请检查后再保存。"
                        % (feedback_view.COL_SOLD, feedback_view.COL_STOCKOUT,
                           feedback_view.COL_SPOILAGE)),
                    render_evolution_html())
        feedback.append({
            "sku": str(row[feedback_view.COL_SKU]).strip(),
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
    return feedback_view.render_result(result, d), render_evolution_html()


def render_evolution_html() -> str:
    logs = memory.get_evolution_log(limit=40)
    if not logs:
        return ("<div class='xm-callout'>还没有学习记录。到「今天生意怎么样」录一次反馈，"
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
        tag = ('<span class="xm-badge xm-badge-red">断货</span>' if lg["trigger"] == "断货"
               else '<span class="xm-badge xm-badge-orange">积压损耗</span>')
        rows.append("<tr><td>%s</td><td>%s%s</td><td>%s</td><td>%s</td>"
                    "<td><b style=\"color:var(--xm-error)\">%s %s → %s</b></td></tr>"
                    % (lg["day"], star, nm, tag, param_cn, arrow,
                       "%.3f" % (lg["old_value"] or 0), "%.3f" % (lg["new_value"] or 0)))

    n_up = sum(1 for lg in logs
               if (lg["new_value"] or 0) > (lg["old_value"] or 0))
    n_down = len(logs) - n_up

    return ('<div class="xm-cap" style="margin-bottom:8px">'
            '共 %d 次有效调整（%d 次为避免断货上调，%d 次为减少积压下调）。</div>'
            '<table class="xm-table">'
            '<tr><th>日期</th><th>商品</th><th>触发原因</th><th>调整了什么</th><th>变化</th></tr>'
            '%s</table>' % (len(logs), n_up, n_down, ''.join(rows)))


def _scene_label(event_type) -> str:
    """把事件类型翻译成页面上的场景名（普通日/高温/暴雨/节假日/供应商D断供）。"""
    return "普通日" if not event_type or event_type == "正常" else event_type


def render_sku_strategy_html(sku: str) -> str:
    """选中商品的「当前策略状态」：基础/当前安全系数、有效学习次数、最近一次调整。"""
    products = {p["sku"]: p for p in memory.get_products()}
    p = products.get(sku) if sku else None
    if not p:
        return "<div class='xm-callout'>请先在上方选择一个商品。</div>"

    pol = memory.get_policy(sku) or {}
    base = float(pol.get("safety_factor", 0.15))
    details = memory.evolution_details(sku)
    current = float(details[-1]["new_value"]) if details else base
    n_learn = len(details)
    star = "★ " if p.get("is_livelihood") else ""

    # 边界提示：达到系统硬上下限，或单商品累计校准 ±0.06（自适应边界）
    boundary = ""
    if current >= SAFETY_FACTOR_MAX - 1e-9:
        boundary = ('<div class="xm-brief"><span class="xm-badge xm-badge-red">已达上限</span>'
                    '<div class="xm-brief-sub">该商品已达到策略安全边界（系统上限），'
                    '本次不再继续调整。</div></div>')
    elif current <= SAFETY_FACTOR_MIN + 1e-9:
        boundary = ('<div class="xm-brief"><span class="xm-badge xm-badge-red">已达下限</span>'
                    '<div class="xm-brief-sub">该商品已达到策略安全边界（系统下限），'
                    '本次不再继续调整。</div></div>')
    elif abs(current - base) >= MEMORY_SAFETY_MAX_DELTA - 1e-9:
        boundary = ('<div class="xm-brief"><span class="xm-badge xm-badge-red">累计校准到顶</span>'
                    '<div class="xm-brief-sub">该商品累计校准已达 ±%.2f 的自适应边界，'
                    '后续同类反馈不再继续调整安全系数。</div></div>'
                    % MEMORY_SAFETY_MAX_DELTA)

    if not details:
        last_reason = "—"
        change_line = ('<span class="xm-cap">暂未形成有效调整 —— '
                       '提交一次真正触发阈值的经营反馈后，这里会出现变化。</span>')
    else:
        last = details[-1]
        signal = "发生断货" if last["trigger"] == "断货" else "发生报损"
        last_reason = "%s %s%s" % (last["day"], _scene_label(last["event_type"]), signal)
        change_line = ('<b style="color:var(--xm-error)">%s → %s</b>'
                       '<span class="xm-cap" style="margin-left:8px">（累计 %d 次有效调整）</span>'
                       % ("%.2f" % base, "%.2f" % current, n_learn))

    return ('<div class="xm-card">'
            '<div class="xm-h3" style="margin:0 0 12px">当前策略状态 · %s%s</div>'
            '<div style="display:flex;gap:28px;flex-wrap:wrap;margin-bottom:12px">'
            '<div><div class="xm-num">%.2f</div><div class="xm-cap">基础安全库存系数</div></div>'
            '<div><div class="xm-num" style="color:var(--xm-error)">%.2f</div>'
            '<div class="xm-cap">当前安全库存系数</div></div>'
            '<div><div class="xm-num">%d</div><div class="xm-cap">累计有效学习</div></div>'
            '</div>'
            '<div class="xm-sm" style="line-height:1.9">'
            '<div><b>最近一次调整原因：</b>%s</div>'
            '<div><b>策略变化：</b>%s</div>'
            '</div>%s</div>'
            % (star, p["name"], base, current, n_learn, last_reason, change_line, boundary))


def evolution_chart(sku: str):
    """画某商品的安全库存系数演进曲线（只取真实有效的调整记录，重复/被去重不算节点）。"""
    products = {p["sku"]: p for p in memory.get_products()}
    p = products.get(sku, {})
    nm = p.get("name", sku or "未选择商品")
    details = memory.evolution_details(sku) if sku else []

    # plotly 不认 CSS 变量，必须给当前主题的具体色值；深色主题下也不该是白底黑字
    plt = themes.plotly_layout(ACTIVE_THEME)
    P = themes.palette(ACTIVE_THEME)
    fig = go.Figure()

    if not details:
        fig.add_annotation(text=f"{nm} 还没有有效的策略调整记录", showarrow=False,
                           font=dict(size=16, color=P["steel"]))
        lay = dict(plt)
        lay.update({
            "height": 360,
            "title": dict(text=f"{nm} · 安全库存系数演进",
                          font=dict(size=17, color=P["ink"])),
        })
        fig.update_layout(**lay)
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
        line=dict(color=P["error"], width=3),
        marker=dict(size=11, color=P["error"], line=dict(color=P["canvas"], width=1.5)),
        connectgaps=True,
        hovertemplate="%{text}<extra></extra>",
    ))

    # 横轴：0 = 初始值，其后标注每次有效调整的日期（MM-DD）
    tick_vals = list(range(len(xs)))
    tick_text = ["初始"] + [str(d["day"])[5:] for d in details]

    lay = dict(plt)
    lay.update({
        "height": 380,
        "title": dict(text=f"{nm} · 安全库存系数随经营反馈的变化",
                      font=dict(size=17, color=P["ink"])),
        "xaxis": dict(
            plt["xaxis"],
            title=dict(text="经营反馈（0 = 初始值，其后为每次有效调整的日期）",
                       font=dict(size=12, color=P["slate"])),
            tickvals=tick_vals, ticktext=tick_text,
        ),
        "yaxis": dict(
            plt["yaxis"],
            title=dict(text="安全库存系数", font=dict(color=P["error"])),
            tickfont=dict(color=P["error"]),
        ),
        "margin": dict(l=60, r=30, t=70, b=70),
    })
    fig.update_layout(**lay)
    return fig


def submit_feedback_full(day_str: str, df: pd.DataFrame):
    """
    提交反馈的完整联动：本页展示保存结果 + 自动刷新「它学会了什么」页，
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
    return (body, render_sku_strategy_html(sku), evo,
            evolution_chart(sku), sku, learn_view.render_learn_page())


def refresh_evolution(sku: str):
    """刷新自进化页：当前策略状态 + 参数演进曲线 + 调整日志。"""
    return render_sku_strategy_html(sku or ""), evolution_chart(sku or ""), render_evolution_html()


def render_memory_html() -> str:
    """「店里的老账本」— 委托 core.ledger_view（经营档案，遵循 DESIGN.md）。"""
    return ledger_view.render_ledger()




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

        # 主题变量：<style> 注入（换主题只重渲染这一个隐藏组件，页面立即变）
        theme_style = gr.HTML(
            themes.theme_style_tag(ACTIVE_THEME, brand=NAV_BRAND,
                                   theme_label=themes.get(ACTIVE_THEME)["name"]),
            elem_classes=["xm-hidden"])

        # 左侧边栏：品牌 + 竖排导航（真正的 Tab 切换由 nav_radio 驱动）
        with gr.Row(elem_id="xm-shell"):
            with gr.Column(scale=0, min_width=236, elem_id="xm-side"):
                side_brand = gr.HTML(sidebar_brand_html(ACTIVE_THEME))
                nav_radio = gr.Radio(choices=NAV_CHOICES, value="home", show_label=False,
                                     container=False, elem_id="xm-nav")

            with gr.Column(scale=1, min_width=0, elem_id="xm-main"):
                with gr.Tabs(elem_id="main-nav") as main_tabs:
                    # ── Tab 1 ──
                    # ── Tab 1 ── 今天该进什么货（Direction A：KPI 条整宽 + 2/3 主区 + 1/3 侧栏）
                    with gr.Tab("今天该进什么货", id="home"):
                        _init_plan = policy.build_plan(DEFAULT_PLAN_DATE, DEFAULT_BUDGET,
                                                       policy.MODE_DIANNAO, persist=False)
                        plan_top_out = gr.HTML(home_view.render_home_html(_init_plan, 'top'))
                        with gr.Row(elem_id="xm-home-split", elem_classes=["xm-split"]):
                            with gr.Column(scale=2, min_width=0, elem_classes=["xm-main-col"]):
                                plan_out = gr.HTML(home_view.render_home_html(_init_plan, 'result'))
                                with gr.Row(elem_classes=["xm-row"]):
                                    btn_explain = gr.Button("用大白话解释", scale=1)
                                    btn_goto_exp = gr.Button("查看实验验证 ›", scale=1)
                                explain_out = gr.HTML()
                                with gr.Group(elem_classes=["xm-card", "xm-sec"]):
                                    gr.HTML("<div class='xm-h3'>Agent 智能补货</div>"
                                            "<div class='xm-hint'>直接说需求，例如「预算600元，明天高温」；"
                                            "Agent 会读历史数据 → 找历史事件 → 分析影响 → 出方案并解释。</div>")
                                    agent_in = gr.Textbox(label="你的需求", lines=2,
                                                          placeholder="例如：预算600元，明天高温，帮我算算")
                                    btn_agent = gr.Button("让 Agent 来算", variant="primary")
                                    agent_out = gr.HTML()
                            with gr.Column(scale=1, min_width=280, elem_classes=["xm-rail"]):
                                rail_out = gr.HTML(home_view.render_home_html(_init_plan, 'rail'))
                                with gr.Group(elem_classes=["xm-card"]):
                                    gr.HTML("<div class='xm-h3'>明天按什么情况进货</div>"
                                            "<div class='xm-hint'>勾选后会纳入销量预计与补货计算；"
                                            "不勾选则按正常情况算。</div>")
                                    with gr.Group(elem_id="xm-risk-checks", elem_classes=["xm-risk-checks"]):
                                        rain_cb = gr.Checkbox(value=False, label="暴雨")
                                        heat_cb = gr.Checkbox(value=False, label="高温")
                                        holiday_cb = gr.Checkbox(value=False, label="节假日")
                                        supplier_cb = gr.Checkbox(value=False, label="供应商断货")
                                    date_in = gr.Textbox(value=DEFAULT_PLAN_DATE, label="目标经营日",
                                                         info="为这一天的经营备货，默认=明天")
                                    budget_in = gr.Number(value=DEFAULT_BUDGET, label="这次最多花多少（元）")
                                    with gr.Row(elem_classes=["xm-row"]):
                                        btn_plan = gr.Button("重新生成建议", variant="primary", scale=1)
                                    with gr.Row(elem_classes=["xm-row"]):
                                        btn_cmp = gr.Button("与传统算法对比", scale=1)
                        with gr.Accordion('高级实验工具 · 180 天长期仿真（现场无需运行）', open=False):
                            with gr.Row(elem_classes=["xm-row"]):
                                sim_budget = gr.Number(value=simulator.DEFAULT_SIM_BUDGET,
                                                       label="每日进货预算（元）", scale=2,
                                                       info="默认 ¥1800，两种策略使用同一预算")
                                btn_sim = gr.Button("运行 180 天仿真", variant="primary", scale=1)
                            gr.Markdown("约需 2 分钟（其中完整小满每次约 100 秒，传统算法约 20 秒）。"
                                        "完整消融实验请运行 `python run_digital_store.py`。")
                            sim_out = gr.HTML()
                            with gr.Row():
                                sim_plot1 = gr.Plot(scale=1)
                                sim_plot2 = gr.Plot(scale=1)

                    # ── Tab 2 ── 为什么这样进
                    with gr.Tab("为什么这样进", id="why"):
                        gr.HTML(why_view.render_head())
                        with gr.Row(elem_classes=["xm-row"]):
                            why_sku = gr.Dropdown(choices=sku_choices, value=default_sku, label="正在查看", scale=3)
                            btn_why = gr.Button("查看", variant="primary", scale=1)
                        why_out = gr.HTML(render_why_html(default_sku))

                    # ── Tab 3 ──
                    with gr.Tab("今天生意怎么样", id="feedback"):
                        gr.HTML(feedback_view.render_head())
                        with gr.Group(elem_classes=["xm-flow"]):
                            gr.HTML('<div class="xm-sec"><div class="xm-sec-title">经营日期</div></div>')
                            with gr.Group(elem_classes=["fb-date"]):
                                fb_date = gr.Textbox(value=LAST_DAY, label="经营日期",
                                                     info="已卖完货的那一天，如 2026-08-27")
                                gr.HTML(feedback_view.render_date_hint(LAST_DAY))
                            # 次级操作：载入历史初值，不与保存抢主视觉
                            btn_tpl = gr.Button("载入实际数据", variant="secondary", scale=1)

                            gr.HTML('<div class="xm-sec"><div class="xm-sec-title">今日经营记录</div></div>')
                            _fb_init_df, _fb_init_hint = load_feedback_template(LAST_DAY)
                            fb_hint = gr.HTML(_fb_init_hint)
                            fb_df = gr.Dataframe(
                                value=_fb_init_df,
                                headers=feedback_view.FB_COLUMNS,
                                datatype=feedback_view.FB_DATATYPES,
                                interactive=True, wrap=True, row_count=(16, "fixed"),
                                elem_classes=["fb-table"],
                            )
                            # 主操作：保存独占一行
                            btn_submit = gr.Button("保存今天的经营情况", variant="primary")
                        fb_out = gr.HTML()

                    # ── Tab 3 ──
                    with gr.Tab("它学会了什么", id="learn"):
                        gr.HTML(learn_view.render_head())
                        exp_log = gr.HTML(learn_view.render_learn_page())
                        btn_goto_feedback = gr.Button("去记录经营情况 →", scale=1)
                        with gr.Accordion("查看策略变化详情 · 当前策略参数与变化曲线", open=False):
                            with gr.Row(elem_classes=["xm-row"]):
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
                    with gr.Tab("店里的老账本", id="ledger") as tab_mem:
                        mem_html = gr.HTML(render_memory_html())
                        btn_mem_refresh = gr.Button("刷新", scale=1)
                        btn_goto_learn = gr.Button("看看小满学会了什么 →", scale=1)

                    # ── Tab 5 ──（FINAL 实验对比）
                    with gr.Tab("实验验证", id="experiment"):
                        gr.HTML(final_view.render_html())

                    # ── Tab 6 ──
                    with gr.Tab("项目说明", id="about"):
                        gr.HTML(render_about_html())
                        gr.HTML("<div class='xm-sec' style='margin-top:var(--xm-space-lg)'>"
                                "<div class='xm-sec-title'>离线评测对比</div>"
                                "<div class='xm-hint'>点击下方按钮，在<b>隔离临时库</b>上跑一轮快速评测"
                                "（60 天窗口），不影响当前门店记忆。</div></div>")
                        with gr.Row(elem_classes=["xm-row"]):
                            btn_eval = gr.Button("生成评测对比图", scale=1)
                        eval_plot = gr.Plot()

                    # ── Tab 7 · 设置（左侧边栏新栏目）──
                    with gr.Tab("设置", id="settings"):
                        gr.HTML(settings_view.PAGE_HEAD())
                        gr.HTML(settings_view.SECTION_HEAD())
                        # 主题选择器：Radio 本体，靠 settings_view 的 CSS 渲染成卡片网格
                        # （点卡片 = 点 radio，状态只有这一份；不要另做装饰性卡片副本）
                        theme_radio = gr.Radio(
                            choices=settings_view.theme_choices(),
                            value=ACTIVE_THEME, label="应用主题",
                            info="点卡片或上面的选项都能换主题，立即生效",
                            elem_id="st-theme-radio", container=False, interactive=True)
                        theme_status = gr.HTML(settings_view.render_status(ACTIVE_THEME))
                        env_panel = gr.HTML(settings_view.render_env_panel(ACTIVE_THEME))

        # ── 事件绑定统一放在末尾，便于跨标签页联动 ──
        risk_inputs = [rain_cb, heat_cb, holiday_cb, supplier_cb]
        plan_inputs = [date_in, budget_in, rain_cb, heat_cb, holiday_cb, supplier_cb]
        btn_plan.click(do_plan, plan_inputs, [plan_top_out, rail_out, plan_out])
        # 左侧边栏导航 ↔ 内容面板：Radio 选中即切 Tab；跨页跳转按钮同时回写导航高亮
        nav_radio.change(lambda v: gr.Tabs(selected=v), nav_radio, main_tabs)
        btn_goto_exp.click(lambda: (gr.Tabs(selected="experiment"), gr.Radio(value="experiment")),
                           None, [main_tabs, nav_radio])
        btn_why.click(render_why_html, why_sku, why_out)
        why_sku.change(render_why_html, why_sku, why_out)
        btn_cmp.click(do_compare, plan_inputs, plan_out)
        btn_explain.click(do_explain, plan_inputs, explain_out)
        btn_agent.click(do_agent, agent_in, agent_out)
        # 勾选/取消风险事件时，自动重算并同步顶部提醒
        for cb in risk_inputs:
            cb.change(do_plan, plan_inputs, [plan_top_out, rail_out, plan_out])
        btn_tpl.click(lambda d: load_feedback_template(d), fb_date, [fb_df, fb_hint])
        btn_submit.click(
            submit_feedback_full, [fb_date, fb_df],
            [fb_out, evo_status, evo_log, evo_chart, sku_dd, exp_log],
        )
        sku_dd.change(refresh_evolution, sku_dd, [evo_status, evo_chart, evo_log])
        btn_evo_refresh.click(refresh_evolution, sku_dd, [evo_status, evo_chart, evo_log])
        btn_goto_feedback.click(lambda: (gr.Tabs(selected="feedback"), gr.Radio(value="feedback")),
                                None, [main_tabs, nav_radio])
        btn_mem_refresh.click(render_memory_html, None, mem_html)
        btn_goto_learn.click(lambda: (gr.Tabs(selected="learn"), gr.Radio(value="learn")),
                             None, [main_tabs, nav_radio])
        # 进入「店里的老账本」时自动刷新，确保刚沉淀的经营经验立即可见
        tab_mem.select(render_memory_html, None, mem_html)
        btn_eval.click(render_eval_figure, None, eval_plot)
        btn_sim.click(do_digital_store, sim_budget, [sim_out, sim_plot1, sim_plot2])
        # 设置：应用主题（就地换肤 + 落盘，不刷新页面）
        theme_radio.change(apply_theme, [theme_radio, sku_dd],
                           [theme_style, theme_status, env_panel, side_brand, evo_chart])

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
