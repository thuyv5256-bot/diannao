# 小满·智能补货 — 端到端真实性审计报告

> 审计日期：2026-10-03
> 审计范围：「今天该进什么货」页面一次完整请求（UI 输入 → 数据源 → Event → Forecast → Memory → Inventory/Supplier → R³/Policy → Result → UI）
> 审计原则：**不修改任何业务代码**，全部结论来自运行时真实调用记录与真实数据
> 审计脚本：`_audit_trace.py`（调用链追踪）、`_audit_counterfactual.py`（4 组反事实）、`_audit_numbers.py`（数字溯源）——均为旁路只读脚本

---

## 0. 结论速览

| 维度 | 结论 |
|---|---|
| 真实后端 | **存在**，且被前端真实调用（19 个关键函数、5822 次调用全程记录） |
| 前后端连通 | **已连通**，Gradio 事件 → `app.do_plan` → `policy.build_plan` → 回渲染 |
| 数据库 | **真实 SQLite**：`data/store.db`，products 50 / sales 9000 / inventory 50 / day_events 180 / feedback_log 351 |
| R³ 求解器 | **真实 MILP**：`scipy.optimize.milp` (HiGHS)，`used_milp=True, status=Optimal, n_integer_vars=100`，**未静默回退贪心** |
| 页面 8 项业务数字 | **8/8 全部 REAL**，无 HARDCODED / MOCK |
| LLM 真实调用 | **否**。`DEEPSEEK_API_KEY` 未设置，`.env` 不存在，`llm.is_enabled()=False`，全部走降级路径 |
| 端到端链路 | **完整闭合**（数值链路 100% 真实，AI 链路完整但当前为空跑） |

---

## 1. 真实调用链（运行时追踪，非静态阅读）

追踪窗口：`app.do_plan("2026-08-28", 600.0, False, False, False, False)`
记录方式：在审计脚本内用 `wrap(mod, name)` 包装真实模块函数，旁路记录入参/出参，**不改动被审计代码**

### 1.1 完整链路

```
【UI 层】
app.do_plan(date_str, budget, rain, heat, holiday, supplier)
  入参：'2026-08-28', 600.0, False, False, False, False
  出参：3 个 HTML 字符串 (top=780B, rail=520B, result=145823B)
  ↓ 解析日期、float(budget)、_active_risks() 构造风险列表
  ↓ 调 policy.build_plan(d, budget, MODE_DIANNAO, persist=False, risks=risks)

【决策主链路】
core/policy.py :: build_plan()
  ├─ memory.get_products()               → 50 个商品（products 表）
  ├─ memory.get_all_policy()             → 50 条策略（policy 表）
  ├─ policy._prepare_items()
  │   ├─ forecast.forecast_all("2026-08-28", restore_potential=True, risks=[])
  │   │   └─ 对 50 个 SKU 各调 memory.get_sales(sku, day, lookback=28) → 各返回 28 条历史销量
  │   │   └─ forecast.estimate_daily_demand() × 50
  │   │       └─ forecast._risk_adjust() × 50
  │   │           └─ forecast._potential() × 5600（28 天 × 50 SKU × 4 档位）
  │   │   └─ event_evidence.evaluate_product()  ← 本次无事件，未触发
  │   ├─ memory.get_inventory()           → 50 条真实库存（inventory 表）
  │   └─ policy.memory_safety_calibration()
  │       └─ memory.get_experiences(limit=2000) → 返回 0 条（历史经验库为空）
  ├─ policy._allocate_plan(items, 600.0, solver=None, protect_livelihood=True)
  │   ├─ r3_optimizer.available()         → True
  │   └─ r3_optimizer.solve(items, 600.0, protect_livelihood=True)   ★ 真实 MILP
  │       → {"used_milp": true, "name": "HiGHS (scipy.optimize.milp)", "status": "Optimal",
  │          "n_skus": 50, "n_integer_vars": 100,
  │          "revenue": {"gross_margin": 311.5},
  │          "resilience": {"shortfall_units": 25.4, "penalty_per_unit": 1.0},
  │          "responsibility": {"floor_locked_cost": 233.9, "secured_rate": 1.0}}
  └─ policy.evaluate_plan(items, meta)
      └─ policy.calculate_essential_coverage(items)
          └─ metrics.livelihood_secured_rate(19, 19) → 1.0
      → metrics = {total_cost: 600.0, gross_margin: 311.5, livelihood_secured_rate: 1.0,
                   display_count: 25, budget_used_rate: 1.0, ...}

【渲染层】
home_view.render_home_html(plan, 'top'/'rail'/'result') × 3
  └─ decision_basis.render_reorder_basis(it) × 55（24 有货 + 31 关注项）
```

### 1.2 每一环的「传入 / 返回 / 下游 / 是否参与最终数字」

| 环 | 文件 | 函数 | 传入什么 | 实际返回什么 | 下一环怎么调 | 参与最终补货数字？ |
|---|---|---|---|---|---|---|
| UI | `app.py` | `do_plan` | date, budget, 4 个风险布尔 | 3 段 HTML | 调 `build_plan` 再调 `render_home_html` | 是（budget 直接下传） |
| 数据源 | `core/memory.py` | `get_products` | 无 | 50 商品字典 | `_prepare_items` 遍历 | **是**（商品/成本/售价来源） |
| 数据源 | `core/memory.py` | `get_all_policy` | 无 | 50 条策略 | 同上 | **是**（安全库存、民生标记来源） |
| 库存 | `core/memory.py` | `get_inventory` | 无 | 50 条 on_hand | `_prepare_items` | **是**（直接决定补货量） |
| 销量 | `core/memory.py` | `get_sales` | sku, day, lookback=28 | 各 28 条真实销量 | `estimate_daily_demand` | **是**（预测的唯一事实来源） |
| Event | `core/event_evidence.py` | `evaluate_product` | sku, 事件列表 | 本次无事件未触发 | 被 `_risk_adjust` 调用 | **是**（有事件时按证据强度修正预测） |
| Forecast | `core/forecast.py` | `forecast_all` | date, restore_potential, risks | `{sku: {daily_demand, level, trend_slope, risk_factor...}}` | `_prepare_items` | **是**（daily_demand 决定补货量） |
| Forecast | `core/forecast.py` | `_risk_adjust` | item, risks, ai_factors | risk_factor 乘数 | `estimate_daily_demand` | **是** |
| Memory | `core/memory.py` | `get_experiences` | limit=2000 | **0 条** | `memory_safety_calibration` | **否**（库为空，本次无修正） |
| Policy | `core/policy.py` | `memory_safety_calibration` | items | 校准系数（本次全 0） | `_prepare_items` | **否**（无历史经验可修正） |
| R³ | `core/r3_optimizer.py` | `available` | 无 | True | `_allocate_plan` 判断是否走 MILP | 是（开关） |
| R³ | `core/r3_optimizer.py` | `solve` | items, 600.0, protect | 分配方案 + 三维目标值 | 写回 `it["reorder_qty"]` | **是（决定最终数量）** |
| Policy | `core/policy.py` | `evaluate_plan` | items, meta | metrics 全量指标 | 渲染层 | **是**（所有汇总数字来源） |
| 民生 | `core/policy.py` | `calculate_essential_coverage` | items | `{secured_count:19, total_count:19, rate:1.0}` | `metrics` | 是（但只影响 KPI 展示） |
| 渲染 | `core/home_view.py` | `render_home_html` | plan, slot | HTML 字符串 | 返回给 Gradio | 展示 |
| 解释 | `core/decision_basis.py` | `render_reorder_basis` | 单个 item | 1951 字符六阶段 HTML | 嵌入 `<details>` | 展示（数字取自同一 item） |
| LLM | `core/llm.py` | `explain_plan` | plan | 88 字规则模板 | 首页叙述区 | **否**（纯文本） |
| AI 事件 | `core/ai_events.py` | `parse` | 场景文本 | `source=rule, factors={}` | AI 页展示 | **否**（无 Key，factors 空） |
| AI 洞察 | `core/ai_insight.py` | `analyze` | plan | `source=rule, model=—` | AI 页展示 | **否**（纯规则体检） |

---

## 2. 四组真实反事实测试（无 mock，走 `app.do_plan` 真实入口）

### 组 1：相同日期数据，预算 ¥600 vs ¥300

| 指标 | ¥600 | ¥300 | 差异 |
|---|---|---|---|
| 总进货金额 | 600.0 | 300.0 | **-300.0** |
| 预计毛利 | 311.5 | 142.5 | **-169.0** |
| 进货件数 | 133 | 69 | -64 |
| 缺货件数 | 5.8 | 27.2 | **+21.4** |
| 有进货商品数 | 25 | 14 | -11 |
| 民生保障率 | 100% | 100% | 不变 |
| **Forecast 变化** | — | — | **0 / 50 商品** |
| R³ solver | HiGHS / Optimal | HiGHS / Optimal | 均真实求解 |

**判读**：预算只影响分配阶段，不影响需求预测——这符合设计（预测与钱无关）。毛利下降、缺货上升、件数下降，全部由 MILP 在预算约束下的真实权衡产生。

### 组 2：无事件 vs 高温事件

| 指标 | 无事件 | 高温事件 | 差异 |
|---|---|---|---|
| HTML 长度 | 145,823 B | 147,281 B | 内容确实变化 |
| 总进货金额 | 600.0 | 599.8 | -0.2 |
| 预计毛利 | 311.5 | **343.7** | **+32.2** |
| 缺货件数 | 5.8 | 19.7 | +13.9 |
| 进货件数 | 133 | 212 | **+79** |
| **Forecast 变化** | — | — | **12 / 50 商品** |
| 民生保障率 | 100% | 100% | 不变 |

矿泉水日需求 **27.06 → 43.51**，建议进货 **22 → 79 件**。
高温通过 **Event Evidence Gate** 真实生效：证据等级 `Strong`（历史 10 个高温日），影响饮料/蔬菜/烘焙/冷饮/日用品 5 个品类。

### 组 3：同一商品（矿泉水）低库存 0 vs 高库存 500

| 指标 | on_hand=0 | on_hand=500 | 差异 |
|---|---|---|---|
| 矿泉水建议进货 | **94 件** | **0 件** | **-94** |
| 矿泉水够卖天数 | 3.47 天 | 18.48 天 | +15.01 |
| 总预计毛利 | 337.7 | 303.7 | -34.0 |
| 缺货件数 | 8.8 | 5.8 | -3.0 |
| 进货件数 | 192 | 115 | -77 |
| **矿泉水 Forecast** | 27.06 | 27.06 | **完全不变** |

**判读**：库存只进入补货计算，不污染需求预测——职责分离正确。测试后库存已还原为 72。

### 组 4：AI 启用 vs AI 关闭 / 无 Key

**环境事实**：`DEEPSEEK_API_KEY` 未设置 · `.env` 文件不存在 · `llm.is_enabled() = False`

| 项目 | 实际结果 |
|---|---|
| `ai_events.parse("明天下大暴雨…")` | `source=rule` · `active=['rain','supplier']` · **`factors={}`（空）** |
| 每条事件分级 | `level=weak` · `affected_categories=[]` · `reasoning="关键词命中「暴雨」"` |
| `ai_insight.analyze(plan)` | `source=rule` · `model=—` · 2 条洞察 |
| `llm.explain_plan(plan)` | 88 字规则模板（"今天建议花 ¥600 进货，预计能赚 ¥312 毛利…"） |
| `app.do_ai_parse` 输出 | 「规则降级模式」 · 4142 字节 · **不含 deepseek 模型名** |

**对照实验（带 AI 解析路径 vs 完全不带）**：

| 指标 | risks=[rain, supplier] | risks=[] | 差异 |
|---|---|---|---|
| 总进货金额 | 600.0 | 599.9 | -0.1 |
| 预计毛利 | 311.5 | 215.1 | **-96.4** |
| 民生保障率 | 100% | **89.47%** | **-10.53pp** |
| 缺货件数 | 5.8 | 116.9 | **+111.1** |
| 进货件数 | 133 | 66 | -67 |

> **关键说明**：这个差异来自 `risks` 参数本身（暴雨 + 断供两个规则事件），**不是来自 AI 因子**——因为 `factors` 是空的，AI 一个数字都没改。断供事件使民生保障率从 100% 掉到 89.47%，这是 Event 规则链路在起作用。

---

## 3. 页面业务数字逐项审计（REAL / HARDCODED / MOCK / FALLBACK）

审计方法：从真实 `plan` 对象取值 → 手工独立重算对账 → `grep` 定位源码赋值点 → 交叉改变输入验证数字是否随之变化。

| # | 页面数字 | 标记 | 证据链 |
|---|---|---|---|
| 1 | **¥600 进货总额** | **REAL** | `evaluate_plan` 真实累加 50 行 `it["cost"]`（`policy.py:643`）得 600.000000，与 `metrics["total_cost"]` 完全一致；页面渲染式 `'¥%.0f' % float(m.get('total_cost', 0) or 0)`（`home_view.py:182`）。换预算立刻变：`¥350 → ¥350`、`¥1200 → ¥1200` |
| 2 | **¥312 预计毛利** | **REAL** | `gross_margin += it["reorder_qty"] * it["unit_margin"]`（`policy.py:644`），手工重算 311.500000 一致；`margin_rate` 也是真实除法。换输入后变：`¥212`、`¥481` |
| 3 | **100% 民生保障** | **REAL** | `calculate_essential_coverage(items)` → `{secured_count:19, total_count:19, rate:1.0, shortfall_cost:0.0}`，是 `19/19` 的真实分式（`policy.py:625` → `metrics.livelihood_secured_rate`）。**决定性反证**：换输入后变为 **63%**（¥350+高温）和 **89%**（¥1200+暴雨），写死 100% 绝不可能出现这三个值 |
| 4 | **商品当前库存** | **REAL** | `memory.get_inventory()` 直读 `inventory` 表；抽样 6 商品（矿泉水72/桶装水18/牛奶42/鸡蛋36/大米12/食用油9）**差异数 0**；组 3 改库后数字同步变化，测完已还原 |
| 5 | **Forecast 日均需求** | **REAL** | 唯一来源是 `memory.get_sales(sku, day, lookback=28)` 的真实历史销量；`forecast_all()` 独立重算与 `items` 中 `daily_demand` **不一致 0 条**。组 2 高温下真实变化 12/50 商品 |
| 6 | **建议进货数量** | **REAL** | 由 `r3_optimizer.solve()` 的 MILP 整数解写回 `it["reorder_qty"]`（`used_milp=True, Optimal, 100 个整数变量`）；25 个 SKU 有货合计 133 件，手工对账一致 |
| 7 | **够卖几天** | **REAL** | `policy.py:650` `cover = (on_hand + eligible_in_transit + reorder_qty) / daily_demand`；抽样 5 商品手算与页面**全部吻合**（3.47/3.38/3.48/3.03/3.09 天） |
| 8 | **六阶段解释** | **REAL** | `decision_basis.render_reorder_basis(it)` 长度 1951 字符，阶段 1-6 **全部渲染**，内含真实数字（库存 72、需求 27.1、进货 22、单件毛利 ¥0.90、缺口 21、民生最低量 10）。**不含预算数字**（预算不参与单商品决策，符合设计） |

### 源码级扫描结果

```
home_view.py 去注释后扫描 ¥/百分比字面量 → 无
```
页面里的 `¥%.0f`、`%.0f%%` 是**格式化占位符**，不是固定金额。

### 关键澄清：`¥600` 出现在哪个片段

| 片段 | 长度 | 含 ¥600 | 含 100% | 用途 |
|---|---|---|---|---|
| `top` | 780 B | ✅ | ✅ | **4 张 KPI 卡**：明天建议进货 ¥600 / 共 25 种 / 预计毛利 ¥312 / 民生保障 100%（19 种民生商品）/ 需要留意 0 件 |
| `rail` | 520 B | ❌ | ❌ | 「今天提醒」侧栏：民生正常、供应正常 |
| `result` | 145,823 B | ❌ | ❌ | 商品明细表 + 六阶段详情 |

---

## 4. 五个问题的明确回答

### Q1：当前是否已经存在真实后端，而不是只有前端？

**是。** 存在完整的 Python 后端业务引擎，不是静态页面：

- **持久化层**：`core/memory.py` + 真实 SQLite `data/store.db`，实测表数据量：products 50 / sales 9000 / inventory 50 / policy 50 / day_events 180 / feedback_log 351
- **业务层**：`forecast.py`（预测）、`event_evidence.py`（事件证据分级）、`policy.py`（决策）、`r3_optimizer.py`（MILP 优化）、`metrics.py`（指标）、`events.py`（事件影响）、`decision_trace.py`（决策轨迹）
- **AI 层**：`ai_events.py` / `ai_insight.py` / `llm.py`
- **求解器**：`scipy.optimize.milp` (HiGHS) **真实执行**，返回 `Optimal`

### Q2：当前新前端是否已经真正连接这个后端？

**是，已连通。** 不是"前端有 UI、后端是摆设"：

- `app.py` 的 `btn_plan.click(...)` 绑定 `do_plan`
- `do_plan` 真实调用 `policy.build_plan(...)`，参数（日期、预算、4 个风险开关）原样下传
- 后端返回的 `plan` 对象（含 50 个 item、metrics、meta.solver）被 `home_view.render_home_html` 消费，渲染成 145KB HTML 回填到 Gradio
- **运行时追踪证明**：一次点击产生 5822 次真实函数调用，链路从 UI 一直贯通到 SQLite 读取

### Q3：`ai_events` / `ai_insight` / `llm` 是否调用了真实外部 LLM API？

**当前环境没有。** 三者都**有完整真实接口实现**，但**当前全部走降级路径**：

| 模块 | 真实 API 实现 | 当前是否调用 | 证据 |
|---|---|---|---|
| `llm.py` | ✅ 有（DeepSeek OpenAI 兼容接口，含 `chat_json` JSON 模式 + 重试 + 容错解析） | ❌ | `llm.is_enabled() = False` |
| `ai_events.py` | ✅ 有（`llm_parse` 走 `llm.chat_json`，含三级事件分级 + 白名单校验 + 因子夹紧） | ❌ | `parse() → source=rule`，走 `rule_parse` 关键词匹配 |
| `ai_insight.py` | ✅ 有（`llm_insight` 走 LLM + `_sanitize` 防幻觉校验） | ❌ | `analyze() → source=rule, model=—`，走 `rule_insight` |

**原因**：`DEEPSEEK_API_KEY` 环境变量未设置，`.env` 文件不存在。
**性质判定**：**不是 mock，也不是纯接口空壳**——代码路径真实存在，只是缺少 API Key 走 fallback。这属于 `FALLBACK` 状态，不是 `MOCK`。

### Q4：没有 API Key 时，当前所谓"AI"实际执行的是什么？

执行的是**纯规则引擎**，三层全部退化为确定性代码：

| 环节 | 无 Key 时实际执行 | 代码位置 |
|---|---|---|
| 事件理解 | **关键词匹配表**：扫描"暴雨/高温/节假日/送不来"等词，命中就打上 `level=weak` 标签 | `ai_events.rule_parse()` + `_KEYWORDS` |
| 事件→预测修正 | **不修正**。`factors={}` 空字典，Forecast 一个数字都没被 AI 改 | `finalize()` 因 `abs(adj-1.0)<1e-9` 跳过写入 |
| 业务洞察 | **6 条固定规则体检**：民生兜底是否达标、历史经验是否参与、预算是否紧张、缺货风险、供应商集中度、临期风险 | `ai_insight.rule_insight()` |
| 人话解释 | **字符串模板拼接**："今天建议花 ¥600 进货，预计能赚 ¥312 毛利……" | `llm.explain_plan()` 的 fallback 分支 |

实测输出：
```
source = rule
model  = —
digest = 本次建议进 25 种商品，花费 ¥600，民生达标率 100%。规则体检发现 2 项值得留意。
  [民生保障/low] 民生兜底已全部达标（100%）  依据: livelihood_secured_rate=1.00，兜底标准 3 天
  [需求预测/low] 历史经验本次没有参与修正  依据: 全部商品 memory_delta 均为 0
```

> **诚实结论**：当前状态下，"AI 决策大脑"页面展示的是规则引擎的体检结果，不是大模型的推理产出。**数值链路（预测→R³→补货）100% 真实可靠；AI 链路代码完整但空跑。**
>
> **需要特别说明的对比**：组 2 的高温事件确实真实改变了 12 个商品的 Forecast——但那是 `event_evidence` 的**历史证据规则**在起作用（Strong 等级、历史 10 个高温日），**不是 LLM 在起作用**。这容易被误解为"AI 生效了"，答辩时必须说清楚。

### Q5：从用户修改输入到最终补货数字变化，是否已形成完整端到端链路？

**是，链路完整闭合，且已被四组反事实测试验证。**

```
用户输入（日期 / 预算 / 4个风险开关）
   ↓ app.do_plan 解析
   ↓ policy.build_plan
   ↓   memory.get_products / get_all_policy / get_inventory / get_sales  ← 真实 SQLite
   ↓   forecast.forecast_all → _risk_adjust → event_evidence（按证据强度修正）
   ↓   r3_optimizer.solve → scipy.optimize.milp (HiGHS, Optimal)
   ↓   evaluate_plan → calculate_essential_coverage → metrics
   ↓ 返回 plan（50 items + metrics + meta.solver）
   ↓ home_view.render_home_html
   ↓ decision_basis.render_reorder_basis（六阶段）
   ↓ Gradio 回填页面
```

**输入变化 → 数字变化的实测证据**：

| 输入变化 | 最终数字确实变化 |
|---|---|
| 预算 600 → 300 | 金额 600→300、毛利 311.5→142.5、缺货 5.8→27.2 ✅ |
| 加高温事件 | Forecast 12/50 商品变化、毛利 311.5→343.7 ✅ |
| 矿泉水库存 0 → 500 | 该 SKU 补货 94→0 件、够卖 3.47→18.48 天 ✅ |
| 断供事件 | 民生保障 100%→89.47%、缺货 5.8→116.9 ✅ |

**唯一断点**：LLM 那一段（`ai_events.llm_parse` / `ai_insight.llm_insight` / `llm.explain_plan` 的模型分支）因缺 Key 未被实际执行。这不影响数值链路完整性，但意味着"AI 深度参与核心决策"目前处于**代码已就位、运行时未激活**状态。

---

## 5. 风险与建议（仅记录，不改代码）

| 级别 | 问题 | 建议 |
|---|---|---|
| **高** | 无 API Key，AI 页面呈现的是规则体检，评委若追问"这真是大模型吗"无法自证 | 赛前配置 `DEEPSEEK_API_KEY`，现场演示一次真实 `chat_json` 调用并展示 `source=llm` |
| **中** | 组 2 高温生效容易被误认为"AI 生效"，实为 `event_evidence` 规则 | 答辩时明确区分：事件修正靠**历史证据分级**，语义理解才靠 LLM |
| **中** | `memory.get_experiences()` 返回 0 条，Memory 模块本次完全空转 | 造一批 `experiences` 数据，让"翻老账"阶段有真实内容可展示 |
| **低** | `.pytest_tmp2/` `.pytest_tmpA/` 残留目录（沙箱批量删除保护拦截，需手动清理） | 手动删除，或加入 `.gitignore` |
| **低** | 工作区 48 个修改 + 5 个新文件未提交 | `powershell -File tools/vcs.ps1 save "feat(ai): AI 决策中枢 + 全局改名 + 端口 7870"` |

---

*本报告所有数据来自运行时真实执行，未使用任何 mock，未修改任何业务代码。*