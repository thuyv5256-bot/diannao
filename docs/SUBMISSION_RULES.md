# Competition Freeze · 提交包构建规则

> 本文件说明**最终比赛提交产物包含什么、不包含什么**。
> 核心原则：**本地保留全部证据，只在提交层面排除。**

## 一、为什么不删文件

审计与整改过程产生了三类有价值的本地文件：

| 文件 | 为什么必须本地保留 |
|---|---|
| `_backup/store_memory_20261004_140831.db` | **唯一**的「污染清理前」数据库快照。删掉就无法回滚、无法追溯「那2222 条污染是怎么来的」 |
| `_audit_eval_truth.py` 等 6 个审计脚本 | 发现了「owner 缺货 0」这一重大比赛风险的证据链 |
| `_p05_isolation_out.txt` | 记录了「一次并发改源码导致测试异常」的完整现场 |

它们**不应该进入提交包**，但**应该留在本地**。所以做法是：`.gitignore` 排除，而不是删除。

## 二、提交包排除清单

以下路径由 `.gitignore` 排除，`git add .` 时自动跳过：

| 类别 | 路径 | 原因 |
|---|---|---|
| **密钥** | `.env`、`.env.local`、`*.key` | **绝不能提交**，含真实 API Key |
| 本地数据库 | `data/*.db`、`data/*.db-wal`、`data/*.db-shm` | 由 CSV 导入生成，可复现 |
| **回滚证据** | `_backup/` | 污染前快照，体积 1.5 MB 且内容敏感 |
| 审计脚本 | `_audit_*.py` | 研发工具，非产品运行组成 |
| 一次性输出 | `_stress_*.py`、`_gitdiff_*.txt`、`_p05_*.txt`、`*.log` | 过程噪音 |
| **历史失败记录** | `_p05_isolation_out.txt` | 含一次并发改源码造成的 `7 failed / 50 errors`，脱离上下文易被误读为项目缺陷 |
| Python 缓存 | `__pycache__/`、`*.pyc`、`build/`、`dist/` | 可再生 |
| 测试缓存 | `.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`.coverage` | 可再生 |
| 虚拟环境 | `.venv/`、`venv/` | 可再生 |
| 编辑器 | `.vscode/`、`.idea/`、`.DS_Store` | 个人信息 |

## 三、提交包应包含

```
README.md                  完整口径（5 分钟启动 / 实验结论 / 数据局限 / AI 边界）
requirements.txt           兼容范围（版本区间）
requirements-lock.txt      冻结时的精确版本（比赛复现用）
design/ DESIGN.md          设计系统
docs/                      PRD / TRD / ARD / 审计与实验报告
data/*.csv                 180 天仿真数据集（必须包含，实验才能复现）
data/shopmind_*.csv
eval/final/                冻结的 180 天实验结果
eval/fair_ab_results.json  公平 A/B 冻结结果
core/ app.py seed_data.py seed_demo_history.py eval_fair_ab.py
tests/                     全部测试
.env.example               模板（不含真实 Key）
```

**注意**：`eval_fair_ab.py` 属于**正式实验框架**，必须包含；
`_audit_*.py` 属于研发审计工具，默认不包含。

## 四、如果需要把审计工具作为亮点提供

在 README 中明确声明后再纳入提交包，例如：

> 我们保留了完整的研发审计脚本（`_audit_*.py`），
> 用于复现「评测口径不公平」「AI 越权建议」等问题的发现过程。

在没有这句话之前，保持排除 —— 避免评委误以为是产品运行入口
（其中 `_audit_eval_truth.py` 会重建数据库，风险较高）。

## 五、构建命令

```bash
# 1. 确认敏感文件未被跟踪
git ls-files | grep -E "\.env$|_backup/|\.log$|__pycache__"   # 应无输出

# 2. 查看将要提交的文件
git add -A --dry-run

# 3. 提交
git add -A
git commit -m "Competition Freeze"
```

## 六、赛前自查清单

- [ ] `git ls-files | grep .env` 无输出
- [ ] `git ls-files | grep _backup` 无输出
- [ ] 提交包内 `.env.example` 存在且不含真实 Key
- [ ] `data/*.csv` 存在（否则实验无法复现）
- [ ] `eval/fair_ab_results.json` 存在
- [ ] `requirements-lock.txt` 存在
- [ ] 换一台机器按 README 的「5 分钟启动」能跑起来
