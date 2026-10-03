# 一次性实验脚本（历史留档）

这些 `_step*.py` 是项目推进过程中用于**产出并冻结实验证据**的一次性脚本，
原先散落在仓库根目录，2026-10-03 按 ARD T-DOC-02 归档到这里。

## 怎么运行

```powershell
# 必须在**仓库根目录**运行（脚本用相对路径读 data/ 与 eval/）
cd <仓库根>
& 'E:\Python\python.exe' tools/experiments/_step92_verify.py
```

脚本自带 sys.path 引导，所以放在 `tools/experiments/` 下也能 `from core import ...`。

## 各脚本做了什么

| 脚本 | 内容 | 是否可安全重跑 |
|---|---|---|
| `_step43_ab.py` | 损耗控制 A/B（R³ 完整 vs 关掉 `spoilage_control`） | 可（只读数据，几分钟） |
| `_step53_ab.py` | Memory A/B（启用 vs 禁用长期记忆） | 可 |
| `_step62_budget.py` | 极端预算压力测试（固定预测/库存，只变预算） | 可 |
| `_step63_ablation.py` | R³ 三目标消融（Full / −Revenue / −Resilience / −Responsibility） | 可 |
| `_step72_final.py` | R³ vs Traditional 180 天正式对照 | 可 |
| `_step9_verify.py` | 从干净状态复现 Full R³ vs Traditional，与冻结结果对比 | 可（只读） |
| `_step92_verify.py` | FINAL 复现验收：重跑并逐指标与冻结值比对 | 可（只读） |
| `_step83_finalize.py` | **生成并冻结** `eval/final/**` | ⚠️ 会写 `eval/final`，除非明确要重新冻结，否则不要跑 |
| `_step9b_rerun.py` | 重跑并用新结果**替换旧 FINAL** | ⚠️ 同上 |

## 为什么归档而不是删除

`eval/final/**` 的每个数字都由这些脚本产出（见 [docs/ARD.md](../../docs/ARD.md) 的 T-EXP-01 证据）。
保留脚本 = 保留「冻结证据可复现」的路径；归档 = 根目录只留 4 个主线入口
（`app.py` / `demo_flow.py` / `seed_data.py` / `eval.py`）。

> ⚠️ 实验产物只读：**不要**用新结果覆盖 `eval/final/**`（见 CLAUDE.md 铁律 4）。
