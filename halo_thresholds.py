#!/usr/bin/env python3
"""
HALO V5.0 评分阈值与权重 — 单一真相源

generate_report.py 与 halo_harness.py 共享此模块，避免阈值逻辑在两处复制粘贴导致漂移。
"""

from typing import Optional


# ── HALO 六维阈值（按资产类型） ──

HALO_DIMENSION_THRESHOLDS = {
    "tangible_intensity": {
        "heavy": [(80, 5), (60, 4), (40, 3), (20, 2), (0, 1)],
        "mixed": [(70, 5), (50, 4), (30, 3), (15, 2), (0, 1)],
        "light": [(60, 5), (40, 4), (20, 3), (10, 2), (0, 1)],
    },
    "fixed_intensity": {
        "heavy": [(100, 5), (80, 4), (60, 3), (0, 2)],
        "mixed": [(60, 5), (40, 4), (20, 3), (0, 2)],
        "light": [(30, 5), (15, 4), (5, 3), (0, 2)],
    },
    "fixed_share": {
        "universal": [(25, 5), (15, 4), (8, 3), (4, 2), (0, 1)],
    },
    "capital_labor": {
        "universal": [(200, 5), (100, 4), (50, 3), (20, 2), (0, 1)],
    },
    "capex_intensity": {
        "heavy": [(15, 5), (10, 4), (5, 3), (0, 2)],
        "mixed": [(10, 5), (5, 4), (2, 3), (0, 2)],
        "light": [(5, 5), (2, 4), (0.5, 3), (0, 2)],
    },
}

# Capex负担阈值（通用）
CAPEX_BURDEN_THRESHOLDS = [(5, 5), (15, 4), (30, 3), (50, 2), (0, 1)]
CAPEX_BURDEN_OCF_NEGATIVE_SCORE = 1  # OCF为负或为0时，最差
CAPEX_BURDEN_OVER_100_SCORE = 1     # burden > 100 时，最差

# HALO 权重
HALO_WEIGHTS = {
    "tangible_intensity": 0.20,
    "fixed_intensity": 0.15,
    "fixed_share": 0.15,
    "capital_labor": 0.15,
    "capex_intensity": 0.15,
    "capex_burden": 0.20,
}

# 维度 key 列表（与权重一一对应）
HALO_DIMENSION_KEYS = [
    "tangible_intensity",
    "fixed_intensity",
    "fixed_share",
    "capital_labor",
    "capex_intensity",
    "capex_burden",
]


# ── 成长性评分阈值 ──

GROWTH_REVENUE_THRESHOLDS = [
    (30, 9),
    (15, 7),
    (5, 5),
    (0, 3),
    (float("-inf"), 2),
]

GROWTH_PROFIT_THRESHOLDS = [
    (30, 9),
    (15, 7),
    (5, 5),
    (0, 3),
    (float("-inf"), 2),
]

# 增长质量评分规则
GROWTH_QUALITY_BASE = 5
GROWTH_QUALITY_RULES = [
    ("cf_to_profit", ">", 0.8, +1),
    ("debt_ratio", "<", 40, +1),
    ("debt_ratio", ">", 70, -2),
    ("cf_to_profit", "<", 0, -2),
]

# 增长持续性评分规则
GROWTH_SUSTAIN_BASE = 5
GROWTH_SUSTAIN_RULES = [
    (">", 10, +1),
    ("<", 0, -1),
]

# 成长性子维度数量（用于平均）
GROWTH_SUB_DIMENSIONS = ["revenue", "profit", "quality", "sustain"]


# ── 评分函数 ──

def _safe_float(value, default=None):
    """安全转换为 float；失败时返回 default"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _dim_value(dims, key):
    """读取维度原始值；键存在但 value 缺失/为 None/非数字时返回 None"""
    item = dims.get(key, {})
    if not isinstance(item, dict):
        return None
    return _safe_float(item.get("value"))


def _apply_thresholds(value, thresholds):
    """
    用 thresholds 列表 [(边界, 分数), ...] 对 value 打分。
    thresholds 必须按边界降序排列。
    value 为 None 时返回 None。
    """
    if value is None:
        return None
    for boundary, score in thresholds:
        if value >= boundary:
            return score
    return 1  # 保底


def score_halo_dimensions(halo: dict) -> Optional[dict]:
    """
    根据 dimension 原始值复算六维得分。
    任一核心维度原始值缺失则返回 None。
    """
    dims = halo.get("dimensions", {})
    at = halo.get("asset_type", "mixed")

    # 前五个维度
    results = {}
    for key in ["tangible_intensity", "fixed_intensity", "fixed_share", "capital_labor", "capex_intensity"]:
        value = _dim_value(dims, key)
        thresholds_config = HALO_DIMENSION_THRESHOLDS[key]
        # 获取对应资产类型的阈值，或使用 universal
        if at in thresholds_config:
            thresholds = thresholds_config[at]
        elif "universal" in thresholds_config:
            thresholds = thresholds_config["universal"]
        else:
            return None  # 未知资产类型且无 universal 配置

        score = _apply_thresholds(value, thresholds)
        if score is None:
            return None  # 原始值缺失
        results[key] = score

    # Capex负担：从 raw.capex_yi / ocf_yi 计算
    raw = halo.get("raw", {})
    capex = _safe_float(raw.get("capex_yi"))
    ocf = _safe_float(raw.get("ocf_yi"))
    if ocf is not None and ocf > 0 and capex is not None:
        burden = capex / ocf * 100
    else:
        burden = 999  # OCF为负或为0，最差

    if burden > 100:
        results["capex_burden"] = CAPEX_BURDEN_OVER_100_SCORE
    else:
        # Capex负担是反向指标：burden 越小越好，用 <=
        s_cb = None
        for boundary, score in CAPEX_BURDEN_THRESHOLDS:
            if burden <= boundary:
                s_cb = score
                break
        results["capex_burden"] = s_cb if s_cb is not None else 1

    return results


def calc_halo_total(dim_scores: dict) -> float:
    """根据六维得分加权计算 HALO 总分"""
    total = sum(dim_scores[name] * HALO_WEIGHTS[name] for name in HALO_DIMENSION_KEYS)
    return round(total, 2)


def score_growth_breakdown(growth: dict, ratios: dict) -> dict:
    """
    独立复算成长性子项与总分。
    缺失字段按 0 计算（与历史行为一致，不返回 None）。
    返回 {"4_1", "4_2", "4_3", "4_4", "total"}，供 generate_report 直接取子项。
    """
    # 4.1 营收增长
    rev_yoy = _safe_float(growth.get("revenue_yoy"), 0)
    s_rev = None
    for boundary, score in GROWTH_REVENUE_THRESHOLDS:
        if rev_yoy > boundary:
            s_rev = score
            break
    if s_rev is None:
        s_rev = 2

    # 4.2 利润增长
    np_yoy = _safe_float(growth.get("net_profit_yoy"), 0)
    s_np = None
    for boundary, score in GROWTH_PROFIT_THRESHOLDS:
        if np_yoy > boundary:
            s_np = score
            break
    if s_np is None:
        s_np = 2

    # 4.3 增长质量
    cf_ratio = _safe_float(ratios.get("cf_to_profit"), 0)
    debt = _safe_float(ratios.get("debt_ratio"), 0)
    quality = GROWTH_QUALITY_BASE
    if cf_ratio > 0.8:
        quality += 1
    if debt < 40:
        quality += 1
    if debt > 70:
        quality -= 2
    if cf_ratio < 0:
        quality -= 2
    s_quality = max(1, min(10, quality))

    # 4.4 增长持续性
    annual_rev_yoy = _safe_float(growth.get("annual_revenue_yoy"), 0)
    sustain = GROWTH_SUSTAIN_BASE
    if annual_rev_yoy > 10:
        sustain += 1
    if annual_rev_yoy < 0:
        sustain -= 1
    s_sustain = max(1, min(10, sustain))

    total = (s_rev + s_np + s_quality + s_sustain) / 4
    return {"4_1": s_rev, "4_2": s_np, "4_3": s_quality, "4_4": s_sustain, "total": round(total, 1)}


def score_growth(growth: dict, ratios: dict) -> Optional[float]:
    """独立复算成长性总分（委托给 score_growth_breakdown，向后兼容）。"""
    return score_growth_breakdown(growth, ratios)["total"]
