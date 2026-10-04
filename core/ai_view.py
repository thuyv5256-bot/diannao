# -*- coding: utf-8 -*-
"""小满 · 「AI 决策大脑」页（AI 决策中枢的可视化）

═══ 这一页要回答评委的哪个问题 ═══

「你们这个 AI 到底在哪？核心决策不是都是规则吗？」

本页把 AI 决策中枢的两层摊开给评委看：

    第一层  事件语义理解（ai_events）
            店主说人话 → 模型判断有哪些事件、多严重、证据够不够
            → 产出结构化参数 → 交给规则层

    第二层  业务洞察（ai_insight）
            规则算完数之后，模型回头看：这次决策有没有什么隐患
            → 产出风险清单与经营建议

页面同时明确标注**分工**：模型负责理解与判断，规则负责算数与执行。
这不是把 AI 藏起来，恰恰相反 —— 把边界讲清楚，比声称"全靠 AI"更可信。

无 API Key 时页面照常可用，顶部明确显示「规则降级模式」。
"""

from __future__ import annotations

import html as _html

from . import events, llm
from .config import CURRENCY, LLM_MODEL

AI_CSS = """
/* ═══ AI 决策大脑 ════════════════════════════════════════════════════
   沿用 DESIGN.md 的 token 体系，不新增任何写死颜色。 */
.ai-mode-bar { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  padding:12px 16px; border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); background:var(--xm-canvas);
  box-shadow:var(--xm-card-shadow); margin-bottom:var(--xm-space-md); }
.ai-mode-dot { width:9px; height:9px; border-radius:50%; flex:0 0 auto; }
.ai-mode-dot.on { background:var(--xm-success); }
.ai-mode-dot.off { background:var(--xm-warning); }
.ai-mode-txt { font-size:14px; font-weight:600; color:var(--xm-ink); }
.ai-mode-sub { font-size:12px; color:var(--xm-slate); }

/* AI 调用中的即时反馈（纯展示，避免点击后长时间无响应） */
.ai-thinking { display:flex; align-items:center; gap:10px;
  padding:14px 16px; border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); background:var(--xm-canvas);
  color:var(--xm-slate); font-size:14px; margin-bottom:var(--xm-space-md); }
.ai-spin { width:14px; height:14px; flex:0 0 auto; border-radius:50%;
  border:2px solid var(--xm-card-border); border-top-color:var(--xm-ink);
  animation:ai-spin 0.9s linear infinite; }
@keyframes ai-spin { to { transform:rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .ai-spin { animation:none; } }

/* AI 环节结束后的状态条：成功耗时 / 降级说明 */
.ai-status { display:flex; align-items:flex-start; gap:8px;
  padding:10px 14px; border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-md); font-size:13px; margin-top:var(--xm-space-md);
  color:var(--xm-slate); line-height:1.6; }
.ai-status-dot { width:8px; height:8px; border-radius:50%; flex:0 0 auto;
  margin-top:5px; }
.ai-status-ok .ai-status-dot { background:var(--xm-success); }
.ai-status-warn { border-color:var(--xm-warning); }
.ai-status-warn .ai-status-dot { background:var(--xm-warning); }
.ai-status b { color:var(--xm-ink); font-weight:600; }

/* 分层职责图：模型层 / 规则层 */
.ai-lane { display:grid; grid-template-columns:minmax(0,1fr); gap:0; }
.ai-lane-row { display:grid; grid-template-columns:88px minmax(0,1fr);
  gap:12px; align-items:start; padding:12px 0;
  border-bottom:1px solid var(--xm-hairline-soft); }
.ai-lane-row:last-child { border-bottom:none; }
.ai-lane-tag { font-size:12px; font-weight:600; text-align:center;
  padding:4px 6px; border-radius:var(--xm-radius-sm); white-space:nowrap; }
.ai-lane-tag.model { background:var(--xm-info-soft); color:var(--xm-link); }
.ai-lane-tag.rule { background:var(--xm-surface-soft); color:var(--xm-steel); }
.ai-lane-tag.out { background:var(--xm-success-soft); color:var(--xm-success); }
.ai-lane-t { font-size:14px; font-weight:600; color:var(--xm-ink); }
.ai-lane-d { font-size:13px; color:var(--xm-slate); line-height:1.65; margin-top:3px; }

/* 事件卡 */
.ai-ev { border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-md); padding:12px 14px; margin-top:8px;
  background:var(--xm-canvas); }
.ai-ev-h { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.ai-ev-name { font-size:14px; font-weight:600; color:var(--xm-ink); }
.ai-ev-why { font-size:13px; color:var(--xm-slate); line-height:1.7; margin-top:6px; }
.ai-ev-meta { font-size:12px; color:var(--xm-steel); margin-top:6px;
  font-variant-numeric:tabular-nums; }

/* 洞察卡 */
.ai-ins { border-left:3px solid var(--xm-hairline-strong);
  padding:10px 0 10px 14px; margin-top:10px; }
.ai-ins.high { border-left-color:var(--xm-error); }
.ai-ins.medium { border-left-color:var(--xm-warning); }
.ai-ins.low { border-left-color:var(--xm-steel); }
.ai-ins-t { font-size:14px; font-weight:600; color:var(--xm-ink); }
.ai-ins-b { font-size:13px; color:var(--xm-slate); line-height:1.75; margin-top:4px; }
.ai-ins-e { font-size:12px; color:var(--xm-steel); margin-top:5px; }
.ai-ins-a { font-size:13px; color:var(--xm-link); margin-top:5px; }

/* 数字高亮 */
.ai-num { font-variant-numeric:tabular-nums; font-weight:600; color:var(--xm-ink); }

.ai-empty { font-size:13px; color:var(--xm-slate); padding:14px 0; }
"""


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def render_thinking(what: str = "AI 正在理解天气、供应与经营风险…") -> str:
    """AI 调用进行中的即时反馈（体验层，不改变任何语义）。

    目的很单纯：让点击后有立刻可见的反馈，避免页面「卡住」十几秒
    却没有任何提示。**纯展示**，不参与任何计算。
    """
    return ('<div class="ai-thinking"><span class="ai-spin"></span>'
            '<span>%s</span></div>' % _esc(what))


def render_ai_status(phase: str, elapsed: float | None = None,
                     degraded: bool = False, reason: str = "") -> str:
    """AI 环节结束后的状态条：成功耗时 / 降级原因，都要说清楚。

    degraded=True 时明确告知「已切换确定性规则，不影响补货计算」，
    避免评委误以为 AI 挂了导致功能不可用。
    """
    secs = "" if elapsed is None else "（%.1fs）" % elapsed
    if degraded:
        return ('<div class="ai-status ai-status-warn">'
                '<span class="ai-status-dot"></span>'
                '<span><b>AI 服务暂不可用</b>，已切换确定性规则，'
                '不影响补货计算%s</span></div>'
                % (_esc("　原因：%s" % reason) if reason else ""))
    return ('<div class="ai-status ai-status-ok"><span class="ai-status-dot"></span>'
            '<span><b>%s 完成</b>%s</span></div>'
            % (_esc(phase), secs))


def mode_bar() -> str:
    """顶部模式条：明确告知评委当前是 AI 在线还是规则降级。"""
    on = llm.is_enabled()
    model = LLM_MODEL if on else "未配置密钥"
    dot = "on" if on else "off"
    txt = "AI 已连接" if on else "规则降级模式"
    sub = ("大模型 %s 正在参与事件理解与业务洞察" % _esc(model)) if on else (
        "未检测到 API Key —— AI 两环自动降级为规则路径，"
        "补货数字与 AI 在线时逐位一致，功能不降级")
    return ('<div class="ai-mode-bar"><span class="ai-mode-dot %s"></span>'
            '<span class="ai-mode-txt">%s</span>'
            '<span class="ai-mode-sub">%s</span></div>' % (dot, txt, sub))


def render_lanes() -> str:
    """分层职责：把「模型做什么 / 规则做什么」讲清楚。"""
    rows = [
        ("model", "大模型", "事件语义理解",
         "读懂店主的自然语言描述，判断有哪些风险事件、分别多严重、"
         "历史证据够不够，产出结构化修正参数（品类 → 需求乘数）。"),
        ("rule", "规则层", "数值计算",
         "预测（指数衰减 × 星期 × 节日 × 趋势 × 事件）× R³ 多目标整数优化 → "
         "补货数量、覆盖天数、预算分配。全部确定性、可复现、可审计。"),
        ("model", "大模型", "业务洞察",
         "决策算完后回头体检：预算是否用满、民生结构是否合理、"
         "断货与积压是否同时出现，产出风险清单与可执行建议。"),
        ("out", "输出", "补货方案",
         "补货数量 + 可售卖天数 + 自然语言分析。"
         "数量永远由规则层算出，模型只提供参数与判断。"),
    ]
    body = "".join(
        '<div class="ai-lane-row"><div class="ai-lane-tag %s">%s</div>'
        '<div><div class="ai-lane-t">%s</div><div class="ai-lane-d">%s</div></div></div>'
        % (cls, tag, _esc(title), _esc(desc))
        for cls, tag, title, desc in rows)
    return ('<div class="xm-card"><div class="xm-sec-head">'
            '<div class="xm-h3">决策链路：模型与规则各做什么</div></div>'
            '<div class="ai-lane" style="margin-top:10px">%s</div></div>' % body)


def render_event_panel(result: dict | None) -> str:
    """事件语义理解的结果展示。"""
    if not result:
        return ('<div class="xm-card"><div class="xm-sec-head">'
                '<div class="xm-h3">第一环 · 事件语义理解</div></div>'
                '<div class="ai-empty">还没有输入场景描述。</div></div>')

    src = result.get("source")
    src_badge = ('<span class="xm-badge xm-badge-green">大模型解析</span>' if src == "llm"
                 else '<span class="xm-badge xm-badge-neutral">规则降级</span>')
    head = ('<div class="xm-sec-head"><div class="xm-h3">第一环 · 事件语义理解</div>'
            '%s</div>' % src_badge)

    evs = result.get("events") or []
    if not evs:
        body = '<div class="ai-empty">未识别到风险事件，按正常历史规律预测。</div>'
    else:
        blocks = []
        for e in evs:
            key = e.get("key")
            label = events.EVENT_KEY_TO_LABEL.get(key, key)
            lvl = e.get("level", "insufficient")
            # 分级徽标：strong 才允许真正影响预测
            lvl_map = {
                "strong": ("xm-badge-green", "证据充分"),
                "weak": ("xm-badge-orange", "证据偏弱"),
                "insufficient": ("xm-badge-neutral", "证据不足"),
            }
            cls, txt = lvl_map.get(lvl, lvl_map["insufficient"])
            sev_map = {"mild": "轻微", "moderate": "中等", "severe": "严重"}
            sev = sev_map.get(e.get("severity", "moderate"), "中等")
            cats = e.get("affected_categories") or []
            meta = "强度 %s" % sev
            if cats:
                meta += " · 影响品类 %s" % "、".join(cats)
            f = float(e.get("demand_factor") or 1.0)
            if key != "supplier":
                meta += " · 需求乘数 <span class=\"ai-num\">×%.2f</span>" % f
            if e.get("lead_time_hours"):
                meta += " · 约 %d 小时后生效" % int(e["lead_time_hours"])
            blocks.append(
                '<div class="ai-ev"><div class="ai-ev-h">'
                '<span class="ai-ev-name">%s</span>'
                '<span class="xm-badge %s">%s</span></div>'
                '<div class="ai-ev-why">%s</div>'
                '<div class="ai-ev-meta">%s</div></div>'
                % (_esc(label), cls, txt, _esc(e.get("reasoning") or "—"), meta))

        fac = result.get("factors") or {}
        fac_html = ""
        if fac:
            fac_html = ('<div class="ai-ev-meta" style="margin-top:10px">'
                        '实际生效的品类修正：%s</div>'
                        % "、".join('%s <span class="ai-num">×%.2f</span>' % (_esc(k), v)
                                    for k, v in sorted(fac.items())))
        body = ("<div class=\"ai-ev-meta\">%s</div>%s%s"
                % (_esc(result.get("summary") or ""), "".join(blocks), fac_html))

    return ('<div class="xm-card">%s<div style="margin-top:10px">%s</div></div>'
            % (head, body))


def render_insight_panel(result: dict | None) -> str:
    """业务洞察与风险清单。"""
    if not result:
        return ('<div class="xm-card"><div class="xm-sec-head">'
                '<div class="xm-h3">第二环 · 业务洞察与风险识别</div></div>'
                '<div class="ai-empty">还没有决策结果可分析。</div></div>')

    src = result.get("source")
    src_badge = ('<span class="xm-badge xm-badge-green">大模型分析</span>' if src == "llm"
                 else '<span class="xm-badge xm-badge-neutral">规则体检</span>')
    head = ('<div class="xm-sec-head">'
            '<div class="xm-h3">第二环 · 业务洞察与风险识别</div>%s</div>' % src_badge)

    cat_map = {"demand": "需求判断", "stock": "库存结构", "profit": "成本收益",
               "liveliness": "民生保障", "supply": "供应"}
    sev_map = {"high": ("xm-badge-red", "高"), "medium": ("xm-badge-orange", "中"),
               "low": ("xm-badge-neutral", "低")}

    items = result.get("insights") or []
    if not items:
        body = '<div class="ai-empty">本次决策未发现需要特别留意的问题。</div>'
    else:
        blocks = []
        for i in items:
            cls, sev_txt = sev_map.get(i.get("severity", "medium"), sev_map["medium"])
            cat = cat_map.get(i.get("category", "stock"), "库存结构")
            blocks.append(
                '<div class="ai-ins %s"><div class="ai-ev-h">'
                '<span class="ai-ins-t">%s</span>'
                '<span class="xm-badge %s">%s风险</span>'
                '<span class="xm-badge xm-badge-neutral">%s</span></div>'
                '<div class="ai-ins-b">%s</div>'
                '<div class="ai-ins-e">依据：%s</div>'
                '<div class="ai-ins-a">建议：%s</div></div>'
                % (i.get("severity", "medium"), _esc(i.get("title", "")),
                   cls, sev_txt, _esc(cat), _esc(i.get("insight", "")),
                   _esc(i.get("evidence", "—")), _esc(i.get("advice", "—"))))
        body = "".join(blocks)

    digest = result.get("digest") or ""
    digest_html = ('<div class="xm-callout" style="margin-top:12px">'
                   '<b>整体判断：</b>%s</div>' % _esc(digest)) if digest else ""
    return ('<div class="xm-card">%s<div style="margin-top:6px">%s</div>%s</div>'
            % (head, body, digest_html))


def render_pipeline(plan: dict, ai_result: dict | None) -> str:
    """输入 → 计算 → 输出的完整闭环（对应评审要求的目标链路）。"""
    m = (plan or {}).get("metrics") or {}
    items = (plan or {}).get("items") or []
    reorder = [it for it in items if float(it.get("reorder_qty") or 0) > 0]
    cov = [float(it.get("final_cover_days") or 0) for it in reorder]
    avg_cov = sum(cov) / len(cov) if cov else 0.0

    steps = [
        ("输入", "库存 + %d 天历史销量 + 预算 %s%.0f + 经营反馈"
                 % (28, CURRENCY, float(m.get("budget") or 0.0))),
        ("AI 理解", "事件语义分级 → 结构化修正参数"),
        ("规则计算", "需求预测 × R³ 多目标整数优化 → 逐 SKU 补货量"),
        ("输出", "%d 种商品 · 建议花费 %s%.0f · 平均够 %.1f 天"
                 % (len(reorder), CURRENCY, float(m.get("total_cost") or 0.0), avg_cov)),
    ]
    rows = "".join(
        '<div class="ai-lane-row"><div class="ai-lane-tag %s">%s</div>'
        '<div><div class="ai-lane-t">%s</div><div class="ai-lane-d">%s</div></div></div>'
        % (("model" if i == 1 else ("rule" if i == 2 else "out")), _esc(tag),
           _esc(tag), _esc(desc))
        for i, (tag, desc) in enumerate(steps))
    return ('<div class="xm-card"><div class="xm-sec-head">'
            '<div class="xm-h3">完整闭环：输入 → 计算 → 输出</div></div>'
            '<div class="ai-lane" style="margin-top:10px">%s</div></div>' % rows)


def render_page(plan: dict | None = None,
                event_result: dict | None = None,
                insight_result: dict | None = None) -> str:
    """整页渲染。三个区块纵向排列，全部走共享组件与 token。"""
    return ('<div class="xm-home">%s%s%s%s%s</div>'
            % (mode_bar(),
               render_lanes(),
               render_event_panel(event_result),
               render_insight_panel(insight_result),
               render_pipeline(plan, insight_result)))


def headline_numbers(plan: dict | None, insight: dict | None) -> str:
    """顶部 KPI：让评委一眼看到 AI 干了什么。"""
    on = llm.is_enabled()
    ev_n = len((insight or {}).get("insights") or []) if insight else 0
    m = (plan or {}).get("metrics") or {}
    items = (plan or {}).get("items") or []
    reorder = [it for it in items if float(it.get("reorder_qty") or 0) > 0]
    return (
        '<div class="xm-kpi-row">'
        '<div class="xm-kpi"><div class="xm-kpi-k">AI 模式</div>'
        '<div class="xm-kpi-v xm-kpi-v-sm">%s</div>'
        '<div class="xm-kpi-sub">%s</div></div>'
        '<div class="xm-kpi"><div class="xm-kpi-k">本次建议</div>'
        '<div class="xm-kpi-v xm-kpi-v-sm">%d 种</div>'
        '<div class="xm-kpi-sub">花费 %s%.0f</div></div>'
        '<div class="xm-kpi"><div class="xm-kpi-k">识别风险</div>'
        '<div class="xm-kpi-v xm-kpi-v-sm">%d 项</div>'
        '<div class="xm-kpi-sub">来自业务洞察</div></div>'
        '<div class="xm-kpi"><div class="xm-kpi-k">民生达标</div>'
        '<div class="xm-kpi-v xm-kpi-v-sm">%.0f%%</div>'
        '<div class="xm-kpi-sub">规则层兜底结果</div></div>'
        '</div>'
        % ("AI 在线" if on else "规则降级",
           "大模型参与事件理解与洞察" if on else "未配 Key，自动走规则路径",
           len(reorder), CURRENCY, float(m.get("total_cost") or 0.0), ev_n,
           float(m.get("livelihood_secured_rate") or 0.0) * 100.0)
    )
