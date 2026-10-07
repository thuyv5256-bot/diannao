# -*- coding: utf-8 -*-
"""演示日期披露与仿真数据口径的回归测试。

背景
----
本项目使用**固定的 180 天仿真数据集**（2026-03-01 ~ 2026-08-27），
正式演示决策日为** 2026-08-28**。但首页标题叫「今天该进什么货」，
容易被误读成「电脑当前日期」—— 这在比赛现场是实打实的风险：
评委看到的是 8 月 28 日的决策，而机器日期可能是几个月之后。

解决方式（只改文案，不动任何计算）：
  · 首页副标题下加一行披露「仿真经营演示 · 决策日期：… · 基于截至… 的 180 天模拟经营记录」
  · 把容易混淆的「今天提醒 / 今日情况 / 明天建议进货」改成
    「决策日提醒 / 决策日情况 / 决策日建议进货」

本文件把这条披露固化成测试，防止将来改UI 时把它删掉或改回模糊表述。
"""
import re

import pytest

from core import home_view, policy


@pytest.fixture(scope="module")
def plan():
    return policy.build_plan("2026-08-28", 600.0, policy.MODE_DIANNAO,
                             persist=False)


# ══════════════════════════════════════════════════════════════
# 一、首页必须披露仿真性质与两个日期
# ══════════════════════════════════════════════════════════════

def test_home_discloses_simulation_and_both_dates(plan):
    """首页必须同时出现「仿真」披露、决策日期、数据截止日。"""
    html = home_view.render_home_html(plan, part="top")
    assert "仿真经营演示" in html, "首页缺少仿真性质披露"
    assert "决策日期：2026-08-28" in html, "首页未披露正式决策日期"
    assert "2026-08-27" in html, "首页未披露数据截止日期"
    assert "180 天模拟经营记录" in html, "首页未说明数据规模与性质"


def test_home_disclosure_uses_real_data_end_day(plan):
    """披露的数据截止日必须来自真实数据，不能写死。"""
    from core import memory
    days = [str(r.get("day") or "")[:10] for r in memory.get_day_events()]
    assert days, "读不到 day_events"
    real_end = max(days)
    assert home_view._data_end_day() == real_end, \
        "披露的截止日与真实数据不一致"
    html = home_view.render_home_html(plan, part="top")
    assert real_end in html, "披露行未使用真实截止日"


def test_data_end_day_never_raises(monkeypatch):
    """数据源异常时必须降级为「未知」，绝不能影响页面渲染。"""
    from core import memory
    monkeypatch.setattr(memory, "get_day_events",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert home_view._data_end_day() == "未知"
    assert home_view._data_end_day() is not None


# ══════════════════════════════════════════════════════════════
# 二、易混淆的「今天 / 明天」必须限定为决策日语境
# ══════════════════════════════════════════════════════════════

def test_home_has_no_ambiguous_today_labels(plan):
    """首页不得再出现「今天提醒 / 今日情况 / 明天建议进货」等模糊表述。"""
    full = "".join(home_view.render_home_html(plan, part=p)
                   for p in ("top", "rail", "result"))
    for bad in ("今天提醒", "今日情况", "明天建议进货", "明天重点关注",
                "今天没有供应商异常"):
        assert bad not in full, "首页仍有歧义表述：%s" % bad


def test_home_uses_decision_day_wording(plan):
    """改用「决策日」措辞，且三段都能渲染出来。"""
    assert "决策日建议进货" in home_view.render_home_html(plan, part="top")
    assert "决策日提醒" in home_view.render_home_html(plan, part="rail")
    assert "次日重点关注" in home_view.render_home_html(plan, part="result")


def test_home_keeps_store_owner_feature_name(plan):
    """「今天该进什么货」作为店主视角的功能名必须保留。"""
    html = home_view.render_home_html(plan, part="top")
    assert "今天该进什么货" in html, "功能名被误删"


def test_why_view_uses_decision_day_wording(plan):
    """「为什么这样进」页也不能用「今日情况 / 今日断供」。"""
    import core.why_view as why_view
    it = plan["items"][0]
    html = why_view.render_why_page(it) if hasattr(why_view, "render_why_page") else ""
    if not html:
        pytest.skip("why_view 渲染入口不可用")
    assert "今日情况" not in html
    assert "今日断供" not in html


def test_about_view_avoids_today_wording():
    """项目说明页不得承诺「今天的补货建议」（固定仿真日期）。"""
    import core.about_view as about_view
    html = about_view.render_about() if hasattr(about_view, "render_about") else ""
    if not html:
        pytest.skip("about_view 渲染入口不可用")
    assert "给出今天的补货建议" not in html


# ══════════════════════════════════════════════════════════════
# 三、不得把仿真数据说成真实采集数据
# ══════════════════════════════════════════════════════════════

def test_settings_page_declares_simulation_source(plan):
    """设置页必须声明数据来源是仿真数据而非真实门店采集。"""
    import core.settings_view as settings_view
    html = settings_view.render_page() if hasattr(settings_view, "render_page") else ""
    if not html:
        pytest.skip("settings_view 渲染入口不可用")
    assert "仿真" in html
    assert "非真实门店采集数据" in html or "非真实门店" in html


def test_no_page_claims_pos_data_collection():
    """任何页面都不得宣称自动采集 POS / 真实门店生产数据。

    注意：页面里出现「非真实门店采集数据」是正确的**否认式披露**，
    不能因为出现了这几个字就判FAIL —— 判据是「是否存在宣称」。
    """
    import core.about_view as av
    import core.ledger_view as lv
    import core.settings_view as sv
    # 宣称句式（不含否认前缀）
    claims = ("自动采集POS", "自动采集 POS", "已接入 POS", "真实经营数据采集",
              "来自真实商户", "实际商户生产数据")
    for mod in (av, lv, sv):
        fn = None
        for name in ("render_about", "render_ledger", "render_page"):
            if hasattr(mod, name):
                fn = getattr(mod, name)
                break
        if not fn:
            continue
        try:
            html = fn()
        except Exception:
            continue
        for c in claims:
            assert c not in html, "%s 出现宣称式表述：%s" % (mod.__name__, c)
