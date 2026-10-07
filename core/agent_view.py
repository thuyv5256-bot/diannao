# -*- coding: utf-8 -*-
"""小满 · 「Agent 决策台」页 —— 把一次自主决策的全过程摊开给店主看。

═══ 这一页要回答的问题 ═══
「你说它是 Agent，那它到底自己做了哪些决定？」
本页把 `core/agent_loop.AgentRunner.run()` 产出的结构化轨迹**原样渲染**：

  ① 五阶段循环条：感知 → 推理 → 规划 → 执行 → 反思，走到哪一步一目了然；
  ② 这一轮的目标：从数据里诊断出来的（不是写死的），以及为什么是它；
  ③ 思考轨迹：每一步「想了什么 / 为什么这么想 / 得出什么结论」；
  ④ 工具调用：这一轮用了哪些工具、什么分类、什么成本、为什么调它 / 为什么跳过它；
  ⑤ 多候选博弈：A/B/C 三套方案的沙盘结果与按策略加权的打分，谁赢、赢多少；
  ⑥ 自我反思：置信度（含构成）、自我批评、下一轮改进项。

═══ 与 DESIGN.md / CLAUDE.md 的一致性 ═══
  · 颜色一律走 `--xm-*` token，绝不写死色值（UI 铁律）；
  · 不使用彩色 emoji，阶段符号用几何字形（◉ ◇ ▤ ▶ ◈）；
  · 中文引号用「」，避免与 Python 字符串定界符冲突；
  · 不写死数字：页面上每一个数都来自 `run()` 的真实返回。
"""

from html import escape as _esc


AGENT_CSS = """
/* ══════════════════════════════════════════════════════════════════
   「Agent 决策台」页 —— 只消费 --xm-* token，颜色定义见 core/themes.py
   设计基调：工作面（workbench）—— 左侧主轨 = 它怎么想的；右侧轨 = 它动了什么手。
   层级靠「表面色差 + 细描边 + 一处主色」，不靠重阴影堆叠。
   ══════════════════════════════════════════════════════════════════ */

/* ── 页头 ── */
.ag-head { display:flex; align-items:flex-end; justify-content:space-between;
  gap:var(--xm-space-lg); margin-bottom:var(--xm-space-md); flex-wrap:wrap; }
.ag-scene { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.ag-scene .xm-badge { font-size:12px; }

/* ── 五阶段循环条：用一条贯穿的进程线串起 5 段 ── */
.ag-loop { display:flex; align-items:stretch; gap:0; margin:0 0 var(--xm-space-md);
  background:var(--xm-canvas); border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); box-shadow:var(--xm-card-shadow); overflow:hidden; }
.ag-stage { flex:1 1 0; padding:14px 16px; border-right:var(--xm-border-w) solid var(--xm-hairline-soft);
  position:relative; transition:background .18s ease; }
.ag-stage:last-child { border-right:none; }
.ag-stage-ico { font-size:15px; color:var(--xm-steel); line-height:1; }
.ag-stage-on .ag-stage-ico { color:var(--xm-primary); }
.ag-stage-t { font-size:15px; font-weight:600; color:var(--xm-ink); margin-top:6px;
  letter-spacing:.01em; }
.ag-stage-d { font-size:12px; color:var(--xm-slate); margin-top:3px; line-height:1.55; }
.ag-stage-n { font-size:12px; color:var(--xm-steel); margin-top:8px;
  font-variant-numeric:tabular-nums; }
.ag-stage-on { background:var(--xm-info-soft); }
.ag-stage-on::after { content:""; position:absolute; left:0; bottom:0; width:100%;
  height:3px; background:var(--xm-primary); }
/* 顶部的「已走过」细线，让五段读起来像一条流程而不是五个格子 */
.ag-loop { position:relative; }
.ag-stage::before { content:""; position:absolute; left:0; top:0; width:100%;
  height:2px; background:var(--xm-hairline-soft); }
.ag-stage-on::before { background:var(--xm-primary); opacity:.35; }

/* ── 目标卡：整页唯一的主色重音 ── */
.ag-goal { background:var(--xm-canvas); border:var(--xm-border-w) solid var(--xm-card-border);
  border-left:4px solid var(--xm-primary); border-radius:var(--xm-radius-lg);
  padding:var(--xm-space-lg) var(--xm-space-xl); box-shadow:var(--xm-card-shadow);
  margin-bottom:var(--xm-space-md); }
.ag-goal-k { font-size:12px; color:var(--xm-steel); letter-spacing:.06em; }
.ag-goal-v { font-size:26px; font-weight:700; color:var(--xm-primary); margin:5px 0 7px;
  letter-spacing:-.01em; line-height:1.25; }
.ag-goal-d { font-size:14px; color:var(--xm-charcoal); line-height:1.78; max-width:76ch; }
.ag-goal-c { font-size:13px; color:var(--xm-warning); margin-top:10px; line-height:1.7;
  padding:8px 12px; background:var(--xm-warning-soft); border-radius:var(--xm-radius-sm); }

/* ── 诊断条：一排读数 ── */
.ag-diag { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr));
  gap:10px; margin-bottom:var(--xm-space-md); }
.ag-diag > div { background:var(--xm-surface-soft); border:var(--xm-border-w) solid var(--xm-hairline);
  border-radius:var(--xm-radius-md); padding:11px 13px; transition:border-color .18s ease; }
.ag-diag > div:hover { border-color:var(--xm-hairline-strong); }
.ag-diag-k { font-size:12px; color:var(--xm-steel); }
.ag-diag-v { font-size:18px; font-weight:600; color:var(--xm-ink); margin-top:5px;
  font-variant-numeric:tabular-nums; letter-spacing:-.01em; line-height:1.2; }
.ag-diag-sub { font-size:11px; color:var(--xm-slate); margin-top:3px; line-height:1.5; }

/* ── 思考轨迹 ── */
.ag-think { display:flex; gap:12px; padding:12px 0;
  border-bottom:var(--xm-border-w) solid var(--xm-hairline-soft); }
.ag-think:last-child { border-bottom:none; }
.ag-think-dot { flex:0 0 22px; height:22px; line-height:22px; text-align:center;
  border-radius:var(--xm-radius-full); font-size:11px; font-weight:600; margin-top:1px;
  background:var(--xm-surface-soft); color:var(--xm-steel); }
.ag-think-ok .ag-think-dot { background:var(--xm-success-soft); color:var(--xm-success); }
.ag-think-warn .ag-think-dot { background:var(--xm-warning-soft); color:var(--xm-warning); }
.ag-think-body { min-width:0; flex:1 1 auto; }
.ag-think-t { font-size:15px; font-weight:600; color:var(--xm-ink); line-height:1.4; }
.ag-think-d { font-size:13px; color:var(--xm-slate); margin-top:4px; line-height:1.72; }
/* 结论块：左侧一根主色竖线，比灰底更「像引用」 */
.ag-think-c { font-size:13px; color:var(--xm-charcoal); margin-top:7px; padding:7px 12px;
  background:var(--xm-surface-soft); border-left:2px solid var(--xm-hairline-strong);
  border-radius:0 var(--xm-radius-sm) var(--xm-radius-sm) 0; line-height:1.68; }
.ag-think-c b { color:var(--xm-ink); font-weight:600; }

/* ── 工具调用 ── */
.ag-tool { display:flex; gap:10px; align-items:flex-start; padding:9px 0;
  border-bottom:var(--xm-border-w) solid var(--xm-hairline-soft); }
.ag-tool:last-child { border-bottom:none; }
.ag-tool-name { flex:0 0 auto; font-family:var(--xm-font-mono); font-size:12.5px;
  color:var(--xm-ink); font-weight:600; letter-spacing:-.01em;
  background:var(--xm-surface-soft); border-radius:var(--xm-radius-xs);
  padding:2px 7px; line-height:1.6; }
.ag-tool-meta { flex:0 0 auto; }
.ag-tool-why { flex:1 1 auto; min-width:0; font-size:13px; color:var(--xm-slate); line-height:1.65; }
.ag-tool-ms { flex:0 0 auto; font-size:12px; color:var(--xm-steel);
  font-variant-numeric:tabular-nums; }
/* 跳过项：虚线框 + 斜纹底，一眼区别于「调用了」 */
.ag-skip { display:flex; gap:10px; align-items:flex-start; padding:11px 14px;
  background:var(--xm-surface-soft); border:var(--xm-border-w) dashed var(--xm-hairline-strong);
  border-radius:var(--xm-radius-md); margin-top:8px; }
.ag-skip-t { font-size:14px; font-weight:600; color:var(--xm-ink); }
.ag-skip-d { font-size:13px; color:var(--xm-slate); margin-top:3px; line-height:1.72; }

/* ── 候选方案打分 ── */
.ag-cand { border:var(--xm-border-w) solid var(--xm-card-border); border-radius:var(--xm-radius-md);
  padding:13px 15px; margin-bottom:10px; background:var(--xm-canvas);
  transition:border-color .18s ease; }
.ag-cand:hover { border-color:var(--xm-hairline-strong); }
.ag-cand-win { border-color:var(--xm-primary); border-width:2px; background:var(--xm-info-soft); }
.ag-cand-win:hover { border-color:var(--xm-primary); }
.ag-cand-top { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.ag-cand-tag { flex:0 0 auto; width:26px; height:26px; line-height:26px; text-align:center;
  border-radius:var(--xm-radius-full); background:var(--xm-surface-soft);
  color:var(--xm-ink); font-size:13px; font-weight:700; }
.ag-cand-win .ag-cand-tag { background:var(--xm-primary); color:var(--xm-on-primary); }
.ag-cand-note { font-size:15px; font-weight:600; color:var(--xm-ink); }
.ag-cand-score { margin-left:auto; font-size:21px; font-weight:700; color:var(--xm-ink);
  font-variant-numeric:tabular-nums; letter-spacing:-.02em; }
.ag-cand-win .ag-cand-score { color:var(--xm-primary); }
.ag-cand-sub { font-size:12px; color:var(--xm-slate); margin-top:5px; line-height:1.65; }
.ag-obj { display:flex; gap:10px; margin-top:9px; flex-wrap:wrap; }
.ag-obj > div { flex:1 1 120px; background:var(--xm-surface-soft);
  border-radius:var(--xm-radius-sm); padding:8px 11px; }
.ag-obj-k { font-size:11px; color:var(--xm-steel); }
.ag-obj-v { font-size:15px; font-weight:600; color:var(--xm-ink); margin-top:3px;
  font-variant-numeric:tabular-nums; }
.ag-flag { display:inline-block; font-size:12px; color:var(--xm-warning);
  background:var(--xm-warning-soft); border-radius:var(--xm-radius-sm);
  padding:2px 8px; margin:6px 6px 0 0; line-height:1.5; }

/* ── 反思 ── */
.ag-conf { display:flex; gap:16px; align-items:center; flex-wrap:wrap;
  background:var(--xm-canvas); border:var(--xm-border-w) solid var(--xm-card-border);
  border-radius:var(--xm-radius-lg); padding:var(--xm-space-lg) var(--xm-space-xl);
  box-shadow:var(--xm-card-shadow); margin-bottom:var(--xm-space-md); }
.ag-conf-v { font-size:40px; font-weight:700; color:var(--xm-primary); line-height:1;
  letter-spacing:-.03em; font-variant-numeric:tabular-nums; }
.ag-conf-k { font-size:12px; color:var(--xm-steel); }
.ag-conf-parts { flex:1 1 auto; min-width:220px; display:grid;
  grid-template-columns:repeat(3,1fr); gap:10px; }
.ag-conf-parts > div { background:var(--xm-surface-soft);
  border:var(--xm-border-w) solid var(--xm-hairline);
  border-radius:var(--xm-radius-sm); padding:9px 11px; }
.ag-list { margin:0; padding:0; list-style:none; }
.ag-list li { display:flex; gap:10px; padding:10px 0;
  border-bottom:var(--xm-border-w) solid var(--xm-hairline-soft); }
.ag-list li:last-child { border-bottom:none; }
.ag-list-n { flex:0 0 19px; height:19px; line-height:19px; text-align:center;
  border-radius:var(--xm-radius-full); background:var(--xm-surface-soft);
  color:var(--xm-steel); font-size:11px; font-weight:600; margin-top:2px; }
.ag-list-t { font-size:14px; font-weight:600; color:var(--xm-ink); }
.ag-list-d { font-size:13px; color:var(--xm-slate); margin-top:3px; line-height:1.72; }
.ag-trig { display:inline-block; font-size:11px; color:var(--xm-primary);
  background:var(--xm-info-soft); border-radius:var(--xm-radius-sm);
  padding:2px 8px; margin-top:6px; }
.ag-foot { font-size:12px; color:var(--xm-steel); margin-top:var(--xm-space-md);
  line-height:1.75; }

/* ── 空状态 ── */
.ag-empty { background:var(--xm-canvas); border:var(--xm-border-w) dashed var(--xm-hairline-strong);
  border-radius:var(--xm-radius-lg); padding:var(--xm-space-xxl) var(--xm-space-lg);
  text-align:center; }
.ag-empty-t { font-size:17px; font-weight:600; color:var(--xm-ink); }
.ag-empty-d { font-size:14px; color:var(--xm-slate); margin-top:8px; line-height:1.75;
  max-width:52ch; margin-left:auto; margin-right:auto; }
.ag-empty-h { font-size:12px; color:var(--xm-steel); margin-top:16px; line-height:1.8;
  font-family:var(--xm-font-mono); }

/* ── 窄屏：五阶段条与候选读数改为两列，避免挤压 ── */
@media (max-width:1150px) {
  .ag-loop { flex-wrap:wrap; }
  .ag-stage { flex:1 1 33.33%; border-right:none;
    border-bottom:var(--xm-border-w) solid var(--xm-hairline-soft); }
  .ag-stage::before { display:none; }
}
@media (max-width:760px) {
  .ag-stage { flex:1 1 50%; }
  .ag-conf-parts { grid-template-columns:1fr; }
  .ag-goal-v { font-size:22px; }
}
"""


# ── 小工具 ──────────────────────────────────────────────

def _badge(text, kind="neutral"):
    return '<span class="xm-badge xm-badge-%s">%s</span>' % (kind, _esc(str(text)))


def _kpi(label, value, sub=None):
    sub_html = ('<div class="xm-kpi-sub">%s</div>' % sub) if sub else ''
    return ('<div class="xm-kpi"><div class="xm-kpi-k">%s</div>'
            '<div class="xm-kpi-v">%s</div>%s</div>' % (label, value, sub_html))


def _money(v):
    try:
        return '¥%s' % format(float(v), ',.0f')
    except (TypeError, ValueError):
        return '—'


def _level_class(level):
    return {"ok": "ag-think-ok", "warn": "ag-think-warn"}.get(level, "")


# ── 页面头 ──────────────────────────────────────────────

def render_head(result=None) -> str:
    """页头 + 本轮场景标签。"""
    scene = ''
    if result:
        g = result.get("goal", {})
        scene = ('<div class="ag-scene">'
                 + _badge("决策日 %s" % result.get("plan_date", ""), "neutral")
                 + _badge("预算 %s" % _money(result.get("budget")), "neutral")
                 + _badge("目标 · %s" % g.get("label", ""), "orange")
                 + _badge("策略 · %s" % result.get("strategy", {}).get("label", ""), "green")
                 + '</div>')
    return ('<div class="ag-head"><div>'
            '<div class="xm-h1">Agent 决策台</div>'
            '<div class="xm-page-sub">看它自己定目标、自己选打法、自己认错 —— 全程规则可复现，不依赖大模型</div>'
            '</div>%s</div>' % scene)


# ── ① 五阶段循环条 ──────────────────────────────────────

def render_loop(result: dict) -> str:
    """五阶段横条：标出每阶段留下了几条思考。"""
    phases = result.get("phases", [])
    steps = result.get("stats", {}).get("steps_by_phase", {})
    cells = []
    for p in phases:
        n = steps.get(p["label"], 0)
        on = " ag-stage-on" if n > 0 else ""
        cells.append(
            '<div class="ag-stage%s">'
            '<div class="ag-stage-ico">%s</div>'
            '<div class="ag-stage-t">%s</div>'
            '<div class="ag-stage-d">%s</div>'
            '<div class="ag-stage-n">%d 步思考</div>'
            '</div>' % (on, _esc(p["icon"]), _esc(p["label"]),
                        _esc(p["desc"]), n))
    return '<div class="ag-loop">%s</div>' % ''.join(cells)


# ── ② 目标 + 诊断 ───────────────────────────────────────

def render_goal(result: dict) -> str:
    d = result.get("diagnosis", {})
    g = result.get("goal", {})
    diag = [
        ("断货缺口压力", "%.0f%%" % (float(d.get("gap_pressure") or 0) * 100),
         "整体缺口天数 / 目标天数"),
        ("最紧的差", "%.1f 天" % float(d.get("worst_gap_days") or 0),
         "还差多少天的量才够"),
        ("民生最低覆盖", _fmt_days(d.get("livelihood_min_cover")),
         "本店常态 %s" % _fmt_days(d.get("livelihood_norm_cover"))),
        ("民生告急", "%d 种" % int(d.get("livelihood_stockout") or 0),
         "跌破警戒线 %.1f 天" % float(d.get("alert_line") or 0)),
        ("压货压力", "%.2f" % float(d.get("overstock_pressure") or 0),
         "%d 种超保质期" % int(d.get("overstocked_count") or 0)),
        ("估算所需资金", _money(d.get("need_money")),
         "预算覆盖 %s" % _fmt_pct(d.get("budget_ratio"))),
    ]
    diag_html = ''.join(
        '<div><div class="ag-diag-k">%s</div><div class="ag-diag-v">%s</div>'
        '<div class="ag-diag-sub">%s</div></div>' % (k, v, s)
        for k, v, s in diag)
    return ('<div class="ag-goal">'
            '<div class="ag-goal-k">这一轮它给自己定的目标</div>'
            '<div class="ag-goal-v">%s</div>'
            '<div class="ag-goal-d">%s</div>'
            '<div class="ag-goal-c">已知取舍：%s</div>'
            '</div>'
            '<div class="ag-diag">%s</div>'
            % (_esc(g.get("label", "")), _esc(g.get("desc", "")),
               _esc(g.get("conflict", "")), diag_html))


def _fmt_days(v):
    return "—" if v is None else "%.1f 天" % float(v)


def _fmt_pct(v):
    return "—" if v is None else "%.0f%%" % (float(v) * 100)


# ── ③ 思考轨迹 ──────────────────────────────────────────

def render_trace(result: dict) -> str:
    """按阶段分组渲染思考项（只渲染 think，工具调用另有一块）。"""
    trace = result.get("trace", [])
    blocks = []
    cur_phase = None
    buf = []
    for e in trace:
        if e.get("kind") == "phase":
            if buf:
                blocks.append(_trace_group(cur_phase, buf))
                buf = []
            cur_phase = e
        elif e.get("kind") == "think":
            buf.append(e)
    if buf:
        blocks.append(_trace_group(cur_phase, buf))
    return ''.join(blocks)


def _trace_group(phase, items):
    label = phase["label"] if phase else ""
    icon = phase["icon"] if phase else "·"
    rows = ''.join(
        '<div class="ag-think %s">'
        '<div class="ag-think-dot">%s</div>'
        '<div class="ag-think-body">'
        '<div class="ag-think-t">%s</div>'
        '%s%s'
        '</div></div>'
        % (_level_class(it.get("level")), _esc(icon),
           _esc(it.get("title", "")),
           ('<div class="ag-think-d">%s</div>' % _esc(it["detail"]))
           if it.get("detail") else '',
           ('<div class="ag-think-c">结论：<b>%s</b></div>' % _esc(it["conclusion"]))
           if it.get("conclusion") else '')
        for it in items)
    return ('<div class="xm-card" style="margin-bottom:12px">'
            '<div class="xm-sec-title">%s · %s</div>%s</div>'
            % (_esc(icon), _esc(label), rows))


# ── ④ 工具调用 ──────────────────────────────────────────

def render_tools(result: dict) -> str:
    """本轮真实调用过的工具 + 被跳过的工具及理由（资源意识）。"""
    calls = [e for e in result.get("trace", []) if e.get("kind") == "call"]
    rows = []
    for c in calls:
        ok = c.get("ok")
        sym = "✓" if ok else "✗"
        kind = "green" if ok else "red"
        rows.append(
            '<div class="ag-tool">'
            '<div class="ag-tool-name">%s</div>'
            '<div class="ag-tool-meta">%s%s</div>'
            '<div class="ag-tool-why">%s</div>'
            '<div class="ag-tool-ms">%s&nbsp;ms</div>'
            '</div>' % (_esc(c.get("tool", "")),
                        _badge(c.get("category", ""), "neutral"),
                        _badge("%s %s" % (sym, c.get("cost", "")), kind),
                        _esc(c.get("why", "")),
                        format(float(c.get("elapsed_ms") or 0), ',.0f')))
    tools_html = ''.join(rows) or '<div class="xm-sm">本轮没有工具调用。</div>'

    # 被跳过的工具解释（来自规划阶段）
    skipped = []
    for e in result.get("trace", []):
        if e.get("kind") == "think" and "跳过" in (e.get("title") or ""):
            skipped.append(e)
    skip_html = ''
    for e in skipped:
        skip_html += ('<div class="ag-skip"><div>'
                      '<div class="ag-skip-t">%s</div>'
                      '<div class="ag-skip-d">%s</div>'
                      '<div class="ag-skip-d"><b>%s</b></div>'
                      '</div></div>' % (_esc(e.get("title", "")),
                                        _esc(e.get("detail", "")),
                                        _esc(e.get("conclusion", ""))))

    stat = result.get("stats", {})
    head = ('<div class="xm-sm" style="margin-bottom:10px">'
            '本轮共调用 <b>%d</b> 个工具，其中高成本 %d 个、失败 %d 个；'
            '合计耗时约 %s ms。'
            '</div>' % (stat.get("tool_calls", 0),
                        (stat.get("cost_counts") or {}).get("高", 0),
                        stat.get("failed_calls", 0),
                        format(float(stat.get("elapsed_ms") or 0), ',.0f')))
    return ('<div class="xm-card">'
            '<div class="xm-sec-title">它调用了哪些工具，为什么</div>'
            + head + tools_html + skip_html + '</div>')


# ── ⑤ 多候选博弈 ────────────────────────────────────────

def render_candidates(result: dict) -> str:
    cands = result.get("candidates", [])
    if not cands:
        return ''
    winner_tag = result.get("chosen", {}).get("tag")
    max_score = max((float(c.get("score") or 0) for c in cands), default=1.0)
    cards = []
    for c in cands:
        s = c.get("sim", {})
        bd = c.get("breakdown", {}) or {}
        win = " ag-cand-win" if c.get("tag") == winner_tag else ""
        obj = ''.join(
            '<div><div class="ag-obj-k">%s</div><div class="ag-obj-v">%+.2f</div></div>'
            % (_esc(k), float(v)) for k, v in bd.items())
        flags = ''.join('<span class="ag-flag">%s</span>' % _esc(f)
                        for f in (c.get("flags") or []))
        cards.append(
            '<div class="ag-cand%s">'
            '<div class="ag-cand-top">'
            '<div class="ag-cand-tag">%s</div>'
            '<div class="ag-cand-note">%s</div>'
            '%s'
            '<div class="ag-cand-score">%+.2f</div>'
            '</div>'
            '<div class="ag-cand-sub">'
            '沙盘推演 3 天：成本 %s · 断货 %d 次 · 积压 %.0f 件 · 民生保障 %s'
            '%s'
            '</div>'
            '<div class="ag-obj">%s</div>'
            '%s'
            '</div>'
            % (win, _esc(c.get("tag", "")), _esc(c.get("note", "")),
               _badge("胜出", "green") if c.get("tag") == winner_tag else '',
               float(c.get("score") or 0),
               _money(s.get("cost")), int(s.get("starvation_days") or 0),
               float(s.get("excess_units") or 0),
               _fmt_pct(s.get("livelihood_rate")),
               '（备货天数 ×%s）' % c.get("day_scale")
               if c.get("day_scale") not in (None, 1.0) else '',
               obj, flags))
    w = result.get("chosen", {})
    second = next((c for c in cands if c.get("tag") != winner_tag), None)
    lead = ''
    if second:
        lead = ('（领先第二名 %+.2f 分）' % (float(w.get("score") or 0)
                                          - float(second.get("score") or 0)))
    return ('<div class="xm-card">'
            '<div class="xm-sec-title">三套方案，沙盘推演后按策略打分</div>'
            '<div class="xm-sm" style="margin-bottom:12px">'
            '同一笔预算，三种花钱思路，都用沙盘预演 3 天。'
            '得分 = 收益 × %.0f%% + 抗风险 × %.0f%% + 保民生 × %.0f%%（本轮策略「%s」的权重）。'
            '胜出：候选 %s %s。'
            '</div>%s</div>'
            % (_w(result, "margin") * 100, _w(result, "resilience") * 100,
               _w(result, "livelihood") * 100,
               _esc(result.get("strategy", {}).get("label", "")),
               _esc(w.get("tag", "")), _esc(lead),
               ''.join(cards)))


def _w(result, key):
    return float(result.get("strategy", {}).get("weights", {}).get(key) or 0.0)


# ── ⑥ 反思 ──────────────────────────────────────────────

def render_reflection(result: dict) -> str:
    rf = result.get("reflection", {})
    parts = rf.get("confidence_parts", {})
    conf = float(rf.get("confidence") or 0.0)
    conf_html = (
        '<div class="ag-conf">'
        '<div><div class="ag-conf-k">本轮置信度</div>'
        '<div class="ag-conf-v">%.0f%%</div></div>'
        '<div class="ag-conf-parts">'
        '<div><div class="ag-diag-k">证据充分度</div><div class="ag-diag-v">%s</div>'
        '<div class="ag-diag-sub">历史窗口 %s 天</div></div>'
        '<div><div class="ag-diag-k">过程可靠性</div><div class="ag-diag-v">%s</div>'
        '<div class="ag-diag-sub">失败调用 %d 次</div></div>'
        '<div><div class="ag-diag-k">预算从容度</div><div class="ag-diag-v">%s</div>'
        '<div class="ag-diag-sub">钱够不够备齐</div></div>'
        '</div></div>'
        % (conf * 100, _fmt_pct(parts.get("evidence")),
           int(result.get("diagnosis", {}).get("evidence_days") or 0),
           _fmt_pct(parts.get("reliability")),
           int(result.get("stats", {}).get("failed_calls") or 0),
           _fmt_pct(parts.get("budget"))))

    crit = ''.join(
        '<li><div class="ag-list-n">%d</div><div>'
        '<div class="ag-list-t">%s</div>'
        '<div class="ag-list-d">%s</div></div></li>' % (i, _esc(c.get("title", "")),
                                                        _esc(c.get("detail", "")))
        for i, c in enumerate(rf.get("critiques", []), 1))
    nxt = ''.join(
        '<li><div class="ag-list-n">%d</div><div>'
        '<div class="ag-list-t">%s</div>'
        '<div class="ag-list-d">%s</div>'
        '%s</div></li>'
        % (i, _esc(a.get("action", "")), _esc(a.get("detail", "")),
           ('<span class="ag-trig">触发条件：%s</span>' % _esc(a.get("trigger", "")))
           if a.get("trigger") else '')
        for i, a in enumerate(rf.get("next_actions", []), 1))

    return (conf_html
            + '<div class="xm-card" style="margin-bottom:12px">'
            '<div class="xm-sec-title">自我批评：这一轮哪里没做好</div>'
            '<ul class="ag-list">%s</ul></div>' % crit
            + '<div class="xm-card">'
            '<div class="xm-sec-title">下一轮改进项：具体、可执行</div>'
            '<ul class="ag-list">%s</ul></div>' % nxt)


# ── 动作与页脚 ──────────────────────────────────────────

def render_actions(result: dict) -> str:
    acts = result.get("actions", [])
    if not acts:
        return ''
    rows = ''.join(
        '<li><div class="ag-list-n">%d</div><div>'
        '<div class="ag-list-t">%s</div>'
        '<div class="ag-list-d">%s</div></div></li>'
        % (i, _esc(a.get("action", "")), _esc(a.get("detail", "")))
        for i, a in enumerate(acts, 1))
    return ('<div class="xm-card" style="margin-top:12px">'
            '<div class="xm-sec-title">这一轮落地的动作</div>'
            '<ul class="ag-list">%s</ul></div>' % rows)


def render_foot(result: dict) -> str:
    p = result.get("path", {})
    return ('<div class="ag-foot">'
            '本轮路径摘要：目标「%s」→ 策略「%s」→ 调用 %d 次工具'
            '（客流评估：%s）→ 候选 %s 胜出 → 置信度 %.0f%%。<br>'
            '同一份代码换个日期或预算，这条路径就会不一样 —— '
            '这才是「自主决策」而非「流程演示」的可验证证据。'
            '</div>'
            % (_esc(p.get("goal", "")), _esc(p.get("strategy", "")),
               int(p.get("tools_called") or 0),
               '做了' if p.get("traffic_assessed") else '未做',
               _esc(p.get("winner", "")),
               float(p.get("confidence") or 0) * 100))


# ── 总装 ────────────────────────────────────────────────

def render_page(result: dict, head_only: bool = False) -> str:
    """把整页拼起来。result 为 `run_agent()` 的真实返回。"""
    if not result:
        return ('<div class="xm-page"><div class="ag-head"><div>'
                '<div class="xm-h1">Agent 决策台</div>'
                '<div class="xm-page-sub">选个决策日和预算，点「让它自己决策」</div>'
                '</div></div>'
                '<div class="ag-empty">'
                '<div class="ag-empty-t">它还没开始想</div>'
                '<div class="ag-empty-d">给它一个决策日和一个预算上限，'
                '它会自己诊断店况、自己定目标、自己挑打法，'
                '把中间每一步的判断依据都摊开给你看。</div>'
                '<div class="ag-empty-h">感知 PERCEIVE → 推理 REASON → '
                '规划 PLAN → 执行 ACT → 反思 REFLECT</div>'
                '</div></div>')
    if head_only:
        return render_head(result)
    return ('<div class="xm-page">'
            + render_head(result)
            + render_loop(result)
            + render_goal(result)
            + '<div class="xm-split"><div class="xm-main-col">'
            + render_trace(result)
            + '</div><div class="xm-rail">'
            + render_tools(result)
            + render_actions(result)
            + '</div></div>'
            + render_candidates(result)
            + render_reflection(result)
            + render_foot(result)
            + '</div>')
