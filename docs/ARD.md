# ARD — 小满（diannao）任务分解与进度台账

> **Action & Roadmap Document**：把 [PRD](PRD.md) 的需求与 [TRD](TRD.md) 的设计拆成**可认领、可验收、可交接**的任务点，并记录真实进度与下一步。
> **这是全项目唯一的进度真相**。任何人接手，先看 §1 看板，再进 §6 任务池取活。

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-10-03 |
| 代码基线 | git `ca17f07` + 未提交改动（详见 T-ENV-02） |
| 任务总数 | 30（已完成 18 · 进行中 0 · 阻塞 1 · 待办 11） |
| 更新义务 | **每次开始/完成/阻塞一个任务，必须回来改本文件**（见 §0.4） |

---

## 0. 这份文档怎么用

### 0.1 状态图例（只允许五种）

| 状态 | 含义 | 谁能改 |
|---|---|---|
| 待办 | 还没开始，可被认领 | 任何人 |
| 进行中 | 已认领，正在做（必须写认领人和开始日期） | 认领人 |
| 已完成 | **有证据**（命令 + 输出/文件/数字） | 完成人 |
| 阻塞 | 有明确外部依赖挡住（必须写"卡在哪、谁解除"） | 认领人 |
| 待复核 | 做完了但证据不足或需他人确认 | 复核人 |

### 0.2 任务 ID 规则

`T-<域>-<两位序号>`，域取值：

| 域 | 范围 |
|---|---|
| `ENV` | 环境、依赖、仓库卫生、提交 |
| `CORE` | 预测 / 事件 / 决策 / R³ / 指标 |
| `MEM` | 记忆库 / 自进化 / 数据导入 |
| `UI` | 页面渲染与 UI v2 迁移 |
| `EXP` | 实验、消融、冻结证据 |
| `QA` | 测试、质量、一致性校验 |
| `DOC` | 文档、README、脚本归档 |
| `RISK` | 风险与已知缺陷 |

**新发现的问题先建任务，再决定做不做**；不要顺手改无关代码。

### 0.3 "完成"的定义（验收铁律）

一条任务只有同时满足才算完成：
1. 验收标准逐条满足；
2. 有**可复现证据**：命令 + 真实输出摘要（`pytest` 结果 / 脚本 stdout / JSON 数字 / 文件:行号）；
3. 影响文件已列出；
4. 本文件已更新（状态 + 证据 + 关联任务）。

### 0.4 更新流程

```text
开始：状态改「进行中」+ 写认领人/开始日期
完成：状态改「已完成」+ 补证据 + 补"影响文件" + 必要时新建后续任务
卡住：状态改「阻塞」+ 写具体阻塞条件 + 谁/什么能解除
每次编辑：在 §9 变更记录追加一行（日期 / 谁 / 改了什么），禁止静默修改
```

---

## 1. 当前进度看板（2026-10-03）

**总体阶段：M3（UI v2 迁移中）—— 核心闭环与实验证据已完成，正在做交付层收尾。**

| 状态 | 数量 | 任务 |
|---|---|---|
| 已完成 | 18 | T-CORE-01..05、T-MEM-01..03、T-EXP-01、T-EXP-04、T-UI-05..07、T-QA-03、T-QA-05、T-DOC-03、T-ENV-02、T-ENV-03 |
| 进行中 | 0 | —（当前没有进行中任务，取活见 §6） |
| 阻塞 | 1 | T-ENV-01（缺 gradio / plotly） |
| 待办 | 11 | 见 §6 |

**今天的真实状态（可复核）**

| 检查项 | 结果 | 证据 |
|---|---|---|
| 测试 | 138 passed / 2 failed / 2 skipped（61s） | `pytest -q --basetemp .pytest_tmp`；2 失败为缺 plotly |
| 网页 | ❌ 起不来 | `import gradio / plotly` 均 ModuleNotFoundError |
| 命令行脚本 | ✅ 可跑 | pandas/numpy/scipy 已装 |
| 实验证据 | ✅ 已冻结 | `eval/final/FROZEN.json`（2026-10-02 12:35:18） |
| 工作区 | ✅ 干净 | 全部改动已提交并推送到本地备份区（`main` = `v0.2.0`、`develop` 为集成线）；`git status --short` 无输出 |
| 版本控制 | ✅ 本地 GitHub 式 | `origin → _backup/diannao.git`（裸仓库，HEAD=main）；分支 `main`/`develop`；标签 `v0.1.0`（初始基线）/`v0.2.0`；`.gitignore` 已删除，忽略规则在 `.git/info/exclude` + `vcs.ps1` 提交守卫 |
| 记忆库快照 | demo-store 真实状态 | `sqlite3` 实测：products 50 / policy 50 / sales 9000 / day_events 180 / **experiences 0** / **evolution_log 0** / feedback_log 301 / plan_log 0；销量表 `qty_stockout`、`qty_spoilage` 非零行数 **0**；日期范围 2026-03-01 ~ 2026-08-27 |

### 🎯 建议的下一个动作（Top 3）

1. **T-ENV-01（P0，唯一硬阻塞）**：装 `gradio` + `plotly` → 网页能起、2 个失败测试转绿。
2. **T-UI-01（P1）**：首页 v2 迁移（`app.py` 里 30+ 处 emoji + `dn-*` 旧 class），这是「看起来还没做完」的最大观感来源。
3. **T-DOC-01（P1）**：README 与实现对齐（界面导览仍是 5 页版、仍引用 9 个已失效常量）。

> 规矩：**每完成一件事就 `powershell -File tools/vcs.ps1 save "type(scope): 说明"`**，否则这件事没有回退点 —— 见 [VERSIONING.md](VERSIONING.md)。

---

## 2. 里程碑

| # | 里程碑 | 交付物 | 状态 |
|---|---|---|---|
| M0 | 工程基线 | 可跑的数据导入 + 记忆库 + 测试框架 | ✅ 已完成 |
| M1 | 决策闭环 | 预测 → 事件 → 惠民约束 → 自进化 → 页面闭环（demo_flow 五幕可跑通） | ✅ 已完成 |
| M2 | 实验证据 | 180 天长期仿真 + 消融 + 冻结产物（`eval/final`） | ✅ 已完成（2026-10-02 冻结） |
| M3 | 交付层收尾 | UI v2 全站迁移 + 文档体系 + 版本控制与备份 + 环境可复现 | 🚧 进行中（UI 3/7 页已迁移；文档体系 ✅；本地版本控制 ✅；环境待补齐 T-ENV-01） |
| M4 | 最终交付 | 全绿测试 + 可现场演示 + 接手零障碍 | ⬜ 待办 |

---

## 3. 已完成任务台账

### 3.1 决策与算法（CORE）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-CORE-01 | 需求预测链路（EWMA × 星期 × 节日 × 趋势 + 断货潜在需求还原） | 预测含完整推导字段；断货日还原生效；冷启动有兜底 | `tests/test_forecast.py` 6 用例通过；`demo_flow.py` 第二幕 | `core/forecast.py` |
| T-CORE-02 | 事件感知 + 证据门控（strong/weak/insufficient） | 倍数从历史现算并夹紧；只有 strong 改进预测；断供走供给侧 | `test_event_evidence.py` 12 + `test_event_tool.py` 7 + `test_event_ab.py` 5 通过 | `core/events.py` `core/event_evidence.py` `core/risk.py` |
| T-CORE-03 | 三层惠民约束分配 | 民生先锁定；剩余按资金效率；极端按"客流×缺口"保底 | `tests/test_policy.py` 5 + `test_r3_priority.py` 7 通过 | `core/policy.py` |
| T-CORE-04 | R³ 两阶段字典序 MILP + 贪心回退 | 民生兜底冻结不被利润挤掉；求解失败绝不崩 | `tests/test_r3_optimizer.py` 5 通过 | `core/r3_optimizer.py` `core/policy.py` |
| T-CORE-05 | 指标口径统一 | 所有率/成本经 `metrics.py`，页面不得另算 | `tests/test_metrics.py` 8 通过 | `core/metrics.py` |

### 3.2 记忆与自进化（MEM）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-MEM-01 | SQLite 长期记忆库 + CSV 导入 | 9 表 + 迁移 + 幂等 uid；`seed_data.py` 可重建 | `tests/test_memory_persistence.py` 6 用例中 5 通过；1 条 `import app` 的用例因缺 plotly 失败（环境问题，见 T-ENV-01） | `core/memory.py` `core/dataset.py` `seed_data.py` |
| T-MEM-02 | 自进化闭环（反馈 → 经验 → 在线校准） | 阈值 0.10 才沉淀；同日断货+损耗只按断货；重复提交幂等；±0.06 内夹紧 | `tests/test_evolution.py` 11 + `test_memory_learning.py` 6 通过 | `core/evolution.py` `core/policy.py` |
| T-MEM-03 | 批次库存 / 在途资格 / 损耗上限口径 | 批次单次报损、FEFO、有效在途只算窗口内 | `test_batch_inventory.py` 7 + `test_in_transit_eligibility.py` 7 + `test_spoilage_cap.py` 12 通过 | `core/simulator.py` `core/policy.py` |

### 3.3 实验证据（EXP）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-EXP-01 | 180 天 FINAL 实验冻结（主对比 + Memory A/B + 三目标消融 + 损耗 A/B） | 结果落盘且页面只读不重跑；结论可归因 | `eval/final/FROZEN.json`（seed 42 / ¥1800 / 180 天）+ `final_experiment_summary.json`；关键数字：民生保障 1.000 vs 0.948、民生断货 425 vs 681、Memory 开毛利 +¥752 | `core/simulator.py` `_step*.py` `eval/final/**` |
| T-EXP-04 | 事件感知 A/B 脚本 | 同一外部世界下 Aware vs Blind 公平对照 | `run_event_awareness_ab.py`（脚本完整、可运行） | `run_event_awareness_ab.py` |

### 3.4 页面与 UI v2（UI）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-UI-05 | 「今天生意怎么样」v2 迁移 | 四分支文案正确；保存按钮独占行；列名同源 | 新增 `core/feedback_view.py` + `tests/test_feedback_view.py` 10 用例；相关 23 项通过 | `core/feedback_view.py` `app.py`(Tab3) |
| T-UI-06 | 「它学会了什么」v2 迁移 | 只读本店经验表；空状态如实；经验三段式表达 | 重写 `core/learn_view.py`；相关 33 项通过 | `core/learn_view.py` `app.py`(Tab4) `tests/test_learn_view.py` |
| T-UI-07 | 「店里的老账本」v2 迁移 | 五 section + 紧凑 summary；不引实验数据；空状态如实 | 重写 `core/ledger_view.py`；相关 24 项通过 | `core/ledger_view.py` `app.py`(Tab5) `tests/test_ledger_view.py` |

> UI 迁移的详细业务事实与约束记录在 `.workbuddy/memory/2026-10-03.md`（B.2/B.3/B.4），建议后续把有效内容并入 TRD §7.2 或本文件。

### 3.5 质量与文档（QA / DOC）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-QA-03 | 测试基线建立 | 全量可跑、失败可解释 | 2026-10-03 实测 `138 passed, 2 failed, 2 skipped in 61.14s`；142 用例 / 21 文件 | `tests/**` `conftest.py` |
| T-QA-05 | 忽略并清理 pytest 临时目录 | 忽略规则覆盖 `.pytest_tmp/`；工作区无残留 | 原 `.gitignore:23-24` 新增规则；`Remove-Item` 删除 115 个残留条目，`Test-Path` 返回 False，`git status` 不再出现该项。**该规则后续随 T-ENV-03 迁移到 `.git/info/exclude`（`.gitignore` 已删除）** | `.gitignore` → `.git/info/exclude` |
| T-DOC-03 | 接手文档体系初始化 | 任何人可无门槛接手：规范 + 流程 + 需求 + 设计 + 进度 | 新增 `CLAUDE.md` / `AGENT.md` / `AGENTS.md`（入口指针）/ `docs/PRD.md` / `docs/TRD.md` / `docs/ARD.md`（本文件）；`README.md` 追加「十二、项目文档索引」 | 上述文件 + `README.md` |

### 3.6 工程与版本控制（ENV）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-ENV-02 | 冻结未提交改动（UI v2 三页迁移 + 文档体系） | 工作区干净；改动全部入库并推送到本地 origin | 4 个逻辑提交（`feat(ui)` / `docs` / `chore(vcs)` / `docs`）+ `--no-ff` 合并到 `main`；提交哈希见 §9 | `app.py` `core/*_view.py` `tests/*` `docs/**` `CLAUDE.md` `AGENT.md` `README.md` |
| T-ENV-03 | 建立本地 GitHub 式版本控制与备份区（无 GitHub） | ① 无 GitHub 也能 push / pull / tag / branch / 合并；② 删除 `.gitignore` 后仍不误提交密钥与运行产物；③ 能回退到任意历史版本 | ① `_backup/diannao.git`（bare，HEAD=main）登记为 `origin`，`git remote -v` 可见；② `.git/info/exclude` 忽略规则 + `vcs.ps1 save` 提交守卫（实测：`.env` 命中即中止、产物自动撤出）；③ 标签 `v0.1.0`（初始基线 `ca17f07`）/`v0.2.0`（本次交付）；④ 回退演练：`rollback v0.1.0` 成功创建 `restore/v0.1.0-*` 分支；⑤ 灾难恢复演练：`clone` 到临时目录成功 | `tools/vcs.ps1` `docs/VERSIONING.md` `_backup/**` `.git/info/exclude` `README.md` `CLAUDE.md` `AGENT.md` |

---

## 4. 进行中

| ID | 任务 | 认领人 | 开始 | 现状 | 下一步 |
|---|---|---|---|---|---|
| — | 当前没有进行中的任务 | — | — | 待办 11 项见 §6；P0 是 T-ENV-01 | 认领后把该行替换为本任务的信息，并同步 §1 计数 |

---

## 5. 阻塞

| ID | 任务 | 阻塞条件 | 谁能解除 | 影响 |
|---|---|---|---|---|
| T-ENV-01 | 补齐运行依赖（`gradio>=6,<7` / `plotly>=6,<8`） | 本机 `E:\Python` 未安装这两个包，网页无法启动，3 个 `import app` 的测试在收集期报 `ModuleNotFoundError: No module named 'plotly'` | 有网络与 pip 权限的任何人：`& 'E:\Python\python.exe' -m pip install -r requirements.txt` | 阻塞 M3/M4 里程碑：无法现场演示网页、无法跑内嵌评测图 |

**解除后的验收标准**：
1. `& 'E:\Python\python.exe' -c "import gradio, plotly; print(gradio.__version__, plotly.__version__)"` 成功；
2. `python app.py` 起在 `127.0.0.1:7861` 且 7 个标签页可切换；
3. `pytest -q --basetemp .pytest_tmp` 变成 `140 passed, 2 skipped`（无 failed）。

---

## 6. 下一步任务池

### P0 — 不解决就交付不了

| ID | 任务 | 建议写作用域 | 依赖 | 验收标准 |
|---|---|---|---|---|
| T-ENV-01 | 安装 gradio / plotly 并验证 | `requirements*.txt`（如版本需调整） | — | 见 §5 三条 |
| T-DOC-01 | README 与实现对齐 | `README.md` | — | ①"界面导览"改为 7 页；②删除已失效的常量引用（见 TRD §9 末尾）；③补三档预算口径；④补 `--basetemp` 与 Python 解释器说明 |

**T-DOC-01 的具体差异清单**（已核对）：

- `README.md` 第二节表格只有 5 个标签页，实际为 7（缺"为什么这样进""实验验证"）。
- `README.md` 第三节引用 `EVOLVE_UP_STEP / EVOLVE_DOWN_STEP / EVOLVE_UP_MAX_MULT` 描述"防震荡设计"，但当前实现是**残差均值 × 0.5、夹紧 ±0.06**（`policy.memory_safety_calibration`），这些常量未被引用。
- `README.md` 第五节目录结构缺 `core/` 下 10 个模块（simulator / r3_optimizer / decision_trace / event_evidence / metrics / risk / llm / ui_theme / *_view 等）。
- `README.md` 未提 `--basetemp .pytest_tmp`、未提三档预算（600 / 360 / 1800）。

### P1 — 明显影响观感或可信度

| ID | 任务 | 建议写作用域 | 依赖 | 验收标准 |
|---|---|---|---|---|
| T-UI-01 | 首页 v2 迁移 | `app.py`(Tab1/内联渲染) `core/home_view.py` | — | 去掉全部 emoji（现有 30+ 处，如 🤖/📊/🚀/🔬/🏪/⚠️）；`dn-row`/`dn-risk-panel` → `.xm-*`；`home_view` 文档串里的"DESIGN.md v1.0"改为 v2；页面结构仍为"经营工作台"而非 Dashboard |
| T-UI-02 | 「为什么这样进」v2 迁移 | `core/why_view.py` `app.py`(Tab2) | — | `.yw-*`/`.ev-*` 改用 `--xm-*` token 与 `.xm-*` 组件；去掉内联硬编码色（#234E70/#66737F…） |
| T-UI-03 | 「实验验证」v2 迁移 | `core/final_view.py` | — | 去掉内联 style 与硬编码色；数字仍全部来自 `eval/final`；结论含归因说明 |
| T-UI-04 | 「项目说明」v2 迁移 | `core/about_view.py` `app.py`(Tab7 内联 Markdown 的 emoji) | T-ENV-01（内嵌评测图需 plotly） | `.ab-*` 改用 token；去掉 📊/🔬 等 emoji |
| T-EXP-02 | 排查 `spoilage_ab` 开/关结果完全一致 | `core/simulator.py` `core/policy.py`(`spoilage_control`) `_step63_ablation.py` | — | 给出结论二选一：(a) 开关确实生效但该数据集下无差异 → 补证据并改文案；(b) 开关未生效 → 修复并重跑该消融（**写入新目录，不覆盖 eval/final**） |
| T-QA-01 | 处理 9 个未使用常量 | `core/config.py` 及引用文档 | T-DOC-01 | 逐个决定"接线 / 删除 / 标注为废弃"，并在 TRD §9 与 README 同步 |

### P2 — 优化与长期健康

| ID | 任务 | 建议写作用域 | 验收标准 |
|---|---|---|---|
| T-EXP-03 | 解释 `ablation_3obj.no_revenue` 毛利反超 Full R³（152,939 vs 152,707） | 实验分析（只读 `eval/final`） | 给出机制解释（或明确标注为包装取整/指标口径导致）并写入 TRD §6.3 |
| T-DOC-02 | 归档根目录 9 个 `_step*.py` 一次性脚本 | 移动文件 + 更新引用 | 移入 `tools/` 或 `eval/_scripts/`，`README`/TRD 引用同步；主线脚本只剩 4 个 run/eval/demo/seed |
| T-QA-02 | 加 UI 规范一致性校验（禁 emoji / 禁硬编码色） | `tests/test_ui_consistency.py`（新建） | 新增测试能在 CI 里挡住违规；现有页面违规项列入白名单并逐条消掉 |
| T-QA-04 | `app.py` 层测试去 gradio 依赖（或显式 skip） | `tests/test_display_layer.py` `tests/test_feedback_view.py` `tests/test_memory_persistence.py` | 无 gradio 环境下不再"失败"，而是 skip 并给出原因；有环境时仍真跑 |
| T-QA-06 | 清理 app.py 中已无引用的渲染函数 | `app.py` | `render_analysis_html`(957)、`render_decision_trace`(246)、`_home_hero`(203)、`_agent_judgement`(211)、`_trim_flag`(174) 逐个确认后删除或重新接线（`render_plan_html`/`render_experiences_html` 仍被测试引用，保留） |
| T-ENV-04 | 自动备份习惯（可选）：Windows 计划任务每日 `vcs.ps1 save -WithData` | `tools/` 新增计划任务安装脚本 | 每天至少一个备份提交；失败时不影响开发；文档写清如何卸载 |

---

## 7. 风险与问题台账

| # | 风险/问题 | 等级 | 当前状态 | 对应任务 |
|---|---|---|---|---|
| R1 | 缺 gradio/plotly → 无法现场演示网页 | 高 | 未解除 | T-ENV-01 |
| R2 | ~~三页迁移未提交，随时可能丢~~ | 中 | ✅ 已解除：全部改动已提交并推送到本地 origin（v0.2.0） | T-ENV-02 |
| R3 | README 与实现漂移，误导接手人 | 中 | 已知，已列差异清单 | T-DOC-01 |
| R4 | `spoilage_ab` 无差异 → 该实验无法自证 | 中 | 未排查 | T-EXP-02 |
| R5 | `no_revenue` 毛利反超 → 可能被评委追问 | 中 | 无解释 | T-EXP-03 |
| R6 | 页面视觉两套体系并存 | 低 | 迁移中 | T-UI-01..04 |
| R7 | 9 个常量已定义未使用，文档却引用 | 低 | 已知 | T-QA-01 / T-DOC-01 |
| R8 | `.pytest_tmp/` 未被忽略，115 个残留条目有误提交风险 | 低 | ✅ 已解除（T-QA-05） | T-QA-05 |
| R9 | 仿真数据局限（无断货/报损记录、50 SKU） | 说明性 | 已在 PRD §8 如实披露 | 对外表述口径：不得夸大 |
| R10 | SQLite schema 变更靠手工 `_migrate()` | 低 | 受控 | 新增字段时补测试 |
| R11 | 删除 `.gitignore` 后，**新克隆环境**不继承忽略规则，可能误提交密钥/产物 | 低 | 已缓解：`vcs.ps1 guard` 一键恢复规则 + `save` 提交守卫（密钥中止、产物撤出） | T-ENV-03 |
| R12 | 本地备份区与工作仓库同盘同目录，磁盘损坏会一起丢 | 低 | 已知：如需异地，把 `_backup/diannao.git` 另拷一份到别的盘/网盘即可 | T-ENV-04 |

---

## 8. 交接记录

### 交接：T-DOC-03 接手文档体系初始化
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成
- 我改了什么：新增 `CLAUDE.md`（规范）、`AGENT.md`（接手/交接流程）、`docs/PRD.md`（需求）、`docs/TRD.md`（设计）、`docs/ARD.md`（本文件）；**未改任何业务代码、未动 data/ 与 eval/final/**
- 证据：本次会话实测 —— `pytest -q --basetemp .pytest_tmp` → 138 passed / 2 failed / 2 skipped；`import gradio/plotly` → ModuleNotFoundError；`eval/final/FROZEN.json` 时间戳与关键指标已核对；`git status --short` 已核对
- 没做完的部分：README 与实现的对齐（T-DOC-01）未做；未提交改动未冻结（T-ENV-02）——**后两项已于同日完成**（T-ENV-02 已入库，见下方交接记录）
- 下一步具体动作：先做 T-ENV-01（装依赖）→ T-DOC-01（README）→ T-UI-01（首页迁移）
- 需要谁配合：有 pip 安装权限的人解除 T-ENV-01

### 交接：T-ENV-02 / T-ENV-03 本地版本控制与备份体系
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成
- 我改了什么：
  - 新增本地备份区 `_backup/`：`diannao.git`（裸仓库，登记为 `origin`，HEAD=main）、`README.txt`、`db-snapshots/`（按需生成）
  - 新增 `tools/vcs.ps1`（guard / status / save / feature / finish / release / rollback / log / branches / versions / verify / snapshot / clone）与 [VERSIONING.md](VERSIONING.md)（GitHub 概念对照、分支模型、提交规范、发布、四种回退方式、忽略策略、FAQ）
  - 删除 `.gitignore`，忽略规则迁入 `.git/info/exclude`（由 `guard` 幂等维护），并在 `save` 中加提交守卫
  - 同步 `CLAUDE.md`（§2.1、铁律 11、检查清单、文档义务）、`AGENT.md`（命令速查、踩坑 3/11）、`README.md`（文档索引 + 第十三节）、`docs/TRD.md`（ADR-008、§1.1、D10）
  - 移除原 GitHub 远端（`https://github.com/wdf8826/diannao-main.git`），URL 已记入 [VERSIONING.md](VERSIONING.md) 备查
- 证据（本次实测）：`git remote -v` → `origin E:/vibe coding/AIC/diannao/_backup/diannao.git`；`git tag` → `v0.1.0`（`ca17f07`）/`v0.2.0`；`vcs.ps1` 各子命令实跑通过；回退演练 `rollback v0.1.0` 生成 `restore/v0.1.0-*` 分支成功；提交守卫实测（强制暂存 `data/*.db` 后被自动撤出、`.env` 命中即中止）；`vcs.ps1 clone` 灾难恢复演练成功；提交哈希见 §9
- 没做完的部分：T-ENV-04（每日自动备份的计划任务）未做，列为 P2；`_backup/` 与工作仓库同盘，异地冗余未做（见 R12）
- 下一步具体动作：装依赖解 T-ENV-01 → 按 [VERSIONING.md](VERSIONING.md) §6.2 从 `develop` 拉 `feature/ui-home` 做 T-UI-01 → 完成后 `vcs.ps1 finish`
- 需要谁配合：无（本地闭环）；如需要异地冗余，需要有人提供第二个磁盘/网盘路径

---

## 9. 变更记录

| 日期 | 谁 | 变更 |
|---|---|---|
| 2026-10-03 | 初始化 Agent | 创建 ARD：拆出 29 个任务点（15 完成 / 1 进行中 / 1 阻塞 / 12 待办）；建立状态口径、ID 规则、验收铁律、风险台账与交接记录模板 |
| 2026-10-03 | 初始化 Agent | 顺手完成 T-QA-05（`.pytest_tmp/` 入 `.gitignore` + 清理 115 个残留）；同步 ARD 计数（16 完成 / 11 待办）与风险台账 R8 状态；README 追加「十二、项目文档索引」并新增 `AGENTS.md` 入口指针 |
| 2026-10-03 | 初始化 Agent | 完成 T-ENV-02（改动全部入库并推送本地 origin）与 T-ENV-03（本地 GitHub 式版本控制：`_backup/diannao.git` 裸仓库作 origin、main/develop 分支、tag v0.1.0/v0.2.0、`tools/vcs.ps1`、[VERSIONING.md](VERSIONING.md)）；删除 `.gitignore`（规则迁至 `.git/info/exclude` + 提交守卫）；同步计数（18 完成 / 0 进行中 / 11 待办）、里程碑 M3、Top3、风险 R2/R11/R12 与交接记录 |
