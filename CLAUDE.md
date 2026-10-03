# CLAUDE.md — 小满（diannao）仓库级作业规范

> 面向所有在本仓库写代码的 AI Agent 与开发者。**动手前必读**；改完代码必须回头更新 [docs/ARD.md](docs/ARD.md)。
> 配套文档：[AGENT.md](AGENT.md)（接手/交接流程）、[docs/PRD.md](docs/PRD.md)（产品需求）、[docs/TRD.md](docs/TRD.md)（技术设计）、[docs/ARD.md](docs/ARD.md)（任务与进度台账）。

---

## 0. 三十秒认清这个项目

| 项 | 值 |
|---|---|
| 产品名 | **小满**（`core/config.py` 的 `APP_NAME`），面向社区小店的自进化智能补货 Agent |
| 工程/仓库名 | **店脑**（目录 `diannao`；`eval/final`、`core/simulator.py` 里叫「店脑 R³」） |
| 别名 | 「小满」= 面向店主的产品名，「店脑」= 工程/实验口径名。**两者指同一系统，不要再造第三个名字** |
| 形态 | 单进程 Python + Gradio 网页应用，`python app.py` 即用，无需专用硬件 |
| 入口 | 网页 `app.py`（7 个标签页）／演示 `demo_flow.py`／离线评测 `eval.py`／长期实验 `run_digital_store.py` |
| 数据 | 仿真数据 `data/shopmind_*.csv`（50 SKU × 180 天，2026-03-01 ~ 2026-08-27），**不是真实门店采集数据** |
| 存储 | SQLite 长期记忆库 `data/store_memory.db`（由 `.git/info/exclude` 忽略，首次运行自动重建） |
| 当前状态 | 核心闭环已完成、FINAL 实验已冻结；UI v2 迁移进行中。**进度以 [docs/ARD.md](docs/ARD.md) 为唯一事实来源** |

---

## 1. 铁律（违反即返工）

1. **不写死数字**。页面/文档里出现的每个业务数字都必须来自真实执行结果（`memory` / `policy` / `eval/final`）。禁止为了"好看"在 HTML 或文案里硬编码结论。
2. **不造数据**。查不到就说查不到（空状态文案如实写「还没有形成经营经验」）。不虚构经验命中、不虚构事件、不虚构供应商替代方案。
3. **不引入随机**。历史需求一律来自 CSV；`random` 只允许出现在与业务结论无关的地方。实验用固定 `seed=42`，结果必须可复现。
4. **不动冻结产物**。`eval/final/**`（`FROZEN.json` + 4 组实验 CSV/JSON）是已冻结的实验证据，**只读**。要重跑请另建目录并在 ARD 记录。
5. **不碰原始数据**。`data/shopmind_products_50sku.csv`、`data/shopmind_180days_50sku.csv` 是数据源，只读。
6. **决策必须确定性、可解释、可降级**：
   - 核心补货决策是确定性规则/优化，**LLM 只是外层"翻译成人话"**，未配 Key 或调用失败必须自动降级为规则模板（`core/llm.py`），不得影响决策；
   - MILP 求解失败/超时必须回退贪心 `_allocate`（`R3_SOLVER_ENABLED` / `R3_SOLVER_TIMEOUT`），任何情况下系统不得崩溃。
7. **参数集中在 `core/config.py`**。新增业务常量一律加在 config 并写中文注释说明业务含义与来源，禁止散落在各模块。
8. **UI 遵循 [DESIGN.md](DESIGN.md)（v2）**：颜色/字号/圆角/间距只用 `core/ui_theme.py` 的 `--xm-*` token 与 `.xm-*` 组件类；**不使用彩色 Emoji、不使用机器人/大脑/AI sparkle 图标、不做 Dashboard 卡片阵列、不写死颜色**。`DESIGN.legacy.md` 已废弃，仅作历史参考。
9. **源码统一 LF**（见 `.gitattributes`）；文件一律 UTF-8，Python 文件首行 `# -*- coding: utf-8 -*-`，面向用户的中文文案直接写中文。
10. **改完必须自证**：跑测试 + 跑受影响页面的真实渲染（见 §4），并在 ARD 里写清"改了什么 / 证据是什么 / 下一步"。
11. **不提交秘密**：`.env` 由 `.git/info/exclude` 忽略（本项目使用本地备份区，已删除 `.gitignore`），只维护 `.env.example`。
12. **不做无授权的架构重构**。`app.py` 是 63KB 单体，重构它属于独立任务，必须先在 ARD 建任务再动手。

---

## 2. 环境与命令（Windows 本机，2026-10-03 实测）

**解释器**：本仓库的 `__pycache__` 与实验均为 **Python 3.13**（`E:\Python\python.exe`，3.13.7）。
注意 PATH 里的 `python` 是 msys2 的 3.12，**不要用它跑本项目**（其 site-packages 里没有本项目依赖）。

**依赖已就绪（2026-10-03 补齐，T-ENV-01 已解除）**：`E:\Python` 已装 pandas / numpy / scipy / pytest / **gradio 6.29.1 / plotly 7.1.0** ⇒ 网页可启动，测试全绿（142 passed）。
⚠️ 副作用：gradio 6 拉入了 `huggingface-hub 2.1.1`，与本机 `tokenizers 0.23.1`（要求 hub<2.0）冲突 —— 不影响本项目（项目不用 tokenizers），但会影响该 Python 环境里依赖 tokenizers 的其他项目（见 ARD R14）。

```powershell
# 安装/更新依赖（当前已装 gradio 6.29.1 / plotly 7.1.0）
& 'E:\Python\python.exe' -m pip install -r requirements.txt

# 启动网页（首次运行会读 CSV 建库）
& 'E:\Python\python.exe' app.py          # http://127.0.0.1:7861

# 单元测试（必须带 --basetemp，否则临时目录清理会被权限拦住）
& 'E:\Python\python.exe' -m pytest -q --basetemp .pytest_tmp
# 基线（依赖补齐后实测）：142 passed，全绿，约 92s

# 答辩五幕闭环演示 / 命令行离线评测
& 'E:\Python\python.exe' demo_flow.py
& 'E:\Python\python.exe' eval.py         # 产出 eval_report.md / eval_results.csv / eval_results.html

# 180 天 Digital Store 长期实验（5~8 分钟，会写 eval/*.csv）
& 'E:\Python\python.exe' run_digital_store.py            # 默认预算 ¥1800 / seed=42
& 'E:\Python\python.exe' run_event_awareness_ab.py        # 事件感知 A/B
```

### 2.1 版本控制与本地备份（无 GitHub）

本项目**不推 GitHub**，用项目内的裸仓库 `_backup/diannao.git`（登记为 `origin`）扮演远端。
完整策略见 [docs/VERSIONING.md](docs/VERSIONING.md)。日常只有三条命令：

```powershell
# 看状态 / 提交并备份（等价 GitHub 的 commit + push）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 save "feat(ui): 首页迁移（T-UI-01）"

# 本地 CI（跑测试）与回退验证
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 verify -Fast
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 rollback v0.2.0
```

- **分支模型**：`main`（稳定，只接受 `--no-ff` 合并）/ `develop`（集成）/ `feature/*` / `hotfix/*` / `restore/*`。
- **忽略规则**：`.gitignore` 已删除，规则在 `.git/info/exclude`（由 `vcs.ps1 guard` 幂等维护），外加 `save` 的提交守卫拦截密钥与运行产物。
- **必须做**：任何一次有意义的改动完成后都要 `save`，否则没有回退点 —— 这是 [docs/ARD.md](docs/ARD.md) 里“完成”的定义之一。
- ⚠️ **`tools/vcs.ps1` 保存时必须带 UTF-8 BOM**：Windows PowerShell 5.1 会把无 BOM 的 UTF-8 脚本按 ANSI(GBK) 解析，中文注释被截断后报 `Unexpected token`。若编辑后脚本报语法错，先补 BOM（见 [docs/VERSIONING.md](docs/VERSIONING.md) FAQ）。

---

## 3. 代码地图（改哪里、先读什么）

```
app.py                 Gradio 装配层：7 个 Tab 的布局 + 事件绑定 + 若干渲染函数（63KB 单体，见 ARD 技术债）
  │
  ├─ core/ui_theme.py       UI v2 唯一 tokens/CSS 来源（--xm-* / .xm-*）
  ├─ core/*_view.py         各页面渲染：home / why / feedback / learn / ledger / final / about
  │
  ├─ core/dataset.py        唯一数据入口：CSV → 清洗 → 记忆库（字段映射、单位/包规/客流系数的确定性推断）
  ├─ core/memory.py         SQLite 长期记忆库：9 张表 + 迁移 + 幂等去重（uid）+ 统计
  ├─ core/events.py         历史事件日历与品类影响倍数（从 CSV 现算，夹紧 [0.5, 1.8]）
  ├─ core/event_evidence.py 事件证据门控：strong/weak/insufficient 三级，只有 strong 才改进预测
  ├─ core/forecast.py       需求预测：EWMA × 星期效应 × 节日因子 × 趋势；断货日还原潜在需求
  ├─ core/policy.py         补货决策：目标库存 → 三层惠民约束分配 → 计划与指标（创新点 1）
  ├─ core/r3_optimizer.py   R³-Stock 两阶段字典序 MILP（HiGHS/scipy），失败回退贪心
  ├─ core/evolution.py      经营反馈 → 经验沉淀 → 策略参数校准（创新点 2）
  ├─ core/agent.py          Agent 查询 + 自然语言预算/事件解析 + 人话解释
  ├─ core/decision_trace.py 六工具决策过程追踪（Inventory/Event/Memory/Forecast/Supplier/R³）
  ├─ core/decision_basis.py 单商品"为什么这样进"的依据字段
  ├─ core/metrics.py        指标定义唯一来源（断货率/便民指数/周转/损耗…）
  ├─ core/analysis.py       客流带动实证（民生缺货 → 非民生销量下滑）
  ├─ core/simulator.py      180 天长期仿真（5 策略、FEFO、保质期、报损、断供环境强制）
  ├─ core/eval_core.py      离线评测引擎（60 天窗口 × 5 种决策方式）
  └─ core/llm.py            可选 LLM 说明层（OpenAI 兼容，可失败可降级）

tests/                 21 个测试文件 / 142 个用例（见 §4）
data/                  CSV 数据源 + 生成的 store_memory.db
eval/                  实验产物；eval/final/** = 已冻结的 FINAL 证据（只读）
docs/                  PRD / TRD / ARD
```

**先读这个顺序**：`README.md` → [docs/PRD.md](docs/PRD.md) → [docs/TRD.md](docs/TRD.md) → [docs/ARD.md](docs/ARD.md) → 你要改的那个模块。

---

## 4. 领域不变量（最容易踩的坑，改代码前先确认）

1. **日期语义**：`LAST_DAY = 2026-08-27` 是"已经卖完货的那一天"；`DEFAULT_PLAN_DATE = 2026-08-28` 是"为明天备货"。两者差一天，文案不能说"今天进货"。
2. **断货日必须还原潜在需求**：`潜在需求 = 实际销量 + 未满足缺货量`（`forecast._potential`）。直接用记录销量训练会陷入"越缺货越不敢进货"。
3. **事件因子只乘一次**：事件影响只在预测侧 `forecast._risk_adjust` 生效；覆盖天数里**不再**叠加风险缓冲（否则同一事件算两遍）。
4. **目标覆盖天数** = 供应商交期 + 补货缓冲(`REVIEW_BUFFER_DAYS=1`) + 民生保障缓冲，且 ≤ 保质期。
5. **选择安全库存的入口**：`safety = clamp(base_safety + memory_delta, 0.05, 0.60)`，`memory_delta` 来自 `policy.memory_safety_calibration`（单条 ±0.02，累计 ±0.06）。
6. **供应商断供只影响该供应商的商品**，且**不从商品配置之外编造替代来源**；断供商品 `reorder=0`，仿真层再强制拦截订单。
7. **整包取整**：`_ceil_to_pack`（向上取整到包规）；预算反算用 `_floor_to_pack`。
8. **R³ 是两阶段字典序**：先最大化民生兜底（Responsibility），冻结后再最大化 收益 − λ·韧性缺口；民生兜底不会被利润挤掉。
9. **自进化防震荡**：触发阈值 `0.10`、上调步长 `0.06`/下调 `0.04`、硬边界 `0.05~0.60` 与 `2~12 天`、同一天断货与损耗同现只按断货处理、幂等去重（`uid` 唯一索引）。
10. **反馈保存的四种分支**（`process_feedback` 返回值）：`changes` 真校准 / `skipped` 幂等去重 / `updated` 数据修正 / `removed` 异常消除撤销。**文案必须按 `result["changes"]` 是否为空分支**，不得伪造 Memory 命中。
11. **`metrics.py` 是口径唯一来源**。任何"率"的计算必须调它，禁止在页面里现算。
12. **`eval` 三档预算不要混**：网页 ¥600（`DEFAULT_BUDGET`）、离线评测 ¥360（`EVAL_BUDGET`，故意设紧）、长期仿真 ¥1800（`DEFAULT_SIM_BUDGET`）。写文档时必须注明用的是哪档。

---

## 5. 常见改动怎么做

**改业务参数** → 只动 `core/config.py` + 在 [docs/TRD.md](docs/TRD.md) 参数表同步 + 跑 `pytest tests/test_policy.py tests/test_evolution.py`。

**改预测/决策逻辑** → 先读 `forecast.py` / `policy.py` 顶部的中文设计注释（那里写了"为什么这样做"），改完必须跑 `pytest -q --basetemp .pytest_tmp`，并检查 `eval/` 里是否有需要重跑的冻结实验（若有：在 ARD 建新任务，**不要覆盖 eval/final**）。

**改/加网页页面** → 渲染逻辑写进 `core/<page>_view.py`（返回 HTML 字符串，纯函数、无副作用），`app.py` 只做布局与绑定；样式只用 `ui_theme.py` 的 token；不引入 emoji；页面数据必须真实可空（写空状态）。改完跑相关 `tests/test_<page>_view.py`。

**加测试** → 放 `tests/test_*.py`，用 `conftest.py` 的 `db` fixture（隔离临时库，`monkeypatch memory.DB_PATH`）；**不要写库到 data/，不要跑真实验**（`test_simulator.py` 这类昂贵测试标注清楚）。

**改 LLM 说明层** → 保持"可失败可降级"，不得让 LLM 参与数值决策。

---

## 6. 提交前检查清单

- [ ] `pytest -q --basetemp .pytest_tmp` 无新增失败（当前基线 **142 passed 全绿**）
- [ ] 页面渲染真实可跑，空数据/异常分支有文案
- [ ] 没有新增写死数字、没有新增 emoji、没有新增硬编码颜色
- [ ] 没有修改 `data/*.csv` 与 `eval/final/**`
- [ ] 新常量进了 `config.py`，新页面 CSS 走 token
- [ ] 改动已保存到本地版本库：`powershell -File tools/vcs.ps1 save "type(scope): 说明"`
- [ ] [docs/ARD.md](docs/ARD.md) 的任务状态、证据、下一步已更新
- [ ] 涉及产品行为变化 → 同步 [docs/PRD.md](docs/PRD.md)；涉及架构/算法/接口变化 → 同步 [docs/TRD.md](docs/TRD.md)

---

## 7. 文档维护义务（谁改谁负责）

| 文档 | 什么时候必须改 |
|---|---|
| [docs/ARD.md](docs/ARD.md) | **每次完成/开始/阻塞一个任务** —— 这是接手者唯一的进度真相 |
| [docs/PRD.md](docs/PRD.md) | 需求、用户、成功指标、范围变化 |
| [docs/TRD.md](docs/TRD.md) | 架构、模块职责、数据模型、算法口径、接口、依赖变化 |
| [AGENT.md](AGENT.md) | 接手流程、协作方式、踩坑清单变化 |
| [README.md](README.md) | 面向外部读者的介绍/快速开始（注意：现有 README 的"界面导览"仍是旧的 5 页版，已列入 ARD） |
| [docs/VERSIONING.md](docs/VERSIONING.md) | 分支模型、发布、回退流程、忽略策略变化 |
| [DESIGN.md](DESIGN.md) | 视觉 token 与组件规范变化 |

文档与代码不一致时，**以代码与实测为准**，并立刻在 ARD 记一条修复任务。
