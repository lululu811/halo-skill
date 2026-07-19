#!/usr/bin/env python3
"""
HALO V5.0 数据层 Harness
验证 data/{code}.json、reports/{code}_skeleton.md 和 reports/{code}_halo_v5.md 的完整性、一致性与正确性
"""

import json
import os
import re
import sys
from datetime import datetime
from halo_thresholds import score_halo_dimensions, calc_halo_total, score_growth


# ── 路径工具 ──
def _project_root():
    return os.path.dirname(os.path.abspath(__file__))


def _data_path(code):
    return os.path.join(_project_root(), "data", f"{code}.json")


def _skeleton_path(code):
    return os.path.join(_project_root(), "reports", f"{code}_skeleton.md")


def _report_path(code):
    return os.path.join(_project_root(), "reports", f"{code}_halo_v5.md")


def _harness_report_path(code, layer):
    if layer == "data":
        return os.path.join(_project_root(), "data", f"{code}_harness.json")
    if layer == "report":
        return os.path.join(_project_root(), "reports", f"{code}_report_harness.json")
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
    print(f"\n[HALO Harness] {harness.code} - {harness.layer}层")
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


# ── 评分复算工具（保留简单工具函数，阈值逻辑已迁移到 halo_thresholds） ──

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

    # 9. 评分计算复核（允许 ±0.1 浮点误差）- 使用 halo_thresholds 共享阈值
    json_halo_total = _safe_float(halo.get("total_score"))
    json_growth_total = _safe_float(growth.get("total_score"))
    dim_scores = score_halo_dimensions(halo) if has_dims and has_burden_raw and asset_type else None
    recalc_halo = calc_halo_total(dim_scores) if dim_scores is not None else None
    recalc_growth = score_growth(growth, ratios) if has_growth and has_ratios else None

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

    # 10.1 股东人数数据（warning）
    holder_num = d.get("holder_num", [])
    h.check("股东人数数据存在", len(holder_num) > 0,
            detail=f"holder_num={len(holder_num)}条", level="warning")

    # 10.2 分红历史数据（warning）
    dividend = d.get("dividend", [])
    h.check("分红历史数据存在", len(dividend) > 0,
            detail=f"dividend={len(dividend)}条", level="warning")

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

            # 当 JSON 未存储 total_score 时，用复算值与骨架比对 - 使用 halo_thresholds 共享阈值
            dim_scores = score_halo_dimensions(halo) if has_dims and has_burden_raw and asset_type else None
            recalc_halo_total = calc_halo_total(dim_scores) if dim_scores is not None else None
            recalc_growth_total = score_growth(growth, ratios) if has_growth and has_ratios else None
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


# ── 最终报告校验（AI 填充后的 reports/{code}_halo_v5.md）──

# 期望章节（关键片段，0-11章必齐，12章可选）
EXPECTED_CHAPTERS = [
    ("第零章", "执行摘要"),
    ("一、", "公司概况"),
    ("二、", "最新基本面"),
    ("三、", "HALO框架六维"),
    ("四、", "成长性分析"),
    ("五、", "低淘汰率"),
    ("六、", "滞胀防御"),
    ("七、", "ESG评估"),
    ("八、", "管理层质量"),
    ("九、", "股东与资金面"),
    ("十、", "风险评估"),
    ("十一", "综合评估与投资建议"),
]

# 每章最小字数（基于 600519 标杆实际字数的 ~90%，防 AI 草草填）
REPORT_CHAPTER_MIN_CHARS = {
    "第零章": 1100,
    "一、": 1000,
    "二、": 1000,
    "三、": 2600,
    "四、": 1000,
    "五、": 600,
    "六、": 630,
    "七、": 540,
    "八、": 600,
    "九、": 600,
    "十、": 660,
    "十一": 1640,
}

# 综合评分各维度权重（与 SKILL.md 综合评分公式一致）
COMPREHENSIVE_WEIGHTS = [
    ("HALO六维", 0.15, True),    # 归一化 ÷5×10
    ("成长性", 0.15, False),
    ("低淘汰率", 0.15, False),
    ("滞胀防御", 0.10, False),
    ("ESG", 0.10, False),
    ("管理层", 0.10, False),
    ("股东资金面", 0.05, False),
    ("估值吸引力", 0.10, False),
    ("风险", -0.10, False),       # 减分项
]


def _split_chapters(text):
    """按 ## 标题分割章节，返回 [(标题, 字符数)]"""
    chapters = []
    current_title = None
    current_len = 0
    for line in text.splitlines():
        if line.startswith("## "):
            if current_title is not None:
                chapters.append((current_title, current_len))
            current_title = line
            current_len = len(line)
        elif current_title is not None:
            current_len += len(line) + 1
    if current_title is not None:
        chapters.append((current_title, current_len))
    return chapters


def _extract_score_from_line(line):
    """从表格行提取 评分/满分 的评分值（如 3.85/5.0 -> 3.85）"""
    m = re.search(r"(\d+\.?\d*)\s*/\s*\d+\.?\d*", line)
    return float(m.group(1)) if m else None


def _recalc_comprehensive_score(report):
    """从第十一章 11.1 表格提取各维评分，按权重复算综合评分；任一维度缺失返回 None"""
    # 定位 11.1 综合评级表格区间
    start = report.find("11.1")
    if start == -1:
        start = report.find("十一、综合评估")
    if start == -1:
        return None
    end = report.find("综合评分计算", start)
    if end == -1:
        end = len(report)
    section = report[start:end]

    total = 0.0
    for keyword, weight, normalize in COMPREHENSIVE_WEIGHTS:
        score = None
        for line in section.splitlines():
            if keyword in line and "|" in line:
                score = _extract_score_from_line(line)
                if score is not None:
                    break
        if score is None:
            return None
        if normalize:
            score = score / 5 * 10
        total += score * weight
    return round(total, 2)


def _extract_comprehensive_score(report):
    """提取报告声明的综合评分（如 6.2/10 -> 6.2）"""
    m = re.search(r"综合评分[：:]\s*(\d+\.?\d*)\s*/\s*10", report)
    if m:
        return float(m.group(1))
    m = re.search(r"=\s*(\d+\.?\d*)\s*/\s*10\b", report)
    if m:
        return float(m.group(1))
    return None


def validate_report(code):
    """校验 reports/{code}_halo_v5.md 的 AI 填充完整性与评分自洽性"""
    h = Harness(code, "report")
    report_path = _report_path(code)

    # 1. 文件存在且非空（报告可能尚未生成，缺失为 warning 不阻断）
    exists = os.path.exists(report_path) and os.path.getsize(report_path) > 0
    h.check("最终报告存在", exists, detail=f"路径: {report_path}", level="warning")
    if not exists:
        _save_report(h)
        _print_summary(h)
        return h.report()

    with open(report_path, "r", encoding="utf-8") as f:
        report = f.read()

    # 2. 无残留 AI/SERENITY 槽位（双括号 + 单括号两种格式）
    leftover = re.findall(r"\{\{[A-Z][A-Z_0-9]+\}\}", report)
    leftover += re.findall(r"(?<!\{)\{[A-Z][A-Z_0-9]+\}(?!\})", report)
    h.check("无残留AI槽位", len(leftover) == 0,
            detail=f"残留: {leftover[:5]}", level="error")

    # 3. 章节齐备（0-11章必齐，只检查 ## 标题行，避免与 11.1 表格维度名冲突）
    chapter_titles = [line for line in report.splitlines() if line.startswith("## ")]
    missing_chapters = []
    for key, frag in EXPECTED_CHAPTERS:
        if not any(key in t or frag in t for t in chapter_titles):
            missing_chapters.append(frag)
    h.check("11章标题齐备", len(missing_chapters) == 0,
            detail=f"缺失: {missing_chapters}", level="error")

    # 3.1 第十二章产业链（可选，缺失仅 warning）
    has_ch12 = "十二" in report and "产业链定位" in report
    h.check("产业链章节存在", has_ch12,
            detail="第十二章为可选，缺失建议先生成 serenity 数据", level="warning")

    # 4. 各章字数下限
    chapters = _split_chapters(report)
    short_chapters = []
    for ch_title, ch_len in chapters:
        for key, min_chars in REPORT_CHAPTER_MIN_CHARS.items():
            if key in ch_title and ch_len < min_chars:
                short_chapters.append(f"{ch_title.strip()}({ch_len}字<{min_chars})")
                break
    h.check("各章字数达标", len(short_chapters) == 0,
            detail=f"偏短: {short_chapters[:8]}", level="warning")

    # 5. 综合评分自洽
    recalc = _recalc_comprehensive_score(report)
    reported = _extract_comprehensive_score(report)
    if recalc is not None and reported is not None:
        h.check("综合评分自洽", abs(recalc - reported) <= 0.5,
                detail=f"报告={reported}, 复算={recalc:.2f}, 差={abs(recalc - reported):.2f}", level="warning")
    elif reported is not None:
        h.check("综合评分可复算", False,
                detail="无法从第十一章提取全部维度评分，跳过自洽校验", level="warning")

    # 6. 免责声明与有效期
    h.check("包含免责声明", "免责声明" in report, level="warning")
    h.check("包含30日有效期", "30日有效期" in report or "报告有效期30日" in report or "有效期至" in report,
            level="warning")

    # 7. 缺失标记不过多
    missing_count = report.count("⚠️ 缺失")
    h.check("缺失标记不过多", missing_count <= 10,
            detail=f"缺失标记={missing_count}", level="warning")

    _save_report(h)
    _print_summary(h)
    return h.report()


def run_harness(code):
    """依次运行数据层、骨架层、报告层校验，并保存组合报告"""
    data_result = validate_data(code)
    skeleton_result = validate_skeleton(code)
    report_result = validate_report(code)
    combined = {
        "code": code,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": data_result["ok"] and skeleton_result["ok"] and report_result["ok"],
        "data_layer": data_result,
        "skeleton_layer": skeleton_result,
        "report_layer": report_result,
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
