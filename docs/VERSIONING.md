# 版本控制与本地备份策略（GitHub 式 · 纯本地）

| 项 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 最后更新 | 2026-10-03 |
| 适用仓库 | 小满（`diannao`） |
| 工具入口 | `tools/vcs.ps1`（PowerShell，Windows 自带 5.1 即可） |
| 相关文档 | [ARD](ARD.md)（任务台账）· [../CLAUDE.md](../CLAUDE.md)（作业规范）· [../AGENT.md](../AGENT.md)（交接手册） |

---

## 0. 为什么这样设计

1. **不推 GitHub**：项目只在本地流转，不需要联网、不需要账号、不怕仓库被公开。
2. **但仍然用 Git**：分支、提交、标签、合并、回退这些能力是"以后能回滚"的唯一保障，
   文件复制式的"备份文件夹"做不到差异对比与版本回退。
3. **用本地裸仓库扮演 GitHub**：`_backup/diannao.git` 是一个 **bare 仓库**，
   被登记为 `origin`。于是 `push / pull / fetch / clone / tag / branch` **全部照旧可用**，
   体验与操作 GitHub 完全一致 —— 只是"服务器"就在你硬盘上。
4. **删掉 `.gitignore`**：它原来只管"哪些文件不入库"，与 GitHub 无关。
   规则已迁移到 `.git/info/exclude`（同为 Git 原生机制，但不随仓库分发、不在工作区露面），
   再加一层 `vcs.ps1` 的**提交守卫**，因此删掉 `.gitignore` 后**依然不会误提交密钥或大文件**。

> ⚠️ 唯一需要记住的副作用：`.git/info/exclude` 属于**当前克隆**。
> 如果你从备份区重新 `clone` 出一个新目录，请先在新目录执行一次
> `tools/vcs.ps1 guard`（或手动复制原 `.git/info/exclude`），忽略规则才会生效。
> 这已写入 [../AGENT.md](../AGENT.md) 的踩坑清单。

---

## 1. 概念对照：GitHub ↔ 本地

| GitHub 概念 | 本项目的本地对应物 |
|---|---|
| GitHub 远端仓库 | `_backup/diannao.git`（裸仓库，即"本地 GitHub"） |
| `origin` remote | `git remote origin → E:/vibe coding/AIC/diannao/_backup/diannao.git` |
| 默认分支 main | 同名 `main`（稳定分支，只接受合并） |
| Pull Request | `vcs.ps1 finish` / `release` 的 `--no-ff` 合并提交（保留"这是⼀次合并"的历史形状） |
| Protected branch | 约定：不直接往 `main` 提交，只从 `develop`／`release` 合并 |
| Releases / 版本 | annotated tag `vX.Y.Z`（`vcs.ps1 versions` 查看） |
| Actions / CI | `vcs.ps1 verify`（跑 pytest，可选 `-Fast` 跳过昂贵仿真测试） |
| Issues / 看板 | [docs/ARD.md](ARD.md) 任务台账（状态、验收标准、证据） |
| Fork / 分支保护 | 本地 `feature/*` `hotfix/*` `restore/*` 分支 |
| 仓库设置 | `vcs.ps1 guard`（幂等重建裸仓库、origin 与忽略规则） |

**原 GitHub 远端（已移除，仅备查）**：`https://github.com/wdf8826/diannao-main.git`
如需恢复联网远端：`git remote add github <url>`（推送前请自行确认项目是否允许公开）。

---

## 2. 目录与远端

```text
E:\vibe coding\AIC\diannao\
├── .git/                     工作仓库（当前工作现场）
│   └── info/exclude          忽略规则（替代 .gitignore，本地专用）
├── _backup/                  ★ 本地备份区（已被忽略，绝不入库）
│   ├── diannao.git/          裸仓库 = 本地 GitHub（所有分支与标签都在这里）
│   ├── db-snapshots/         可选：data/*.db 的时间戳快照
│   └── README.txt            备份区说明
├── tools/vcs.ps1             版本控制工具（guard/save/feature/finish/release/rollback/verify…）
└── docs/VERSIONING.md        本文件
```

**为什么裸仓库放在项目内**：单机自包含、整目录拷贝即可搬走。
它被 `.git/info/exclude` 的 `_backup/` 规则排除，因此不会被自己跟踪（避免递归）。

---

## 3. 分支模型

```text
main        ●───────────────●──────────────●   ← 稳定线，每个 ● 都有 vX.Y.Z 标签
             \             /              /
develop       ●───●───●───●──────────────●     ← 集成线，日常在这里汇总
                   \     /
feature/*           ●───●                      ← 功能分支，做完 finish 回 develop
hotfix/*                                      ← 紧急修复，直接从 main 拉、修完合回 main
restore/*                                     ← 回退验证分支，从旧版本拉，验证完可弃
```

| 分支 | 从哪里拉 | 合回哪里 | 约定 |
|---|---|---|---|
| `main` | — | — | 只接受 `--no-ff` 合并；每次合并后打 tag；**永远可运行、可发布** |
| `develop` | `main` | `main`（经 release） | 日常开发与文档的主战场 |
| `feature/<名>` | `develop` | `develop` | 一个功能/一个任务一条分支，命名用小写连字符（如 `feature/ui-home`） |
| `hotfix/<名>` | `main` | `main` | 线上/交付期紧急修复 |
| `restore/<版本>-<时间>` | 任意旧版本 | 视情况 | 回退验证用的临时分支，不推送也可以 |

---

## 4. 提交规范

格式：`<type>(<范围>): <中文简述>`，一行说清"做了什么"。

| type | 用途 | 例子 |
|---|---|---|
| `feat` | 新功能 | `feat(ui): 首页迁移到 UI v2` |
| `fix` | 修 bug | `fix(policy): 断供商品不再计入民生兜底` |
| `docs` | 文档 | `docs: 初始化 PRD/TRD/ARD` |
| `chore` | 工程杂项 | `chore(vcs): 建立本地备份区` |
| `refactor` | 重构（不改行为） | `refactor(app): 抽出页面渲染函数` |
| `test` | 测试 | `test(evolution): 补幂等去重用例` |
| `exp` | 实验与数据 | `exp: 重跑 memory A/B（新目录）` |

**纪律**：一次提交只做一件事；提交信息里不写"等等""若干修改"；改完必须能在
[ARD](ARD.md) 里对上号（任务 ID 可写进提交信息，例如 `feat(ui): 首页 v2（T-UI-01）`）。

---

## 5. 版本与标签（语义化版本）

`vMAJOR.MINOR.PATCH`：

| 位 | 何时 +1 | 本项目含义 |
|---|---|---|
| MAJOR | 不兼容变更 | 数据 schema 不兼容、接口契约改变 |
| MINOR | 向后兼容的新增 | 新页面、新实验、新决策能力 |
| PATCH | 修 bug / 文档 | 文案修正、参数订正、文档同步 |

**已发布版本**：

| 标签 | 含义 | 备注 |
|---|---|---|
| `v0.1.0` | 初始代码基线（git `ca17f07`） | 原始提交「店脑补货 Agent 完整项目代码」 |
| `v0.2.0` | UI v2 三页迁移 + 接手文档体系 + 本地版控 | 见 [ARD](ARD.md) T-UI-05..07 / T-DOC-03 / T-ENV-03 |
| `v0.2.1` | 版本控制加固 | 守卫撤出密钥/产物、ignore 规则编码修复（ASCII 标记 + UTF-8 BOM）、停止跟踪误入库的 `data/*.db.bak`、消除红色假报错（`1de5f08`/`69f9867`/`42afc03`） |
| `v0.2.2` | `rollback` 提示文案修正 | 纯提示修复，无行为变化 |
| `v0.2.3` | 最终校验记录 | 文档 |
| `v0.2.4` | T-ENV-01 解除 + `save` 的 `git add -q` 缺陷修复 | 依赖补齐、7 页预览截图、备份工具修复 |
| `v0.3.0` | **顶部导航改为左侧边栏 + 新增「设置」栏目与主题系统** | 6 套主题（4 套移植自 CodeForge）、`core/themes.py`/`settings_store.py`/`settings_view.py`、测试 169 passed（详见 [ARD](ARD.md) T-UI-08/09） |

查看：`tools/vcs.ps1 versions`；某版本改了什么：`git show v0.2.0 --stat`。

---

## 6. 标准流程

### 6.1 日常保存（最常用）

```powershell
# 看一眼现在有什么改动
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 status

# 提交全部改动并推送到本地 origin（=备份）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 save "feat(ui): 首页迁移到 UI v2"

# 需要连 data/store_memory.db 一起留档时（演示前/答辩前推荐）
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 save "chore: 答辩前备份" -WithData
```

### 6.2 功能开发（等价 GitHub PR 流程）

```powershell
powershell -File tools/vcs.ps1 feature ui-home      # 从 develop 拉功能分支
# …改代码、跑测试…
powershell -File tools/vcs.ps1 save "feat(ui): 首页 v2（T-UI-01）"
powershell -File tools/vcs.ps1 verify -Fast         # 本地 CI
powershell -File tools/vcs.ps1 finish               # --no-ff 合并回 develop 并删除功能分支
```

### 6.3 发布（等价 GitHub Release）

```powershell
powershell -File tools/vcs.ps1 release 0.3.0
# 等价动作：develop --no-ff→ main；打 annotated tag v0.3.0；推送 main/develop/--tags
```

### 6.4 紧急修复

```powershell
git switch -c hotfix/fix-xxx main
# …修…
powershell -File tools/vcs.ps1 save "fix(xxx): …"
powershell -File tools/vcs.ps1 finish               # hotfix 自动合回 main
powershell -File tools/vcs.ps1 release 0.3.1
```

---

## 7. 回退与灾难恢复（"以后有回退余地"的具体做法）

### 方式 A｜安全回退（推荐，先验证再决定）

```powershell
powershell -File tools/vcs.ps1 rollback v0.1.0
# → 从 v0.1.0 新建并切到 restore/v0.1.0-<时间> 分支，工作区即该版本内容
# 验证无误后要采纳：git switch main && git merge --no-ff restore/v0.1.0-<时间>
# 确认放弃：        git switch main && git branch -D restore/v0.1.0-<时间>
```

不带参数运行 `rollback` 会先列出所有可回退的版本标签。

### 方式 B｜保留历史的回退（适合已发布版本）

```powershell
git switch main
git log --oneline                 # 找到要撤销的提交
git revert <commit>               # 生成一个"反向提交"，历史完整保留
powershell -File tools/vcs.ps1 save "fix: revert <commit>（原因…）"
```

### 方式 C｜硬回退（本地强制，危险）

```powershell
powershell -File tools/vcs.ps1 rollback v0.2.0 -Hard
# 把当前分支直接重置到 v0.2.0，之后的本地提交从当前分支消失
```

> **为什么硬回退也安全**：所有提交在 `save` 时都会 `push` 到 `_backup/diannao.git`。
> 即使本地分支被重置，仍可通过 `git reflog` 找回，或从裸仓库重新 `clone` / `fetch` 恢复。

### 方式 D｜整机/目录丢失后的恢复

```powershell
# 只要 _backup/diannao.git 还在（或把它拷到新机器）
powershell -File tools/vcs.ps1 clone diannao-restored
cd diannao-restored
powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 guard   # 重建 origin 与忽略规则
```

### 回退前的自检清单

- [ ] 当前改动已 `save`（或确认可以丢弃）
- [ ] `tools/vcs.ps1 versions` 确认目标版本存在
- [ ] 优先用方式 A/B；只有在明确知道后果时才用 C
- [ ] 回退后在 [ARD](ARD.md) 变更记录里写清楚"回到哪个版本、为什么"

---

## 8. 忽略策略（没有 .gitignore 之后）

**规则位置**：`.git/info/exclude`（Git 原生，格式与 `.gitignore` 相同）。
**维护方式**：`tools/vcs.ps1 guard` 幂等写入/校验；脚本里内嵌同一份规则块。

| 被忽略 | 为什么 |
|---|---|
| `_backup/` | 本地备份区自身（裸仓库不得入库，避免递归与体积膨胀） |
| `data/*.db` `*.db.bak` | SQLite 记忆库，首次运行自动重建；1.3MB 且随时变化 |
| `__pycache__/` `*.pyc` | Python 缓存 |
| `.pytest_tmp/` | pytest 临时目录（测试必须用 `--basetemp .pytest_tmp`） |
| `.env` `.env.*` | **密钥**，绝不入库（`.env.example` 例外） |
| `eval_results.html` 等 | 评测产物，4.8MB 且可再生 |
| `*.log` / `.vscode/` / `.idea/` 等 | 日志与编辑器杂项 |
| `data/*.csv` | **不忽略**：CSV 是数据源，必须入库 |

> 补记（2026-10-03）：初始提交 `ca17f07` 曾把一个运行产物 `data/store_memory.db.bak`（1.3MB）误入库。本次已 `git rm --cached` 停止跟踪（文件仍留在磁盘，并由 `data/*.db.bak` 规则忽略）。

**第二道防线（提交守卫）**：`vcs.ps1 save` 在提交前检查暂存区 ——
命中密钥模式（`.env`/`*.pem`/`*.key`）直接中止；命中产物模式自动撤出暂存并提示。
（`-Force` 可强制提交产物；密钥无法被强制。）

> 原 `.gitignore` 的内容已完整迁移到 `.git/info/exclude`；
> 迁移动作与理由记录在 [TRD §13 ADR-008](TRD.md) 与 [ARD](ARD.md) T-ENV-03。

---

## 9. 数据快照（可选）

```powershell
powershell -File tools/vcs.ps1 snapshot            # 单独快照 data/*.db
powershell -File tools/vcs.ps1 save "…" -WithData  # 提交的同时快照
# 产物：_backup/db-snapshots/<yyyyMMdd-HHmmss>/*.db
```

用途：答辩/演示前留一份门店记忆库原样；回退代码时若需要旧库，直接拷回 `data/`。
注意：快照不进 Git（`_backup/` 已忽略），不会撑大仓库。

---

## 10. 本地 CI

```powershell
powershell -File tools/vcs.ps1 verify          # 全量 pytest
powershell -File tools/vcs.ps1 verify -Fast    # 跳过三个昂贵仿真测试，日常用这个
```

当前基线（2026-10-03，依赖补齐后）：**`142 passed` 全绿（约 92s）**。此前缺 `plotly` 时是 138 passed / 2 failed / 2 skipped，随 [ARD](ARD.md) T-ENV-01 解除而消失。

---

## 11. 命令速查

| 场景 | 命令 |
|---|---|
| 看状态 | `vcs.ps1 status` |
| 提交+推送 | `vcs.ps1 save "type(scope): 说明"` |
| 带数据快照 | `vcs.ps1 save "…" -WithData` |
| 开功能分支 | `vcs.ps1 feature <名称>` |
| 合并功能分支 | `vcs.ps1 finish` |
| 发布版本 | `vcs.ps1 release <版本号>` |
| 安全回退 | `vcs.ps1 rollback <版本>` |
| 硬回退 | `vcs.ps1 rollback <版本> -Hard` |
| 列版本 | `vcs.ps1 versions` |
| 历史图 | `vcs.ps1 log` |
| 分支 | `vcs.ps1 branches` |
| 本地 CI | `vcs.ps1 verify [-Fast]` |
| 校验/修复环境 | `vcs.ps1 guard` |
| 灾难恢复克隆 | `vcs.ps1 clone <目录>` |

（在 PowerShell 里可直接 `powershell -NoProfile -ExecutionPolicy Bypass -File tools/vcs.ps1 <命令>`；
也可先 `Set-Alias vcs ...` 或把 `tools` 加进 PATH 后简写为 `vcs.ps1 <命令>`。）

---

## 12. 常见问题

**Q：为什么不用 PowerShell 7（pwsh）？**
A：本机只有 Windows PowerShell 5.1（`powershell.exe`），脚本已按 5.1 兼容编写，且带 UTF-8 BOM
（5.1 对无 BOM 的 UTF-8 脚本会按 ANSI 解析，中文会导致语法错误）。

**Q：删了 `.gitignore` 之后，别人克隆出去会不会把 `.env` 提交上去？**
A：克隆出来的目录里本来就没有 `.env`/`*.db`（它们从来没进过库）；新环境执行一次 `guard`
即获得同样的忽略规则；即使忘了执行，`save` 的提交守卫也会拦下密钥、撤出产物。

**Q：`_backup/diannao.git` 会跟着一起被备份吗？**
A：它本身就是备份。"整目录拷贝"即可搬走全部历史；`_backup/` 被忽略，所以不会被自己跟踪。

**Q：能不能以后再加 GitHub 远端？**
A：可以。`git remote add github <url>` 即可，`origin` 仍指向本地备份区，互不影响。

**Q：`save` 之后本地工作区还能继续改吗？**
A：能。`save` 只是"提交 + 推送本地 origin"，工作区状态不变，随时继续开发。

**Q：执行 `rollback` 报 “Your local changes to the following files would be overwritten by checkout”？**
A：这是 Git 的保护：回退会覆盖工作区，所以**要求先提交或丢弃本地改动**（`vcs.ps1 save` 后再回退）。脚本不会替你丢掉未提交的工作，这是期望行为。

**Q：为什么 `develop` 比 `main` 新？**
A：这是 GitHub Flow 的正常状态 —— `main` 只承载已发布版本（每次合并后打 tag），`develop` 持续领先。要发布时执行 `vcs.ps1 release <版本号>`。

**Q：什么时候允许 force-push？**
A：仅当被改写的提交是**本地误操作/演练产生且尚未交付**时，用 `--force-with-lease`（例：2026-10-03 误产生的 `chore: 守卫演练` 已被改写）。**已发布（打过 tag）或已交付的历史一律不改写**，改用 `git revert` 生成反向提交。

---

## 13. 验证记录（2026-10-03 演练实测）

| # | 演练 | 命令 | 实测结果 |
|---|---|---|---|
| 1 | 产物守卫 | `git add -f data/_drill_artifact.db` → `vcs.ps1 save` | 守卫提示「已自动撤出暂存区」，退出码 0，暂存区清空、该文件未入库 ✅ |
| 2 | 密钥守卫 | `git add -f .env` → `vcs.ps1 save` | 守卫中止提交并把 `.env` 撤出暂存区，退出码 1，`.env` 未入库 ✅ |
| 3 | 安全回退 | `vcs.ps1 rollback v0.1.0` | 成功创建并切到 `restore/v0.1.0-20261003-173535`（该版本下 `tools/vcs.ps1` 不存在，符合预期）；切回 `develop` 后文件恢复；分支可安全删除 ✅ |
| 4 | 灾难恢复 | `git clone _backup/diannao.git _backup/_drill-clone` | 克隆成功，历史与 `v0.1.0`/`v0.2.0` 标签齐全 ✅ |
| 5 | 忽略规则 | `git check-ignore` 探针 `_backup/` `data/*.db` `.env` `.pytest_tmp/` `eval_results.html` | 7/7 命中（含规则来源行号）✅ |
| 6 | guard 幂等 | 连续两次 `vcs.ps1 guard` | 第一次写入规则、第二次提示「已就绪」，无重复追加 ✅ |
| 7 | 发布流程 | `vcs.ps1 release 0.2.0` | `main` 生成 `--no-ff` 合并提交并打 tag `v0.2.0`；`main`/`develop`/tags 全部推送到本地 origin ✅ |

**演练中发现并修掉的两个真问题**（提交 `1de5f08`）：

1. 守卫中止密钥提交后**没有把密钥撤出暂存区** → 改为先 `git reset` 撤出再中止；
2. `guard` 重写 `.git/info/exclude` 时走了 PowerShell 5.1 的 ANSI 编码往返，**中文注释被写坏且幂等判断失效** → 改为 ASCII 标记判断 + `[System.IO.File]::WriteAllText(..., UTF8Encoding($true))` 写入。

**第四处真问题（2026-10-03 预览时发现并修复）**：`save` 里给 `git add` 误加了 `-q` —— `git add` **不支持** `-q`（以退出码 129 失败），结果是 `save` 永远暂存不到东西、永远提示「没有需要提交的改动」。已改为捕获输出 + `Write-Host` 打印，并用 `save` **自身**提交该修复以验证（提交 `3de3c8e`）。教训：`-q` 只对 `commit / push / fetch / switch / reset / branch / clone / init` 有效，`add` 没有。

**另一处真问题**：`rollback`/`release` 里 git 的提示信息（`Switched to branch…`）与 CRLF 提醒会被 PowerShell 5.1 渲染成红色 `NativeCommandError`，甚至因上层 `$ErrorActionPreference='Stop'` 变成终止错误 → 已把相关子命令加 `-q`，并在 `Invoke-Git` 内临时放开错误偏好、捕获取缔后再按退出码判断。

---

## 14. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-10-03 | v1.0 | 建立本地备份区（裸仓库 `_backup/diannao.git` 作为 origin）、GitHub 式分支/标签/发布/回退流程、`tools/vcs.ps1` 工具、以及删除 `.gitignore` 后的忽略与守卫策略；基线与首发版本 tag `v0.1.0`/`v0.2.0` |
| 2026-10-03 | v1.1 | 新增 §13 演练验证记录；修掉守卫不撤出密钥、guard 编码往返两个真问题（`1de5f08`）；`-q` + 错误偏好收敛消除红色假报错；停止跟踪误入库的 `data/*.db.bak`；FAQ 增补 BOM、回退前置条件、force-push 边界；发布 `v0.2.1` |
| 2026-10-03 | v1.2 | 补「已发布版本」表（v0.2.1/v0.2.2）；修 `rollback` 提示文案拼接；发布 `v0.2.2` |
| 2026-10-03 | v1.3 | 补版本表 v0.2.3/v0.2.4/v0.3.0；新增忽略规则 `data/ui_settings.json`（界面偏好属本机设置）；发布 `v0.3.0`（左侧边栏 + 设置/主题）与 `v0.3.1`（本文档同步） |
