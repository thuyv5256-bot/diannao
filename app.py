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
    from core import agent, analysis, evolution, forecast, memory, policy, tools
    from core.config import (
        CURRENCY, DEFAULT_BUDGET, HOLIDAYS, LIVELIHOOD_MIN_COVER_DAYS,
    )
else:
    from .core import agent, analysis, evolution, forecast, memory, policy, tools
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

/* ── Agent 自主决策页专用样式 ───────────────────────── */
.ag-loop { display:flex; gap:0; margin:0 0 18px; flex-wrap:wrap; }
.ag-node { flex:1; min-width:140px; background:#f8f9fb; border:1px solid #e3e6eb;
           border-radius:10px; padding:12px 14px; margin-right:8px; position:relative; }
.ag-node.active { background:#eef4fb; border-color:#1f4e79; border-width:2px; }
.ag-node.done   { background:#f3fbf5; border-color:#2c7a4b; }
.ag-node .ic { font-size:20px; }
.ag-node .nm { font-weight:700; color:#1f4e79; font-size:14px; margin:4px 0 2px; }
.ag-node .ds { font-size:12px; color:#6b7a8d; line-height:1.5; }
.ag-node .cnt { position:absolute; top:8px; right:10px; font-size:11px;
                color:#8b98a8; background:#fff; border-radius:8px; padding:1px 7px; }

.ag-step { border-left:3px solid #dfe4ea; padding:0 0 14px 18px; margin-left:8px;
           position:relative; }
.ag-step:last-child { padding-bottom:2px; }
.ag-step::before { content:''; position:absolute; left:-7px; top:5px; width:11px;
                   height:11px; border-radius:50%; background:#fff;
                   border:2px solid #b9c3cf; }
.ag-step.key::before  { border-color:#c0392b; background:#c0392b; }
.ag-step.ok::before   { border-color:#2c7a4b; background:#2c7a4b; }
.ag-step.warn::before { border-color:#e67e22; background:#e67e22; }
.ag-step .ph { font-size:11px; font-weight:700; letter-spacing:.5px;
               color:#8b98a8; text-transform:uppercase; }
.ag-step .tt { font-weight:600; color:#2c3e50; font-size:15px; margin:1px 0 3px; }
.ag-step .dt { font-size:13px; color:#5a6b7d; line-height:1.65; }
.ag-step .cc { font-size:13px; color:#1f4e79; margin-top:4px; line-height:1.65;
               background:#f6f9fc; border-radius:5px; padding:5px 9px; }
.ag-step .cc b { color:#c0392b; }

.ag-tool { font-family:'SF Mono',Consolas,monospace; font-size:12px;
           background:#f4f6f9; border:1px solid #e3e6eb; border-radius:6px;
           padding:8px 11px; margin-bottom:7px; }
.ag-tool .tn { color:#1f4e79; font-weight:700; }
.ag-tool .tc { color:#8b98a8; font-size:11px; }
.ag-tool .tw { color:#5a6b7d; font-style:italic; }
.ag-tool.err { background:#fdecea; border-color:#f5c6c0; }

.ag-cand { border:1px solid #e3e6eb; border-radius:10px; padding:13px 15px;
           margin-bottom:10px; background:#fff; }
.ag-cand.win { border:2px solid #2c7a4b; background:#f3fbf5; }
.ag-cand .hd { display:flex; justify-content:space-between; align-items:baseline;
               margin-bottom:7px; }
.ag-cand .nm { font-weight:700; color:#1f4e79; font-size:15px; }
.ag-cand .sc { font-family:'SF Mono',Consolas,monospace; font-size:19px;
               font-weight:700; color:#2c7a4b; }
.ag-cand .bd { font-size:13px; color:#5a6b7d; line-height:1.7; }
.ag-bar { display:inline-block; height:7px; border-radius:4px; background:#e3e6eb;
          margin-right:6px; vertical-align:middle; }
.ag-bar span { display:block; height:100%; border-radius:4px; }
.ag-flag { display:inline-block; padding:2px 9px; border-radius:10px; font-size:12px;
           font-weight:600; background:#e8f5e9; color:#2c7a4b; margin-left:6px; }
.ag-score-box { background:#f8f9fb; border:1px solid #e8ebef; border-radius:10px;
                padding:14px 18px; margin-bottom:14px; }
.ag-score-box .big { font-size:34px; font-weight:700; color:#1f4e79; line-height:1.1; }
.ag-score-box .lb { font-size:13px; color:#6b7a8d; margin-top:2px; }
.ag-crit { background:#fffaf3; border-left:4px solid #e67e22; padding:11px 15px;
           border-radius:6px; font-size:14px; color:#6b4a1f; line-height:1.75;
           margin-bottom:9px; }
.ag-next { background:#f6f9fc; border-left:4px solid #1f4e79; padding:11px 15px;
           border-radius:6px; font-size:14px; color:#2c3e50; line-height:1.75;
           margin-bottom:9px; }
.ag-goal { background:linear-gradient(135deg,#1f4e79,#2e7d5b); color:#fff;
           border-radius:12px; padding:16px 20px; margin-bottom:16px; }
.ag-goal .t { font-size:13px; opacity:.85; letter-spacing:.5px; }
.ag-goal .g { font-size:22px; font-weight:700; margin:3px 0 6px; }
.ag-goal .d { font-size:14px; opacity:.92; line-height:1.6; }
.ag-chips { margin-top:9px; }
.ag-chip { display:inline-block; background:rgba(255,255,255,.18);
           border:1px solid rgba(255,255,255,.35); border-radius:12px;
           padding:3px 11px; font-size:12px; margin-right:7px; }
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
# Agent 自主决策轨迹渲染
# ════════════════════════════════════════════════════════════
_PHASE_ICON = {"感知": "👁", "推理": "🧩", "规划": "🗺", "执行": "⚙️", "反思": "🪞"}


def _count_by_phase(trace: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in trace:
        out[t["phase"]] = out.get(t["phase"], 0) + 1
    return out


def render_agent_loop_html(run: dict) -> str:
    """渲染决策循环总览：五个阶段各自走了多少步。"""
    cnt = _count_by_phase(run["trace"])
    nodes = []
    for ph in agent.PHASES:
        n = cnt.get(ph["key"], 0)
        cls = "done" if n > 0 else ""
        nodes.append(f"""
        <div class="ag-node {cls}">
          <div class="cnt">{n} 步</div>
          <div class="ic">{ph['icon']}</div>
          <div class="nm">{ph['key']}</div>
          <div class="ds">{ph['desc']}</div>
        </div>""")
    return f'<div class="ag-loop">{"".join(nodes)}</div>'


def render_agent_goal_html(run: dict) -> str:
    """渲染 Agent 本轮自主确定的目标与所选策略。"""
    g = run["goal"]
    st = run["strategy"]
    dg = run["reasoning"]["diagnosis"]
    w = st["weights"]
    return f"""
    <div class="ag-goal">
      <div class="t">本轮自主确定的首要目标（由当前店况推导得出）</div>
      <div class="g">🎯 {g['key']}</div>
      <div class="d">{g['detail']}</div>
      <div class="ag-chips">
        <span class="ag-chip">策略：{st['label']}</span>
        <span class="ag-chip">民生断货 {dg['livelihood_stockout']} 项</span>
        <span class="ag-chip">高毛利断货 {dg['profit_stockout']} 项</span>
        <span class="ag-chip">积压损耗 {dg['spoilage']} 项</span>
      </div>
      <div class="d" style="margin-top:9px;font-size:13px;opacity:.85">
        ⚖ 识别的核心矛盾：{g['conflict']}
      </div>
      <div class="ag-chips">
        <span class="ag-chip">民生权重 {w['livelihood']:.0%}</span>
        <span class="ag-chip">收益权重 {w['margin']:.0%}</span>
        <span class="ag-chip">风险权重 {w['risk']:.0%}</span>
      </div>
    </div>"""


def render_agent_trace_html(run: dict) -> str:
    """渲染完整思考链 —— 每一步都带依据与结论。"""
    steps = []
    for t in run["trace"]:
        icon = _PHASE_ICON.get(t["phase"], "·")
        dt = (f'<div class="dt">{t["detail"]}</div>') if t["detail"] else ""
        cc = (f'<div class="cc">→ {t["conclusion"]}</div>'
              if t["conclusion"] else "")
        steps.append(f"""
        <div class="ag-step {t['level']}">
          <div class="ph">{icon} {t['phase']} · 第 {t['step']} 步</div>
          <div class="tt">{t['title']}</div>
          {dt}{cc}
        </div>""")
    ref = run["reflection"]
    conf = ref["confidence"]
    conf_color = "#2c7a4b" if conf >= 0.8 else ("#e67e22" if conf >= 0.6 else "#c0392b")
    return f"""
    <div class="ag-score-box">
      <div class="big" style="color:{conf_color}">{conf:.0%}</div>
      <div class="lb">本轮决策置信度（{ref['confidence_level']}）·
        参考依据：{'；'.join(ref['confidence_reasons'])}</div>
      <div class="lb" style="margin-top:7px">
        共 {len(run['trace'])} 步思考 ·
        {len(run['tool_calls'])} 次工具调用 ·
        耗时 {ref['elapsed_sec']:.2f} 秒
      </div>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">🧠 完整思考链</h3>
      <div style="margin-top:14px">{''.join(steps)}</div>
    </div>"""


def render_agent_tools_html(run: dict) -> str:
    """渲染工具调用轨迹，并展示这个 Agent 手里有哪些工具。"""
    rows = []
    for i, t in enumerate(run["tool_calls"], 1):
        cls = "" if t["ok"] else "err"
        args = "，".join(f"{k}={v}" for k, v in t["args"].items() if v not in ("", None))
        rows.append(f"""
        <div class="ag-tool {cls}">
          <span class="tn">{i:02d} · {t['tool']}</span>
          <span class="tc">[{t['category']}] · {t['cost_ms']:.0f}ms</span><br>
          <span class="tw">为什么调它：{t['why']}</span>
          {f'<br><span class="tc">参数：{args}</span>' if args else ''}
          {f'<br>→ {t["conclusion"]}' if t["conclusion"] else ''}
        </div>""")

    cat_rows = []
    for c in tools.tool_catalog():
        color = {"感知": "#1f4e79", "分析": "#6b4c9a",
                 "决策": "#c0392b", "行动": "#e67e22"}.get(c["category"], "#5a6b7d")
        cat_rows.append(f"""
        <tr><td><span class="badge" style="background:#eef1f4;color:{color}">
              {c['category']}</span></td>
            <td style="font-family:Consolas,monospace;font-size:13px">{c['name']}</td>
            <td style="font-size:13px;color:#5a6b7d">{c['desc']}</td>
            <td style="font-size:12px;color:#8b98a8">{c['cost']}</td></tr>""")

    cov = len({t["tool"] for t in run["tool_calls"]})
    tot = len(tools.all_tools())
    return f"""
    <div class="dn-card">
      <h3 style="margin-top:0">🔧 本轮工具调用轨迹（按真实调用顺序）</h3>
      <div style="font-size:13px;color:#6b7a8d;margin-bottom:12px">
        Agent 不是把流程写死在代码里 —— 它每调一个工具，都要先说明「为什么调」。
        换成别的店况，这条轨迹会不一样。
      </div>
      {''.join(rows)}
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">🧰 Agent 的工具箱</h3>
      <div style="font-size:13px;color:#6b7a8d;margin-bottom:12px">
        它自主挑选调用，不是被动执行流水线。本轮用了 {cov} 个（工具箱共 {tot} 个）。
      </div>
      <table class="dn">
        <tr><th>类别</th><th>工具名</th><th>作用</th><th>开销</th></tr>
        {''.join(cat_rows)}
      </table>
    </div>"""


def render_agent_candidates_html(run: dict) -> str:
    """渲染多方案博弈：三套候选各自打分，为什么这套胜出。"""
    cards = []
    best_tag = run["best_candidate"]["tag"]
    for c in run["candidates"]:
        win = c["tag"] == best_tag
        p = c["parts"]
        m = c["metrics"]
        sim = c["sim"]

        def bar(v, color):
            pct = max(2, int(v * 100))
            return (f'<span class="ag-bar" style="width:76px">'
                    f'<span style="width:{pct}%;background:{color}"></span></span>')

        cards.append(f"""
        <div class="ag-cand {'win' if win else ''}">
          <div class="hd">
            <div class="nm">候选 {c['tag']} · {c['label']}
              {f'<span class="ag-flag">✔ 采纳</span>' if win else ''}</div>
            <div class="sc">{c['score']:.4f}</div>
          </div>
          <div class="bd">
            {bar(p['livelihood'], '#2c7a4b')} 民生保障 {p['livelihood']:.2f}
            　{bar(p['margin'], '#1f4e79')} 门店收益 {p['margin']:.2f}
            　{bar(p['risk'], '#e67e22')} 风险控制 {p['risk']:.2f}
          </div>
          <div class="bd" style="margin-top:7px">
            花费 <b>{CURRENCY}{m['total_cost']:.0f}</b>　
            民生保障度 <b>{m['livelihood_index']:.0%}</b>　
            预计毛利 <b>{CURRENCY}{m['gross_margin']:.0f}</b>　
            沙盘缺口 <b>{sim['risk_total']}</b> 项（民生 {len(sim['risk_livelihood'])}）　
            压货风险 <b>{len(sim['overstock'])}</b> 项
          </div>
        </div>""")

    worst = min(run["candidates"], key=lambda x: x["score"])
    best = run["best_candidate"]

    # 检测"惠民约束未生效"的情况：预算充裕到不需要取舍时，
    # 惠民版与纯利润版的结果会自然趋同 —— 这不是 bug，是逻辑正确。
    by_tag = {c["tag"]: c for c in run["candidates"]}
    a, b = by_tag.get("A"), by_tag.get("B")
    tie_note = ""
    if a and b and abs(a["score"] - b["score"]) < 1e-6:
        tie_note = f"""
        <div class="note" style="margin-top:10px">
          <b>为什么候选 A 和候选 B 得分一样？</b>
          因为这一轮<b>预算充裕</b>（{CURRENCY}{run['budget']:.0f}）到足以覆盖全部商品的需求上限，
          不需要在任何东西之间做取舍 —— 惠民约束自然就不触发，
          两套算法的结果也就趋同了。<br>
          这恰恰反过来说明一件事：<b>惠民约束不是无条件的补贴，而是预算紧张时的分配原则。</b>
          把预算调低，两条路就会立刻分叉。
        </div>"""
    else:
        tie_note = f"""
        <div class="good" style="margin-top:10px">
          🏆 <b>裁决：</b>采纳候选 {best['tag']}（{best['label']}），综合得分
          {best['score']:.4f}，领先末位候选 {worst['tag']}（{worst['label']}）
          {best['score'] - worst['score']:.4f} 分。<br>
          这个结论不是写死的 —— 换一个店况、换一套策略权重，胜出的可能就是另一套方案。
        </div>"""

    return f"""
    <div class="dn-card">
      <h3 style="margin-top:0">⚖️ 多方案博弈：不是算一套，是裁决几套</h3>
      <div style="font-size:13px;color:#6b7a8d;margin-bottom:14px">
        每套候选方案都先做 3 天沙盘推演，再按本轮策略的权重打分。
        Agent 不预设答案 —— 让方案在推演中自己胜出。
      </div>
      {''.join(cards)}
      {tie_note}
    </div>"""


def render_agent_reflect_html(run: dict) -> str:
    """渲染自我反思：置信度、自我批评、下一轮预案。"""
    ref = run["reflection"]
    crit = "".join(f'<div class="ag-crit">💬 {c}</div>' for c in ref["critiques"])
    nxt = "".join(f'<div class="ag-next">▸ {a}</div>' for a in ref["next_actions"])
    return f"""
    <div class="dn-card">
      <h3 style="margin-top:0">🪞 自我反思</h3>
      <div style="font-size:13px;color:#6b7a8d;margin-bottom:12px">
        Agent 跑完一轮不直接结束 —— 它会回头审视自己这一轮哪里做得不够，
        并给下一轮留预案。这是它和固定脚本最本质的区别。
      </div>
      <h4 style="color:#e67e22;margin:14px 0 8px">对自己这一轮的批评</h4>
      {crit}
      <h4 style="color:#1f4e79;margin:16px 0 8px">给下一轮的预案</h4>
      {nxt}
    </div>"""


def render_agent_chart(run: dict):
    """多方案打分对比柱状图。"""
    names = [f"候选 {c['tag']}｜{c['label']}" for c in run["candidates"]]
    liv = [c["parts"]["livelihood"] for c in run["candidates"]]
    mar = [c["parts"]["margin"] for c in run["candidates"]]
    rsk = [c["parts"]["risk"] for c in run["candidates"]]
    tot = [c["score"] for c in run["candidates"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=liv, name="民生保障", marker_color="#2c7a4b"))
    fig.add_trace(go.Bar(x=names, y=mar, name="门店收益", marker_color="#1f4e79"))
    fig.add_trace(go.Bar(x=names, y=rsk, name="风险控制", marker_color="#e67e22"))
    fig.add_trace(go.Scatter(
        x=names, y=tot, name="综合得分", mode="lines+markers+text",
        text=[f"{v:.3f}" for v in tot], textposition="top center",
        line=dict(color="#c0392b", width=3), marker=dict(size=11),
    ))
    fig.update_layout(
        height=400, template="plotly_white", barmode="group",
        paper_bgcolor="#fff", plot_bgcolor="#fff",
        title=dict(text="候选方案三维度得分与综合裁决", font=dict(size=17, color="#1f4e79")),
        xaxis=dict(gridcolor="#eef1f4"),
        yaxis=dict(title=dict(text="归一化得分（0~1）"), gridcolor="#eef1f4", range=[0, 1.15]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=30, t=80, b=50),
    )
    return fig


def render_agent_html(run: dict) -> str:
    """Agent 页面的完整渲染（除图表外）。"""
    return f"""
    {_hero(f"Agent 自主决策 · {run['date']} · 预算 {CURRENCY}{run['budget']:.0f}　|　"
           f"目标「{run['goal']['key']}」· 策略「{run['strategy']['label']}」")}
    {render_agent_loop_html(run)}
    {render_agent_goal_html(run)}
    {render_agent_trace_html(run)}
    """


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


def do_agent(date_str: str, budget: float):
    """跑一轮完整的 Agent 自主决策循环，返回轨迹相关的四个输出。"""
    try:
        d = str(date_str).strip()
        date.fromisoformat(d)
    except Exception:
        err = "<div class='note'>日期格式不对，请填写类似 2026-09-25 的格式。</div>"
        return err, "", "", None
    budget = float(budget or DEFAULT_BUDGET)
    run = agent.run_agent(d, budget, persist=False)
    return (render_agent_html(run),
            render_agent_tools_html(run),
            render_agent_candidates_html(run) + render_agent_reflect_html(run),
            render_agent_chart(run))


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
      <b>① 带惠民约束的自主决策 Agent。</b>
      不是把「预测 + 分配」打包成函数就叫 Agent —— 那种代码调用顺序写死在源码里，
      不管门店什么状况都走同一条路。店脑实现的是一条显式的
      <b>感知 → 推理 → 规划 → 执行 → 反思</b> 决策循环：它自己盘点店况、
      诊断问题、确定本轮目标、从 13 个工具里挑选用哪些（并主动跳过用不上的）、
      生成多套候选方案做沙盘推演后裁决、最后反思自己哪里没做好。
      <b>换一个店况，整条路径都会不一样</b> —— 见「🤖 Agent 自主决策」。
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
      降低小微企业使用人工智能的门槛。Agent 的每一步思考都用店主听得懂的话写在界面上，
      不出现"安全库存系数"这类术语 —— 可解释才能被信任。
      </p>
    </div>
    <div class="dn-card">
      <h3 style="margin-top:0">技术实现</h3>
      <table class="dn">
        <tr><th>模块</th><th>做法</th></tr>
        <tr><td>Agent 决策循环</td>
            <td><code>core/agent.py</code>：感知 → 推理 → 规划 → 执行 → 反思五阶段循环；
                目标由店况推导而非写死；记录完整思考链与工具调用轨迹</td></tr>
        <tr><td>Agent 工具层</td>
            <td><code>core/tools.py</code>：13 个原子工具，分感知 / 分析 / 决策 / 行动四类；
                Agent 自主决定调用哪些、跳过哪些（含资源意识）</td></tr>
        <tr><td>多方案博弈</td>
            <td>每轮生成 3 套候选方案，逐套做 3 天沙盘推演，按本轮策略权重打分后裁决；
                权重随店况在 4 种策略间自主切换</td></tr>
        <tr><td>长期记忆库</td><td>SQLite 持久化商品档案 / 销量事件 / 策略参数 / 进化轨迹</td></tr>
        <tr><td>需求预测</td><td>指数衰减加权移动平均 × 星期效应 × 节日因子；
            关键细节：把断货日的销量还原为<b>潜在需求</b>再学习</td></tr>
        <tr><td>三层惠民约束</td><td>民生兜底锁定 → 剩余预算按资金效率竞争 → 极端不足时按客流价值保底</td></tr>
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
            # ── Tab 1：Agent 自主决策（核心）──
            with gr.Tab("🤖 Agent 自主决策"):
                gr.Markdown(
                    "这里展示的是店脑 **真正跑过的决策过程**，不是事后补的说明文字。"
                    "它会自己盘点店况、诊断问题、确定目标、挑选用哪些分析工具、"
                    "生成多套方案做沙盘推演后裁决，最后还会反思自己哪里没做好。"
                    "**换一个经营状况，它的整条路径都会不一样。**"
                )
                with gr.Row():
                    ag_date = gr.Textbox(value=DEFAULT_PLAN_DATE, label="决策日期",
                                         scale=2, info="格式：2026-09-25")
                    ag_budget = gr.Number(value=DEFAULT_BUDGET, label="进货预算（元）",
                                          scale=2)
                    btn_agent = gr.Button("🚀 让店脑自己想一想", variant="primary", scale=1)
                with gr.Row():
                    ag_preset = gr.Button("📅 中秋节前夜（民生断货）", size="sm")
                    ag_preset2 = gr.Button("📆 平常工作日（店况平稳）", size="sm")
                    ag_preset3 = gr.Button("💰 预算收紧到 250 元", size="sm")
                    ag_preset4 = gr.Button("🏦 预算充裕 1500 元（会换方案）", size="sm")

                # 打开即有内容：先跑一轮，不让店主面对空白页
                _default_run = agent.run_agent(DEFAULT_PLAN_DATE, DEFAULT_BUDGET)
                ag_loop = gr.HTML(render_agent_html(_default_run))
                ag_tools = gr.HTML(render_agent_tools_html(_default_run))
                ag_detail = gr.HTML(render_agent_candidates_html(_default_run)
                                    + render_agent_reflect_html(_default_run))
                ag_chart = gr.Plot(render_agent_chart(_default_run))

            # ── Tab 2 ──
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

            # ── Tab 3 ──
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

            # ── Tab 4 ──
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

            # ── Tab 5 ──
            with gr.Tab("📚 店里的老账本"):
                mem_html = gr.HTML(render_memory_html())
                btn_mem_refresh = gr.Button("↻ 刷新")
                gr.Markdown("---")
                gr.HTML(render_analysis_html())

            # ── Tab 6 ──
            with gr.Tab("ℹ️ 项目说明"):
                gr.HTML(render_about_html())

        # ── 事件绑定统一放在末尾，便于跨标签页联动 ──
        ag_outputs = [ag_loop, ag_tools, ag_detail, ag_chart]
        btn_agent.click(do_agent, [ag_date, ag_budget], ag_outputs)
        ag_preset.click(lambda: ("2026-09-25", DEFAULT_BUDGET), None,
                        [ag_date, ag_budget]).then(
            do_agent, [ag_date, ag_budget], ag_outputs)
        ag_preset2.click(lambda: ("2026-09-15", DEFAULT_BUDGET), None,
                         [ag_date, ag_budget]).then(
            do_agent, [ag_date, ag_budget], ag_outputs)
        ag_preset3.click(lambda: ("2026-09-25", 250.0), None,
                         [ag_date, ag_budget]).then(
            do_agent, [ag_date, ag_budget], ag_outputs)
        ag_preset4.click(lambda: ("2026-09-15", 1500.0), None,
                         [ag_date, ag_budget]).then(
            do_agent, [ag_date, ag_budget], ag_outputs)

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
