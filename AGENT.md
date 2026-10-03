# AGENT.md — 小满（diannao）接手与交接手册

> 这份文档的目标只有一个：**任何一个人或 AI Agent，读完就能无门槛接手，接着干活，并把状态干净地交出去。**
> 规则约束看 [CLAUDE.md](CLAUDE.md)；产品需求看 [docs/PRD.md](docs/PRD.md)；技术设计看 [docs/TRD.md](docs/TRD.md)；**进度与下一步看 [docs/ARD.md](docs/ARD.md)**。

---

## 1. 五分钟上手

```text
第 0 分钟  读本文件 §2（心智模型）——先知道这个系统在干什么
第 1 分钟  读 docs/ARD.md 的「当前进度看板」与「下一步任务池」——知道现在在哪、该干什么
第 2 分钟  读 docs/TRD.md §1 分层架构 + §3 数据层——知道数据从哪来
第 3 分钟  读 docs/PRD.md §5 功能需求——知道页面为什么长这样
第 4 分钟  跑通验证（见 §8）：pytest + 目标页面渲染
第 5 分钟  在 docs/ARD.md 里认领一个任务（把状态改成「进行中」并写上自己的名字/标识），开工
```

⚠️ **接手第一原则：先跑通，再动手。** 不要相信"应该能跑"；先执行 §8 的验证命令，拿到真实输出。

---

## 2. 系统心智模型

### 2.1 一句话
小满是社区小店的补货决策 Agent：**每天给出一张进货建议单，并根据店主的真实经营反馈，持续校准这家店自己的补货策略参数。**

### 2.2 一条主闭环（所有功能都挂在这条线上）

```text
        ┌──────────────────────────── 长期记忆库（SQLite）────────────────────────────┐
        │  products / policy / sales / inventory / day_events / experiences /        │
        │  feedback_log / evolution_log / plan_log                                   │
        └───────┬─────────────────────────────────────────────────────────┬──────────┘
                │ 读                                                       │ 写
                ▼                                                          │
   ① 预测需求 forecast.py（EWMA×星期×节日×趋势，断货日还原潜在需求）          │
                │                                                          │
                ▼                                                          │
   ② 事件门控 event_evidence.py（strong 才改预测；weak/insufficient 只记提示）│
                │                                                          │
                ▼                                                          │
   ③ 分配决策 policy.py / r3_optimizer.py                                   │
      （民生兜底 → 弹性分配 → 极端保底；或 R³ 两阶段 MILP）                    │
                │                                                          │
                ▼                                                          │
   ④ 方案输出（7 个网页标签页 / demo_flow.py）                                │
                │                                                          │
                ▼                                                          │
   ⑤ 店主录入真实经营结果（今天生意怎么样）───► evolution.process_feedback ───┘
      （断货 → 安全系数上调；积压损耗 → 下调；带阈值与硬边界防震荡）
```

### 2.3 三条技术主线（改代码前先判断自己属于哪条）

| 主线 | 模块 | 改动风险 |
|---|---|---|
| **决策正确性** | `forecast.py` / `event_evidence.py` / `policy.py` / `r3_optimizer.py` / `metrics.py` | 高：会改变所有实验结论，必须重跑评测并在 ARD 记录 |
| **记忆与自进化** | `memory.py` / `evolution.py` / `dataset.py` | 中高：涉及 SQLite schema 与幂等，改动需迁移与回归 |
| **展示与交互** | `app.py` / `core/*_view.py` / `ui_theme.py` | 低：不影响数值，但必须遵循 DESIGN.md v2 且保持数据真实 |

### 2.4 三条你一定会用到的"事实源"
- **数值口径** → `core/metrics.py`（唯一）、`core/config.py`（全部常量）
- **实验结论** → `eval/final/FROZEN.json` + `eval/final/final_experiment_summary.json`（只读）
- **进度真相** → [docs/ARD.md](docs/ARD.md)

---

## 3. 角色分工与写作用域（并行协作时用）

> 单人/单 Agent 时不必分工；**多人或多 Agent 并行时，必须先按下面切分写作用域，避免同文件并发写**。

| 角色 | 职责 | 建议写作用域（互不重叠） |
|---|---|---|
| 决策/算法 | 预测、事件门控、R³、指标口径 | `core/forecast.py` `core/event_evidence.py` `core/policy.py` `core/r3_optimizer.py` `core/metrics.py` `core/config.py` |
| 记忆/进化 | SQLite、反馈与经验沉淀 | `core/memory.py` `core/evolution.py` `core/dataset.py` |
| 前端/交互 | 7 个页面、UI v2 迁移 | `app.py` `core/*_view.py` `core/ui_theme.py` |
| 实验/证据 | 180 天仿真、消融、冻结产物 | `core/simulator.py` `core/eval_core.py` `run_*.py` `eval/**`（**不覆盖 eval/final**） |
| 文档/交接 | PRD/TRD/ARD/README | `docs/**` `README.md` `CLAUDE.md` `AGENT.md` |

**冲突规则**：`core/config.py` `core/memory.py` `app.py` 是热点文件。同一时间只允许一个写者；需要别人改，先发消息约定，改完再让出。
**交叉依赖**：改决策层 → 实验负责人要在 ARD 里新建"重跑实验"任务；改 schema → 文档负责人同步 TRD §3。

---

## 4. 任务生命周期（ARD 是唯一真相）

```text
   [待办] ──认领──► [进行中] ──有证据──► [已完成]
      ▲                  │                  │
      │                  ├── 遇到硬阻塞 ──► [阻塞]（写明阻塞条件与解除方式）
      └── 打回/需返工 ────┴── 复核不通过 ──► [待复核]
```

**硬性要求：**

1. **没有证据的任务不算完成。** 证据 = 命令 + 输出摘要（`pytest` 结果、脚本 stdout、`eval/` 里的 JSON 数字、文件路径+行号），不能用"应该没问题"。
2. **开始一个任务前**：把 ARD 中该任务状态改为「进行中」并写认领人；若任务不在 ARD 里，先补一条再开工。
3. **完成一个任务时**：把状态改为「已完成」，补上：证据、影响文件、下一步建议。
4. **发现新问题时**：不要顺手改无关代码，直接在 ARD 新建任务（写清现象 + 复现命令 + 影响面）。
5. **blocked 满 3 轮仍无进展**：在 ARD 写明"具体阻塞条件"，并列出解除它需要谁做什么。

---

## 5. 标准工作流 SOP

```text
① 选任务     从 docs/ARD.md「下一步任务池」按 P0 → P1 → P2 取；检查依赖是否已完成
② 认领       更新 ARD 状态为「进行中」+ 认领人 + 开始日期
③ 读上下文   CLAUDE.md §4 领域不变量 → TRD 对应章节 → 目标模块顶部的中文设计注释
④ 先验证现状 跑一次目标功能的当前行为（测试或脚本），记录"改之前是什么样"
⑤ 最小改动   只改必要文件；不顺手重构；新常量进 config；页面样式走 ui_theme token
⑥ 验证       跑 §8 验证手册；对比"改之前/改之后"的真实输出
⑦ 更新文档   ARD 必更；行为变化更 PRD；架构/口径变化更 TRD
⑧ 交接       按 §7 模板留一条交接记录（下一个人不需要问你任何问题就能继续）
```

---

## 6. ARD 更新规范（摘要，详见 [docs/ARD.md](docs/ARD.md) 顶部）

- 任务 ID 格式：`T-<域>-<两位序号>`，域取 `ENV`（环境/依赖）`CORE`（决策算法）`MEM`（记忆进化）`UI`（页面）`EXP`（实验证据）`QA`（测试质量）`DOC`（文档）`RISK`（风险项）。
- 每条任务必须写清：**做什么 / 验收标准 / 证据 / 依赖 / 建议写作用域 / 状态**。
- 状态只允许五种：待办、进行中、已完成、阻塞、待复核。
- 每次编辑在文末「变更记录」追加一行（日期 + 谁 + 改了什么），禁止静默修改。

---

## 7. 交接模板（复制即用）

```markdown
### 交接：<任务 ID> <任务名>
- 日期 / 交接人：
- 状态：进行中 / 已完成 / 阻塞
- 我改了什么（文件 + 关键函数）：
- 证据（命令 + 真实输出摘要）：
- 没做完的部分 / 已知副作用：
- 下一步具体动作（下一个人照着做即可）：
- 需要谁配合：
```

---

## 8. 验证手册（"我怎么证明改对了"）

### 8.1 通用验证

```powershell
# 1) 单元测试（必须带 --basetemp）
& 'E:\Python\python.exe' -m pytest -q --basetemp .pytest_tmp
# 期望：全绿。当前基线（依赖补齐后）= 142 passed，约 92s
#      历史：依赖缺失时曾为 138 passed / 2 failed / 2 skipped（缺 plotly 导致 import app 失败）

# 2) 只跑相关文件（更快）
& 'E:\Python\python.exe' -m pytest -q --basetemp .pytest_tmp tests/test_policy.py tests/test_evolution.py

# 3) 依赖健康检查（应全为 True；缺 gradio/plotly 则网页起不来）
& 'E:\Python\python.exe' -c "import importlib.util as u;print({m:bool(u.find_spec(m)) for m in ['gradio','plotly','pandas','scipy']})"
```

### 8.2 页面类改动（渲染真值）

```powershell
# 期望：打印出非空 HTML 且不含"未定义/None/nan"
& 'E:\Python\python.exe' -c "from core import home_view, policy; p=policy.build_plan('2026-08-28',600.0,policy.MODE_DIANNAO,persist=False); h=home_view.render_home_html(p,'result'); print(len(h)); assert 'None' not in h"
```

**截图核对（推荐，比看 HTML 字符串可靠得多）**：项目已装 `agent-browser`（Chrome/CDP），可自动化截图；
注意 **Windows PowerShell 5.1 不支持 `&&`**，用 `;` 串联，且元素引用必须加引号（否则 `@e1` 会被当成数组展开）：

```powershell
# 1) 起服务（另开后台任务）：& 'E:\Python\python.exe' app.py
# 2) 打开 + 等渲染 + 整页截图
agent-browser open http://127.0.0.1:7861/
agent-browser wait --load networkidle
agent-browser wait 4000
agent-browser screenshot -f _backup/preview/01-home.png
# 3) 列元素找标签页 ref，再逐个切换截图（引号不能省）
agent-browser snapshot -i
agent-browser click '@e3'; agent-browser wait 3000; agent-browser screenshot -f _backup/preview/03-feedback.png
```

> 截图统一存 `_backup/preview/`（该目录已被忽略，不会污染版本库）。2026-10-03 已按此流程核对 7 个标签页：首页/为什么这样进/今天生意怎么样/它学会了什么/店里的老账本/实验验证/项目说明。

自检清单（每个页面改动都要过）：
- [ ] 有真实数据时显示真实数字（不是占位符）
- [ ] **无数据时显示空状态文案**（不许伪造）
- [ ] 没有 emoji、没有硬编码颜色、没有 Dashboard 卡片阵列（DESIGN.md v2）
- [ ] 窄屏不溢出（表格允许横向滚动）

### 8.3 决策类改动

```powershell
# 固定 seed 的长期实验（5~8 分钟，写入 eval/，注意不要覆盖 eval/final）
& 'E:\Python\python.exe' run_digital_store.py
# 快速离线评测（60 天窗口，产出 eval_report.md / eval_results.csv）
& 'E:\Python\python.exe' eval.py
```
改动决策层后，必须对比 `eval/final/final_experiment_summary.json` 里的对应数字，把差异写进 ARD。

---

## 9. 踩坑清单（本仓库真实踩过，别再来一次）

1. **`python` 不是本项目的解释器**。PATH 里是 msys2 3.12（无依赖），必须用 `E:\Python\python.exe`。
2. **pytest 必须带 `--basetemp .pytest_tmp`**，否则临时目录清理会被权限拒绝，报一堆无关错误；该目录可能残留，可手动删。
3. **`--basetemp` 会在根目录生成 `.pytest_tmp/`**：本项目已删除 `.gitignore`，该目录由 `.git/info/exclude` 忽略（`tools/vcs.ps1 guard` 维护），可放心跑；残留可手动删。
4. **日期差一天**：数据末日 `2026-08-27`（已卖完）vs 备货日 `2026-08-28`（明天）。文案写错会被评委抓。
5. **CSV 里 `qty_stockout` / `qty_spoilage` 恒为 0**（9000 行全 0）。任何"店主历史上断货/报损多少"的结论都不成立，必须如实说明数据局限。
6. **`demo-store` 的 `experiences=0`、`evolution_log=0`，但 `feedback_log` 有 301 行** —— 未超阈值不沉淀为经验，这是设计正确行为，不是 bug；页面必须显示真实空状态。
7. **实验数据与门店记忆是隔离的两套东西**：`eval/**` 里 739 条实验经验**绝不能**混进 demo-store 页面（页面只读 `memory.get_experiences()`）。
8. **反馈保存有四种分支**（changes/skipped/updated/removed），文案必须按 `result["changes"]` 判空，不能一律说"已学习"。
9. **事件系数只能乘一次**（预测侧），覆盖天数里再叠就重复计算 —— 这是历史踩过的坑。
10. **不要覆盖 `eval/final/**`：那是已冻结证据。重跑请另建目录，并在 `FROZEN.json` 之外记录。
11. **`eval_results.html` 有 4.8MB**（含内嵌图），别意外提交；它和 `eval_results.csv`/`eval_report.md` 由 `.git/info/exclude` 忽略（原 `.gitignore` 已迁移删除）。
12. **`app.py` 是 63KB 单体**，改页面时优先改 `core/*_view.py`；`app.py` 只改布局/绑定，尽量别在里边写业务逻辑。
13. **UI 迁移是分页进行的**，已完成 反馈/学习/账本 三页；首页、为什么这样进、实验验证、项目说明 仍用旧 class（`dn-*` / `ab-*` / inline style）与 emoji，改的时候不要混用两套体系。
14. **`tools/vcs.ps1` 必须保持 UTF-8 with BOM**（Windows PowerShell 5.1 对无 BOM 的 UTF-8 脚本按 ANSI 解析 → 中文注释破坏语法 → `Unexpected token`）。`.ps1` 的 `.NOTES` 里也写明了这条约束。
15. **`vcs.ps1 rollback` 要求工作区干净**（Git 会拒绝覆盖未提交改动）—— 这是保护而非 bug：先 `vcs.ps1 save` 再回退。
16. **Gradio 6 的 `gr.Tabs` 会自动折叠导航**：横向放不下时它只保留前几个标签、其余塞进「More tabs」下拉（实测把 Tab 容器压到 232px，8 个标签只剩 2 个可见）。所以左侧边栏**没有**去改造 Tabs 的横排导航，而是隐藏它的 `.tab-wrapper`，用 `gr.Radio#xm-nav` 做导航并驱动 `gr.Tabs(selected=…)`；改导航相关代码前先读 [docs/TRD.md](docs/TRD.md) §7.2 与 `core/ui_theme.py` 的 `#xm-nav` 规则。
17. **主题改动只能在 `core/themes.py`**：页面里写死颜色在默认主题下看不出来，一换主题就露馅；`pytest tests/test_themes.py` 会拦住漏 token 的主题。

---

## 10. 命令速查

```powershell
& 'E:\Python\python.exe' app.py                       # 起网页 http://127.0.0.1:7861
& 'E:\Python\python.exe' demo_flow.py                  # 五幕闭环演示
& 'E:\Python\python.exe' eval.py                       # 离线评测 + 报告
& 'E:\Python\python.exe' seed_data.py                  # 重建记忆库（清空并从 CSV 重导入）
& 'E:\Python\python.exe' run_digital_store.py           # 180 天长期实验
& 'E:\Python\python.exe' run_event_awareness_ab.py      # 事件感知 A/B
& 'E:\Python\python.exe' -m pytest -q --basetemp .pytest_tmp

# 版本控制（本地备份区，无 GitHub；见 docs/VERSIONING.md）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 save "feat(x): 说明"
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 verify -Fast
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 versions
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 rollback v0.2.0
```

---

## 11. 当前（2026-10-03）接手速览

- **可跑**：全部命令行脚本（依赖 pandas/numpy/scipy 已具备）。
- **网页可跑**：`python app.py` → http://127.0.0.1:7861（gradio 6.29.1 / plotly 7.1.0 已装，7 个标签页均已人工截图核对）。
- **测试**：142 passed 全绿（92s）。
- **有未提交改动**：`app.py`、`core/learn_view.py`、`core/ledger_view.py`、`tests/test_learn_view.py`、`tests/test_ledger_view.py`（修改）；`core/feedback_view.py`、`tests/test_feedback_view.py`（新增）。**接手前先搞清楚这批改动是否要一起提交。**
- **下一步优先级**：见 [docs/ARD.md](docs/ARD.md) §「下一步任务池」（P0：环境补齐 + 冻结当前改动；P1：剩余页面 UI v2 迁移 + README 对齐；P2：实验异常项排查）。
