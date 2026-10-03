# TRD — 小满 · 技术需求与设计文档

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-10-03 |
| 对应代码基线 | git `ca17f07`（单次提交）+ 未提交的 UI v2 迁移改动 |
| 面向读者 | 接手开发者 / 评审技术方 / 后续 Agent |
| 相关文档 | [PRD](PRD.md) · [ARD](ARD.md) · [../CLAUDE.md](../CLAUDE.md) · [../DESIGN.md](../DESIGN.md) |
| 说明 | 本文档描述**当前真实实现**（以代码为准），不是理想设计图；与代码不一致处已在 §13 记录 |

---

## 1. 系统总览

### 1.1 运行形态

单进程 Python 应用。三种运行方式共用同一份 `core/` 决策引擎：

| 入口 | 命令 | 用途 |
|---|---|---|
| 网页应用 | `python app.py` → `http://127.0.0.1:7861` | 店主日常使用（7 个标签页） |
| 闭环演示 | `python demo_flow.py` | 答辩五幕一次性跑通 |
| 离线评测 | `python eval.py` | 60 天窗口 × 5 种决策方式对照 |
| 长期实验 | `python run_digital_store.py` | 180 天 × 5 策略仿真 + 消融 + 压力测试 |
| 事件 A/B | `python run_event_awareness_ab.py` | 事件感知价值验证 |
| 数据重置 | `python seed_data.py` | 清空记忆库并从 CSV 重导入 |
| 版本/备份 | `powershell -File tools/vcs.ps1`（status / save / verify / rollback / release） | 本地 Git 备份：裸仓库 `_backup/diannao.git` 作为 `origin`，无 GitHub；策略见 [VERSIONING](VERSIONING.md) |

**端口与环境变量**：`PORT` 存在 → 绑 `0.0.0.0:PORT`（云平台反向代理）；否则 `127.0.0.1:HOST_PORT(默认 7861)`。
**Gradio 版本兼容**：`GR_MAJOR >= 6` 时 `css/theme` 走 `launch()`，否则走 `Blocks()`；`>=5` 强制 `ssr_mode=False`（云沙箱无 Node.js）。

### 1.2 分层架构

```text
┌── 展示层 ─────────────────────────────────────────────────────────────┐
│ app.py（装配：7 Tab + 事件绑定）                                       │
│ core/*_view.py（home/why/feedback/learn/ledger/final/about 渲染）      │
│ core/ui_theme.py（UI v2 tokens/CSS 唯一来源）  core/llm.py（可选解释） │
├── 决策层 ─────────────────────────────────────────────────────────────┤
│ core/policy.py（目标库存 → 三层惠民约束 → 计划+指标）                   │
│ core/r3_optimizer.py（R³ 两阶段字典序 MILP，失败回退贪心）              │
│ core/decision_trace.py / decision_basis.py（可解释性输出）              │
├── 推断层 ─────────────────────────────────────────────────────────────┤
│ core/forecast.py（EWMA×星期×节日×趋势，断货还原）                       │
│ core/events.py（历史事件日历 + 品类影响倍数，现算）                     │
│ core/event_evidence.py（证据门控 strong/weak/insufficient）             │
│ core/risk.py（风险键规范化）  core/metrics.py（指标口径唯一来源）        │
├── 记忆层 ─────────────────────────────────────────────────────────────┤
│ core/memory.py（SQLite 9 表 + 迁移 + 幂等 uid）                         │
│ core/evolution.py（反馈 → 经验 → 在线校准 → 进化轨迹）                  │
│ core/dataset.py（CSV 清洗与导入，唯一数据入口）                         │
│ core/analysis.py（客流带动实证：民生缺货 → 非民生销量下滑）              │
├── 实验层 ─────────────────────────────────────────────────────────────┤
│ core/simulator.py（180 天长期仿真：5 策略 / FEFO / 保质期 / 断供强制）   │
│ core/eval_core.py（60 天离线评测引擎）  run_*.py  *_step*.py（一次性脚本）│
└───────────────────────────────────────────────────────────────────────┘
                        ▼
              data/shopmind_*.csv  →  data/store_memory.db
              eval/**（实验产物）；eval/final/**（只读冻结证据）
```

### 1.3 模块职责与规模（代码行数按文件字节估算）

| 模块 | 职责 | 被谁调用 |
|---|---|---|
| `core/memory.py` (26KB) | 全部持久化：9 张表、迁移、幂等去重、统计 | 几乎全部模块 |
| `core/policy.py` (39KB) | 单商品需求分解 `_prepare_items` + 预算分配 `_allocate` / `_allocate_plan` + 方案 `build_plan` | app / demo_flow / simulator / eval_core / agent |
| `core/simulator.py` (40KB) | 长期仿真环境（批次/FEFO/报损/在途/断供）+ 5 策略 + 压力/消融与出图 | run_digital_store / run_event_awareness_ab / app |
| `core/evolution.py` (16KB) | 反馈幂等沉淀为经验；算校准变化并写进化轨迹 | app / simulator / eval_core |
| `core/forecast.py` (10KB) | 需求预测全链路（含推导字段供页面展示） | policy |
| `core/events.py` (12KB) / `event_evidence.py` (12KB) | 事件日历、影响倍数、证据门控 | forecast / policy / agent / decision_trace |
| `core/r3_optimizer.py` (11KB) | MILP 建模与求解（scipy/HiGHS） | policy |
| `core/app.py` (63KB) | Gradio 装配 + 若干内联渲染函数 | 网页入口 |
| `core/*_view.py` | 纯渲染函数（返回 HTML 字符串，无副作用） | app |
| `core/eval_core.py` (10KB) | 60 天重演评测引擎 + 图表 | eval.py / app |

---

## 2. 数据层

### 2.1 数据源（只读，仿真数据）

| 文件 | 规模 | 字段 |
|---|---|---|
| `data/shopmind_products_50sku.csv` | 50 行 | `item_id, product_name, category, price, cost, essential, shelf_life_days, supplier, lead_time_days, base_daily_demand` |
| `data/shopmind_180days_50sku.csv` | 9000 行（180 天 × 50 SKU） | 上述 + `date, sales, weather, temperature_c, event, is_weekend, supplier_available` |

日期范围 `2026-03-01 ~ 2026-08-27`；19 个 `essential=1` 民生商品；品类分布：日用品10 / 零食6 / 饮料5 / 方便食品5 / 粮油4 / 调味4 / 水果3 / 蔬菜3 / 乳品2 / 烘焙2 / 冷饮2 / 应急用品2 / 生鲜1 / 冷冻食品1。

### 2.2 字段映射（`core/dataset.py`）

| CSV | 记忆库 | 备注 |
|---|---|---|
| `item_id` → `sku`；`product_name` → `name`；`price` → `sell_price`；`cost` → `cost_price`；`essential` → `is_livelihood` | products | 直接映射 |
| `date` → `day`；`sales` → `qty_sold` | sales | `qty_stockout` / `qty_spoilage` **导入恒为 0**（CSV 未记录，由店主录入） |
| `weather / temperature_c / event / is_weekend / supplier_available` | day_events | 每日一行 |
| 缺失字段 `unit / pack_size / traffic_pull` | 确定性推断 | 单位按 SKU 白名单；`traffic_pull` 按品类表；`pack_size` 按品类/价格确定性推导，**禁止随机** |
| 初始库存 | `INIT_INVENTORY_DAYS = 3.0 × 基础日均需求` | 供首日决策冷启动 |

### 2.3 记忆库（SQLite，`data/store_memory.db`，已 gitignore）

9 张表（DDL 全文见 `core/memory.py: SCHEMA`）：

| 表 | 主键/唯一 | 用途 |
|---|---|---|
| products | sku | 商品档案（含 `base_daily_demand`、`traffic_pull`） |
| policy | sku | **基础**策略参数（`base_days / safety_factor / version / updated_at`）——不回写反馈 |
| sales | (day, sku) | 历史销量（CSV 导入，不断货/损耗） |
| inventory | sku | 当前在手量 |
| day_events | day | 天气/温度/事件/周末/供应商可用 |
| experiences | id + **uid 唯一索引** | 经营经验（含 `lesson / adjustment` 文案字段） |
| feedback_log | id + **uid 唯一索引** | 每次提交的经营结果全量留痕（含 `submission_id`） |
| evolution_log | id | 真正发生校准变化的轨迹（old_value/new_value/trigger/reason） |
| plan_log | id | 每次落库的补货计划明细（persist=True 时写） |

- **幂等**：`_stable_uid(day, sku, sold, stockout, spoilage)` 取 SHA1 前 16 位；经验与反馈均建唯一索引，重复提交不产生重复记录。
- **迁移**：`_migrate()` 负责为历史库补列/补索引；`_dedup_learning()` 清理重复学习行。
- **重置**：`reset_all()` / `python seed_data.py`。

---

## 3. 推断层

### 3.1 需求预测（`core/forecast.py`）

```text
潜在需求 p = qty_sold + qty_stockout            （restore_potential=True 时）
基准 level = Σ wᵢ·pᵢ / Σ wᵢ ,  wᵢ = (1 − DECAY_ALPHA)^age   （DECAY_ALPHA=0.06，age=0 为最新）
趋势 trend_mult = clamp(1 + slope×TREND_HORIZON, 0.75, 1.35) （≥7 样本才启用）
星期 wd_factor  = 同星期几均值 / 全体均值         （夹在合理区间，见 weekday_profile）
节日 h_factor   = 品类 × 节日日历（HOLIDAYS）；"holiday" 风险激活时取 1.0（避免重复计入）
事件 risk_mult  = event_evidence 门控后的品类/SKU 系数（见 §3.2）
daily = level × trend_mult × wd_factor × h_factor × risk_mult
```

- **冷启动**（无历史记录）：`daily = base_daily_demand × risk_mult`，返回 `cold_start=True`。
- 返回结构含完整推导字段（`level / weekday_factor / holiday_factor / trend_multiplier / risk_factor / risk_note / potential_total`），供"为什么这样进"直接展示，**不允许页面另算**。

### 3.2 事件与证据门控

**`core/events.py`**：按「同星期几」做基线，算事件日实际需求相对基线的倍数；夹紧 `[MULT_MIN, MULT_MAX] = [0.5, 1.8]`；带缓存（`clear_impact_cache()`）。供应商断供属供给侧，不进需求系数。

**`core/event_evidence.py`**：把"检测到就乘固定倍率"升级为"先验证据，再决定是否进入预测"。

| 等级 | 判定 | 行为 |
|---|---|---|
| strong | 事件样本 ≥3、可比普通日 ≥5、`|uplift−1| ≥ 0.05`、方向一致性 ≥0.67、log 空间 t 区间不含 1 | 允许乘进预测 |
| weak | 有信号但样本不足/方向不稳/效应过小 | 保持基础预测，仅记风险提示 |
| insufficient | 样本极少/首次出现/无可比基线 | 同上 |

可比普通日口径：事件为"正常"、与事件日**同星期几**、落在事件日 ±45 天内，剔除其它事件日污染。参数：`EVIDENCE_MIN_EVENT_SAMPLES=3`、`EVIDENCE_MIN_BASE_SAMPLES=5`、`EVIDENCE_MIN_UPLIFT_DELTA=0.05`、`EVIDENCE_MIN_CONSISTENCY=0.67`、`EVIDENCE_CI_T_CRIT=2.0`、`EVIDENCE_SEASON_WINDOW_DAYS=45`。

---

## 4. 决策层

### 4.1 单商品需求量分解（`policy._prepare_items`）

```text
目标覆盖天数 target_cover_days
  = min( max( lead_days + REVIEW_BUFFER_DAYS(=1),  民生保障下限 LIVELIHOOD_MIN_COVER_DAYS(=3) 若为民生 ),
         max(shelf_life_days, 1.5) )

安全系数 safety = clamp(base_safety + memory_delta, 0.05, 0.60)
安全库存 safety_stock = daily × target_cover_days × safety

目标库存 target_stock = daily × target_cover_days + safety_stock
有效在途 eligible = 在 target_cover_days 窗口内真正能到货的在途量
建议进货 need = max(0, target_stock − on_hand − eligible)
raw_reorder = ceil_to_pack(need, pack_size)
```

同时产出：断供商品 `reorder=0` 与"同品类不同供应商"的**真实**替代来源（数据里没有就留空，不编造）；`floor_qty / floor_cost`（民生兜底量）；`capital_eff = 单位资金预期毛利`；短保商品的过量/损耗风险标记；各项 `*_sources` 解释文本。

> ⚠️ 事件系数只在 `forecast._risk_adjust` 乘一次；覆盖天数里**不再**叠加风险缓冲（历史 bug 已修，勿回退）。

### 4.2 三层惠民约束（`policy._allocate`，创新点 1 的规则形态）

1. **民生兜底**：民生商品按 `floor_qty` 先锁定，不参与利润竞价；民生内部排序 = `客流带动系数 × 缺口`，同分按 SKU 字典序（保证确定性）。
2. **弹性分配**：剩余预算按 `capital_efficiency`（单位资金预期毛利）降序分配给增量需求，民生与非民生公平竞争。
3. **极端保底**：预算不够时 `_floor_to_pack` 能买多少买多少，标记 `trimmed + "预算不足，已按惠民底线优先保障"`。
- 民生保障率口径统一为**按 SKU 计数**：`secured_cnt / all_liv`（全站唯一，`calculate_essential_coverage`）。

### 4.3 R³-Stock 多目标 MILP（`core/r3_optimizer.py`）

求解器：HiGHS（`scipy.optimize.milp`，wheel 自带二进制）。**两阶段字典序**：

```text
变量：y_i ∈ ℤ⁺ 整包数；s_i ≥ 0 韧性缺口；f_i ∈ ℤ⁺ 民生兜底整包数（仅民生）
硬约束：Σ cost_i·pack_i·y_i ≤ budget；0 ≤ y_i ≤ U_i；断供 y_i = 0；
        s_i ≥ target_stock_i − on_hand_i − eligible_in_transit_i − pack_i·y_i
阶段一（Responsibility）max Σ_{民生} w_i·f_i          预算不足时不 infeasible，最大化保障程度
阶段二（Revenue+Resilience）max Σ unit_margin_i·x_i − λ·Σ s_i   s.t. y_i ≥ f_i*（民生兜底冻结）
λ = RESILIENCE_SHORTFALL_PENALTY = 1.0；超时 R3_SOLVER_TIMEOUT = 30s
```

**回退链**：`mode≠diannao` 或 `solver=False` 或 `R3_SOLVER_ENABLED=False` 或 scipy 缺失 或求解异常/超时 → 一律回退 `_allocate` 贪心，`meta.solver.used_milp=False` 如实标注给页面。**任何情况下不得崩溃。**

### 4.4 两种模式与消融开关（`build_plan`）

| 参数 | 含义 |
|---|---|
| `mode` | `"diannao"`（惠民约束版）/ `"baseline"`（纯利润对照） |
| `use_memory` | 是否启用经营记忆校准（对照组 False，保证差异只来自"目标"而非"学没学过"） |
| `protect_livelihood` | `None` 跟随 mode；显式 False = 消融"去掉 R³ 责任目标"（仍走 MILP 收益+韧性阶段） |
| `solver` | `None` 跟随全局开关 |
| `restore_potential` | 消融"去掉需求还原" |
| `in_transit_map / on_hand_batches` | 长期仿真注入在途与批次（单日决策缺省为空） |
| `persist` | 是否写 `plan_log` |

返回值：`{date, budget, mode, mode_label, items, meta, metrics, risks, risk_summary}`；`metrics` 由 `evaluate_plan` 产出且全部走 `core/metrics.py`。

---

## 5. 记忆与自进化层（创新点 2）

### 5.1 反馈处理（`evolution.process_feedback`）

```text
输入：day, feedback[{sku, qty_sold, qty_stockout, qty_spoilage, is_promo, is_holiday}], plan_context
① 写 feedback_log（全量留痕，uid 幂等）
② derive_experiences：仅当 断货率 > 0.10 或 损耗率 > 0.10 才沉淀经验
     stockout_ratio = qty_stockout / (qty_sold + qty_stockout)
     spoilage_ratio = qty_spoilage / (qty_sold + qty_spoilage)
     同日两者同现 → 只按断货计（避免自我抵消）
③ _log_calibration：对比"处理前/处理后"的校准量，**只有真的变化才写 evolution_log**
返回 {day, summary{stockout_days, spoilage_days, adjustments, skipped, updated, removed},
      experiences, changes}
```

**四种分支**（页面文案必须据此分支，不得伪造）：
`changes` 非空 = 真校准；`skipped>0` = 完全重复被跳过；`updated>0` = 数据修正覆盖；`removed` 非空 = 修正后不再触发阈值而撤销。

### 5.2 在线校准（`policy.memory_safety_calibration`）

```text
学习对象 = Forecast/Event 未能解释的残差，而非再次学习事件本身
  err_ratio = (实际潜在需求 − 原预测) / 原预测
按「同场景（event_type == 当前生效事件标签，普通日="正常"）」取最近 MEMORY_BIAS_WINDOW(=5) 条经验
  mean_err = 均值(err_ratio)
  delta = clamp(mean_err × MEMORY_BIAS_GAIN(=0.5), ±MEMORY_SAFETY_MAX_DELTA(=0.06))
  factor = 1 + delta
```
时间约束：`as_of` 只统计 **早于决策日** 的经验（不看当天及未来，防数据泄漏）。
设计理由：有界 + 取均值（非连乘）→ 不会误差放大；用残差而非全效应 → 不与 Event/Forecast 重复学习。

> ⚠️ policy 表的 `safety_factor` 是**基础参数，反馈不回写它**；生效值 = 基础值 + 在线校准量，在每次决策时重算。

---

## 6. 实验层

### 6.1 长期仿真（`core/simulator.py`）

**策略矩阵**（`_strategy_specs()`，5 个不同配置）：`diannao`（完整）、`baseline`（纯利润、无记忆、无民生兜底）、`diannao_no_memory`、`diannao_no_event`、`diannao_no_responsibility`。
**公平性设计**：所有策略共用同一环境（同需求/天气/供应商/交期/保质期/预算/初始库存/成本/FEFO），差异仅允许出现在 `mode`（MILP vs 贪心）、`protect_livelihood`、`use_memory` 三处。

**环境机制**：
- 库存按**批次**管理（`arrival / expiry / qty`），`expiry = arrival + shelf_life_days`，`[arrival, expiry)` 可售。
- 销售 `_fefo_sell`（最早到期优先）；售前 `_expire_batches` 整体报废（每批次只报损一次）。
- 在途：下单后按 `lead_time_days` 到货，参与"有效在途"扣减，避免重复下单。
- 断供：`_enforce_supplier_outage` 在结算层强制拦截断供供应商订单（Event-Blind 策略也会被拦，保证"世界一样、差别只在认知"）。
- 每日回写：`set_inventory_bulk` + 以当日决策与真实需求构造 `feedback` 调 `evolution.process_feedback`（即仿真内也在学习）。

**配置**：`DEFAULT_SIM_BUDGET = 1800.0`、`DEFAULT_SEED = 42`、`INIT_INVENTORY_DAYS = 3.0`、180 天。

### 6.2 离线评测（`core/eval_core.py`）

`DAYS=60`、`SEEDS=[42]`（CSV 固定，多种子退化为单次重演）、`EVAL_BUDGET=360.0`（**故意设紧**，使"预算一紧先砍民生"显形）。
5 种方式：`owner`（店主原做法，断货/报损恒 0，数据局限）/ `baseline` / `diannao` / `no_evolve` / `no_potential`。
产出 `eval_report.md / eval_results.csv / eval_results.html`（后三者已 gitignore）。

### 6.3 FINAL 冻结证据（`eval/final/`，**只读**）

冻结时间 2026-10-02 12:35:18，seed 42，预算 ¥1800，180 天，指标口径 `core.metrics`：

| 实验 | 对比 | 累计毛利 | 断货率 | 民生保障率 | 民生断货量 | 经验数 |
|---|---|---|---|---|---|---|
| r3_vs_traditional | 小满 R³（完整） | 152,707.2 | 2.931% | **1.000** | **425** | 739 |
| | 传统算法（纯利润） | 152,769.6 | 2.688% | 0.948 | 681 | 0 |
| memory_ab | Memory 开 | 152,707.2 | 2.931% | 1.000 | 425 | 739 |
| | Memory 关 | 151,955.3 | 3.401% | 1.000 | 498 | 0 |
| ablation_3obj | Full R³ | 152,707.2 | 2.931% | 1.000 | 425 | 739 |
| | −Revenue | 152,939.3 | 2.811% | 1.000 | 417 | 734 |
| | −Resilience | 152,710.3 | 3.214% | 1.000 | 447 | 759 |
| | −Responsibility | 153,613.0 | 2.241% | 0.950 | 612 | 614 |
| spoilage_ab | 损耗控制开 | 152,707.2 | 2.931% | 1.000 | 425 | 739 |
| | 损耗控制关 | 152,707.2 | 2.931% | 1.000 | 425 | 739 |

**读法**：① 小满用 −0.04% 毛利换来民生保障 100% 与民生断货 −37.6%；② 经营记忆带来 +¥752 毛利与断货率 −0.47pp；③ 去掉责任目标毛利最高但民生保障掉到 95%。**⚠️ ③ 与 spoilage_ab 无差异两点存在待解释项，见 §13 与 ARD。**

---

## 7. 展示层

### 7.1 信息架构（7 个标签页，DESIGN.md §7）

| # | 标签页 | 面向 | 渲染来源 |
|---|---|---|---|
| 1 | 今天该进什么货 | 店主 | `home_view.render_home_html(plan, part)` + app.py 内联（风险面板/Agent/仿真工具） |
| 2 | 为什么这样进 | 店主 | `why_view.render_why_page(it)` ← `decision_basis` |
| 3 | 今天生意怎么样 | 店主 | `feedback_view.*`（head/date_hint/table_hint/render_result/render_invalid/render_empty） |
| 4 | 它学会了什么 | 店主/评委 | `learn_view.*` + `app.evolution_chart` |
| 5 | 店里的老账本 | 评委 | `ledger_view.render_ledger()` 等 |
| 6 | 实验验证 | 评委 | `final_view.render_html()` ← `eval/final/*.json` |
| 7 | 项目说明 | 评委 | `about_view.render_about()` + 内嵌离线评测按钮 |

跨页联动：`btn_goto_exp / btn_goto_feedback / btn_goto_learn` 通过 `gr.Tabs(selected=…)` 跳转；`tab_mem.select` 自动刷新。

### 7.2 UI v2 规范与迁移状态

- **唯一 token 来源**：`core/ui_theme.py` 的 `--xm-*` 与 `.xm-*`（Notion 产品级视觉语言；画布 #ffffff、表面 #f6f5f4、主操作 #5645d4、语义 success/warning/error）。
- **禁令**：彩色 Emoji、机器人/大脑/AI sparkle 图标、Dashboard 卡片阵列、写死颜色、营销式 Hero/定价卡。
- 页面级 CSS：各 `*_view.py` 自带命名空间（`.lx-*` 学习页 / `.lb-*` 账本页 / `.fb-*` 反馈页），全部以 `--xm-*` 变量取值。
- **迁移状态**：✅ 反馈页 / 学习页 / 账本页；🚧 首页 `home_view`（结构已新、文本仍含 emoji）；⬜ 为什么这样进 / 实验验证 / 项目说明 / app.py 内联区块（仍 `dn-*`/`ab-*` + 内联 style + emoji）。详见 [ARD](ARD.md) T-UI-01..04。

### 7.3 LLM 说明层（`core/llm.py`，可选）

`is_enabled()` 由 `LLM_API_KEY` 决定；调用 OpenAI 兼容 `/chat/completions`（默认 DeepSeek `deepseek-chat`，`LLM_TIMEOUT=8s`），**只用标准库 `urllib`**。三个入口：`plan_narrative / explain_plan / answer_question`。未配置或调用失败 → 规则模板，功能不降级。

---

## 8. 关键接口清单（接手必看）

| 函数 | 签名要点 | 说明 |
|---|---|---|
| `policy.build_plan` | `(plan_date, budget=600, mode, persist=True, restore_potential=True, risks=None, solver=None, use_memory=True, protect_livelihood=None, in_transit_map=None, on_hand_batches=None, spoilage_control=True)` | 决策唯一入口 |
| `policy._prepare_items` | 同上关键项 | 需求分解与解释素材 |
| `policy._allocate` / `_allocate_plan` | `(items, budget, protect_livelihood)` / `(+mode, solver)` | 贪心 / 求解器入口 |
| `policy.memory_safety_calibration` | `(active, db_path=None, as_of=None)` | 在线校准（决策与进化共用的唯一口径） |
| `policy.compare_plans` | `(plan_date, budget, persist=False, ...)` | 小满 vs 传统对比 |
| `forecast.estimate_daily_demand` | `(product, plan_date, records, restore_potential=True, risks=None)` | 单商品预测（含推导） |
| `forecast.forecast_all` | `(plan_date, lookback=28, ...)` | 全商品预测 |
| `event_evidence.evaluate_product` | `(event_key, product, as_of=None)` | 事件证据判定 |
| `evolution.process_feedback` | `(day, feedback, persist=True, plan_context=None)` | 学习入口 |
| `memory.memory_stats` | `(db_path=None)` | 档案页统计 |
| `metrics.*` | 各率/成本函数 | 口径唯一来源 |
| `simulator.run_strategies` | `(strategy_keys, budget=1800, ...)` | 长期仿真 |
| `eval_core.run_eval` | `(seeds=None, days=60, db_path=None)` | 离线评测 |
| `agent.plan_and_explain` | `(plan_date, budget=600, risks=None)` | Agent 全流程 + 解释 |

---

## 9. 参数总表（`core/config.py`）

| 组 | 常量 | 值 | 说明 |
|---|---|---|---|
| 经营 | `DEFAULT_BUDGET` | 600.0 | 网页默认预算 |
| 惠民 | `LIVELIHOOD_MIN_COVER_DAYS` | 3.0 | 民生最低覆盖天数 |
| | `REVIEW_BUFFER_DAYS` | 1.0 | 补货缓冲（下次检查间隔） |
| 覆盖 | `LIVELIHOOD_BASE_DAYS_MIN` | 4.0 | 民生备货天数下限（evolution/policy 使用） |
| 防震荡 | `SAFETY_FACTOR_MIN/MAX` | 0.05 / 0.60 | 安全系数硬边界 |
| | `BASE_DAYS_MIN/MAX` | 2.0 / 12.0 | 备货天数硬边界 |
| | `STOCKOUT_TRIGGER / SPOILAGE_TRIGGER` | 0.10 / 0.10 | 触发沉淀经验的阈值 |
| 在线校准 | `MEMORY_BIAS_GAIN / WINDOW` | 0.5 / 5 | 残差增益与窗口 |
| | `MEMORY_SAFETY_MAX_DELTA` | 0.06 | 累计校准上限 |
| 预测 | `LOOKBACK_DAYS / DECAY_ALPHA` | 28 / 0.06 | 回看窗口与指数衰减 |
| | `USE_TREND / TREND_HORIZON / TREND_MIN_SAMPLES` | True / 1.0 / 7 | 趋势外推 |
| | `TREND_MULT_MIN/MAX` | 0.75 / 1.35 | 趋势夹紧 |
| 证据门控 | `EVIDENCE_MIN_EVENT_SAMPLES / MIN_BASE_SAMPLES` | 3 / 5 | 样本下限 |
| | `EVIDENCE_MIN_UPLIFT_DELTA / MIN_CONSISTENCY` | 0.05 / 0.67 | 效应量与一致性下限 |
| | `EVIDENCE_CI_T_CRIT / SEASON_WINDOW_DAYS` | 2.0 / 45 | 置信与季节窗口 |
| R³ | `R3_SOLVER_ENABLED / TIMEOUT` | True / 30s | 求解器开关与超时 |
| | `RESILIENCE_SHORTFALL_PENALTY` | 1.0 | 韧性缺口惩罚 λ |
| LLM | `LLM_BASE_URL / MODEL / TIMEOUT` | api.deepseek.com / deepseek-chat / 8s | 可降级说明层 |
| 日历 | `HOLIDAYS` | 12 条 | 节日日历 |
| 实验 | `DEFAULT_SIM_BUDGET / DEFAULT_SEED`（simulator） | 1800 / 42 | 长期仿真 |
| | `DAYS / SEEDS / EVAL_BUDGET`（eval_core） | 60 / [42] / 360 | 离线评测 |

**已定义但当前代码未被引用（疑似历史遗留，待清理或接线）**：`LIVELIHOOD_FLOOR_RATIO`、`EVOLVE_UP_STEP`、`EVOLVE_DOWN_STEP`、`EVOLVE_UP_MAX_MULT`、`MEMORY_SAFETY_UP_STEP`、`MEMORY_SAFETY_DOWN_STEP`、`RESTORE_POTENTIAL`、`COLOR_LIVELIHOOD`、`COLOR_PROFIT`。**注意：`README.md` 第 3 节曾引用这些常量作为"防震荡设计"，与当前实现（残差均值 × 0.5，夹紧 ±0.06）不一致，需订正。**

---

## 10. 质量保障

| 层次 | 覆盖 | 命令 |
|---|---|---|
| 单元测试 | 21 个文件 / 142 用例：政策分配边界、进化防震荡、预测夹紧、R³ 优先级、批次库存、在途资格、事件证据/工具、记忆持久化、各页面渲染 | `pytest -q --basetemp .pytest_tmp` |
| 昂贵测试 | `test_simulator.py` / `test_event_ab.py` / `test_baseline_fairness.py`（分钟级） | 同上，注意耗时 |
| 端到端 | `demo_flow.py`（五幕闭环） | `python demo_flow.py` |
| 实验复现 | `eval.py` / `run_digital_store.py` / `run_event_awareness_ab.py` | 见 §1.1 |
| 页面自检 | 渲染非空 + 空状态 + 无 emoji/硬编码色 | [../AGENT.md](../AGENT.md) §8.2 |

**2026-10-03 实测基线**：依赖补齐后 **`142 passed`（92s，全绿）**。此前缺 `plotly` 时为 `138 passed, 2 failed, 2 skipped` —— 2 项失败均为 `import app` 的环境问题（`test_display_layer`、`test_feedback_view`），非代码缺陷；装好 gradio 6.29.1 / plotly 7.1.0（T-ENV-01）后自动消失。

---

## 11. 性能与容量

| 场景 | 实测/设计 |
|---|---|
| 单次决策（50 SKU） | 秒级（预测 + MILP；MILP 超时上限 30s，异常即回退） |
| 180 天完整仿真 | 5~8 分钟（完整小满约 100s/策略，传统算法约 20s/策略） |
| 离线评测（60 天 × 5 模式） | 约 1~2 分钟 |
| 测试全量 | 61s（含昂贵仿真测试） |
| 数据规模 | 9000 行销量 / 50 SKU / 180 天；DB 约 1.3MB |
| 展示产物 | `eval_results.html` 约 4.8MB（内嵌图，已 gitignore） |

---

## 12. 技术债与风险（与 [ARD](ARD.md) 风险台账一一对应）

| # | 问题 | 影响 | 处置 |
|---|---|---|---|
| D1 | ~~环境缺 `gradio / plotly`~~ | ✅ 已解除：装上 gradio 6.29.1 / plotly 7.1.0 后网页可启动（7 页截图核对）、测试 142 passed 全绿 | ✅ ARD T-ENV-01 |
| D2 | `README.md` 与实现漂移（仍写 5 个标签页、旧常量、旧参数语义） | 误导接手人 | ARD T-DOC-01（P0/P1） |
| D3 | `app.py` 63KB 单体，含内联 HTML/CSS/emoji | 修改易冲突、违反 DESIGN.md v2 | ARD T-UI-01..04 + T-QA-02 |
| D4 | 页面视觉体系两套并存（v2 与 `dn-*`/`ab-*`） | 观感不一致 | 随 UI 迁移收敛 |
| D5 | `spoilage_ab` 开/关结果完全相同 | 该消融无法证明损耗控制价值 | ARD T-EXP-02（P1，需排查开关是否真正生效） |
| D6 | `ablation_3obj.no_revenue` 毛利反而更高 | 结论反直觉，易被评委追问 | ARD T-EXP-03（P2，需给出解释或标注局限） |
| D7 | 9 个常量定义未使用，README 却引用 | 文档与代码互不信任 | ARD T-QA-01（P2） |
| D8 | 根目录 9 个 `_step*.py` 一次性脚本 + 4 个 run 脚本混杂 | 新人难辨主线 | ARD T-DOC-02（P2，建议移入 `tools/` 或 `eval/_scripts/`） |
| D9 | SQLite schema 变更依赖 `_migrate()` 手工维护 | 迁移遗漏风险 | 新增字段时补测试 |
| D10 | ~~未提交改动与新增文件未入库~~ | 已解除：改动全部提交并推送到本地备份区（`v0.2.0`）。**残余**：`.git/info/exclude` 属当前克隆，新克隆环境需执行一次 `vcs.ps1 guard` | ✅ ARD T-ENV-02 / T-ENV-03；残余见 [AGENT](../AGENT.md) 踩坑清单 |

---

## 13. 架构决策记录（ADR）

**ADR-001 用"可解释参数校准"替代大模型微调**（`evolution.py` / `policy.memory_safety_calibration`）
理由：成本低、可解释、门店数据量撑不起微调；店主能看懂"为什么安全系数从 0.15 变成 0.21"才会信任。代价：学习能力上限有限，只学"残差"这一路信号。

**ADR-002 从贪心升级为 R³ 两阶段字典序 MILP，并保留贪心回退**（`policy._allocate_plan`）
理由：预算约束下的多目标是真正的整数优化问题，贪心排序无法表达"民生兜底不可被利润挤掉"。风险：求解器依赖 scipy；通过"不可用/超时/异常 → 回退贪心 + 如实标注"消除。

**ADR-003 断货日必须还原潜在需求**（`forecast._potential`）
理由：断货日销量被压扁，直接学习会陷入"越缺货越不敢进货"的恶性循环。代价：需要 `qty_stockout` 字段（CSV 无、由反馈补录）。

**ADR-004 事件影响"先证据、后应用"**（`event_evidence.py`）
理由：固定倍率在样本不足时会放大噪声。代价：新场景（首次出现的品类事件）只能给风险提示，不调整预测。

**ADR-005 历史需求一律来自固定 CSV，取消随机生成**（`dataset.py` / `seed_data.py`）
理由：可复现、可对账；多种子取均值退化为单次重演。代价：数据多样性受限（50 SKU / 180 天）。

**ADR-006 实验数据与门店记忆严格隔离**（`eval/**` vs `memory.db`）
理由：演示页展示的必须是"这家店真实沉淀的东西"，实验中的 739 条经验不得混入。实现：`*_view.py` 只读 `memory.*`。

**ADR-007 决策确定性 + LLM 仅做外层解释**（`llm.py`）
理由：补货是要花钱的决策，必须可复现、可审计；生成式只用于表达。实现：LLM 可失败、可降级，不参与数值。

**ADR-008 用本地裸仓库镜像 GitHub，并删除 .gitignore（改用 .git/info/exclude + 提交守卫）**（`tools/vcs.ps1`）
决策：不做 GitHub 远端；在项目内建 `_backup/diannao.git`（bare）并登记为 `origin`，保留 push / pull / tag / branch / 合并 / 回退的完整 Git 语义；删除 `.gitignore`，忽略规则迁至 `.git/info/exclude`，由 `vcs.ps1 guard` 幂等维护，`save` 的提交守卫做第二道防线（密钥命中直接中止、运行产物自动撤出暂存）。
理由：需求是「纯本地备份 + 可回滚」；裸仓库单机自包含、整目录可搬走。`.gitignore` 是**随仓库分发**的文件，在纯本地备份场景里既多余又会约束别人的环境；`.git/info/exclude` 不随仓库分发，更贴合「纯本地」。
代价：新克隆环境不继承忽略规则，需执行一次 `guard`（已登记到 [../AGENT.md](../AGENT.md) 踩坑清单）。

详见 [VERSIONING.md](VERSIONING.md)。

---

## 14. 变更记录

| 日期 | 版本 | 变更 | 作者 |
|---|---|---|---|
| 2026-10-03 | v1.0 | 首版：反向固化架构、数据模型、算法口径、参数表、实验证据、技术债与 ADR | 接手初始化 |
| 2026-10-03 | v1.1 | 新增 ADR-008（本地裸仓库镜像 GitHub、删除 .gitignore）；§1.1 增加版本/备份入口；D10 标记解除 | 接手初始化 |
