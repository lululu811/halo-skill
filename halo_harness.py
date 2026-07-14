#!/usr/bin/env python3
"""
HALO V5.0 数据层 Harness
验证 data/{code}.json 和 reports/{code}_skeleton.md 的完整性、一致性与正确性
"""

import json
import os
import re
import sys
from datetime import datetime


# ── 路径工具 ──
def _project_root():
    return os.path.dirname(os.path.abspath(__file__))


def _data_path(code):
    return os.path.join(_project_root(), "data", f"{code}.json")


def _skeleton_path(code):
    return os.path.join(_project_root(), "reports", f"{code}_skeleton.md")


def _harness_report_path(code, layer):
    if layer == "data":
        return os.path.join(_project_root(), "data", f"{code}_harness.json")
    return os.path.join(_project_root(), "reports", f"{code}_harness.json")


# ── Harness 类 ──
class Harness:
    def __init__(self, code, layer):
        self.code = code
        self.layer = layer
        self.checks = []
        self.warnings = []
        self.errors = []

    def check(self, name, condition, detail="", level="error"):
        """记录一项检查结果"""
        passed = bool(condition)
        record = {"name": name, "passed": passed, "detail": detail, "level": level}
        self.checks.append(record)
        if not passed:
            if level == "error":
                self.errors.append(record)
            else:
                self.warnings.append(record)
        return passed

    def ok(self):
        return len(self.errors) == 0

    def report(self):
        return {
            "code": self.code,
            "layer": self.layer,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "ok": self.ok(),
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _save_report(harness):
    path = _harness_report_path(harness.code, harness.layer)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(harness.report(), f, ensure_ascii=False, indent=2)
    return path


def _print_summary(harness):
    print(f"\n[HALO Harness] {harness.code} — {harness.layer}层")
    for c in harness.checks:
        if c["passed"]:
            icon = "✅"
        elif c.get("level") == "warning":
            icon = "⚠️"
        else:
            icon = "❌"
        print(f"  {icon} {c['name']}")
        if c["detail"]:
            print(f"     {c['detail']}")
    if harness.warnings:
        print(f"  ⚠️  {len(harness.warnings)} 个警告")
    status = "通过" if harness.ok() else "未通过"
    print(f"  结果: {status} ({len(harness.errors)} errors, {len(harness.warnings)} warnings)")


# ── 评分复算工具 ──

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


def _score_halo_dimensions(halo):
    """根据 dimension 原始值复算六维得分（与 generate_report.py 阈值一致）"""
    dims = halo.get("dimensions", {})
    at = halo.get("asset_type", "mixed")

    # 有形资产密集度
    ti = _dim_value(dims, "tangible_intensity")
    if at == "heavy":
        thresholds = [(80, 5), (60, 4), (40, 3), (20, 2), (0, 1)]
    elif at == "mixed":
        thresholds = [(70, 5), (50, 4), (30, 3), (15, 2), (0, 1)]
    else:
        thresholds = [(60, 5), (40, 4), (20, 3), (10, 2), (0, 1)]
    s_ti = next((s for t, s in thresholds if ti >= t), 1) if ti is not None else None

    # 固定资产密集度
    fi = _dim_value(dims, "fixed_intensity")
    if at == "heavy":
        thresholds = [(100, 5), (80, 4), (60, 3), (0, 2)]
    elif at == "mixed":
        thresholds = [(60, 5), (40, 4), (20, 3), (0, 2)]
    else:
        thresholds = [(30, 5), (15, 4), (5, 3), (0, 2)]
    s_fi = next((s for t, s in thresholds if fi >= t), 1) if fi is not None else None

    # 固定资产份额
    fs = _dim_value(dims, "fixed_share")
    thresholds = [(25, 5), (15, 4), (8, 3), (4, 2), (0, 1)]
    s_fs = next((s for t, s in thresholds if fs >= t), 1) if fs is not None else None

    # 资本-劳动力比率
    cl = _dim_value(dims, "capital_labor")
    thresholds = [(200, 5), (100, 4), (50, 3), (20, 2), (0, 1)]
    s_cl = next((s for t, s in thresholds if cl >= t), 1) if cl is not None else None

    # Capex密集度
    ci = _dim_value(dims, "capex_intensity")
    if at == "heavy":
        thresholds = [(15, 5), (10, 4), (5, 3), (0, 2)]
    elif at == "mixed":
        thresholds = [(10, 5), (5, 4), (2, 3), (0, 2)]
    else:
        thresholds = [(5, 5), (2, 4), (0.5, 3), (0, 2)]
    s_ci = next((s for t, s in thresholds if ci >= t), 1) if ci is not None else None

    # 任一核心维度原始值缺失均无法复算
    if None in (s_ti, s_fi, s_fs, s_cl, s_ci):
        return None

    # Capex负担：与 generate_report.py 一致，使用 raw.capex_yi / ocf_yi
    raw = halo.get("raw", {})
    capex = _safe_float(raw.get("capex_yi"))
    ocf = _safe_float(raw.get("ocf_yi"))
    if ocf is not None and ocf > 0 and capex is not None:
        burden = capex / ocf * 100
    else:
        burden = 999
    thresholds = [(5, 5), (15, 4), (30, 3), (50, 2), (0, 1)]
    s_cb = 1 if burden > 100 else next((s for t, s in thresholds if burden <= t), 1)

    return {
        "tangible_intensity": s_ti,
        "fixed_intensity": s_fi,
        "fixed_share": s_fs,
        "capital_labor": s_cl,
        "capex_intensity": s_ci,
        "capex_burden": s_cb,
    }


def _recalc_halo_score(halo):
    """独立复算 HALO 总分"""
    dim_scores = _score_halo_dimensions(halo)
    if dim_scores is None:
        return None
    weights = {
        "tangible_intensity": 0.20,
        "fixed_intensity": 0.15,
        "fixed_share": 0.15,
        "capital_labor": 0.15,
        "capex_intensity": 0.15,
        "capex_burden": 0.20,
    }
    total = sum(dim_scores[name] * weight for name, weight in weights.items())
    return round(total, 2)


def _recalc_growth_score(growth, ratios):
    """独立复算成长性总分"""
    # 4.1 营收增长
    rev_yoy = _safe_float(growth.get("revenue_yoy"), 0)
    if rev_yoy > 30:
        s_rev = 9
    elif rev_yoy > 15:
        s_rev = 7
    elif rev_yoy > 5:
        s_rev = 5
    elif rev_yoy > 0:
        s_rev = 3
    else:
        s_rev = 2

    # 4.2 利润增长
    np_yoy = _safe_float(growth.get("net_profit_yoy"), 0)
    if np_yoy > 30:
        s_np = 9
    elif np_yoy > 15:
        s_np = 7
    elif np_yoy > 5:
        s_np = 5
    elif np_yoy > 0:
        s_np = 3
    else:
        s_np = 2

    # 4.3 增长质量
    cf_ratio = _safe_float(ratios.get("cf_to_profit"), 0)
    debt = _safe_float(ratios.get("debt_ratio"), 0)
    quality = 5
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
    sustain = 5
    if annual_rev_yoy > 10:
        sustain += 1
    if annual_rev_yoy < 0:
        sustain -= 1
    s_sustain = max(1, min(10, sustain))

    total = (s_rev + s_np + s_quality + s_sustain) / 4
    return round(total, 1)


# ── 入口函数 ──
def validate_data(code):
    """校验 data/{code}.json 的完整性、合理性与一致性"""
    h = Harness(code, "data")
    data_path = _data_path(code)

    # 1. 文件存在
    exists = os.path.exists(data_path)
    h.check("数据文件存在", exists, detail=f"路径: {data_path}")
    if not exists:
        _save_report(h)
        _print_summary(h)
        return h.report()

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except json.JSONDecodeError as e:
        h.check("JSON 文件可解析", False, detail=f"{data_path} 解析失败: {e}", level="error")
        _save_report(h)
        _print_summary(h)
        return h.report()

    # 2. meta 字段完整
    meta = d.get("meta", {})
    h.check("meta 字段完整",
            meta.get("stock_code") == code and bool(meta.get("stock_name")) and bool(meta.get("fetch_time")),
            detail=f"stock_code={meta.get('stock_code')}, stock_name={meta.get('stock_name')}")

    # 3. 行情数据存在且合理
    market = d.get("market", {})
    required_market = ["price", "pe_ttm", "pb", "mcap_yi"]
    has_market = all(k in market for k in required_market)
    h.check("行情数据字段完整", has_market, detail=f"缺失: {[k for k in required_market if k not in market]}")
    if has_market:
        price = _safe_float(market.get("price"))
        pe = _safe_float(market.get("pe_ttm"))
        pb = _safe_float(market.get("pb"))
        mcap = _safe_float(market.get("mcap_yi"))
        all_positive = all(v is not None and v > 0 for v in (price, pe, pb, mcap))
        h.check("行情数值合理", all_positive,
                detail=f"price={market.get('price')}, pe={market.get('pe_ttm')}, pb={market.get('pb')}, mcap={market.get('mcap_yi')}")
        if not all_positive:
            h.check("行情数值类型合法",
                    all(v is not None for v in (price, pe, pb, mcap)),
                    detail="行情字段均可解析为数字，但 price/PE/PB/mcap 中存在非正数", level="warning")

    # 4. 财报三表期数
    financial = d.get("financial", {})
    income = financial.get("income", [])
    balance = financial.get("balance", [])
    cashflow = financial.get("cashflow", [])
    h.check("财报三表期数 ≥2",
            len(income) >= 2 and len(balance) >= 2 and len(cashflow) >= 2,
            detail=f"利润表{len(income)}期, 负债表{len(balance)}期, 现金流表{len(cashflow)}期")

    # 5. 资产类型合法
    halo = d.get("halo", {})
    asset_type = halo.get("asset_type", "")
    h.check("资产类型合法", asset_type in ("heavy", "mixed", "light"), detail=f"asset_type={asset_type}")

    # 6. HALO 核心维度原始值存在（capex_burden 由 raw 复算，不强制要求 dims 中提供）
    dims = halo.get("dimensions", {})
    required_dims = ["tangible_intensity", "fixed_intensity", "fixed_share", "capital_labor", "capex_intensity"]
    has_dims = all(k in dims for k in required_dims)
    h.check("HALO 核心维度原始值存在", has_dims,
            detail=f"缺失: {[k for k in required_dims if k not in dims]}")

    # 6.1 Capex负担复算依赖的原始字段存在
    raw = halo.get("raw", {})
    required_raw_burden = ["capex_yi", "ocf_yi"]
    has_burden_raw = all(k in raw for k in required_raw_burden)
    h.check("Capex负担原始数据存在", has_burden_raw,
            detail=f"缺失: {[k for k in required_raw_burden if k not in raw]}")

    # 7. 关键财务比率
    ratios = d.get("ratios", {})
    required_ratios = ["roe", "roa", "gross_margin", "net_margin", "debt_ratio", "cf_to_profit"]
    has_ratios = all(k in ratios for k in required_ratios)
    h.check("关键财务比率存在", has_ratios,
            detail=f"缺失: {[k for k in required_ratios if k not in ratios]}", level="warning")
    if has_ratios:
        debt = _safe_float(ratios.get("debt_ratio"), 0)
        h.check("负债率合理", 0 <= debt <= 100, detail=f"debt_ratio={ratios.get('debt_ratio')}", level="warning")

    # 8. 成长性字段
    growth = d.get("growth", {})
    has_growth = "revenue_yoy" in growth and "net_profit_yoy" in growth
    h.check("成长性字段存在", has_growth,
            detail=f"缺失: revenue_yoy={growth.get('revenue_yoy')}, net_profit_yoy={growth.get('net_profit_yoy')}",
            level="warning")

    # 9. 评分计算复核（允许 ±0.1 浮点误差）
    json_halo_total = _safe_float(halo.get("total_score"))
    json_growth_total = _safe_float(growth.get("total_score"))
    recalc_halo = _recalc_halo_score(halo) if has_dims and has_burden_raw and asset_type else None
    recalc_growth = _recalc_growth_score(growth, ratios) if has_growth and has_ratios else None

    # 若核心维度存在但 value 缺失/非法，则无法复算，作为 warning 提示并列出具体维度
    if recalc_halo is None and has_dims and has_burden_raw and asset_type:
        missing_or_invalid = []
        for k in required_dims:
            v = _dim_value(dims, k)
            if v is None:
                missing_or_invalid.append(k)
        h.check("HALO 评分可复算", False,
                detail=f"维度原始值缺失或非法: {missing_or_invalid}", level="warning")

    if json_halo_total is not None and recalc_halo is not None:
        h.check("HALO 评分复算一致",
                abs(json_halo_total - recalc_halo) <= 0.1,
                detail=f"JSON={json_halo_total}, 复算={recalc_halo:.2f}")
    elif recalc_halo is not None:
        h.check("HALO 总分已复算", True,
                detail=f"JSON 未存储 total_score, 复算={recalc_halo:.2f}")

    if json_growth_total is not None and recalc_growth is not None:
        h.check("成长性评分复算一致",
                abs(json_growth_total - recalc_growth) <= 0.1,
                detail=f"JSON={json_growth_total}, 复算={recalc_growth:.2f}")
    elif recalc_growth is not None:
        h.check("成长性总分已复算", True,
                detail=f"JSON 未存储 total_score, 复算={recalc_growth:.2f}")

    # 9.1 成长性/比率缺失导致无法复算时给出警告
    if not has_growth:
        h.check("成长性评分已复算", False,
                detail="缺少 revenue_yoy 或 net_profit_yoy，跳过成长性评分复算", level="warning")
    if not has_ratios:
        h.check("成长性质量已复算", False,
                detail="缺少关键财务比率，跳过增长质量/持续性复算", level="warning")

    # 10. 资金流数据（warning）
    fund_flow = d.get("fund_flow", [])
    h.check("资金流数据存在", len(fund_flow) > 0,
            detail=f"fund_flow={len(fund_flow)}条", level="warning")

    _save_report(h)
    _print_summary(h)
    return h.report()


def validate_skeleton(code):
    """校验 reports/{code}_skeleton.md 的数据填充正确性"""
    h = Harness(code, "skeleton")
    skeleton_path = _skeleton_path(code)
    data_path = _data_path(code)

    # 1. 文件存在且非空
    exists = os.path.exists(skeleton_path) and os.path.getsize(skeleton_path) > 0
    h.check("骨架文件存在", exists, detail=f"路径: {skeleton_path}", level="error")
    if not exists:
        _save_report(h)
        _print_summary(h)
        return h.report()

    with open(skeleton_path, "r", encoding="utf-8") as f:
        skeleton = f.read()

    # 2. 无残留数据占位符（允许 {{AI_*}} 和 {{SERENITY_*}}）
    unknown_placeholders = re.findall(r"\{\{[A-Z][A-Z_0-9]+\}\}", skeleton)
    allowed = {"{{AI_", "{{SERENITY_"}
    leftover = [p for p in unknown_placeholders if not any(p.startswith(a) for a in allowed)]
    h.check("无残留数据占位符", len(leftover) == 0,
            detail=f"残留: {leftover[:5]}", level="error")

    # 3. 关键数字与 JSON 一致
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except json.JSONDecodeError as e:
            h.check("JSON 文件可解析", False,
                    detail=f"{data_path} 解析失败: {e}", level="error")
            d = None

        if d is not None:
            market = d.get("market", {})
            price = _safe_float(market.get("price"))
            pe = _safe_float(market.get("pe_ttm"))
            halo = d.get("halo", {})
            growth = d.get("growth", {})
            ratios = d.get("ratios", {})

            # 复算前提
            dims = halo.get("dimensions", {})
            required_dims = ["tangible_intensity", "fixed_intensity", "fixed_share", "capital_labor", "capex_intensity"]
            has_dims = all(k in dims for k in required_dims)
            raw = halo.get("raw", {})
            has_burden_raw = all(k in raw for k in ["capex_yi", "ocf_yi"])
            asset_type = halo.get("asset_type", "")
            has_growth = "revenue_yoy" in growth and "net_profit_yoy" in growth
            required_ratios = ["cf_to_profit", "debt_ratio"]
            has_ratios = all(k in ratios for k in required_ratios)

            # 当 JSON 未存储 total_score 时，用复算值与骨架比对
            recalc_halo_total = _recalc_halo_score(halo) if has_dims and has_burden_raw and asset_type else None
            recalc_growth_total = _recalc_growth_score(growth, ratios) if has_growth and has_ratios else None
            json_halo_total = _safe_float(halo.get("total_score"))
            json_growth_total = _safe_float(growth.get("total_score"))

            if price is not None:
                h.check("骨架中价格与 JSON 一致",
                        _find_number_in_text(skeleton, price),
                        detail=f"JSON price={price}", level="error")
            if pe is not None:
                h.check("骨架中 PE 与 JSON 一致",
                        _find_number_in_text(skeleton, pe),
                        detail=f"JSON pe_ttm={pe}", level="error")

            if recalc_halo_total is not None:
                h.check("骨架中 HALO 总分与 JSON 一致",
                        _find_number_in_text(skeleton, recalc_halo_total),
                        detail=f"复算 halo_total={recalc_halo_total:.2f}", level="error")
            elif json_halo_total is not None:
                h.check("骨架中 HALO 总分与 JSON 一致",
                        _find_number_in_text(skeleton, json_halo_total),
                        detail=f"JSON stored halo_total={json_halo_total:.2f}", level="error")
            else:
                h.check("骨架中 HALO 总分可校验", False,
                        detail="HALO 维度数据不足且 JSON 未存储 total_score", level="warning")

            if recalc_growth_total is not None:
                h.check("骨架中成长分与 JSON 一致",
                        _find_number_in_text(skeleton, recalc_growth_total),
                        detail=f"复算 growth_total={recalc_growth_total:.2f}", level="error")
            elif json_growth_total is not None:
                h.check("骨架中成长分与 JSON 一致",
                        _find_number_in_text(skeleton, json_growth_total),
                        detail=f"JSON stored growth_total={json_growth_total:.2f}", level="error")
            else:
                h.check("骨架中成长分可校验", False,
                        detail="成长性/比率数据不足且 JSON 未存储 total_score", level="warning")
    else:
        h.check("数据文件存在", False,
                detail=f"{data_path} 不存在，跳过数字一致性校验", level="warning")

    # 4. 免责声明和有效期
    h.check("包含免责声明", "免责声明" in skeleton, level="warning")
    h.check("包含30日有效期", "30日有效期" in skeleton or "报告有效期30日" in skeleton, level="warning")

    # 5. 产业链章节（如果 serenity 数据存在）
    serenity_path = os.path.join(_project_root(), "data", f"{code}_serenity.json")
    if os.path.exists(serenity_path):
        chapter12 = skeleton.split("## 🔗 十二、产业链定位")[-1] if "## 🔗 十二、产业链定位" in skeleton else ""
        h.check("产业链章节不为空", len(chapter12.strip()) > 200,
                detail=f"章节长度={len(chapter12.strip())}", level="warning")

    # 6. 缺失标记数量
    missing_count = skeleton.count("⚠️ 缺失")
    h.check("缺失标记不过多", missing_count <= 10,
            detail=f"缺失标记={missing_count}", level="warning")

    _save_report(h)
    _print_summary(h)
    return h.report()


def _find_number_in_text(text, number):
    """在文本中查找数字的字符串表示（支持 ±0.01 误差）"""
    if number is None:
        return False
    num = float(number)
    # 精确匹配：整数、1位、2位小数的表示，先验证格式化值与目标数值一致
    for fmt in [f"{num:.0f}", f"{num:.1f}", f"{num:.2f}"]:
        if abs(float(fmt) - num) <= 0.01 and fmt in text:
            return True
    # 容错：查找接近值
    for m in re.finditer(r"[-+]?\d+\.?\d*", text):
        try:
            if abs(float(m.group()) - num) <= 0.01:
                return True
        except ValueError:
            continue
    return False


def run_harness(code):
    """依次运行数据层和骨架层校验，并保存组合报告"""
    data_result = validate_data(code)
    skeleton_result = validate_skeleton(code)
    combined = {
        "code": code,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": data_result["ok"] and skeleton_result["ok"],
        "data_layer": data_result,
        "skeleton_layer": skeleton_result,
    }
    path = os.path.join(_project_root(), "data", f"{code}_harness.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    return combined


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python halo_harness.py <股票代码>")
        sys.exit(1)
    code = sys.argv[1]
    result = run_harness(code)
    sys.exit(0 if result["ok"] else 1)
