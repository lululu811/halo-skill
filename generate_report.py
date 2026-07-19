#!/usr/bin/env python3
"""
HALO V5.0 报告骨架生成器
读取 JSON 数据 → 生成报告骨架（数据完整，分析槽位留空）
输出: reports/{code}_skeleton.md

骨架中的 {{AI_*}} 占位符由 AI 后续填充
"""

import json, os, sys
from datetime import datetime
from halo_thresholds import score_halo_dimensions, calc_halo_total, score_growth as _score_growth_impl, score_growth_breakdown as _score_growth_breakdown_impl

# Harness 骨架校验
import halo_harness
from halo_harness import validate_skeleton


def fmt_yi(v):
    """格式化亿元（输入单位：元）"""
    if v is None or v == "":
        return "⚠️ 缺失"
    try:
        return f"{float(v)/1e8:.2f}"
    except:
        return str(v)


def fmt_wan(v):
    if v is None or v == "":
        return "⚠️ 缺失"
    try:
        return f"{float(v)/1e4:.2f}"
    except:
        return str(v)


def fmt_pct(v):
    if v is None or v == "":
        return "⚠️ 缺失"
    try:
        return f"{float(v):.2f}"
    except:
        return str(v)


def rating_5(score):
    if score >= 4.0: return "🟢 极强"
    if score >= 3.0: return "🟡 强"
    if score >= 2.0: return "🟠 中等"
    return "🔴 弱"


def rating_10(score):
    if score >= 8.0: return "🟢 极强"
    if score >= 6.5: return "🟡 强"
    if score >= 5.0: return "🟠 中等"
    return "🔴 弱"


def risk_lvl(score):
    if score < 3: return "🟢 低风险"
    if score < 5: return "🟡 中等风险"
    if score < 7: return "🟠 较高风险"
    return "🔴 高风险"


def asset_desc(at):
    return {
        "heavy": "核心壁垒=物理资产",
        "mixed": "物理+无形资产并重",
        "light": "核心壁垒=品牌/技术/网络"
    }.get(at, at)


# ── HALO 评分函数 ──

def score_halo(d):
    """根据 JSON 数据计算 HALO 六维评分（使用 halo_thresholds 共享阈值）"""
    halo = d.get("halo", {})
    raw = halo.get("raw", {})

    # 调用共享模块复算六维得分
    dim_scores = score_halo_dimensions(halo)

    if dim_scores is None:
        # 维度数据缺失时降级
        scores = {f"3_{i}": 1 for i in range(1, 7)}
        scores["burden_pct"] = "⚠️ 缺失"
        scores["total"] = 0.0
        scores["rating"] = rating_5(0.0)
        return scores

    scores = {
        "3_1": dim_scores["tangible_intensity"],
        "3_2": dim_scores["fixed_intensity"],
        "3_3": dim_scores["fixed_share"],
        "3_4": dim_scores["capital_labor"],
        "3_5": dim_scores["capex_intensity"],
        "3_6": dim_scores["capex_burden"],
    }

    # Capex负担百分比显示
    capex = raw.get("capex_yi", 0)
    ocf = raw.get("ocf_yi", 0)
    if ocf and float(ocf) > 0 and capex is not None:
        burden = float(capex) / float(ocf) * 100
        scores["burden_pct"] = f"{burden:.1f}"
    else:
        scores["burden_pct"] = "⚠️ OCF为负"

    # HALO 总分 (加权) — 使用共享模块
    scores["total"] = calc_halo_total(dim_scores)
    scores["rating"] = rating_5(scores["total"])
    return scores


def score_growth(d):
    """成长性评分（子项与总分均来自 halo_thresholds 共享模块）"""
    g = d.get("growth", {})
    ratios = d.get("ratios", {})

    bd = _score_growth_breakdown_impl(g, ratios)

    if bd is None:
        # 数据缺失时降级
        scores = {f"4_{i}": 1 for i in range(1, 5)}
        scores["total"] = 0.0
        scores["rating"] = rating_10(0.0)
        return scores

    scores = {"4_1": bd["4_1"], "4_2": bd["4_2"], "4_3": bd["4_3"], "4_4": bd["4_4"]}
    scores["total"] = bd["total"]
    scores["rating"] = rating_10(bd["total"])
    return scores


def generate_skeleton(json_path, qual_path=None):
    """生成报告骨架"""
    with open(json_path) as f:
        d = json.load(f)
    
    qual = {}
    if qual_path and os.path.exists(qual_path):
        with open(qual_path) as f:
            qual = json.load(f)
    
    code = d.get("meta", {}).get("stock_code", "")
    name = d.get("meta", {}).get("stock_name", "")
    fetch_time = d.get("meta", {}).get("fetch_time", "")
    today = datetime.now().strftime("%Y-%m-%d")
    expiry = (datetime.now() + __import__('datetime').timedelta(days=30)).strftime("%Y-%m-%d")
    
    # 市场数据
    mkt = d.get("market", {})
    price = mkt.get("price", 0)
    change = mkt.get("change_pct", 0)
    pe_ttm = mkt.get("pe_ttm", 0)
    pb = mkt.get("pb", 0)
    mcap = mkt.get("mcap_yi", 0)
    
    # 公司信息
    f10 = d.get("f10", {})
    full_name = f10.get("full_name", name)
    industry = f10.get("industry_csrc", d.get("halo", {}).get("industry", ""))
    emp = f10.get("employee_count", 0)
    chairman = f10.get("chairman", "")
    gm = f10.get("general_manager", "")
    
    # 资产类型
    at = d.get("halo", {}).get("asset_type", "mixed")
    at_desc = asset_desc(at)
    
    # HALO 评分
    halo_scores = score_halo(d)
    growth_scores = score_growth(d)
    
    # 财务指标
    ratios = d.get("ratios", {})
    gross_margin = ratios.get("gross_margin", 0)
    net_margin = ratios.get("net_margin", 0)
    debt_ratio = ratios.get("debt_ratio", 0)
    current_ratio = ratios.get("current_ratio", 0)
    roe = ratios.get("roe", 0)
    roa = ratios.get("roa", 0)
    cf_profit = ratios.get("cf_to_profit", 0)
    
    # HALO 原始数据
    halo_raw = d.get("halo", {}).get("raw", {})
    total_assets = halo_raw.get("total_assets_yi", 0)
    fixed_assets = halo_raw.get("fixed_assets_yi", 0)
    cip = halo_raw.get("cip_yi", 0)
    inventory = halo_raw.get("inventory_yi", 0)
    intangible = halo_raw.get("intangible_yi", 0)
    tangible = halo_raw.get("tangible_yi", 0)
    capex = halo_raw.get("capex_yi", 0)
    ocf = halo_raw.get("ocf_yi", 0)
    revenue = halo_raw.get("revenue_yi", 0)
    total_liab = halo_raw.get("total_liabilities_yi", 0)
    
    # HALO 维度原始值
    halo_dims = d.get("halo", {}).get("dimensions", {})
    ti_val = halo_dims.get("tangible_intensity", {}).get("value", 0)
    fi_val = halo_dims.get("fixed_intensity", {}).get("value", 0)
    fs_val = halo_dims.get("fixed_share", {}).get("value", 0)
    cl_val = halo_dims.get("capital_labor", {}).get("value", 0)
    ci_val = halo_dims.get("capex_intensity", {}).get("value", 0)
    
    # 成长性数据
    g = d.get("growth", {})
    rev_yoy = g.get("revenue_yoy", 0)
    np_yoy = g.get("net_profit_yoy", 0)
    annual_rev_yoy = g.get("annual_revenue_yoy", 0)
    annual_np_yoy = g.get("annual_profit_yoy", 0)
    latest_period = g.get("latest_period", "")
    compare_period = g.get("compare_period", "")
    
    # 最新财报数据
    fin = d.get("financial", {})
    inc = fin.get("income", [])
    bal = fin.get("balance", [])
    cf_stmt = fin.get("cashflow", [])
    
    latest_rev = inc[0].get("营业收入", 0) if inc else 0
    latest_np = inc[0].get("净利润", 0) if inc else 0
    latest_eps = inc[0].get("基本每股收益", 0) if inc else 0
    prev_rev = inc[1].get("营业收入", 0) if len(inc) > 1 else 0
    prev_np = inc[1].get("净利润", 0) if len(inc) > 1 else 0
    
    # 资金流：从逐日 fund_flow 计算近5日主力净流入（单位：元，符合 JSON 金额统一为元的约定）
    _ff = d.get("fund_flow", [])
    _recent5 = _ff[-5:] if len(_ff) >= 5 else _ff
    main_5d = sum(float(f.get("main_net_inflow") or 0) for f in _recent5)
    
    # 研报统计
    reports = qual.get("reports", [])
    ratings_dist = qual.get("reports_summary", {}).get("ratings", {})
    
    # 最新报告期
    latest_report = d.get("meta", {}).get("data_quality", {}).get("latest_report", latest_period)
    
    # 固定权重
    halo_weights = {"3_1": "20%", "3_2": "15%", "3_3": "15%", "3_4": "15%", "3_5": "15%", "3_6": "20%"}
    
    # ── 生成骨架 Markdown ──
    
    lines = []
    w = lines.append
    
    # 报告头
    w(f"# 🏢 {name}({code}) HALO滞胀复合分析报告\n")
    w(f"📅 **分析日期**：{today} | 🏭 **所属行业**：{industry} | 📦 **资产类型**：{at}({at_desc}) | 📄 **模板**：V5.0\n")
    w("")
    w("🌐 **数据来源**：")
    w("| 数据层 | 来源 | 可信度 | 内容 |")
    w("|:-------|:-----|:------:|:-----|")
    w("| 行情层 | 腾讯财经 | ⭐⭐⭐⭐⭐ | 实时价格/PE/PB/市值 |")
    w("| 信息层 | 东方财富 | ⭐⭐⭐⭐ | 行业/股本/资金流向/F10 |")
    w("| 财务层 | 新浪财经 | ⭐⭐⭐⭐⭐ | 三表（8期纵向） |")
    w(f"| 舆情层 | 东财搜索 | ⭐⭐⭐⭐ | 新闻{len(qual.get('news', []))}条/研报{len(reports)}篇 |")
    w("")
    w(f"⏳ **报告有效期**：30日（至{expiry}） | 📅 **最新报告期**：{latest_report} | 👥 **员工**：{int(emp):,}人")
    w("")
    w("---")
    w("")

    # ── 报告导读 ──
    w("## 📖 报告导读\n")
    w("> 本报告基于 **HALO V5.0 滞胀复合分析框架**，从11个维度对目标公司进行全方位评估。")
    w(">")
    w("> **🔒 数据层**（第零章~第四章部分）：所有财务数据、行情数据、HALO计算结果均由 Python 从 API 获取并填充，100% 准确。")
    w(">")
    w("> **✍️ 分析层**（各章 💡 标记部分）：由 AI 基于数据生成分析判断，包括护城河、滞胀防御、ESG、管理层等定性评估。")
    w(">")
    w("> **📊 评分体系**：")
    w("> - 🔷 **HALO六维**（5分制）：衡量企业重资产属性，适配不同行业（重/混合/轻资产）")
    w("> - 🌱 **成长性**（10分制）：营收/利润增速 + 增长质量 + 持续性")
    w("> - 🏰 **护城河**（10分制）：技术壁垒 + 客户粘性 + 竞争格局 + 差异化 + 进入壁垒")
    w("> - 🛡️ **滞胀防御**（10分制）：实物资产 + 通胀转嫁 + 现金流 + 债务结构 + 战略安全")
    w("> - 🌍 **ESG**（10分制）：环境 + 社会 + 治理")
    w("> - 👔 **管理层**（10分制）：战略 + 资本配置 + 激励 + 诚信")
    w("> - 💰 **资金面**（10分制）：股东结构 + 北向资金 + 主力 + 融资")
    w("> - ⚠️ **风险**（10分制，越低越好）：7类风险矩阵加权")
    w("")
    w("---")
    w("")

    # ── 第零章：执行摘要 ──
    w("## 📋 第零章：执行摘要\n")
    w("### ⭐ 核心评分卡片\n")
    w("| 评估维度 | 评分 | 评级 | 核心结论 |")
    w("|:---------|:----:|:----:|:---------|")
    w(f"| 🔷 **HALO评分** | **{halo_scores['total']}/5.0** | {halo_scores['rating']} | {{AI_HALO_SUMMARY}} |")
    w(f"| 🌱 **成长性评分** | **{growth_scores['total']}/10** | {growth_scores['rating']} | {{AI_GROWTH_SUMMARY}} |")
    w(f"| 🏰 **低淘汰率评分** | **{{AI_MOAT_SCORE}}/10** | {{AI_MOAT_RATING}} | {{AI_MOAT_SUMMARY}} |")
    w(f"| 🛡️ **滞胀防御评分** | **{{AI_STAG_SCORE}}/10** | {{AI_STAG_RATING}} | {{AI_STAG_SUMMARY}} |")
    w(f"| 🌍 **ESG评分** | **{{AI_ESG_SCORE}}/10** | {{AI_ESG_RATING}} | {{AI_ESG_SUMMARY}} |")
    w(f"| 👔 **管理层评分** | **{{AI_MGMT_SCORE}}/10** | {{AI_MGMT_RATING}} | {{AI_MGMT_SUMMARY}} |")
    w(f"| 💰 **股东资金面** | **{{AI_SH_SCORE}}/10** | {{AI_SH_RATING}} | {{AI_SH_SUMMARY}} |")
    w(f"| ⚠️ **综合风险** | **{{AI_RISK_SCORE}}/10** | {{AI_RISK_RATING}} | {{AI_RISK_SUMMARY}} |")
    w("")
    w("**💰 实时估值**：")
    change_str = f"({change:+.2f}%)" if change else ""
    w(f"| 📈 当前价 | 📊 PE(TTM) | 📊 PB | 💰 市值 | 💵 股息率 |")
    w(f"|:---------:|:---------:|:-----:|:-------:|:---------:|")
    w(f"| {price}元{change_str} | {pe_ttm} | {pb} | {mcap}亿 | {{AI_DIV_YIELD}} |")
    w("")
    w("---")
    w("")
    w("### 🎯 投资结论\n")
    w("> 📈 **投资评级**：**{{AI_INVEST_RATING}}**")
    w("> 🎯 **目标价位**：{{AI_TARGET_LOW}}-{{AI_TARGET_HIGH}}元")
    w("> 📊 **潜在空间**：{{AI_UPSIDE}}")
    w("")
    w("### 💡 核心投资逻辑\n")
    w("> **1️⃣** {{AI_LOGIC_1}}")
    w("> **2️⃣** {{AI_LOGIC_2}}")
    w("> **3️⃣** {{AI_LOGIC_3}}")
    w("")
    w("---")
    w("")
    
    # ── 一、公司概况 ──
    w("## 📊 一、公司概况\n")
    w("### 🏛️ 1.1 基本信息\n")
    w("| 📌 项目 | 📝 内容 | 🌐 来源 |")
    w("|:--------|:--------|:-------:|")
    w(f"| **公司全称** | {full_name} | 东财F10 |")
    w(f"| **股票代码** | {code}.SH | 腾讯 |")
    w(f"| **所属行业** | {industry} | 东财 |")
    w(f"| **资产类型** | {at}({at_desc}) | AI判定 |")
    w(f"| **当前市值** | {mcap}亿元 | 腾讯 |")
    w(f"| **实时股价** | {price}元{change_str} | 腾讯 |")
    w(f"| **董事长** | {chairman} | 东财F10 |")
    w(f"| **总经理** | {gm} | 东财F10 |")
    w(f"| **员工人数** | {int(emp):,}人 | 东财F10 |")
    w("")
    w("### 💼 1.2 主营业务结构\n")
    w("| 🏷️ 业务板块 | 📊 营收占比 | 💹 毛利率 | 🎯 核心产品 |")
    w("|:------------|:-----------:|:---------:|:------------|")
    w("{{AI_BIZ_TABLE}}")
    w("")
    w("> 💡 {{AI_BIZ_ANALYSIS}}")
    w("")
    w("### ⭐ 1.3 核心竞争优势\n")
    w("{{AI_ADVANTAGE}}")
    w("")
    w("---")
    w("")
    
    # ── 二、消息面 ──
    w("## 📰 二、最新基本面与消息面\n")
    w(f"> 📡 **数据周期**：近30日 | 📊 **情绪评分**：**{{AI_SENTIMENT_SCORE}}/10**（{{AI_SENTIMENT_DESC}}）")
    w("")
    w("### 📈 利好因素\n")
    w("| # | 🎯 类型 | 📋 事件 | 📅 日期 | 💪 影响 | ⭐ 可信度 |")
    w("|:-:|:-------:|:--------|:-------:|:-------:|:--------:|")
    # Fill news from qualitative data
    news = qual.get("news", [])
    for i, n in enumerate(news[:5]):
        title = n.get("title", "")
        date = n.get("date", "")[:10]
        w(f"| {i+1} | {{AI_NEWS_TYPE_{i+1}}} | {title} | {date} | {{AI_NEWS_IMPACT_{i+1}}} | ⭐⭐⭐⭐ |")
    w("")
    w("### 📉 利空因素\n")
    w("| # | 🎯 类型 | 📋 事件 | 📅 日期 | ⚠️ 影响 | ⭐ 可信度 |")
    w("|:-:|:-------:|:--------|:-------:|:-------:|:--------:|")
    w("{{AI_NEGATIVE_FACTORS}}")
    w("")
    w("### 💡 消息面综合判断\n")
    w("{{AI_MESSAGE_SUMMARY}}")
    w("")
    w("---")
    w("")

    # ── 三、HALO六维分析 ──
    w("## 🔷 三、HALO框架六维分析（5分制，行业调整版）\n")
    w("> 💡 **HALO 是什么？** Heavy Asset Lagflation Orientation — 重资产滞胀导向框架。")
    w(">")
    w("> 核心逻辑：在滞胀环境（高通胀+低增长）中，**重资产企业**更具防御性，因为它们拥有实物资产（厂房、设备、存货），")
    w("> 这些资产会随通胀升值，且企业可以通过提价将成本转嫁给下游。HALO 六维评估企业在这方面的能力。")
    w(">")
    w("> **⭐ V5.0 行业调整**：不再一刀切地歧视轻资产。根据行业特性分为**重资产/混合型/轻资产**三类，采用不同评分阈值。")
    w("> 例如：白酒（轻资产）的品牌价值不应被低固定资产惩罚；钢铁（重资产）的高固定资产不应被过度奖励。")
    w("")
    w(f"> 🟢 极强 ≥4.0 | 🟡 强 3.0-4.0 | 🟠 中等 2.0-3.0 | 🔴 弱 <2.0")
    w(f"> 📦 **资产类型**：{at}({at_desc})")
    w(f"> ⭐ **V5.0**：采用{at}型行业评分标准")
    w("")
    
    # 3.1 有形资产密集度
    w("### 🏭 3.1 有形资产密集度\n")
    w("**📐 公式**：(固定资产+在建工程+存货) / 总资产\n")
    w("| 📦 项目 | 💰 金额 | 📊 占比 | 🌐 来源 |")
    w("|:--------|:-------:|:------:|:-------:|")
    w(f"| 🏭 固定资产 | {fixed_assets}亿 | {fs_val}% | 新浪 |")
    w(f"| 🏗️ 在建工程 | {cip}亿 | {fmt_pct(float(cip)/float(total_assets)*100 if total_assets else 0)}% | 新浪 |")
    w(f"| 📦 存货 | {inventory}亿 | {fmt_pct(float(inventory)/float(total_assets)*100 if total_assets else 0)}% | 新浪 |")
    w(f"| **💎 有形资产合计** | **{tangible}亿** | **{ti_val}%** | 计算 |")
    w(f"| 📊 总资产 | {total_assets}亿 | 100% | 新浪 |")
    w(f"| **📈 有形资产密集度** | **{ti_val}%** | **⭐ {halo_scores['3_1']}分** | - |")
    w("")
    w("> 💡 {{AI_TANGIBLE_ANALYSIS}}")
    w("")
    w("---")
    w("")
    
    # 3.2 固定资产密集度
    w("### 🏗️ 3.2 固定资产密集度\n")
    w("| 📊 指标 | 💰 数值 | ⭐ 评分 |")
    w("|:--------|:-------:|:------:|")
    w(f"| 固定资产 | {fixed_assets}亿 | - |")
    w(f"| 营业收入 | {revenue}亿 | - |")
    w(f"| **📈 密集度** | **{fi_val}%** | **⭐ {halo_scores['3_2']}分** |")
    w("")
    w("> 💡 {{AI_FIXED_INTENSITY_ANALYSIS}}")
    w("")
    w("---")
    w("")
    
    # 3.3 固定资产份额
    w("### 📊 3.3 固定资产份额\n")
    w("| 📊 指标 | 💰 数值 | ⭐ 评分 |")
    w("|:--------|:-------:|:------:|")
    w(f"| 固定资产 | {fixed_assets}亿 | - |")
    w(f"| 总资产 | {total_assets}亿 | - |")
    w(f"| **📈 份额** | **{fs_val}%** | **⭐ {halo_scores['3_3']}分** |")
    w("")
    w("> 💡 {{AI_FIXED_SHARE_ANALYSIS}}")
    w("")
    w("---")
    w("")
    
    # 3.4 资本-劳动力比率
    w("### 👥 3.4 资本-劳动力比率\n")
    w("| 📊 指标 | 💰 数值 | ⭐ 评分 |")
    w("|:--------|:-------:|:------:|")
    w(f"| 有形资产 | {tangible}亿 | - |")
    w(f"| 员工人数 | {int(emp):,}人 | 东财F10 |")
    w(f"| **📈 人均有形资产** | **{cl_val}万元/人** | **⭐ {halo_scores['3_4']}分** |")
    w("")
    w("> 💡 {{AI_CAPITAL_LABOR_ANALYSIS}}")
    w("")
    w("---")
    w("")
    
    # 3.5 Capex密集度
    w("### 💰 3.5 Capex密集度\n")
    w("| 📊 指标 | 💰 数值 | ⭐ 评分 |")
    w("|:--------|:-------:|:------:|")
    w(f"| Capex | {capex}亿 | 新浪 |")
    w(f"| 营业收入 | {revenue}亿 | 新浪 |")
    w(f"| **📈 Capex密集度** | **{ci_val}%** | **⭐ {halo_scores['3_5']}分** |")
    w("")
    w("> 💡 {{AI_CAPEX_INTENSITY_ANALYSIS}}")
    w("")
    w("---")
    w("")
    
    # 3.6 Capex负担
    w("### ⚖️ 3.6 Capex负担\n")
    w("| 📊 指标 | 💰 数值 | ⭐ 评分 |")
    w("|:--------|:-------:|:------:|")
    w(f"| Capex | {capex}亿 | 新浪 |")
    w(f"| 经营现金流 | {ocf}亿 | 新浪 |")
    burden_display = f"{halo_scores['burden_pct']}%" if "⚠️" not in str(halo_scores['burden_pct']) else halo_scores['burden_pct']
    w(f"| **📈 Capex负担** | **{burden_display}** | **⭐ {halo_scores['3_6']}分** |")
    w("")
    w("> 💡 {{AI_CAPEX_BURDEN_ANALYSIS}}")
    w("")
    w("---")
    w("")
    
    # HALO 汇总
    w("### 📈 HALO六维评分汇总\n")
    w("| 🔷 维度 | ⭐ 得分 | ⚖️ 权重 | 📊 加权 | 📝 关键论据 |")
    w("|:--------|:------:|:------:|:------:|:------------|")
    dim_names = ["🏭 有形资产密集度", "🏗️ 固定资产密集度", "📊 固定资产份额", "👥 资本-劳动力比率", "💰 Capex密集度", "⚖️ Capex负担"]
    dim_keys = ["3_1", "3_2", "3_3", "3_4", "3_5", "3_6"]
    for i, (dn, dk) in enumerate(zip(dim_names, dim_keys)):
        score = halo_scores[dk]
        weight = halo_weights[dk]
        weighted = f"{score * float(weight.strip('%'))/100:.2f}"
        w(f"| {dn} | {score} | {weight} | {weighted} | {{AI_REASON_{dk}}} |")
    w(f"| **🔷 HALO总分** | - | - | **{halo_scores['total']}/5.0** | **{halo_scores['rating']}** |")
    w("")
    w("---")
    w("")
    
    # ── 四、成长性分析 ──
    w("## 🌱 四、成长性分析（10分制）⭐NEW V5.0\n")
    w("### 📈 4.1 营收增长\n")
    w("| 📊 期间 | 营收 | 同比 |")
    w("|:--------|:----:|:----:|")
    w(f"| {latest_period} | {fmt_yi(latest_rev)}亿 | **+{rev_yoy}%** |")
    w(f"| 年度 | {fmt_yi(float(revenue)*1e8*4 if revenue else 0)}亿(估) | {annual_rev_yoy}% |")
    w("")
    w(f"**⭐ 评分**：{growth_scores['4_1']}/10")
    w(f"> 💡 {{AI_REVENUE_ANALYSIS}}")
    w("")
    w("### 💰 4.2 利润增长\n")
    w("| 📊 期间 | 净利润 | 同比 |")
    w("|:--------|:------:|:----:|")
    w(f"| {latest_period} | {fmt_yi(latest_np)}亿 | **+{np_yoy}%** |")
    w(f"| 年度 | - | {annual_np_yoy}% |")
    w("")
    w(f"**⭐ 评分**：{growth_scores['4_2']}/10")
    w(f"> 💡 {{AI_PROFIT_ANALYSIS}}")
    w("")
    w("### 🔍 4.3 增长质量\n")
    w("| 📊 评估项 | ⭐ 评分 | 📝 说明 |")
    w("|:----------|:------:|:--------|")
    w(f"| 有机增长 vs 并购 | {{AI_ORGANIC_SCORE}} | {{AI_ORGANIC_COMMENT}} |")
    w(f"| 杠杆增长 vs 效率 | {{AI_LEVERAGE_SCORE}} | {{AI_LEVERAGE_COMMENT}} |")
    w(f"| 主营 vs 非经常性 | {{AI_RECURRING_SCORE}} | {{AI_RECURRING_COMMENT}} |")
    w(f"| 现金流匹配度 | {{AI_CF_MATCH_SCORE}} | CF/净利润={cf_profit} |")
    w("")
    w(f"**⭐ 维度得分**：{growth_scores['4_3']}/10")
    w("")
    w("### 🚀 4.4 增长持续性\n")
    w("| 📊 评估项 | ⭐ 评分 | 📝 说明 |")
    w("|:----------|:------:|:--------|")
    w("| 行业增速 | {{AI_IND_GROWTH_SCORE}} | {{AI_IND_GROWTH_COMMENT}} |")
    w("| 市场空间 | {{AI_MARKET_SCORE}} | {{AI_MARKET_COMMENT}} |")
    w("| 研发投入 | {{AI_RD_SCORE}} | {{AI_RD_COMMENT}} |")
    w("| 新业务储备 | {{AI_NEWBIZ_SCORE}} | {{AI_NEWBIZ_COMMENT}} |")
    w("")
    w(f"**⭐ 维度得分**：{growth_scores['4_4']}/10")
    w("")
    w(f"**🌱 成长性总分**：**{growth_scores['total']}/10（{growth_scores['rating']}）**")
    w("")
    w("---")
    w("")
    
    # ── 五、低淘汰率 ──
    w("## 🏰 五、低淘汰率五维分析（10分制）\n")
    w("> 💡 **低淘汰率 = 护城河深度**。巴菲特的'经济护城河'理论：优秀企业应能长期抵御竞争者侵蚀。")
    w(">")
    w("> 我们从五个维度评估企业被淘汰的风险：技术是否会被颠覆？客户是否会流失？竞争是否激烈？")
    w("> 产品是否可替代？新玩家是否容易进入？得分越高，企业越'长寿'。")
    w("")
    w("{{AI_MOAT_SECTION}}")
    w("")
    w("---")
    w("")
    
    # ── 六、滞胀防御 ──
    w("## 🛡️ 六、滞胀防御五维分析（10分制）\n")
    w("> 💡 **为什么关注滞胀？** 滞胀（Stagflation）= 高通胀 + 低增长，是投资者最痛苦的环境。")
    w(">")
    w("> 在滞胀中：原材料涨价侵蚀利润、消费者购买力下降、央行加息打压估值。")
    w("> **防御者特征**：拥有实物资产（随通胀升值）、强定价权（转嫁成本）、充沛现金流（不依赖融资）、低负债（不怕加息）。")
    w(">")
    w("> 茅台是典型滞胀防御者（品牌+高毛利+零负债）；制造业通常防御力较弱（毛利率低+负债高）。")
    w("")
    w("{{AI_STAGFLATION_SECTION}}")
    w("")
    w("---")
    w("")
    
    # ── 七、ESG ──
    w("## 🌍 七、ESG评估（10分制）⭐NEW V5.0\n")
    w("> 💡 **ESG 不只是'道德投资'**：环境(Environmental)、社会(Social)、治理(Governance)。")
    w(">")
    w("> 研究表明，ESG评分高的企业长期风险更低、资本成本更低、品牌价值更高。")
    w("> 尤其对机构投资者，ESG是'排除法'的硬指标——环保违规、治理丑闻可能导致被动抛售。")
    w("")
    w("{{AI_ESG_SECTION}}")
    w("")
    w("---")
    w("")
    
    # ── 八、管理层 ──
    w("## 👔 八、管理层质量（10分制）⭐NEW V5.0\n")
    w("> 💡 **管理层是企业的'大脑'**：同样的行业、同样的资源，不同的管理层可能产出截然不同的结果。")
    w(">")
    w("> 我们评估：战略是否清晰（知道做什么、不做什么）？资本配置是否高效（ROE/分红/并购）？")
    w("> 激励是否一致（管理层与股东利益绑定）？诚信是否可靠（信披合规、无违规）？")
    w(">")
    w("> ⚠️ 国企 vs 民企差异：国企决策稳健但激励不足；民企激励强但'一股独大'风险高。")
    w("")
    w("{{AI_MGMT_SECTION}}")
    w("")
    w("---")
    w("")
    
    # ── 九、股东资金面 ──
    w("## 💰 九、股东与资金面（10分制）⭐NEW V5.0\n")
    w("> 💡 **资金面是短期股价的'投票器'**：基本面决定长期价值，但短期涨跌由资金驱动。")
    w(">")
    w("> 我们跟踪：控股股东稳定性（是否会减持套现？）、北向资金（外资风向标）、")
    w("> 主力资金（大单流向）、融资动态（杠杆资金情绪）。")
    w(">")
    w("> ⚠️ 资金面是'双刃剑'：今日流入不等于明日不流出，需结合基本面综合判断。")
    w("")
    w(f"> 📊 近5日主力净流入：{fmt_wan(abs(main_5d))}万元 ({'流入' if main_5d > 0 else '流出'})")
    w("")
    w("{{AI_SHAREHOLDER_SECTION}}")
    w("")
    w("---")
    w("")
    
    # ── 十、风险评估 ──
    w("## ⚠️ 十、风险评估（7类风险矩阵）\n")
    w("> 💡 **风险与收益不是线性关系**：高风险不一定高收益，低风险也不一定低收益。")
    w(">")
    w("> 我们的目标是**识别'不可承受之 risk'**——那些可能导致永久性资本损失的风险。")
    w("> 7类风险中，财务风险（破产）和估值风险（买贵了）是最致命的。")
    w(">")
    w("> ⚠️ 风险评分**越低越好**：<3低风险 | 3-5中等 | 5-7较高 | >7高风险")
    w("")
    w("{{AI_RISK_SECTION}}")
    w("")
    w("---")
    w("")
    
    # ── 十一、综合评估 ──
    w("## 💡 十一、综合评估与投资建议\n")
    w("> 💡 **综合评分 = 多维度加权**：不是简单平均，而是根据各维度重要性分配权重。")
    w(">")
    w("> HALO和成长性各占15%（核心），护城河15%（长期价值），滞胀/ESG/管理层各10%（质量），")
    w("> 估值10%（安全边际），资金面5%（短期因素），风险-10%（减分项）。")
    w(">")
    w("> **投资建议逻辑**：综合评分≥6.5且风险<5 → 增持/买入；5-6.5 → 中性；<5 → 减持/回避。")
    w("")
    w("### 📊 11.1 11维综合评级\n")
    w("| 📊 评估框架 | ⭐ 评分 | 🟢 评级 | ⚖️ 权重 | 📝 核心结论 |")
    w("|:------------|:------:|:-------:|:------:|:------------|")
    w(f"| 🔷 HALO六维 | {halo_scores['total']}/5.0 | {halo_scores['rating']} | 15% | {{AI_HALO_CONCLUSION}} |")
    w(f"| 🌱 成长性 | {growth_scores['total']}/10 | {growth_scores['rating']} | 15% | {{AI_GROWTH_CONCLUSION}} |")
    w("| 🏰 低淘汰率 | {{AI_MOAT_SCORE}}/10 | {{AI_MOAT_RATING}} | 15% | {{AI_MOAT_CONCLUSION}} |")
    w("| 🛡️ 滞胀防御 | {{AI_STAG_SCORE}}/10 | {{AI_STAG_RATING}} | 10% | {{AI_STAG_CONCLUSION}} |")
    w("| 🌍 ESG | {{AI_ESG_SCORE}}/10 | {{AI_ESG_RATING}} | 10% | {{AI_ESG_CONCLUSION}} |")
    w("| 👔 管理层 | {{AI_MGMT_SCORE}}/10 | {{AI_MGMT_RATING}} | 10% | {{AI_MGMT_CONCLUSION}} |")
    w("| 💰 股东资金面 | {{AI_SH_SCORE}}/10 | {{AI_SH_RATING}} | 5% | {{AI_SH_CONCLUSION}} |")
    w("| 💵 估值吸引力 | {{AI_VAL_SCORE}}/10 | {{AI_VAL_RATING}} | 10% | {{AI_VAL_CONCLUSION}} |")
    w("| ⚠️ 风险 | {{AI_RISK_SCORE}}/10 | {{AI_RISK_RATING}} | -10% | {{AI_RISK_CONCLUSION}} |")
    w("")
    w("### 📊 综合评分计算\n")
    w("```")
    w(f"综合评分 = {halo_scores['total']}/5×10×15% + {{AI_GROWTH_SCORE}}×15% + {{AI_MOAT_SCORE}}×15%")
    w("         + {{AI_STAG_SCORE}}×10% + {{AI_ESG_SCORE}}×10% + {{AI_MGMT_SCORE}}×10%")
    w("         + {{AI_SH_SCORE}}×5% + {{AI_VAL_SCORE}}×10% - {{AI_RISK_SCORE}}×10%")
    w("= {{AI_COMPREHENSIVE_SCORE}}/10")
    w("```")
    w("")
    w("**📊 综合评分：{{AI_COMPREHENSIVE_SCORE}}/10（{{AI_COMPREHENSIVE_RATING}}）**")
    w("")
    w("### 💼 投资建议\n")
    w("{{AI_INVESTMENT_SECTION}}")
    w("")
    w("### 💰 估值分析\n")
    w("{{AI_VALUATION_SECTION}}")
    w("")
    w("### 🔭 SWOT分析\n")
    w("{{AI_SWOT_SECTION}}")
    w("")
    w("### 📝 总结\n")
    w("{{AI_FINAL_SUMMARY}}")
    w("")
    w("---")
    w("")

    # ── 十二、产业链定位（Serenity 集成，可选） ──
    w("## 🔗 十二、产业链定位（Serenity 集成）⭐OPTIONAL\n")
    w("> 💡 **产业链卡点分析**：基于 Serenity 供应链瓶颈研究方法，定位公司在产业链中的位置。")
    w(">")
    w("> Serenity 方法论：从市场需求出发 → 映射产业链层级 → 找到稀缺环节（卡点） → 定位公司。")
    w("> 核心问题：公司**控制**稀缺环节？**供应**稀缺环节？还是仅仅**受益于**主题？")
    w(">")
    w("> ⚠️ 本章节为可选内容，依赖 Serenity 产业链扫描数据。如无数据，本章内容留空。")
    w("")
    w("### 🗺️ 12.1 产业链位置\n")
    w("| 📍 维度 | 📝 内容 |")
    w("|:--------|:--------|")
    w("| **所属产业链** | {{SERENITY_CHAIN}} |")
    w("| **产业链层级** | {{SERENITY_LAYER}} |")
    w("| **卡住的环节** | {{SERENITY_BOTTLENECK}} |")
    w("| **稀缺性评级** | {{SERENITY_SCARCITY}} |")
    w("| **扩产难度** | {{SERENITY_EXPANSION}} |")
    w("")
    w("> 💡 {{SERENITY_POSITION_ANALYSIS}}")
    w("")
    w("### 🔍 12.2 证据链\n")
    w("| 📋 证据类型 | 📝 内容 | ⭐ 强度 |")
    w("|:------------|:--------|:------:|")
    w("| **核心证据1** | {{SERENITY_EVIDENCE_1}} | {{SERENITY_STRENGTH_1}} |")
    w("| **核心证据2** | {{SERENITY_EVIDENCE_2}} | {{SERENITY_STRENGTH_2}} |")
    w("| **核心证据3** | {{SERENITY_EVIDENCE_3}} | {{SERENITY_STRENGTH_3}} |")
    w("")
    w("> 💡 {{SERENITY_EVIDENCE_ANALYSIS}}")
    w("")
    w("### ⚠️ 12.3 风险与证伪\n")
    w("| 🔴 风险类型 | 📝 描述 |")
    w("|:------------|:--------|")
    w("| **替代风险** | {{SERENITY_RISK_SUBSTITUTE}} |")
    w("| **扩产风险** | {{SERENITY_RISK_EXPANSION}} |")
    w("| **需求风险** | {{SERENITY_RISK_DEMAND}} |")
    w("| **证伪条件** | {{SERENITY_FALSIFICATION}} |")
    w("")
    w("> 💡 {{SERENITY_RISK_ANALYSIS}}")
    w("")
    w("### 🎯 12.4 产业链评分\n")
    w("| 📊 维度 | ⭐ 评分 | 📝 说明 |")
    w("|:--------|:------:|:--------|")
    w("| **稀缺性** | {{SERENITY_SCARCITY_SCORE}}/10 | {{SERENITY_SCARCITY_COMMENT}} |")
    w("| **控制力** | {{SERENITY_CONTROL_SCORE}}/10 | {{SERENITY_CONTROL_COMMENT}} |")
    w("| **证据质量** | {{SERENITY_EVIDENCE_SCORE}}/10 | {{SERENITY_EVIDENCE_COMMENT}} |")
    w("| **产业链综合** | {{SERENITY_TOTAL_SCORE}}/10 | {{SERENITY_TOTAL_COMMENT}} |")
    w("")
    w("---")
    w("")

    w("## ⚠️ 免责声明\n")
    w("1. 本报告仅供参考，不构成投资建议")
    w("2. 投资有风险，入市需谨慎")
    w("3. 数据来源于公开API（腾讯/东财/新浪），可能存在延迟或口径差异")
    w("4. 定性分析（ESG/管理层/舆情）部分基于AI搜索，可能存在信息偏差")
    w(f"5. 报告有效期30日（至{expiry}），逾期请重新生成")
    w("6. 本报告由HALO V5.0模板生成，AI模型可能存在认知偏差")
    w("")
    w("---")
    w("")
    w(f"*模板版本: V5.0 | 数据驱动 + 行业公平版*")
    w(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    w(f"*数据截止: {today}*")
    w(f"*报告有效期至: {expiry}*")
    w("")
    
    return "\n".join(lines)


def integrate_serenity_inline(skeleton, serenity_data):
    """将 Serenity 数据填充到骨架字符串中（不写文件）"""
    replacements = {}

    # 12.1 产业链位置
    replacements["{{SERENITY_CHAIN}}"] = serenity_data.get("chain", "⚠️ 数据缺失")
    replacements["{{SERENITY_LAYER}}"] = serenity_data.get("layer", "⚠️ 数据缺失")
    replacements["{{SERENITY_BOTTLENECK}}"] = serenity_data.get("bottleneck", "⚠️ 数据缺失")
    replacements["{{SERENITY_SCARCITY}}"] = serenity_data.get("scarcity_rating", "⚠️ 数据缺失")
    replacements["{{SERENITY_EXPANSION}}"] = serenity_data.get("expansion_difficulty", "⚠️ 数据缺失")
    replacements["{{SERENITY_POSITION_ANALYSIS}}"] = serenity_data.get("position_analysis", "⚠️ 待 AI 填充")

    # 12.2 证据链
    evidence = serenity_data.get("evidence", [])
    for i in range(3):
        if i < len(evidence):
            replacements[f"{{{{SERENITY_EVIDENCE_{i+1}}}}}"] = evidence[i].get("content", "⚠️ 数据缺失")
            replacements[f"{{{{SERENITY_STRENGTH_{i+1}}}}}"] = evidence[i].get("strength", "⭐")
        else:
            replacements[f"{{{{SERENITY_EVIDENCE_{i+1}}}}}"] = "暂无"
            replacements[f"{{{{SERENITY_STRENGTH_{i+1}}}}}"] = "-"

    replacements["{{SERENITY_EVIDENCE_ANALYSIS}}"] = serenity_data.get("evidence_analysis", "⚠️ 待 AI 填充")

    # 12.3 风险与证伪
    risks = serenity_data.get("risks", {})
    replacements["{{SERENITY_RISK_SUBSTITUTE}}"] = risks.get("substitute", "⚠️ 数据缺失")
    replacements["{{SERENITY_RISK_EXPANSION}}"] = risks.get("expansion", "⚠️ 数据缺失")
    replacements["{{SERENITY_RISK_DEMAND}}"] = risks.get("demand", "⚠️ 数据缺失")
    replacements["{{SERENITY_FALSIFICATION}}"] = risks.get("falsification", "⚠️ 数据缺失")
    replacements["{{SERENITY_RISK_ANALYSIS}}"] = serenity_data.get("risk_analysis", "⚠️ 待 AI 填充")

    # 12.4 产业链评分
    scores = serenity_data.get("scores", {})
    replacements["{{SERENITY_SCARCITY_SCORE}}"] = str(scores.get("scarcity", "⚠️"))
    replacements["{{SERENITY_SCARCITY_COMMENT}}"] = scores.get("scarcity_comment", "⚠️ 数据缺失")
    replacements["{{SERENITY_CONTROL_SCORE}}"] = str(scores.get("control", "⚠️"))
    replacements["{{SERENITY_CONTROL_COMMENT}}"] = scores.get("control_comment", "⚠️ 数据缺失")
    replacements["{{SERENITY_EVIDENCE_SCORE}}"] = str(scores.get("evidence", "⚠️"))
    replacements["{{SERENITY_EVIDENCE_COMMENT}}"] = scores.get("evidence_comment", "⚠️ 数据缺失")
    replacements["{{SERENITY_TOTAL_SCORE}}"] = str(scores.get("total", "⚠️"))
    replacements["{{SERENITY_TOTAL_COMMENT}}"] = scores.get("total_comment", "⚠️ 数据缺失")

    # 应用替换
    for k, v in replacements.items():
        skeleton = skeleton.replace(k, str(v))

    return skeleton


# ── CLI ──

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_report.py <股票代码>")
        print("示例: python generate_report.py 600519")
        sys.exit(1)
    
    stock_code = sys.argv[1]
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    json_path = os.path.join(data_dir, f"{stock_code}.json")
    qual_path = os.path.join(data_dir, f"{stock_code}_qualitative.json")
    
    if not os.path.exists(json_path):
        print(f"❌ 找不到量化数据: {json_path}")
        print(f"   请先运行: python fetch_stock_data.py {stock_code} <股票名称>")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"  HALO V5.0 骨架生成 — {stock_code}")
    print(f"{'='*60}\n")
    
    skeleton = generate_skeleton(json_path, qual_path)

    # 自动集成 Serenity 数据（如果存在）
    serenity_path = os.path.join(data_dir, f"{stock_code}_serenity.json")
    serenity_integrated = False
    if os.path.exists(serenity_path):
        try:
            from integrate_serenity import integrate_serenity
            with open(serenity_path, 'r', encoding='utf-8') as f:
                serenity_data = json.load(f)
            skeleton = integrate_serenity_inline(skeleton, serenity_data)
            serenity_integrated = True
        except Exception as e:
            print(f"  ⚠️ Serenity 集成失败: {e}")

    output_path = os.path.join(reports_dir, f"{stock_code}_skeleton.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(skeleton)

    # ── Harness 骨架层校验 ──
    print("  🔍 运行骨架层 harness 校验...")
    try:
        harness_result = validate_skeleton(stock_code)
    except Exception as e:
        print(f"  ❌ 骨架层 harness 运行异常: {e}")
        h = halo_harness.Harness(stock_code, "skeleton")
        h.check("骨架层 harness 运行异常", False,
                detail=f"{type(e).__name__}: {e}", level="error")
        halo_harness._save_report(h)
        sys.exit(1)

    if not harness_result["ok"]:
        print(f"  ❌ 骨架层 harness 未通过，请查看 reports/{stock_code}_harness.json")
        sys.exit(1)
    print("  ✅ 骨架层 harness 通过")

    # 统计 AI 槽位数量
    ai_slots = skeleton.count("{{AI_")
    serenity_slots = skeleton.count("{{SERENITY_")

    print(f"  ✅ 骨架保存到: {output_path}")
    print(f"  📊 文件大小: {os.path.getsize(output_path)/1024:.1f} KB")
    print(f"  📝 报告行数: {len(skeleton.splitlines())}")
    print(f"  🔒 数据字段: 已由 Python 填充（100% 来自 JSON）")
    print(f"  ✍️  AI 槽位: {ai_slots} 个（待 AI 填充分析文字）")
    if serenity_integrated:
        print(f"  🔗 Serenity: ✅ 已自动集成产业链数据")
    elif serenity_slots > 0:
        print(f"  🔗 Serenity: ⚠️ {serenity_slots} 个槽位待填充（运行 generate_serenity.py 后重新生成）")
    print(f"{'='*60}\n")
    print(f"  下一步: AI 读取 {output_path}，填充 {ai_slots} 个 {{AI_*}} 槽位")
    print(f"  最终输出: reports/{stock_code}_halo_v5.md")
    print(f"{'='*60}\n")
