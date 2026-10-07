# -*- coding: utf-8 -*-
"""
小满 · R³-Stock 多目标整数优化（创新点 1 的求解器形态）

把「最终采购数量分配」从规则/排序/贪心升级为真正的 Revenue–Resilience–Responsibility
整数优化（MILP）。求解器：HiGHS（经 scipy.optimize.milp 调用，scipy 的 wheel 自带
HiGHS 二进制，无需外部安装求解器）。

═══ 数学模型（两阶段字典序多目标）═══

决策变量（每个商品 i）：
    y_i ∈ ℤ⁺                 —— 进货整包数；x_i = pack_size_i × y_i 为件数
    s_i ∈ ℝ⁺                 —— 相对「目标库存」的韧性缺口（件）
    f_i ∈ ℤ⁺（仅民生商品）   —— 实际锁定的「民生兜底」整包数

硬约束：
    Σ_i (pack_size_i · cost_price_i) · y_i ≤ budget    预算上限
    0 ≤ y_i ≤ U_i（U_i = raw_reorder_i / pack_size_i）  理想补货上界（含保质期封顶）
    y_i = 0（供应商断供商品）                           断供归零
    0 ≤ s_i，且 s_i ≥ target_stock_i − on_hand_i − eligible_in_transit_i − pack_size_i·y_i   韧性缺口定义

目标（字典序，先民生、再收益与韧性）：
    阶段一 Responsibility：max Σ_{i∈民生} w_i · f_i
         （w_i = 客流带动系数 × 需求缺口；预算不足时不 infeasible，而是最大化保障程度）
    阶段二 Revenue + Resilience：
         max Σ_i (unit_margin_i · x_i)  −  λ · Σ_i s_i
         （收益项 = 总毛利；韧性项 = 对相对目标库存缺口的惩罚，λ = RESILIENCE_SHORTFALL_PENALTY）
         s.t. 民生兜底已冻结：y_i ≥ f_i*（阶段一的保障不再被利润挤掉）

求解不可用 / 超时 / 异常时，调用方（policy.build_plan）自动回退到 _allocate 贪心，
保证比赛现场不会因为求解器问题导致系统崩溃。
"""

from .config import RESILIENCE_SHORTFALL_PENALTY, R3_SOLVER_TIMEOUT

SOLVER_NAME = "HiGHS (scipy.optimize.milp)"

try:
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint

    _HAS_SCIPY = True
except Exception:  # noqa: BLE001 —— scipy 缺失时由调用方回退贪心
    _HAS_SCIPY = False


def available() -> bool:
    """求解器是否可用（scipy 是否已安装）。"""
    return _HAS_SCIPY


def unavailable_reason() -> str:
    """不可用原因（供启动自检与测试断言使用，避免静默降级成黑盒）。"""
    if _HAS_SCIPY:
        return ""
    return (
        "scipy.optimize.milp 不可用：已回退规则/贪心，"
        "补货数字仍然可算，但不再是 MILP 整数最优解。"
        "安装冻结依赖可修复：pip install -r requirements-lock.txt"
    )


def _pack(it: dict) -> int:
    return max(1, int(it.get("pack_size") or 1))


def _upper_packs(it: dict) -> int:
    """理想补货量的整包数上界。"""
    return int(float(it.get("raw_reorder") or 0.0) // _pack(it))


def _floor_packs(it: dict) -> int:
    """民生兜底量的整包数。"""
    return int(float(it.get("floor_qty") or 0.0) // _pack(it))


def _solve_milp(c, integrality, bounds, A_rows) -> dict:
    """组装并求解一个最小化 MILP；返回原始求解结果。"""
    if A_rows:
        A = np.vstack([r for r, _, _ in A_rows])
        lb = np.array([lo for _, lo, _ in A_rows], dtype=float)
        ub = np.array([hi for _, _, hi in A_rows], dtype=float)
        constraints = LinearConstraint(A, lb, ub)
    else:
        constraints = None
    return milp(
        c=c,
        integrality=integrality,
        bounds=bounds,
        constraints=constraints,
        options={"time_limit": float(R3_SOLVER_TIMEOUT)},
    )


def _status_label(res) -> str:
    if res.status == 0:
        return "Optimal"
    if res.status == 1:
        return "TimeLimit/IterationLimit"
    if res.status == 2:
        return "Infeasible"
    if res.status == 3:
        return "Unbounded"
    return f"Status{res.status}"


def solve(items: list[dict], budget: float, protect_livelihood: bool = True) -> dict:
    """执行 R³ 两阶段 MILP，把最终采购量写回 items，并返回含求解信息的 meta。

    与 _allocate 约定一致：改写每个 item 的 reorder_qty / cost / trimmed /
    trim_note / floor_secured，返回 meta（含预算、民生兜底、溢出与 solver 信息）。
    任何求解失败都会抛异常，由 policy.build_plan 捕获并回退贪心。
    """
    if not _HAS_SCIPY:
        raise RuntimeError("scipy 未安装，无法调用 HiGHS 求解器")

    # 规范化求解顺序（按 SKU）：并列最优时结果与调用方传入顺序无关（确定性）。
    # 只重排本地列表，不改调用方列表顺序；写回仍作用于同一批 dict 对象。
    items = sorted(items, key=lambda it: str(it.get("sku") or ""))

    n = len(items)
    budget = float(budget)

    # ── 系数准备 ──────────────────────────────────────────
    pack = [_pack(it) for it in items]
    unit_cost = [float(it.get("cost_price") or 0.0) for it in items]
    pack_cost = [pack[i] * unit_cost[i] for i in range(n)]
    unit_margin = [float(it.get("unit_margin") or 0.0) for it in items]
    upper = [_upper_packs(it) for it in items]
    target_stock = [float(it.get("target_stock") or 0.0) for it in items]
    on_hand = [float(it.get("on_hand") or 0.0) for it in items]
    eligible_in_transit = [float(it.get("eligible_in_transit") or 0.0) for it in items]
    floor = [_floor_packs(it) if it.get("is_livelihood") else 0 for it in items]

    liv_idx = [i for i in range(n) if items[i].get("is_livelihood") and floor[i] > 0]

    # ── 阶段一：Responsibility（最大化民生兜底满足度，字典序第一优先）──
    f_star = [0] * n
    if protect_livelihood and liv_idx:
        m = len(liv_idx)
        f_col = {i: k for k, i in enumerate(liv_idx)}  # 商品下标 → f 变量列
        nvars = n + m
        c = np.zeros(nvars)
        for i in liv_idx:
            w = float(items[i].get("traffic_pull") or 1.0) * max(
                float(items[i].get("need_qty") or 0.0), 0.001)
            c[n + f_col[i]] = -w  # minimize −Σ w·f == maximize Σ w·f
        integrality = np.ones(nvars, dtype=int)
        lo = np.zeros(nvars)
        hi = np.zeros(nvars)
        for i in range(n):
            hi[i] = upper[i]
        for i in liv_idx:
            hi[n + f_col[i]] = floor[i]

        rows = []
        # 预算：Σ pack_cost·y ≤ budget
        br = np.zeros(nvars)
        for i in range(n):
            br[i] = pack_cost[i]
        rows.append((br, -np.inf, budget))
        # f_i ≤ y_i  →  f_i − y_i ≤ 0
        for i in liv_idx:
            r = np.zeros(nvars)
            r[i] = -1.0
            r[n + f_col[i]] = 1.0
            rows.append((r, -np.inf, 0.0))

        res1 = _solve_milp(c, integrality, Bounds(lo, hi), rows)
        if res1.status != 0 or res1.x is None:
            raise RuntimeError(f"阶段一(Responsibility)求解失败：{_status_label(res1)}")
        for i in liv_idx:
            f_star[i] = int(round(res1.x[n + f_col[i]]))

    # ── 阶段二：Revenue + Resilience（收益最大化，同时惩罚韧性缺口）──
    nvars = 2 * n
    s_col = n  # s_i 变量从下标 n 开始
    c = np.zeros(nvars)
    for i in range(n):
        c[i] = -pack[i] * unit_margin[i]      # minimize −Σ 毛利·件数
        c[s_col + i] = RESILIENCE_SHORTFALL_PENALTY  # + λ·s_i
    integrality = np.zeros(nvars, dtype=int)
    integrality[:n] = 1                       # y_i 整数；s_i 连续
    lo = np.zeros(nvars)
    hi = np.full(nvars, np.inf)
    for i in range(n):
        hi[i] = upper[i]
        lo[s_col + i] = 0.0

    rows = []
    # 预算约束
    br = np.zeros(nvars)
    for i in range(n):
        br[i] = pack_cost[i]
    rows.append((br, -np.inf, budget))
    # 民生兜底冻结：y_i ≥ f_star[i]  →  −y_i ≤ −f_star[i]
    for i in range(n):
        if f_star[i] > 0:
            r = np.zeros(nvars)
            r[i] = -1.0
            rows.append((r, -np.inf, -float(f_star[i])))
    # 韧性缺口：pack_i·y_i + s_i ≥ target_stock_i − on_hand_i − eligible_in_transit_i
    # 在途库存与补货量(need)同口径：只在覆盖窗口内到货的「有效在途」才抵扣韧性缺口，
    # 晚到的在途不提前算作可用库存，避免韧性度量与建议进货口径不一致。
    for i in range(n):
        rhs = target_stock[i] - on_hand[i] - eligible_in_transit[i]
        r = np.zeros(nvars)
        r[i] = pack[i]
        r[s_col + i] = 1.0
        rows.append((r, rhs, np.inf))

    res2 = _solve_milp(c, integrality, Bounds(lo, hi), rows)
    if res2.status != 0 or res2.x is None:
        raise RuntimeError(f"阶段二(Revenue+Resilience)求解失败：{_status_label(res2)}")

    y_star = [int(round(res2.x[i])) for i in range(n)]
    s_star = [float(res2.x[s_col + i]) for i in range(n)]

    # ── 把最终采购量写回 items（与 _allocate 完全一致的字段语义）──
    for i, it in enumerate(items):
        qty = pack[i] * y_star[i]
        it["reorder_qty"] = float(qty)
        it["cost"] = round(qty * unit_cost[i], 2)
        it["trimmed"] = qty < float(it.get("raw_reorder") or 0.0) - 1e-9
        it["trim_note"] = "预算受限，R³优化后部分满足" if it["trimmed"] else ""
        if it.get("is_livelihood"):
            it["floor_secured"] = qty >= float(it.get("floor_qty") or 0.0) - 1e-9
        else:
            it["floor_secured"] = None

    # ── meta（沿用 _allocate 的键，供下游 evaluate_plan / 决策过程 / 页面使用）──
    total_need_cost = round(sum(float(it.get("raw_cost") or 0.0) for it in items), 2)
    total_cost = round(sum(it["cost"] for it in items), 2)
    overflow = round(max(0.0, budget - total_cost), 2)

    liv = [items[i] for i in liv_idx]
    floor_total = round(sum(float(it.get("floor_cost") or 0.0) for it in liv), 2)
    locked = round(sum(pack[i] * unit_cost[i] * min(y_star[i], floor[i]) for i in liv_idx), 2)
    # 保障率口径与 policy.calculate_essential_coverage 一致：按 SKU 计数（金额口径会虚高）
    all_liv = [i for i in range(n) if items[i].get("is_livelihood")]
    secured_cnt = sum(1 for i in all_liv if pack[i] * y_star[i] >= floor[i] * pack[i] - 1e-9)
    floor_secured = (round(secured_cnt / len(all_liv), 3) if all_liv else 1.0)

    gross_margin = round(sum(y_star[i] * pack[i] * unit_margin[i] for i in range(n)), 2)
    shortfall_units = round(sum(s_star), 1)

    meta = {
        "budget": round(budget, 2),
        "total_need_cost": total_need_cost,
        "budget_tight": total_need_cost > budget + 1e-6,
        "shortfall": round(max(0.0, total_need_cost - budget), 2),
        "livelihood_floor_secured": floor_secured,
        "livelihood_locked_cost": locked,
        "overflow": overflow,
        "solver": {
            "used_milp": True,
            "name": SOLVER_NAME,
            "status": "Optimal",
            "n_skus": n,
            "n_integer_vars": 2 * n,
            "revenue": {"gross_margin": gross_margin},
            "resilience": {
                "shortfall_units": shortfall_units,
                "penalty_per_unit": RESILIENCE_SHORTFALL_PENALTY,
            },
            "responsibility": {
                "floor_locked_cost": locked,
                "floor_total_cost": floor_total,
                "secured_rate": floor_secured,
            },
        },
    }
    return meta
