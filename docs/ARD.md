# ARD — 小满（diannao）任务分解与进度台账

> **Action & Roadmap Document**：把 [PRD](PRD.md) 的需求与 [TRD](TRD.md) 的设计拆成**可认领、可验收、可交接**的任务点，并记录真实进度与下一步。
> **这是全项目唯一的进度真相**。任何人接手，先看 §1 看板，再进 §6 任务池取活。

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-10-03 |
| 代码基线 | git `ca17f07` + 未提交改动（详见 T-ENV-02） |
| 任务总数 | 36（已完成 36 · 进行中 0 · 阻塞 0 · 待办 0）|
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

**总体阶段：M3 已完成（UI v2 全站迁移 + 主题 + 文档 + 版本控制）—— 交付层收尾，剩余为 README 对齐与实验异常项结论。**

| 状态 | 数量 | 任务 |
|---|---|---|
| 已完成 | 36 | T-CORE-01..05、T-MEM-01..03、T-EXP-01..04、T-UI-01..11、T-QA-01..06、T-DOC-01..03、T-ENV-01..04 |
| 进行中 | 0 | —（当前没有进行中任务，取活见 §6） |
| 阻塞 | 0 | —（T-ENV-01 已解除：依赖装齐、网页起得来、测试全绿） |
| 待办 | 0 | 任务池已清空；持续改进清单见 §6 |

**今天的真实状态（可复核）**

| 检查项 | 结果 | 证据 |
|---|---|---|
| 测试 | **179 passed 全绿** | `pytest -q --basetemp .pytest_tmp`（含 `tests/test_ui_consistency.py` 8 项 + 设置页选择器回归防线） |
| 网页 | ✅ 已跑起来 | `python app.py` → http://127.0.0.1:7861，HTTP 200；左侧边栏 8 栏目 + 6 套主题即时切换；**首页 v2 迁移后页面可见 emoji = 0**（浏览器实测 `innerText` 扫描）；深色主题下 plotly 图表纸底 `#1a1d23`、字色 `#f0f2f5`（随主题重渲染） |
| 预览截图 | 12 张 | `_backup/preview/01-home.png`…`07-about.png`（8 栏目版另有 `side-01-home.png`/`side-02-settings.png` 与 `theme-01-animal.png`/`theme-02-wenyang.png`/`theme-03-dark.png`/`theme-04-restored.png`）（agent-browser 自动截图，目录已忽略） |
| 命令行脚本 | ✅ 可跑 | pandas / numpy / scipy / pytest / **gradio 6.29.1** / **plotly 7.1.0** 均已安装 |
| 实验证据 | ✅ 已冻结 | `eval/final/FROZEN.json`（2026-10-02 12:35:18） |
| 工作区 | ✅ 干净 | 全部改动已提交并推送到本地备份区（`main` = 最新发布标签、`develop` 为集成线）；`git status --short` 无输出 |
| 版本控制 | ✅ 本地 GitHub 式 | `origin → _backup/diannao.git`（裸仓库，HEAD=main）；分支 `main`/`develop`；标签 `v0.1.0`（初始基线）/`v0.2.0`/`v0.2.1`/`v0.2.2`/`v0.2.3`；`.gitignore` 已删除，忽略规则在 `.git/info/exclude` + `vcs.ps1` 提交守卫 |
| 记忆库快照 | demo-store 真实状态 | `sqlite3` 实测：products 50 / policy 50 / sales 9000 / day_events 180 / **experiences 0** / **evolution_log 0** / feedback_log 301 / plan_log 0；销量表 `qty_stockout`、`qty_spoilage` 非零行数 **0**；日期范围 2026-03-01 ~ 2026-08-27 |

### 🎯 建议的下一个动作（Top 3）

1. **T-DOC-01（P0）**：README 与实现对齐 —— 界面导览已修，但正文仍引用 9 个已失效常量与旧参数语义（详见下方差异清单）。
2. **T-EXP-02 / T-EXP-03（P1/P2）**：两个实验异常项需要一个明确结论 —— `spoilage_ab` 开/关结果完全一致、`ablation_3obj.no_revenue` 毛利反超 Full R³。（「实验验证」页已如实标注前者「未触发（如实显示，不做美化）」。）
3. **T-QA-01 / T-DOC-02 / T-ENV-04（P2）**：9 个未使用常量逐个裁决、根目录 9 个 `_step*.py` 归档、可选的每日自动备份计划任务。

> 规矩：**每完成一件事就 `powershell -File tools/vcs.ps1 save "type(scope): 说明"`**，否则这件事没有回退点 —— 见 [VERSIONING.md](VERSIONING.md)。

---

## 2. 里程碑

| # | 里程碑 | 交付物 | 状态 |
|---|---|---|---|
| M0 | 工程基线 | 可跑的数据导入 + 记忆库 + 测试框架 | ✅ 已完成 |
| M1 | 决策闭环 | 预测 → 事件 → 惠民约束 → 自进化 → 页面闭环（demo_flow 五幕可跑通） | ✅ 已完成 |
| M2 | 实验证据 | 180 天长期仿真 + 消融 + 冻结产物（`eval/final`） | ✅ 已完成（2026-10-02 冻结） |
| M3 | 交付层收尾 | UI v2 全站迁移 + 文档体系 + 版本控制与备份 + 环境可复现 | ✅ **已完成**（8 栏目全站 v2 + 6 套主题 + PRD/TRD/ARD/CLAUDE/AGENT/VERSIONING + 本地 Git 备份 + 依赖与网页实测） |
| M4 | 最终交付 | 全绿测试 + 可现场演示 + 接手零障碍 | ✅ **已完成**（177 passed 全绿；8 栏目网页实测可演示；CLAUDE/AGENT/PRD/TRD/ARD/VERSIONING 与实现一致；任务池 34/34） |

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
| T-EXP-02 | 排查 `spoilage_ab` 开/关完全一致 | 给出结论二选一（生效但无差异 / 未生效需修复） | 结论 = **(a) 开关生效但该数据集下从未触发**：从冻结流水逐行核算，9,000 条决策「短保可售容量 − 理想补货量」最小 0.0 / 中位 3.3 / 最大 23.2 件，`spoilage_capped` 命中 **0 次** → 上限 `min()` 从未取到右侧值；两臂仅 `strategy` 标签与记录列 `free_sellable_capacity` 不同。页面「实验验证」④ 已把该核算结果直接展示给评委；TRD §6.3 A 段记录完整推导 | `core/final_view.py` `core/policy.py` |
| T-EXP-03 | 解释 `no_revenue` 毛利反超 Full R³ | 给出机制解释并写入 TRD §6.3 | 结论 = **预算被用于补齐缺口，不是收益目标有害**：逐日求差 revenue +852.0 / purchase_cost +619.9 / sold_qty +86 / stockout_qty −86 / gross_margin +232.1；单位经济性几乎不变（毛利/件 2.1933 vs 2.1939），代价在民生侧（−Responsibility 民生保障 95.0%、民生断货 612）。页面「实验验证」② 现算差额并展示 | `core/final_view.py` `docs/TRD.md` |

### 3.4 页面与 UI v2（UI）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-UI-01 | **首页 v2 迁移 + 去 emoji** | 页面无 emoji；无写死颜色；无旧 `dn-*`/`.badge b-*`/`.kpi` 体系；结构与 DESIGN §7 一致（经营工作台） | 删除 app.py 旧内联 CSS（≈3.5KB）与两个死函数；事件图标改 `.xm-badge` 语气徽标（`_EVENT_TONE`/`_event_badge`）；`_hero`/`_trim_flag`/`render_experiences_html`/KPI 卡/分区标题全部 token 化；浏览器实测 `innerText` 可见 emoji **0**、`navLabels=8`；测试 `tests/test_ui_consistency.py` 8 项兜住回归；截图 `tui01-01-home-default.png` / `tui01-04-home-dark.png` | `app.py` `core/ui_theme.py` `tests/test_ui_consistency.py` |
| T-UI-02 | 「为什么这样进」v2 迁移 | 无 emoji；无写死颜色；六步依据链结构不变 | `WHY_CSS` 全部 token 化（`.yw-*`/`.ev-*` 保留命名空间）；民生标记从不存在的 `.xm-tag` 改为 `.xm-badge xm-badge-green`；实测该页渲染正常、主题跟随；截图 `tui02-why.png` | `core/why_view.py` |
| T-UI-03 | 「实验验证」v2 迁移 | 无 emoji；无写死颜色；**修掉旧体系遗留**（原用已删除的 `.dn-card`/`table.dn`）；4 个小节与全部数字不变 | 重写 `core/final_view.py` 表现层（`.xm-card`/`.xm-table`/`.xm-callout`/`.xm-kv*`/`.xm-bar*`/`.xm-chips`/`.xm-acc`）；`tests/test_final_view.py` 4 项仍全绿（含禁止营销词）；截图 `tui03-final.png` / `tui03-final-dark.png` | `core/final_view.py` |
| T-UI-04 | 「项目说明」v2 迁移 | 无 emoji；无写死颜色；结构与 `about_view` 原意一致 | 重写 `core/about_view.py`：hero/问题/三条能力/技术表全部改用共享组件（`ABOUT_CSS` 清空）；`PENDING` 白名单清零 | `core/about_view.py` |
| T-UI-05 | 「今天生意怎么样」v2 迁移 | 四分支文案正确；保存按钮独占行；列名同源 | 新增 `core/feedback_view.py` + `tests/test_feedback_view.py` 10 用例；相关 23 项通过 | `core/feedback_view.py` `app.py`(Tab3) |
| T-UI-06 | 「它学会了什么」v2 迁移 | 只读本店经验表；空状态如实；经验三段式表达 | 重写 `core/learn_view.py`；相关 33 项通过 | `core/learn_view.py` `app.py`(Tab4) `tests/test_learn_view.py` |
| T-UI-07 | 「店里的老账本」v2 迁移 | 五 section + 紧凑 summary；不引实验数据；空状态如实 | 重写 `core/ledger_view.py`；相关 24 项通过 | `core/ledger_view.py` `app.py`(Tab5) `tests/test_ledger_view.py` |
| T-UI-08 | 顶部导航 → **左侧边栏** | 8 个栏目竖排、当前项高亮、点击即切、窄屏折叠为横排 | 新增 `gr.Row#xm-shell` + `Column#xm-side` + `Radio#xm-nav` → `gr.Tabs(selected=…)`；绕开 Gradio 6「More tabs」折叠（隐藏 `.tab-wrapper`）。实测：`navLabels=8`、`tabWrapperDisplay=none`、`moreTabs=0`、`#xm-side=236px`；截图 `_backup/preview/side-01-home.png` | `app.py` `core/ui_theme.py` |
| T-UI-09 | 新增「设置」栏目 + **应用主题**（移植 CodeForge 4 套） | 6 套主题选中即生效、无需刷新；选择持久化；只影响观感；环境信息真实 | `core/themes.py`（6 主题 / 37 必需 token / Gradio 变量）+ `core/settings_store.py` + `core/settings_view.py` + 外壳样式；实测切换森友会/纹样/深色时 `--xm-primary` 分别变为 `#19c8b9`/`#b91c1c`/`#facc15`、侧边栏「当前主题」同步刷新；落盘 `data/ui_settings.json`；新增 27 项测试；截图 `theme-01..04`、`side-02-settings.png` | `core/themes.py` `core/settings_store.py` `core/settings_view.py` `core/ui_theme.py` `app.py` |
| T-UI-10 | **修复：设置页主题卡片点不动** | 点卡片即换主题（无需刷新）；当前主题高亮与「当前」角标正确；键盘可达（Radio 隐藏但可聚焦）；不再有第二份装饰性展示层 | 根因：页面同时存在「好看的主题卡片（`render_theme_cards` 生成的纯 `div`）」与「真正可交互的 `gr.Radio` 胶囊」，用户点的是前者；先试过 `gr.HTML(js_on_load=…)` 转发点击 —— 实测 `window.__xmThemeCardBound` 仍为 false（该参数只对模板模式 `html_template` 生效），放弃 JS。最终改为**让 Radio 本体就是卡片**：`settings_view.theme_choices()` 提供选项、`theme_card_css()` 按 `:nth-of-type(n)` 给每套主题生成色板与标签/说明/来源（CSS 变量不参与状态），删除 `render_theme_cards`；隐藏 input 用 `opacity:0` 保留 tab 顺序（实测 `display:block / opacity:0 / focusable:true / tabIndex:0`）。**浏览器实测**：点「森友会」卡片 → `--xm-primary=#19c8b9`、侧边栏「当前主题：森友会」、`.selected` 移到该卡片；截图 `bug-settings-card-01/02.png` | `core/settings_view.py` `app.py` `tests/test_settings_view.py` |
| T-UI-11 | **排版整改（Direction A：现代极简工作台）** | 主区吃满宽度、首屏 KPI 条、2/3 主区 + 1/3 侧栏、长表格默认收起、数字列右对齐等宽、侧栏分组与设置沉底、原生块底色透明 | 参考调研（4 站截图，见 §6 I-8）：`vue-element-admin` / `shadcn dashboard` / `refine admin` / `Tremor Blocks`。 **实测（1440 视口）**：主区宽 700 → **1068px**（根因：Gradio 的 `main` 默认 960px 上限把主区压成窄列）；首页高度 **4022 → 1386px**（50 行清单改 `.xm-fold` 默认收起）；设置页卡片 2 列 → **4 列**；首页新增 **4 张 KPI 卡**、实验页 3 张；账本页商品档案（50 行）默认收起。 关键实现：`ui_theme` 新增 `.xm-page-head`/`.xm-kpi*`/`.xm-split`/`.xm-rail`/`.xm-fold`/表格数字列与粘性表头/侧栏分组；`themes.py` 把 `--block-*`/`--panel-*` 改成 **transparent**（表面只由 `.xm-card` 承担，避免卡片里再套灰块）；Gradio 原生彩色标签胶囊改素色。 回归：`pytest` **179 passed**；8 个栏目逐页截图无横向溢出 | `core/ui_theme.py` `core/themes.py` `core/home_view.py` `core/ledger_view.py` `core/final_view.py` `app.py` |


> UI 迁移的详细业务事实与约束记录在 `.workbuddy/memory/2026-10-03.md`（B.2/B.3/B.4），建议后续把有效内容并入 TRD §7.2 或本文件。

### 3.5 质量与文档（QA / DOC）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-QA-03 | 测试基线建立 | 全量可跑、失败可解释 | 2026-10-03 实测 `138 passed, 2 failed, 2 skipped in 61.14s`；142 用例 / 21 文件 | `tests/**` `conftest.py` |
| T-QA-02 | UI 规范一致性校验（禁 emoji / 禁写死颜色 / 禁旧 class） | 违规即测试失败；待迁移页有显式白名单且与 ARD 任务联动 | 新增 `tests/test_ui_consistency.py` 8 项：UI 文件无彩色 Emoji（放行 ✓✗★↑↓→ ）、已迁移模块无 hex、`app.py` 无旧体系 class、颜色只住 `themes.py`、`PENDING_MIGRATION` 必须仍在 ARD 里有任务、图表随主题（断言深色下 `paper_bgcolor=#1a1d23`） | `tests/test_ui_consistency.py` |
| T-QA-06 | 清理 app.py 中已无引用的渲染函数 | 逐个确认无引用后删除；不误删被测试/业务引用的函数 | 删除 7 个死函数（`_cover_badge`/`_reorder_basis`/`_reorder_reason`/`_trim_flag`/`render_decision_trace`/`render_experiences_html`/`render_analysis_html`，共 166 行）与随之失效的 `analysis`/`decision_trace` 导入；`render_plan_html`（被 `do_agent` 与测试使用）与 `render_memory_html`（被账本页使用）保留；`test_memory_persistence` 改用 `learn_view.render_learn_page()`；`pytest` 177 passed | `app.py` `tests/test_memory_persistence.py` |
| T-QA-05 | 忽略并清理 pytest 临时目录 | 忽略规则覆盖 `.pytest_tmp/`；工作区无残留 | 原 `.gitignore:23-24` 新增规则；`Remove-Item` 删除 115 个残留条目，`Test-Path` 返回 False，`git status` 不再出现该项。**该规则后续随 T-ENV-03 迁移到 `.git/info/exclude`（`.gitignore` 已删除）** | `.gitignore` → `.git/info/exclude` |
| T-QA-01 | 处理 9 个未使用常量 | 逐个决定接线/删除/废弃，并在 TRD §9 与 README 同步 | 8 个删除（`LIVELIHOOD_FLOOR_RATIO`、`EVOLVE_*_STEP`×3、`MEMORY_SAFETY_*_STEP`×2、`COLOR_LIVELIHOOD`/`COLOR_PROFIT`），1 个接线（`RESTORE_POTENTIAL` 成为 forecast/policy 各入口默认值，值不变故行为零变化）；顺带把 `MEMORY_BIAS_GAIN` 从 `policy.py` 收回 `config.py`；`pytest tests/test_policy.py tests/test_forecast.py tests/test_evolution.py tests/test_in_transit_eligibility.py` → 29 passed | `core/config.py` `core/policy.py` `core/forecast.py` `core/simulator.py` `docs/TRD.md` |
| T-QA-04 | app.py 层测试缺依赖时 skip | 无 gradio/plotly 环境下 skip 并给出原因；有环境时仍真跑 | `conftest.py` 新增 `require_app()`（`importorskip` + 显式 `exc_type=ImportError`）；4 处调用点改造；**实测**：用 meta_path 插件屏蔽 gradio/plotly 后 `22 passed, 4 skipped`（无告警），正常环境仍全跑 | `conftest.py` `tests/test_display_layer.py` `tests/test_feedback_view.py` `tests/test_memory_persistence.py` `tests/test_ui_consistency.py` |
| T-DOC-03 | 接手文档体系初始化 | 任何人可无门槛接手：规范 + 流程 + 需求 + 设计 + 进度 | 新增 `CLAUDE.md` / `AGENT.md` / `AGENTS.md`（入口指针）/ `docs/PRD.md` / `docs/TRD.md` / `docs/ARD.md`（本文件）；`README.md` 追加「十二、项目文档索引」 | 上述文件 + `README.md` |
| T-DOC-01 | README 与实现对齐 | 界面导览/常量/参数语义/预算口径/命令与实现一致 | ①导览改为左侧边栏 8 栏目；②防震荡描述改为真实公式（残差均值 × 0.5、夹紧 ±0.06）；③目录树补全 core 19 个模块 + tools/ + tests/ + eval/；④补三档预算（600/360/1800）、`--basetemp`、Python 解释器说明；⑤**删除无法复现的「客流损失 7.9pp」声称**（CSV 未采集缺货量，见 `core/analysis.py`）并改为可验证的冻结数据（−¥62 毛利 / 民生缺货率 −0.93pp / 保障率 +5.2pp）；⑥去 emoji、修正版本号与任务数 | `README.md` `core/analysis.py`（新增离线 CLI） |
| T-DOC-02 | 归档根目录 9 个 `_step*.py` | 移入 `tools/`，引用同步；主线脚本只剩 4 个 | `git mv` 到 `tools/experiments/` 并给每个脚本补 `sys.path` 引导；新增该目录 README（标注哪两个会写 `eval/final`，不可随便重跑）；**实测** `python tools/experiments/_step92_verify.py` 从头跑通，18/18 指标与冻结值逐位一致 | `tools/experiments/**` |

### 3.6 工程与版本控制（ENV）

| ID | 任务 | 验收标准 | 证据 | 影响文件 |
|---|---|---|---|---|
| T-ENV-01 | 补齐运行依赖并验证网页 | 网页可启动、7 页可切换、测试无环境性失败 | pip 装 gradio 6.29.1 / plotly 7.1.0；`python app.py` → HTTP 200 · 396KB · 7 Tab 截图核对；`pytest` → **142 passed**（92s，原 2 failed/2 skipped 全消）；预览图 `_backup/preview/01..07*.png` | `requirements.txt`（未改动）、`_backup/preview/**` |
| T-ENV-02 | 冻结未提交改动（UI v2 三页迁移 + 文档体系） | 工作区干净；改动全部入库并推送到本地 origin | 4 个逻辑提交：`b0463a5` `feat(ui)` / `a957506` `docs` / `4d3318a` `chore(vcs)` / 本记录提交 `docs(ard)`；再经 `--no-ff` 合并到 `main` | `app.py` `core/*_view.py` `tests/*` `docs/**` `CLAUDE.md` `AGENT.md` `README.md` |
| T-ENV-03 | 建立本地 GitHub 式版本控制与备份区（无 GitHub） | ① 无 GitHub 也能 push / pull / tag / branch / 合并；② 删除 `.gitignore` 后仍不误提交密钥与运行产物；③ 能回退到任意历史版本 | ① `_backup/diannao.git`（bare，HEAD=main）登记为 `origin`，`git remote -v` 可见；② `.git/info/exclude` 忽略规则（7 条探针全命中）+ `vcs.ps1 save` 提交守卫（演练：产物自动撤出、密钥撤出并中止，均实测）；③ 标签 `v0.1.0`（初始基线 `ca17f07`）/`v0.2.0`/`v0.2.1`；④ 回退演练：`rollback v0.1.0` 成功建 `restore/v0.1.0-*` 并切回；⑤ 灾难恢复演练：`clone` 到临时目录成功且标签齐全；⑥ guard 幂等实测；⑦ 演练暴露的 3 个真问题已修（密钥未撤出、guard 编码往返损坏中文、git 提示被当成红色错误）—— 完整记录见 [VERSIONING.md §13](VERSIONING.md) | `tools/vcs.ps1` `docs/VERSIONING.md` `_backup/**` `.git/info/exclude` `README.md` `CLAUDE.md` `AGENT.md` |
| T-ENV-04 | 每日自动备份（Windows 计划任务） | 每天至少一个备份提交；失败不影响开发；可一键卸载 | 新增 `tools/daily-backup.ps1`（调 `vcs.ps1 save`、可选 `-WithData`、写 `_backup/backup.log`、自动清理 >14 份快照）与 `tools/install-daily-backup.ps1`（注册/卸载/`-RunNow`）；**实测已注册**：`diannao-daily-backup`、State=Ready、NextRun=当天 21:00，手动触发 `LastTaskResult=0` | `tools/daily-backup.ps1` `tools/install-daily-backup.ps1` `docs/VERSIONING.md` |

---

## 4. 进行中

| ID | 任务 | 认领人 | 开始 | 现状 | 下一步 |
|---|---|---|---|---|---|
| — | 当前没有进行中的任务 | — | — | **任务池已清空（34/34 完成）**；后续可从 §6 末的持续改进清单取活，认领时在此登记并同步 §1 计数 | — |

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

**当前任务池为空：34 个任务点全部完成（2026-10-03）。**

下面是**持续改进清单** —— 它们不是未完成的交付项，而是后续接手人可以继续投入的方向（按性价比排序）：

| # | 方向 | 为什么值得做 | 起点 |
|---|---|---|---|
| I-1 | 接入真实门店数据 | 现在用的是仿真 CSV，缺货/报损量没被采集 → 「客流带动实证」（`core/analysis.py`）算不出差异，README 曾据此写过无法复现的 7.9pp 声称（T-DOC-01 已删） | 先补 `sales.qty_stockout / qty_spoilage` 的真实来源，再跑 `python -m core.analysis` |
| I-2 | 配了 LLM Key 后的说明层验收 | 未配 Key 自动降级为规则模板（已实现且测试）；配 Key 后的输出质量没有人工验收记录 | 复制 `.env.example` → `.env` 填 `DEEPSEEK_API_KEY`，跑 `demo_flow.py` 与页面「用大白话解释」 |
| I-3 | 窄屏 / 手机端核对 | 侧边栏 ≤900px 折叠为横排（DESIGN §6）只是按规范实现，没在真机核对 | DevTools 375px 宽逐页截图，必要时调 `.xm-*` 布局 |
| I-4 | 主题对比度校验 | 6 套主题都是手工配色，没做 WCAG 对比度检查 | 在 `tests/test_themes.py` 加「前景/背景对比度 ≥ 4.5」断言，按需微调 `core/themes.py` |
| I-5 | `app.py` 继续瘦身 | 已从 1213 行降到 995 行，但 Tab1 仍有内联 HTML（风险面板 / Agent 区块） | 把这两块搬进 `core/home_view.py`，app.py 只留布局与绑定 |
| I-6 | 把 `.workbuddy/memory/*.md` 有效内容并入 TRD/ARD | 见 §3.4 末尾提示；现在信息在两处，接手人可能只看一处 | 逐条比对后归档，失效的删除 |
| I-7 | 每日备份做异地副本 | 备份区与工作仓库同盘同目录（风险 R12） | 计划任务里追加一步 robocopy 到网盘/移动盘 |
| I-8 | **排版整改（已选方向 A，见 T-UI-11 ✅）** | 现状：内容列在 1248px 视口下只有 700px、首页单页 4022px 高（其中 57 行表格占大半）、缺 KPI 摘要条与右侧信息栏；参考 `vue-element-admin` / `shadcn dashboard` / `refine Finefoods` / `Tremor Blocks`（截图见 `_backup/preview/research/ref-*.png`，不入库）—— 共同点是「左导航 + 流体主区 + 3~4 张 KPI 卡 + 卡片内右上角工具条 + 2/3+1/3 工作台 + 表格分页/筛选」 | 先定方向（A 现代极简 / B 中文后台经典 / C 保持 Notion 风只修布局与表格），再按 §7「先建任务」流程开工 |


---

> **排版调研结论（2026-10-03，未开工）**：无头浏览器实测当前首页几何 —— 视口 1248px、左侧栏 236px、主区仅 **700px**、首页总高 **4022px**、单页 `xm-table` **57 行**。
> 四个能正常截图的参考站（Ant Design Pro preview / Grafana play / Shopify Polaris / 秦丝官网 在无头浏览器里分别白屏、白屏、超时、证书错误，已如实记录）：
> ① [`vue-element-admin`](https://panjiachen.github.io/vue-element-admin/)(admin/111111) 中文后台经典：满宽 4 KPI 卡 + 图表网格 + 表格/待办双栏；
> ② [`shadcn dashboard`](https://ui.shadcn.com/examples/dashboard) 现代极简：KPI 卡带涨跌徽标与一句话解读、卡内右上角工具条（时间范围、列设置）、表格带标签页与分页脚；
> ③ [`refine Finefoods admin`](https://example.admin.refine.dev/) 业务后台：3 张带迷你图的 KPI 卡、地图(2/3)+时间线(1/3)、订单表(2/3)+热门商品(1/3)、状态徽标与行操作；
> ④ [`Tremor Blocks`](https://blocks.tremor.so/) 组件图鉴：大数字 + 说明 + 涨跌的小卡片族与图表卡片规范。
> 结论草案：**取结构与密度，不取它们的配色装饰**（本项目 DESIGN.md 是 Notion 风：白底、1px 边、无阴影、单一强调色）。候选方向 A/B/C 与线框见本轮对话，选定后在 ARD 建正式任务（届时 T-UI-11）再动代码。
## 7. 风险与问题台账

| # | 风险/问题 | 等级 | 当前状态 | 对应任务 |
|---|---|---|---|---|
| R1 | ~~缺 gradio/plotly → 无法现场演示网页~~ | 高 | ✅ 已解除：装 gradio 6.29.1 / plotly 7.1.0，网页 HTTP 200、7 页截图核对、测试 142 passed | T-ENV-01 |
| R2 | ~~三页迁移未提交，随时可能丢~~ | 中 | ✅ 已解除：全部改动已提交并推送到本地 origin（v0.2.0） | T-ENV-02 |
| R3 | ~~README 与实现漂移~~ | 中 | ✅ 已解除：界面导览、常量、参数语义、三档预算、命令与解释器说明全部对齐；**并删除了无法复现的 7.9pp 声称**（T-DOC-01） | T-DOC-01 |
| R4 | ~~`spoilage_ab` 无差异~~ | 中 | ✅ 已查清：采购上限从未生效（9,000 条决策余量恒 ≥ 0、capped 命中 0 次），开关逻辑正确、非接线 bug；页面已展示核算过程（T-EXP-02，TRD §6.3 A） | T-EXP-02 |
| R5 | ~~`no_revenue` 毛利反超~~ | 中 | ✅ 已解释：去掉收益项后预算被用于补齐缺口（多进 ¥620 / 多卖 86 件），收入盖过成本，代价在民生侧；页面现算差额（T-EXP-03，TRD §6.3 B） | T-EXP-03 |
| R6 | ~~页面视觉两套体系并存~~ | 低 | ✅ 已解除：全站统一 v2，`PENDING` 白名单清零、全部 `*_view.py` 进 `MIGRATED` | T-UI-01..04 |
| R7 | ~~9 个常量已定义未使用~~ | 低 | ✅ 已解除：8 删 1 接线，`MEMORY_BIAS_GAIN` 收回 config；TRD §9 与 README 同步（T-QA-01） | T-QA-01 |
| R8 | `.pytest_tmp/` 未被忽略，115 个残留条目有误提交风险 | 低 | ✅ 已解除（T-QA-05） | T-QA-05 |
| R9 | 仿真数据局限（无断货/报损记录、50 SKU） | 说明性 | 已在 PRD §8 如实披露 | 对外表述口径：不得夸大 |
| R10 | SQLite schema 变更靠手工 `_migrate()` | 低 | 受控 | 新增字段时补测试 |
| R11 | 删除 `.gitignore` 后，**新克隆环境**不继承忽略规则，可能误提交密钥/产物 | 低 | 已缓解：`vcs.ps1 guard` 一键恢复规则 + `save` 提交守卫（密钥中止、产物撤出） | T-ENV-03 |
| R12 | 本地备份区与工作仓库同盘同目录，磁盘损坏会一起丢 | 低 | 已缓解一半：每日自动备份（21:00）已在跑，但仍是同盘；异地副本见 §6 改进项 I-7 | T-ENV-04 |
| R13 | `vcs.ps1 rollback` 在工作区不干净时会失败（Git 保护） | 低 | 期望行为，已在 [VERSIONING.md](VERSIONING.md) FAQ 与 [../AGENT.md](../AGENT.md) 踩坑 15 说明 | T-ENV-03 |
| R14 | 装 gradio 6 时它拉入 `huggingface-hub 2.1.1`，与本机 `tokenizers 0.23.1`（要求 hub<2.0）冲突 | 低（对本项目无影响） | 已知：本项目不依赖 tokenizers；但 `E:\Python` 是共享环境，**该环境里其他依赖 tokenizers 的项目可能受影响** —— 如需修复可在那些项目自己的虚拟环境里约束版本 | T-ENV-01 |
| R15 | `跟随系统` 主题下**图表按浅色渲染**（plotly 图是服务端生成的，服务端不知道浏览器偏好） | 低 | 已记录为已知限制（DESIGN §8 / TRD §7.4）；如需精确跟随，可改为生成时同时输出两套图或用 JS 重绘 | T-UI-01 |
| R16 | 冻结记录里的 `metrics_version` 哈希与当前 `core/metrics.py` 不一致（`c28cf12a…` vs `e5e64a08…`） | 低 | 已知并已量化：仓库只有一次导入提交，差异应发生在冻结之后、入库之前；**重跑验收 18/18 指标与冻结值逐位一致**（`tools/experiments/_step92_verify.py`），故证据仍有效。今后改 `core/metrics.py` 口径必须新建目录重新冻结（铁律 4） | T-DOC-02 |
| R17 | ~~设置页主题选择器有两份展示层（装饰卡片点不动、可用的 Radio 在最上面）~~ | 低 | ✅ 已解除（T-UI-10）：控件本体即卡片，`tests/test_settings_view.py::test_picker_is_a_single_control` 兜住「不许再出现装饰性副本」 | T-UI-10 |

---

## 8. 交接记录

### 交接：T-UI-10 修复「设置页主题卡片点不动」
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成
- 现象与根因：设置页同时存在两份「主题选择」——`render_theme_cards()` 生成的好看卡片（纯 `div`，无任何事件）与真正可交互的 `gr.Radio` 胶囊；用户点的是卡片，所以毫无反应。
- 走过的弯路（已记录，避免重犯）：先试图用 `gr.HTML(js_on_load=…)` 把卡片点击转发给 Radio —— 浏览器实测 `window.__xmThemeCardBound` 仍为 false，说明该参数只对模板模式（`html_template`）生效，普通 `value=` 模式不执行脚本。
- 最终做法：**让控件本体就是卡片** —— `theme_choices()` 提供 Radio 选项，`theme_card_css()` 按 `:nth-of-type(n)` 为每套主题生成色板渐变与「标签/说明/来源」文案（`::after` content）；删除 `render_theme_cards` 与 `CARD_CLICK_JS`；原生 input 用 `opacity:0` 隐藏以保留 tab 顺序与键盘切换。
- 证据（浏览器实测）：点「森友会」卡片 → `--xm-primary=#19c8b9`、侧边栏「当前主题：森友会」、`.selected` 类移到该卡片；`display:block / opacity:0 / focusable:true / tabIndex:0`；截图 `_backup/preview/bug-settings-card-01.png`（默认态）、`bug-settings-card-02.png`（点后）。`pytest` **179 passed**（含新增 `test_picker_is_a_single_control` 回归防线）。
- 没做完的部分：无。
- 下一步具体动作：若继续做 §6 的改进项，注意沿用「控件本体承担外观」这条规则（已写进 CLAUDE 铁律 8、DESIGN §8 第 6 条、AGENT 踩坑 23）。
- 需要谁配合：无

---
### 交接：收尾 7 项（文档对齐 / 常量裁决 / 两个实验异常项 / 脚本归档 / 测试降级依赖 / 自动备份）
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成（任务池 34/34 清零）
- 我改了什么：
  - `README.md`：界面导览/防震荡机制/目录树/三档预算/命令与解释器说明全部对齐；**删掉「客流损失 7.9pp」这一在当前数据集上无法复现的声称**，换成冻结数据可验证的口径
  - `core/config.py`：删 8 个未使用常量、`RESTORE_POTENTIAL` 接线为 forecast/policy 各入口默认值、`MEMORY_BIAS_GAIN` 从 policy 收回 config、颜色常量移除并说明颜色归 `themes.py`
  - `core/final_view.py`：新增 `spoilage_headroom()` 与 `tradeoff_mechanism()`，把两个异常项的核算过程直接展示在「实验验证」页（数字全部从 `eval/final` 现算）
  - `core/analysis.py`：新增 `python -m core.analysis` 离线入口，并如实输出「本数据集无民生缺货日 → 无法量化客流带动」
  - `tools/experiments/`：9 个 `_step*.py` 归档 + sys.path 引导 + 目录 README（标明哪两个会写 `eval/final`）
  - `tools/daily-backup.ps1` + `tools/install-daily-backup.ps1`：每日自动备份（含日志、快照清理、一键卸载）
  - `conftest.py` 新增 `require_app()`：UI 层测试缺 gradio/plotly 时 skip 而非失败
- 证据：`pytest` 177 passed；`tools/experiments/_step92_verify.py` → `ALL_EXACT_MATCH: True`（18/18 指标与冻结值逐位一致）；屏蔽 gradio/plotly 后 `22 passed, 4 skipped`；`Get-ScheduledTask diannao-daily-backup` → Ready / NextRun 当天 21:00 / LastTaskResult 0；`python -m core.analysis` 输出如实结论
- 没做完的部分：无未完成任务。持续改进项见 §6（接入真实数据、LLM Key 验收、窄屏核对、主题对比度、app.py 继续瘦身、异地备份）
- 下一步具体动作：若继续投入，建议 I-1（真实数据里的缺货/报损采集）—— 它能一次性解锁「客流带动实证」与更真实的损耗控制验证
- 需要谁配合：无

---
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

### 交接：T-UI-02 / T-UI-03 / T-UI-04 / T-QA-06 全站 v2 收尾 + 死代码清理
- 日期 / 交接人：2026-10-03 / 初始化 Agent
- 状态：已完成
- 我改了什么：
  - `core/why_view.py`：`WHY_CSS` 全部改为 `--xm-*` token（保留 `.yw-*`/`.ev-*` 命名空间）；民生标记从不存在的 `.xm-tag` 改为 `.xm-badge xm-badge-green`
  - `core/final_view.py`：表现层重写为共享组件（`.xm-card`/`.xm-h3`/`.xm-table`/`.xm-callout`/`.xm-kv*`/`.xm-bar*`/`.xm-chips`/`.xm-acc`），数据逻辑一字未改；**并修掉它引用已删除的 `.dn-card`/`table.dn` 造成的样式破损**
  - `core/about_view.py`：hero / 问题 / 三条能力 / 技术表全部改用共享组件，`ABOUT_CSS` 清空
  - `core/ui_theme.py`：新增 `.xm-kv-row/.xm-kv/.xm-kv-k/.xm-kv-v/.xm-kv-sub`、`.xm-bar-*`、`.xm-chips`；删掉 `.st-kv*`（settings_view 改用 `.xm-kv*`）
  - `app.py`：删除 7 个无引用渲染函数（`_cover_badge`/`_reorder_basis`/`_reorder_reason`/`_trim_flag`/`render_decision_trace`/`render_experiences_html`/`render_analysis_html`，共 166 行）与随之失效的 `analysis`/`decision_trace` 导入
  - 测试：`tests/test_ui_consistency.py` 的 `MIGRATED` 收下三页、`PENDING` 清空，并把「待迁移白名单必须与 ARD 联动」改成「每个 `*_view.py` 必须已分类」；`tests/test_memory_persistence.py` 改用 `learn_view.render_learn_page()`
- 证据（本次实测）：三页渲染正常且主题跟随（截图 `tui02-why.png`、`tui03-final.png`、`tui03-final-dark.png`、`tui04-about.png`）；浏览器 `innerText` 扫描 emoji = 0；`why_view`/`final_view`/`about_view`/`app.py` 残留 hex = 0、无旧 `dn-*`；`pytest` **177 passed**（`test_final_view` 4 项含「禁止营销词」全绿）；`app.py` 由 1213 行降到 1047 行
- 没做完的部分：T-DOC-01（README 常量/参数语义）、T-EXP-02/03（两个实验异常项结论）、T-QA-01（9 个未使用常量裁决）、T-DOC-02（`_step*.py` 归档）、T-ENV-04（自动备份计划任务）；`system` 主题下图表仍按浅色渲染（R15）
- 下一步具体动作：先做 T-DOC-01（纯文档，风险最低），再做 T-EXP-02 —— 在 `core/simulator.py` 里确认 `spoilage_control` 开关是否真的进入了决策路径（若确实未触发就直接在 ARD/TRD 记「该数据下无差异」并保留页面上的如实说明）
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
| 2026-10-03 | 初始化 Agent | **T-UI-11 补丁（v0.7.1）**：修掉表格里中文逐字竖排 —— 表头/数字/徽标/说明 nowrap、内边距收紧（14/20→10/14）、`进货后约够`→`够几天`、数值列右对齐、≤1280px 分栏改为上下排（1250 视口表格 495→812px，表头全部单行）；`DESIGN` 增第 8 条「短文本不许换行」；测试仍 179 passed |
| 2026-10-03 | 初始化 Agent | **T-UI-11 排版整改（Direction A）**：主区 700→1068px、首页 4022→1386px、设置卡片 2→4 列、首屏 4 张 KPI 卡、长表格折叠、数字列右对齐、侧栏分组+设置沉底、原生块底色透明；调研 4 站记入 I-8；测试仍 179 passed |
| 2026-10-03 | 初始化 Agent | **T-UI-10 修复设置页主题卡片点不动**：根因是「装饰性卡片 + 隐藏 Radio」双份展示层；改为 Radio 本体渲染成卡片（`theme_choices()` + `theme_card_css()`，删除 `render_theme_cards`），隐藏 input 保留键盘可达；浏览器实测点卡即换肤；测试 177 → 179 passed |
| 2026-10-03 | 初始化 Agent | **收尾 7 项（T-DOC-01 / T-QA-01 / T-EXP-02 / T-EXP-03 / T-DOC-02 / T-QA-04 / T-ENV-04）→ 任务池清零**：README 全面对齐（含删除无法复现的 7.9pp 声称）；9 个未使用常量 8 删 1 接线；两个实验异常项查清并写进 TRD §6.3 + 页面现算展示；`_step*.py` 归档 `tools/experiments/` 并实测复现 18/18 指标；UI 层测试缺依赖时 skip；每日自动备份计划任务已注册实测。测试仍 **177 passed** |
| 2026-10-03 | 初始化 Agent | **全站 v2 迁移收尾（T-UI-02/03/04）+ 死代码清理（T-QA-06）**：为什么这样进 / 实验验证 / 项目说明三页迁完 → `test_ui_consistency.py` 的 `PENDING` 白名单清零、三页进 `MIGRATED`；`final_view` 顺带修掉引用已删除 `.dn-card`/`table.dn` 的遗留破损；新增共享组件 `.xm-kv*`/`.xm-bar*`/`.xm-chips`（`.st-kv*` 并入）；删除 7 个无引用渲染函数（166 行）与失效导入，`test_memory_persistence` 改用 `learn_view`；新增测试「每个 `*_view.py` 必须已分类」；测试仍 177 passed；D3/D4 关闭 |
| 2026-10-03 | 初始化 Agent | **T-UI-01 首页 v2 迁移 + T-QA-02 UI 一致性校验**：删除 app.py 旧内联 CSS（≈3.5KB）与两个死函数；事件图标 → `.xm-badge` 语气徽标；`_hero`/`_trim_flag`/经验卡/KPI/分区标题全部 token 化；**页面可见 emoji 归零**；新增 `themes.plotly_layout/palette` 并让演进曲线、离线评测图、180 天仿真图随主题（深色实测纸底 `#1a1d23`、字色 `#f0f2f5`），换主题时 `apply_theme` 一并重画曲线；新增 `tests/test_ui_consistency.py`（8 项，含 PENDING 白名单与 ARD 联动）；测试 169 → **177 passed**；风险 R6 降级、新增 R15（system 主题图表按浅色） |
| 2026-10-03 | 初始化 Agent | **T-UI-08 左侧边栏 + T-UI-09 设置栏目与主题系统**：导航从顶部 Tab 改为左侧边栏；新增 `core/themes.py`（6 套主题，其中野兽风浅/深、森友会、纹样·宣纸 4 套移植自 `E:\vibe coding\CodeForge`）、`core/settings_store.py`、`core/settings_view.py`；新增 FR-15、DESIGN §8、TRD §7.1/§7.2 + ADR-009/ADR-010；测试 142 → **169 passed**；截图核对侧边栏 + 4 套主题；风险 R6 更新 |
