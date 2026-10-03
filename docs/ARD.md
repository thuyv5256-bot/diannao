# ARD — 小满（diannao）任务分解与进度台账

> **Action & Roadmap Document**：把 [PRD](PRD.md) 的需求与 [TRD](TRD.md) 的设计拆成**可认领、可验收、可交接**的任务点，并记录真实进度与下一步。
> **这是全项目唯一的进度真相**。任何人接手，先看 §1 看板，再进 §6 任务池取活。

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-10-03 |
| 代码基线 | git `ca17f07` + 未提交改动（详见 T-ENV-02） |
| 任务总数 | 32（已完成 23 · 进行中 0 · 阻塞 0 · 待办 9） |
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
| 已完成 | 23 | T-CORE-01..05、T-MEM-01..03、T-EXP-01、T-EXP-04、T-UI-01、T-UI-05..09、T-QA-02、T-QA-03、T-QA-05、T-DOC-03、T-ENV-01、T-ENV-02、T-ENV-03 |
| 进行中 | 0 | —（当前没有进行中任务，取活见 §6） |
| 阻塞 | 0 | —（T-ENV-01 已解除：依赖装齐、网页起得来、测试全绿） |
| 待办 | 11 | 见 §6 |

**今天的真实状态（可复核）**

| 检查项 | 结果 | 证据 |
|---|---|---|
| 测试 | **177 passed 全绿**（约 62s） | `pytest -q --basetemp .pytest_tmp`（新增 `tests/test_ui_consistency.py` 8 项） |
| 网页 | ✅ 已跑起来 | `python app.py` → http://127.0.0.1:7861，HTTP 200；左侧边栏 8 栏目 + 6 套主题即时切换；**首页 v2 迁移后页面可见 emoji = 0**（浏览器实测 `innerText` 扫描）；深色主题下 plotly 图表纸底 `#1a1d23`、字色 `#f0f2f5`（随主题重渲染） |
| 预览截图 | 12 张 | `_backup/preview/01-home.png`…`07-about.png`（8 栏目版另有 `side-01-home.png`/`side-02-settings.png` 与 `theme-01-animal.png`/`theme-02-wenyang.png`/`theme-03-dark.png`/`theme-04-restored.png`）（agent-browser 自动截图，目录已忽略） |
| 命令行脚本 | ✅ 可跑 | pandas / numpy / scipy / pytest / **gradio 6.29.1** / **plotly 7.1.0** 均已安装 |
| 实验证据 | ✅ 已冻结 | `eval/final/FROZEN.json`（2026-10-02 12:35:18） |
| 工作区 | ✅ 干净 | 全部改动已提交并推送到本地备份区（`main` = 最新发布标签、`develop` 为集成线）；`git status --short` 无输出 |
| 版本控制 | ✅ 本地 GitHub 式 | `origin → _backup/diannao.git`（裸仓库，HEAD=main）；分支 `main`/`develop`；标签 `v0.1.0`（初始基线）/`v0.2.0`/`v0.2.1`/`v0.2.2`/`v0.2.3`；`.gitignore` 已删除，忽略规则在 `.git/info/exclude` + `vcs.ps1` 提交守卫 |
| 记忆库快照 | demo-store 真实状态 | `sqlite3` 实测：products 50 / policy 50 / sales 9000 / day_events 180 / **experiences 0** / **evolution_log 0** / feedback_log 301 / plan_log 0；销量表 `qty_stockout`、`qty_spoilage` 非零行数 **0**；日期范围 2026-03-01 ~ 2026-08-27 |

### 🎯 建议的下一个动作（Top 3）

1. **T-UI-02（P1，观感）**：「为什么这样进」页 v2 迁移 —— `why_view` 仍用 `.yw-*`/`.ev-*` 与内联色（11 处），换主题时该页配色不跟随。
2. **T-UI-03 / T-UI-04（P1）**：「实验验证」(`final_view`，28 处内联色) 与「项目说明」(`about_view`，9 处 `.ab-*` 内联色) 同上；这三页迁完，`test_ui_consistency.py` 的 PENDING 白名单即可清空。
3. **T-DOC-01（P1）**：README 与实现对齐（界面导览已修；仍引用 9 个已失效常量、旧参数语义待订正）。

> 规矩：**每完成一件事就 `powershell -File tools/vcs.ps1 save "type(scope): 说明"`**，否则这件事没有回退点 —— 见 [VERSIONING.md](VERSIONING.md)。

---

## 2. 里程碑

| # | 里程碑 | 交付物 | 状态 |
|---|---|---|---|
| M0 | 工程基线 | 可跑的数据导入 + 记忆库 + 测试框架 | ✅ 已完成 |
| M1 | 决策闭环 | 预测 → 事件 → 惠民约束 → 自进化 → 页面闭环（demo_flow 五幕可跑通） | ✅ 已完成 |
| M2 | 实验证据 | 180 天长期仿真 + 消融 + 冻结产物（`eval/final`） | ✅ 已完成（2026-10-02 冻结） |
| M3 | 交付层收尾 | UI v2 全站迁移 + 文档体系 + 版本控制与备份 + 环境可复现 | 🚧 进行中（文档体系 ✅；本地版本控制 ✅；环境 ✅ 依赖与网页验证通过；**仅剩 UI 3/7 页**） |
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
| T-UI-01 | **首页 v2 迁移 + 去 emoji** | 页面无 emoji；无写死颜色；无旧 `dn-*`/`.badge b-*`/`.kpi` 体系；结构与 DESIGN §7 一致（经营工作台） | 删除 app.py 旧内联 CSS（≈3.5KB）与两个死函数；事件图标改 `.xm-badge` 语气徽标（`_EVENT_TONE`/`_event_badge`）；`_hero`/`_trim_flag`/`render_experiences_html`/KPI 卡/分区标题全部 token 化；浏览器实测 `innerText` 可见 emoji **0**、`navLabels=8`；测试 `tests/test_ui_consistency.py` 8 项兜住回归；截图 `tui01-01-home-default.png` / `tui01-04-home-dark.png` | `app.py` `core/ui_theme.py` `tests/test_ui_consistency.py` |
| T-UI-05 | 「今天生意怎么样」v2 迁移 | 四分支文案正确；保存按钮独占行；列名同源 | 新增 `core/feedback_view.py` + `tests/test_feedback_view.py` 10 用例；相关 23 项通过 | `core/feedback_view.py` `app.py`(Tab3) |
| T-UI-06 | 「它学会了什么」v2 迁移 | 只读本店经验表；空状态如实；经验三段式表达 | 重写 `core/learn_view.py`；相关 33 项通过 | `core/learn_view.py` `app.py`(Tab4) `tests/test_learn_view.py` |
| T-UI-07 | 「店里的老账本」v2 迁移 | 五 section + 紧凑 summary；不引实验数据；空状态如实 | 重写 `core/ledger_view.py`；相关 24 项通过 | `core/ledger_view.py` `app.py`(Tab5) `tests/test_ledger_view.py` |
| T-UI-08 | 顶部导航 → **左侧边栏** | 8 个栏目竖排、当前项高亮、点击即切、窄屏折叠为横排 | 新增 `gr.Row#xm-shell` + `Column#xm-side` + `Radio#xm-nav` → `gr.Tabs(selected=…)`；绕开 Gradio 6「More tabs」折叠（隐藏 `.tab-wrapper`）。实测：`navLabels=8`、`tabWrapperDisplay=none`、`moreTabs=0`、`#xm-side=236px`；截图 `_backup/preview/side-01-home.png` | `app.py` `core/ui_theme.py` |
| T-UI-09 | 新增「设置」栏目 + **应用主题**（移植 CodeForge 4 套） | 6 套主题选中即生效、无需刷新；选择持久化；只影响观感；环境信息真实 | `core/themes.py`（6 主题 / 37 必需 token / Gradio 变量）+ `core/settings_store.py` + `core/settings_view.py` + 外壳样式；实测切换森友会/纹样/深色时 `--xm-primary` 分别变为 `#19c8b9`/`#b91c1c`/`#facc15`、侧边栏「当前主题」同步刷新；落盘 `data/ui_settings.json`；新增 27 项测试；截图 `theme-01..04`、`side-02-settings.png` | `core/themes.py` `core/settings_store.py` `core/settings_view.py` `core/ui_theme.py` `app.py` |

> UI 迁移的详细业务事实与约束记录在 `.workbuddy/memory/2026-10-03.md`（B.2/B.3/B.4），建议后续把有效内容并入 TRD §7.2 或本文件。

### 3.5 质量与文档（QA / DOC）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-QA-03 | 测试基线建立 | 全量可跑、失败可解释 | 2026-10-03 实测 `138 passed, 2 failed, 2 skipped in 61.14s`；142 用例 / 21 文件 | `tests/**` `conftest.py` |
| T-QA-02 | UI 规范一致性校验（禁 emoji / 禁写死颜色 / 禁旧 class） | 违规即测试失败；待迁移页有显式白名单且与 ARD 任务联动 | 新增 `tests/test_ui_consistency.py` 8 项：UI 文件无彩色 Emoji（放行 ✓✗★↑↓→ ）、已迁移模块无 hex、`app.py` 无旧体系 class、颜色只住 `themes.py`、`PENDING_MIGRATION` 必须仍在 ARD 里有任务、图表随主题（断言深色下 `paper_bgcolor=#1a1d23`） | `tests/test_ui_consistency.py` |
| T-QA-05 | 忽略并清理 pytest 临时目录 | 忽略规则覆盖 `.pytest_tmp/`；工作区无残留 | 原 `.gitignore:23-24` 新增规则；`Remove-Item` 删除 115 个残留条目，`Test-Path` 返回 False，`git status` 不再出现该项。**该规则后续随 T-ENV-03 迁移到 `.git/info/exclude`（`.gitignore` 已删除）** | `.gitignore` → `.git/info/exclude` |
| T-DOC-03 | 接手文档体系初始化 | 任何人可无门槛接手：规范 + 流程 + 需求 + 设计 + 进度 | 新增 `CLAUDE.md` / `AGENT.md` / `AGENTS.md`（入口指针）/ `docs/PRD.md` / `docs/TRD.md` / `docs/ARD.md`（本文件）；`README.md` 追加「十二、项目文档索引」 | 上述文件 + `README.md` |

### 3.6 工程与版本控制（ENV）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-ENV-01 | 补齐运行依赖并验证网页 | 网页可启动、7 页可切换、测试无环境性失败 | pip 装 gradio 6.29.1 / plotly 7.1.0；`python app.py` → HTTP 200 · 396KB · 7 Tab 截图核对；`pytest` → **142 passed**（92s，原 2 failed/2 skipped 全消）；预览图 `_backup/preview/01..07*.png` | `requirements.txt`（未改动）、`_backup/preview/**` |
| T-ENV-02 | 冻结未提交改动（UI v2 三页迁移 + 文档体系） | 工作区干净；改动全部入库并推送到本地 origin | 4 个逻辑提交：`b0463a5` `feat(ui)` / `a957506` `docs` / `4d3318a` `chore(vcs)` / 本记录提交 `docs(ard)`；再经 `--no-ff` 合并到 `main` | `app.py` `core/*_view.py` `tests/*` `docs/**` `CLAUDE.md` `AGENT.md` `README.md` |
| T-ENV-03 | 建立本地 GitHub 式版本控制与备份区（无 GitHub） | ① 无 GitHub 也能 push / pull / tag / branch / 合并；② 删除 `.gitignore` 后仍不误提交密钥与运行产物；③ 能回退到任意历史版本 | ① `_backup/diannao.git`（bare，HEAD=main）登记为 `origin`，`git remote -v` 可见；② `.git/info/exclude` 忽略规则（7 条探针全命中）+ `vcs.ps1 save` 提交守卫（演练：产物自动撤出、密钥撤出并中止，均实测）；③ 标签 `v0.1.0`（初始基线 `ca17f07`）/`v0.2.0`/`v0.2.1`；④ 回退演练：`rollback v0.1.0` 成功建 `restore/v0.1.0-*` 并切回；⑤ 灾难恢复演练：`clone` 到临时目录成功且标签齐全；⑥ guard 幂等实测；⑦ 演练暴露的 3 个真问题已修（密钥未撤出、guard 编码往返损坏中文、git 提示被当成红色错误）—— 完整记录见 [VERSIONING.md §13](VERSIONING.md) | `tools/vcs.ps1` `docs/VERSIONING.md` `_backup/**` `.git/info/exclude` `README.md` `CLAUDE.md` `AGENT.md` |

---

## 4. 进行中

| ID | 任务 | 认领人 | 开始 | 现状 | 下一步 |
|---|---|---|---|---|---|
| — | 当前没有进行中的任务 | — | — | 待办 11 项见 §6；已无阻塞，P0 仅剩 T-DOC-01 | 认领后把该行替换为本任务的信息，并同步 §1 计数 |

---

## 5. 阻塞

**当前无阻塞项。**

| ID | 任务 | 状态 | 证据 |
|---|---|---|---|
| T-ENV-01 | 补齐运行依赖（`gradio>=6,<7` / `plotly>=6,<8`） | ✅ 已解除（2026-10-03） | ① `import gradio, plotly` → **6.29.1 / 7.1.0**；② `python app.py` → http://127.0.0.1:7861 **HTTP 200**、页面 396KB、7 个标签页逐页截图核对；③ `pytest -q --basetemp .pytest_tmp` → **142 passed**（无 failed、无 skipped） |

> 原验收标准写的是「140 passed, 2 skipped」，实际结果更好：连原先被 skip 的 2 项也跑通了 → **142 passed**。
> 遗留副作用见风险 R14（该 Python 环境的 huggingface-hub / tokenizers 版本冲突，与本项目无关）。

---

## 6. 下一步任务池

### P0 — 不解决就交付不了

| ID | 任务 | 建议写作用域 | 依赖 | 验收标准 |
|---|---|---|---|---|
| T-DOC-01 | README 与实现对齐 | `README.md` | — | ①"界面导览"改为 7 页；②删除已失效的常量引用（见 TRD §9 末尾）；③补三档预算口径；④补 `--basetemp` 与 Python 解释器说明 |

**T-DOC-01 的具体差异清单**（已核对）：

- `README.md` 第二节表格只有 5 个标签页，实际为 7（缺"为什么这样进""实验验证"）。
- `README.md` 第三节引用 `EVOLVE_UP_STEP / EVOLVE_DOWN_STEP / EVOLVE_UP_MAX_MULT` 描述"防震荡设计"，但当前实现是**残差均值 × 0.5、夹紧 ±0.06**（`policy.memory_safety_calibration`），这些常量未被引用。
- `README.md` 第五节目录结构缺 `core/` 下 10 个模块（simulator / r3_optimizer / decision_trace / event_evidence / metrics / risk / llm / ui_theme / *_view 等）。
- `README.md` 未提 `--basetemp .pytest_tmp`、未提三档预算（600 / 360 / 1800）。

### P1 — 明显影响观感或可信度

| ID | 任务 | 建议写作用域 | 依赖 | 验收标准 |
|---|---|---|---|---|
| T-UI-02 | 「为什么这样进」v2 迁移 | `core/why_view.py` `app.py`(Tab2) | — | `.yw-*`/`.ev-*` 改用 `--xm-*` token 与 `.xm-*` 组件；去掉内联硬编码色（#234E70/#66737F…） |
| T-UI-03 | 「实验验证」v2 迁移 | `core/final_view.py` | — | 去掉内联 style 与硬编码色；数字仍全部来自 `eval/final`；结论含归因说明 |
| T-UI-04 | 「项目说明」v2 迁移 | `core/about_view.py` `app.py`(Tab7 内联 Markdown 的 emoji) | —（plotly 已就绪） | `.ab-*` 改用 token；去掉 📊/🔬 等 emoji |
| T-EXP-02 | 排查 `spoilage_ab` 开/关结果完全一致 | `core/simulator.py` `core/policy.py`(`spoilage_control`) `_step63_ablation.py` | — | 给出结论二选一：(a) 开关确实生效但该数据集下无差异 → 补证据并改文案；(b) 开关未生效 → 修复并重跑该消融（**写入新目录，不覆盖 eval/final**） |
| T-QA-01 | 处理 9 个未使用常量 | `core/config.py` 及引用文档 | T-DOC-01 | 逐个决定"接线 / 删除 / 标注为废弃"，并在 TRD §9 与 README 同步 |

### P2 — 优化与长期健康

| ID | 任务 | 建议写作用域 | 验收标准 |
|---|---|---|---|
| T-EXP-03 | 解释 `ablation_3obj.no_revenue` 毛利反超 Full R³（152,939 vs 152,707） | 实验分析（只读 `eval/final`） | 给出机制解释（或明确标注为包装取整/指标口径导致）并写入 TRD §6.3 |
| T-DOC-02 | 归档根目录 9 个 `_step*.py` 一次性脚本 | 移动文件 + 更新引用 | 移入 `tools/` 或 `eval/_scripts/`，`README`/TRD 引用同步；主线脚本只剩 4 个 run/eval/demo/seed |
| T-QA-04 | `app.py` 层测试去 gradio 依赖（或显式 skip） | `tests/test_display_layer.py` `tests/test_feedback_view.py` `tests/test_memory_persistence.py` | 无 gradio 环境下不再"失败"，而是 skip 并给出原因；有环境时仍真跑 |
| T-QA-06 | 清理 app.py 中已无引用的渲染函数 | `app.py` | `render_analysis_html`(957)、`render_decision_trace`(246)、`_home_hero`(203)、`_agent_judgement`(211)、`_trim_flag`(174) 逐个确认后删除或重新接线（`render_plan_html`/`render_experiences_html` 仍被测试引用，保留） |
| T-ENV-04 | 自动备份习惯（可选）：Windows 计划任务每日 `vcs.ps1 save -WithData` | `tools/` 新增计划任务安装脚本 | 每天至少一个备份提交；失败时不影响开发；文档写清如何卸载 |

---

## 7. 风险与问题台账

| # | 风险/问题 | 等级 | 当前状态 | 对应任务 |
|---|---|---|---|---|
| R1 | ~~缺 gradio/plotly → 无法现场演示网页~~ | 高 | ✅ 已解除：装 gradio 6.29.1 / plotly 7.1.0，网页 HTTP 200、7 页截图核对、测试 142 passed | T-ENV-01 |
| R2 | ~~三页迁移未提交，随时可能丢~~ | 中 | ✅ 已解除：全部改动已提交并推送到本地 origin（v0.2.0） | T-ENV-02 |
| R3 | README 与实现漂移，误导接手人 | 中 | 已知，已列差异清单 | T-DOC-01 |
| R4 | `spoilage_ab` 无差异 → 该实验无法自证 | 中 | 未排查 | T-EXP-02 |
| R5 | `no_revenue` 毛利反超 → 可能被评委追问 | 中 | 无解释 | T-EXP-03 |
| R6 | 页面视觉两套体系并存：**app.py 侧已全部统一 v2**，剩 `why_view`/`final_view`/`about_view` 三页仍自带内联色 | 低 | 迁移中（`test_ui_consistency.py` 的 PENDING 白名单即这三页） | T-UI-02..04 |
| R7 | 9 个常量已定义未使用，文档却引用 | 低 | 已知 | T-QA-01 / T-DOC-01 |
| R8 | `.pytest_tmp/` 未被忽略，115 个残留条目有误提交风险 | 低 | ✅ 已解除（T-QA-05） | T-QA-05 |
| R9 | 仿真数据局限（无断货/报损记录、50 SKU） | 说明性 | 已在 PRD §8 如实披露 | 对外表述口径：不得夸大 |
| R10 | SQLite schema 变更靠手工 `_migrate()` | 低 | 受控 | 新增字段时补测试 |
| R11 | 删除 `.gitignore` 后，**新克隆环境**不继承忽略规则，可能误提交密钥/产物 | 低 | 已缓解：`vcs.ps1 guard` 一键恢复规则 + `save` 提交守卫（密钥中止、产物撤出） | T-ENV-03 |
| R12 | 本地备份区与工作仓库同盘同目录，磁盘损坏会一起丢 | 低 | 已知：如需异地，把 `_backup/diannao.git` 另拷一份到别的盘/网盘即可 | T-ENV-04 |
| R13 | `vcs.ps1 rollback` 在工作区不干净时会失败（Git 保护） | 低 | 期望行为，已在 [VERSIONING.md](VERSIONING.md) FAQ 与 [../AGENT.md](../AGENT.md) 踩坑 15 说明 | T-ENV-03 |
| R14 | 装 gradio 6 时它拉入 `huggingface-hub 2.1.1`，与本机 `tokenizers 0.23.1`（要求 hub<2.0）冲突 | 低（对本项目无影响） | 已知：本项目不依赖 tokenizers；但 `E:\Python` 是共享环境，**该环境里其他依赖 tokenizers 的项目可能受影响** —— 如需修复可在那些项目自己的虚拟环境里约束版本 | T-ENV-01 |
| R15 | `跟随系统` 主题下**图表按浅色渲染**（plotly 图是服务端生成的，服务端不知道浏览器偏好） | 低 | 已记录为已知限制（DESIGN §8 / TRD §7.4）；如需精确跟随，可改为生成时同时输出两套图或用 JS 重绘 | T-UI-01 |

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

### 交接：T-UI-08 / T-UI-09 左侧边栏 + 设置栏目与主题系统
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成
- 我改了什么：
  - `app.py`：应用外壳改为 `gr.Row#xm-shell` = 左栏（品牌 `side_brand` + 竖排导航 `gr.Radio#xm-nav`）+ 右栏（`gr.Tabs#main-nav` 的 8 个面板）；`nav_radio.change → gr.Tabs(selected=…)`；三个跨页跳转按钮同时回写导航高亮；新增「设置」Tab（主题单选 + 主题卡片 + 状态 + 运行环境）；`apply_theme()` 落盘 + 就地换肤
  - `core/themes.py`（新）：6 套主题（小满默认 / 野兽风浅色 / 野兽风深色 / 森友会 / 纹样·宣纸 / 跟随系统），其中 **4 套逐色移植自 `E:\vibe coding\CodeForge\src\renderer\styles\{global,dark-theme,animal-theme,wenyang-theme}.css`**；含 `REQUIRED_TOKENS` 完整性约束、Gradio 原生变量、`theme_css()/theme_style_tag()`
  - `core/settings_store.py`（新）：`data/ui_settings.json` 读写（默认值/容错/原子写）
  - `core/settings_view.py`（新）：「设置」页渲染（主题卡片 + 真实运行环境读数）
  - `core/ui_theme.py`：颜色/字体/圆角/描边/阴影全部改为消费主题 token；新增应用外壳与 `#xm-nav` 样式；保留 `THEME_CSS` 兼容名
  - 测试：`tests/test_themes.py`（12）、`tests/test_settings_store.py`（7）、`tests/test_settings_view.py`（8）
  - 文档：PRD FR-15、DESIGN §4/§6/§7/§8、TRD §7.1/§7.2/§8/§10/§12 + ADR-009/010、CLAUDE 铁律 8/代码地图、AGENT 踩坑 16-17、README 界面导览
- 证据（本次实测）：导航 `navLabels=8`、Gradio 自带导航条 `display:none`、无「More tabs」折叠、`#xm-side=236px`；切换主题时 `--xm-primary` 依次为 `#19c8b9`（森友会）/`#b91c1c`（纹样）/`#facc15`（深色），`--xm-sidebar-bg` 同步变化，侧边栏品牌区「当前主题」即时刷新；`data/ui_settings.json` 落盘并在重启后读回；`pytest` **169 passed**；截图 12 张见 `_backup/preview/`
- 没做完的部分：首页/为什么这样进/实验验证/项目说明 四页正文仍是旧 class 与 emoji（T-UI-01..04）；主题只覆盖了 Gradio 常见组件变量，**未逐个核对**每个 Gradio 组件在深色主题下的边角样式（如 Plot 图表背景仍由 plotly 模板决定）
- 下一步具体动作：接 T-UI-01（首页 v2 迁移，去掉 emoji 与 `dn-*`），完成后用 `agent-browser` 在 **两套主题**（默认 + 野兽风深色）各截一次图对比
- 需要谁配合：无

### 交接：T-UI-01 首页 v2 迁移 + T-QA-02 UI 一致性校验
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成
- 我改了什么：
  - `app.py`：删除整段旧内联 CSS（`.dn-hero`/`.dn-card`/`.kpi`/`table.dn`/`.badge b-*`/`.note`/`.good`/`.risk-note`，≈3.5KB）与两个死函数（`_home_hero`/`_agent_judgement`）；事件图标 `_EVENT_ICON` → `_EVENT_TONE` + `_event_badge()`（`.xm-badge` 语气徽标）；`_hero`/`_trim_flag`/`render_experiences_html`/KPI 行/分区标题全部改为 token 化 v2 结构；Tab1 风险面板与 Agent 区块改用 `.xm-sec-title`/`.xm-hint`；按钮与说明文案去 emoji
  - `core/themes.py`：新增 `palette()`（具体色值，plotly 用）与 `plotly_layout()`（模板/底/字/网格/色序）
  - 图表随主题：`evolution_chart`（演进曲线）、`render_eval_figure`（离线评测）、`do_digital_store`（180 天仿真双图）统一套用主题布局；`apply_theme()` 换主题时一并重画演进曲线（plotly 颜色是服务端烘进图里的）
  - `core/ui_theme.py`：新增 `.xm-row` 与 `.xm-callout(-ok/-info)`，取代旧 `.dn-row`/`.note`/`.good`
  - `tests/test_ui_consistency.py`（新，8 项）：UI 文件禁彩色 Emoji、已迁移模块禁写死颜色、颜色只住 `themes.py`、`app.py` 禁旧体系 class、PENDING 白名单必须与 ARD 任务联动、深色主题图表色断言
  - 文档：DESIGN §5（图标/emoji 规则）与 §8（图表主题）、PRD FR-01 状态、TRD §7.2/§7.4/§8/§10/§11/§12/§14、CLAUDE 基线、AGENT 踩坑 18、ARD 看板与任务表
- 证据（本次实测）：浏览器 `document.body.innerText` 可见 emoji **0**；`navLabels=8`、无「More tabs」折叠；切到野兽风深色后 plotly `paper_bgcolor=#1a1d23`、`font.color=#f0f2f5`（换主题即重画）；`app.py` 残留 hex = 0；`pytest` **177 passed**；截图 `_backup/preview/tui01-01-home-default.png`、`tui01-04-home-dark.png`、`tui01-03-learn-dark-chart.png`
- 没做完的部分：`why_view`(T-UI-02)、`final_view`(T-UI-03)、`about_view`(T-UI-04) 三页仍有内联色（已在 `test_ui_consistency.py` 的 `PENDING_MIGRATION` 白名单里显式登记）；`跟随系统` 主题下图表按浅色渲染（R15）；`render_analysis_html`/`render_decision_trace`/`render_experiences_html` 等已无引用函数仍在（T-QA-06）
- 下一步具体动作：按 T-UI-02 → T-UI-03 → T-UI-04 逐页迁移，每迁完一页把模块名从 `PENDING_MIGRATION` 移进 `MIGRATED`（测试立刻开始兜住该页）；完成后可顺手做 T-QA-06 清死代码
- 需要谁配合：无

---

## 9. 变更记录

| 日期 | 谁 | 变更 |
|---|---|---|
| 2026-10-03 | 初始化 Agent | 创建 ARD：拆出 29 个任务点（15 完成 / 1 进行中 / 1 阻塞 / 12 待办）；建立状态口径、ID 规则、验收铁律、风险台账与交接记录模板 |
| 2026-10-03 | 初始化 Agent | 顺手完成 T-QA-05（`.pytest_tmp/` 入 `.gitignore` + 清理 115 个残留）；同步 ARD 计数（16 完成 / 11 待办）与风险台账 R8 状态；README 追加「十二、项目文档索引」并新增 `AGENTS.md` 入口指针 |
| 2026-10-03 | 初始化 Agent | 完成 T-ENV-02（改动全部入库并推送本地 origin）与 T-ENV-03（本地 GitHub 式版本控制：`_backup/diannao.git` 裸仓库作 origin、main/develop 分支、tag v0.1.0/v0.2.0、`tools/vcs.ps1`、[VERSIONING.md](VERSIONING.md)）；删除 `.gitignore`（规则迁至 `.git/info/exclude` + 提交守卫）；同步计数（18 完成 / 0 进行中 / 11 待办）、里程碑 M3、Top3、风险 R2/R11/R12 与交接记录 |
| 2026-10-03 | 初始化 Agent | **v0.2.0 版本哈希**（develop 线）：`b0463a5` = feat(ui) UI v2 三页迁移；`a957506` = docs 接手文档体系；`4d3318a` = chore(vcs) 本地版控与备份区；`fba32b0` = docs(ard) 哈希记录；发布点 = `main` 上的 `--no-ff` 合并提交 `a473142` + annotated tag `v0.2.0` |
| 2026-10-03 | 初始化 Agent | **版本控制演练 + 加固**（T-ENV-03）：跑 7 项演练（产物/密钥守卫、安全回退、灾难恢复克隆、忽略探针、guard 幂等、发布流程），暴露并修掉 3 个真问题 → 提交 `1de5f08`（守卫撤出密钥/产物、ASCII 标记 + UTF-8(BOM) 写 exclude、停止跟踪误入库的 `data/*.db.bak`）与 `69f9867` `fix(vcs)`（`-q` + 错误偏好收敛，消除红色假报错）、`42afc03` `docs(vcs)`（验证记录与边界说明）；证据与修法见 [VERSIONING.md §13](VERSIONING.md)；新增风险 R13；发布点 = `main` 合并提交 `763a676` + tag `v0.2.1`。随后 `6ff13e2`（rollback 提示修复）+ `8e3c536`（版本表）发布 `v0.2.2`（合并提交 `51ee83c`）。**最终状态校验**：工作区干净；`origin` 同步 `main`/`develop`；4 个 tag（v0.1.0/v0.2.0/v0.2.1/v0.2.2）；`.gitignore` 已删除、`.git/info/exclude` 生效（6/6 忽略探针命中）；跟踪文件 108 个、其中**无任何产物或密钥**；数据源 `data/*.csv` 已入库；备份区 `_backup/` 3.14MB（本地 origin 已同步：`git ls-remote --heads --tags origin` 可见 main/develop/v0.1.0/v0.2.0/v0.2.1） |
| 2026-10-03 | 初始化 Agent | **T-ENV-01 解除（依赖 + 网页验证 + 预览截图）**：`pip install -r requirements.txt` → gradio 6.29.1 / plotly 7.1.0；测试从 138 passed / 2 failed / 2 skipped 变为 **142 passed 全绿（92s）**；`python app.py` 起在 http://127.0.0.1:7861（HTTP 200、页面 396KB），用 `agent-browser` 逐页截图 7 个标签页存于 `_backup/preview/`（首页/为什么这样进/今天生意怎么样/它学会了什么/店里的老账本/实验验证/项目说明）；同步 CLAUDE §2/§6、AGENT §8.1/§8.2/§11（新增截图工作流）、TRD §10 与 §12 D1、PRD FR-07、VERSIONING §10、ARD 计数（19 完成 / 0 阻塞 / 11 待办）与 Top3；新增风险 R14（共享环境的 huggingface-hub 版本冲突） |
| 2026-10-03 | 初始化 Agent | **修掉 `vcs.ps1 save` 的致命缺陷**（预览时发现）：给 `git add` 误加 `-q`（`git add` 不支持该选项，退出码 129）会导致 `save` 永远"没有需要提交的改动"；改为捕获输出 + `Write-Host`，并用 `save` 自身提交修复完成端到端验证（`3de3c8e`）；记录于 [VERSIONING.md §13](VERSIONING.md) |
| 2026-10-03 | 初始化 Agent | **T-UI-01 首页 v2 迁移 + T-QA-02 UI 一致性校验**：删除 app.py 旧内联 CSS（≈3.5KB）与两个死函数；事件图标 → `.xm-badge` 语气徽标；`_hero`/`_trim_flag`/经验卡/KPI/分区标题全部 token 化；**页面可见 emoji 归零**；新增 `themes.plotly_layout/palette` 并让演进曲线、离线评测图、180 天仿真图随主题（深色实测纸底 `#1a1d23`、字色 `#f0f2f5`），换主题时 `apply_theme` 一并重画曲线；新增 `tests/test_ui_consistency.py`（8 项，含 PENDING 白名单与 ARD 联动）；测试 169 → **177 passed**；风险 R6 降级、新增 R15（system 主题图表按浅色） |
| 2026-10-03 | 初始化 Agent | **T-UI-08 左侧边栏 + T-UI-09 设置栏目与主题系统**：导航从顶部 Tab 改为左侧边栏；新增 `core/themes.py`（6 套主题，其中野兽风浅/深、森友会、纹样·宣纸 4 套移植自 `E:\vibe coding\CodeForge`）、`core/settings_store.py`、`core/settings_view.py`；新增 FR-15、DESIGN §8、TRD §7.1/§7.2 + ADR-009/ADR-010；测试 142 → **169 passed**；截图核对侧边栏 + 4 套主题；风险 R6 更新 |
