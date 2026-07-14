#!/usr/bin/env python3
"""
HALO V5.0 数据获取脚本
输入: 股票代码 (如 600519)
输出: data/{stock_code}.json

数据源:
  - 腾讯行情: 实时价/PE/PB/市值 (HTTP, 不封IP)
  - 东财信息: 行业/股本/上市日期/概念板块 (HTTP, 限流)
  - 新浪财报: 利润表/资产负债表/现金流量表 (HTTP)
  - 东财信号: 资金流向/股东户数/分红/研报 (HTTP, 限流)

所有财务数据统一输出单位为 元
"""

import sys, json, os, time, random, re
import urllib.request
import requests
from datetime import datetime

# Harness 数据校验
from halo_harness import validate_data

# ══════════════════════════════════════════
#  全局配置
# ══════════════════════════════════════════
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ══════════════════════════════════════════
#  通用工具
# ══════════════════════════════════════════
def sf(v, default=0.0):
    """safe float"""
    if v is None or v == "" or v == "N/A":
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

def yi(val):
    """元 → 亿元"""
    return round(sf(val) / 1e8, 2)

def wan(val):
    """元 → 万元"""
    return round(sf(val) / 1e4, 2)

def pct(val):
    return round(sf(val), 2)

# ── 东财限流 ──
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0
_em_last = [0.0]

def em_get(url, params=None, timeout=15):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, timeout=timeout)
    finally:
        _em_last[0] = time.time()


# ══════════════════════════════════════════
#  §1 腾讯行情
# ══════════════════════════════════════════
def fetch_tencent_quote(code):
    """实时行情: 价格/PE/PB/市值/换手"""
    prefix = "sh" if code.startswith(("6","9")) else ("bj" if code.startswith("8") else "sz")
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    for line in data.strip().split(";"):
        if "=" not in line or '"' not in line:
            continue
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        return {
            "name": vals[1],
            "price": sf(vals[3]),
            "last_close": sf(vals[4]),
            "open": sf(vals[5]),
            "change_pct": sf(vals[32]),
            "high": sf(vals[33]),
            "low": sf(vals[34]),
            "amount_wan": sf(vals[37]),
            "turnover_pct": sf(vals[38]),
            "pe_ttm": sf(vals[39]),
            "mcap_yi": sf(vals[44]),
            "float_mcap_yi": sf(vals[45]),
            "pb": sf(vals[46]),
            "pe_static": sf(vals[52]),
        }
    return {}


# ══════════════════════════════════════════
#  §2 东财公司信息
# ══════════════════════════════════════════
def fetch_eastmoney_info(code):
    """公司基本信息: 行业/股本/市值/上市日期"""
    mc = 1 if code.startswith("6") else 0
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43,f162,f163,f167",
        "secid": f"{mc}.{code}",
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json().get("data", {})
    return {
        "code": d.get("f57", ""),
        "name": d.get("f58", ""),
        "industry": d.get("f127", ""),
        "total_shares": sf(d.get("f84")),
        "float_shares": sf(d.get("f85")),
        "mcap": sf(d.get("f116")),
        "float_mcap": sf(d.get("f117")),
        "list_date": str(d.get("f189", "")),
        "price": sf(d.get("f43")),
    }


def fetch_f10_detail(code):
    """F10详细数据: 员工人数/董事长/法人代表等"""
    prefix = "SH" if code.startswith("6") else "SZ"
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax"
    params = {"code": f"{prefix}{code}"}
    try:
        r = em_get(url, params=params, timeout=10)
        data = r.json()
        info = data.get("jbzl", data.get("gsjb", {}))
        return {
            "full_name": info.get("gsmc", ""),
            "english_name": info.get("ywmc", ""),
            "industry_csrc": info.get("sszjhhy", ""),
            "employee_count": sf(info.get("gyrs")),
            "management_count": sf(info.get("glryrs")),
            "chairman": info.get("frdb", ""),
            "general_manager": info.get("zjl", ""),
            "secretary": info.get("dm", ""),
            "phone": info.get("lxdh", ""),
            "website": info.get("gswz", ""),
            "address": info.get("bgdz", ""),
            "business_scope": info.get("jyfw", ""),
        }
    except Exception:
        return {}


# ══════════════════════════════════════════
#  §3 东财概念板块
# ══════════════════════════════════════════
def fetch_concept_blocks(code):
    """个股所属板块/概念"""
    mc = 1 if code.startswith("6") else 0
    url = "https://push2.eastmoney.com/api/qt/slist/get"
    params = {
        "spt": "3", "fields": "f12,f14,f3,f128,f136,f140",
        "secid": f"{mc}.{code}",
    }
    try:
        r = em_get(url, params=params, timeout=10)
        data = r.json().get("data", {})
        blocks = data.get("diff", []) if data else []
        result = []
        for b in (blocks or []):
            result.append({
                "code": b.get("f12", ""),
                "name": b.get("f14", ""),
                "change_pct": sf(b.get("f3")),
            })
        return result
    except Exception:
        return []


# ══════════════════════════════════════════
#  §4 新浪财报三表
# ══════════════════════════════════════════
def fetch_sina_report(code, report_type, num=8):
    """
    新浪财报: lrb=利润表, fzb=资产负债表, llb=现金流量表
    返回最近 num 期数据
    """
    prefix = "sh" if code.startswith("6") else "sz"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": f"{prefix}{code}",
        "source": report_type,
        "type": "0", "page": "1", "num": str(num),
    }
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
    report_list = r.json().get("result", {}).get("data", {}).get("report_list", {}) or {}

    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"period": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = sf(it.get("item_value"))
            tongbi = it.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_yoy"] = sf(tongbi)
        rows.append(rec)
    return rows


def fetch_all_financial_statements(code):
    """获取三表完整数据"""
    print("  [4/7] 利润表...")
    income = fetch_sina_report(code, "lrb", num=8)
    time.sleep(0.3)

    print("  [5/7] 资产负债表...")
    balance = fetch_sina_report(code, "fzb", num=8)
    time.sleep(0.3)

    print("  [6/7] 现金流量表...")
    cashflow = fetch_sina_report(code, "llb", num=8)

    return income, balance, cashflow


# ══════════════════════════════════════════
#  §5 东财资金流向 + 股东户数 + 分红
# ══════════════════════════════════════════
def fetch_fund_flow(code, days=120):
    """个股资金流向（日级，最近days天）"""
    mc = 1 if code.startswith("6") else 0
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": f"{mc}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "klt": "101", "lmt": str(days),
    }
    try:
        r = em_get(url, params=params, timeout=10)
        data = r.json().get("data", {})
        klines = data.get("klines", []) if data else []
        result = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 7:
                result.append({
                    "date": parts[0],
                    "main_net_inflow": sf(parts[1]),       # 主力净流入
                    "small_net_inflow": sf(parts[2]),      # 小单净流入
                    "medium_net_inflow": sf(parts[3]),     # 中单净流入
                    "large_net_inflow": sf(parts[4]),      # 大单净流入
                    "super_large_net_inflow": sf(parts[5]),# 超大单净流入
                })
        return result
    except Exception:
        return []


def fetch_holder_num(code):
    """股东户数变化"""
    mc = 1 if code.startswith("6") else 0
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "HOLD_NOTICE_DATE",
        "sortTypes": "-1",
        "pageSize": "20",
        "pageNumber": "1",
        "reportName": "RPT_HOLDERNUMLATEST",
        "columns": "ALL",
        "filter": f'(SECURITY_CODE="{code}")',
    }
    try:
        r = em_get(url, params=params, timeout=10)
        result = r.json().get("result", {})
        data = result.get("data", []) if result else []
        records = []
        for d in (data or []):
            records.append({
                "date": d.get("HOLD_NOTICE_DATE", ""),
                "holder_num": sf(d.get("HOLDER_NUM")),
                "holder_num_change": sf(d.get("HOLDER_NUM_CHANGE")),
                "holder_num_change_rate": sf(d.get("HOLDER_NUM_CHANGE_RATE")),
                "avg_amount": sf(d.get("AVG_MARKET_CAP")),
            })
        return records
    except Exception:
        return []


def fetch_dividend_history(code):
    """分红送转历史"""
    mc = 1 if code.startswith("6") else 0
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "pageSize": "20",
        "pageNumber": "1",
        "reportName": "RPT_SHAREBONUS_DET",
        "columns": "ALL",
        "filter": f'(SECURITY_CODE="{code}")',
    }
    try:
        r = em_get(url, params=params, timeout=10)
        result = r.json().get("result", {})
        data = result.get("data", []) if result else []
        records = []
        for d in (data or []):
            records.append({
                "report_date": d.get("REPORT_DATE", ""),
                "bonus_amount": sf(d.get("BONUS_AMOUNT")),
                "dividend_per_share": sf(d.get("PER_CASH_DIV")),
                "dividend_ratio": sf(d.get("DIVIDENT_BONUS_RATIO")),
                "transfer_ratio": sf(d.get("TRANSFER_RATIO")),
                "record_date": d.get("EX_DIVIDEND_DATE", ""),
            })
        return records
    except Exception:
        return []


# ══════════════════════════════════════════
#  §6 HALO 计算 + 财务指标衍生
# ══════════════════════════════════════════

# 行业分类映射（申万一级 → 资产类型）
HEAVY_ASSET_INDUSTRIES = [
    "钢铁", "煤炭", "石油石化", "建筑材料", "建筑装饰",
    "银行", "房地产", "公用事业", "交通运输", "有色金属",
    "基础化工", "采掘", "非银金融",
]
LIGHT_ASSET_INDUSTRIES = [
    "计算机", "传媒", "通信", "电子", "食品饮料",
    "白酒", "休闲服务", "商业贸易", "纺织服装", "综合",
    "软件", "互联网", "游戏", "影视",
]
# 其余为混合型

def classify_industry(industry_str):
    """行业 → 资产类型分类"""
    for h in HEAVY_ASSET_INDUSTRIES:
        if h in industry_str:
            return "heavy"
    for l in LIGHT_ASSET_INDUSTRIES:
        if l in industry_str:
            return "light"
    return "mixed"


def calculate_halo(balance, cashflow, income, industry="", employee_count=0):
    """
    计算 HALO 六维原始数据
    输入: 新浪资产负债表/现金流/利润表（最近期）+ 行业 + 员工人数
    输出: dict，包含六维计算所需数据和评分
    """
    if not balance or not cashflow:
        return {"error": "缺少财务数据"}

    b = balance[0]  # 最新期
    c = cashflow[0] if cashflow else {}
    i = income[0] if income else {}

    # 提取核心数据
    total_assets = sf(b.get("资产总计"))
    fixed_assets = sf(b.get("固定资产及清理合计", b.get("固定资产")))
    cip = sf(b.get("在建工程合计", b.get("在建工程")))
    inventory = sf(b.get("存货"))
    intangible = sf(b.get("无形资产"))
    total_liabilities = sf(b.get("负债合计"))

    # Capex: 购建固定资产、无形资产和其他长期资产所支付的现金
    capex_key = "购建固定资产、无形资产和其他长期资产所支付的现金"
    capex = sf(c.get(capex_key))

    # 经营现金流
    ocf = sf(c.get("经营活动产生的现金流量净额"))

    # 营收
    revenue = sf(i.get("营业收入", i.get("营业总收入")))

    # 有形资产 = 固定资产 + 在建工程 + 存货
    tangible = fixed_assets + cip + inventory

    asset_type = classify_industry(industry)

    # 六维计算
    halo = {
        "asset_type": asset_type,
        "industry": industry,
        "raw": {
            "total_assets": total_assets,
            "total_assets_yi": yi(total_assets),
            "fixed_assets": fixed_assets,
            "fixed_assets_yi": yi(fixed_assets),
            "cip": cip,
            "cip_yi": yi(cip),
            "inventory": inventory,
            "inventory_yi": yi(inventory),
            "intangible": intangible,
            "intangible_yi": yi(intangible),
            "tangible": tangible,
            "tangible_yi": yi(tangible),
            "total_liabilities": total_liabilities,
            "total_liabilities_yi": yi(total_liabilities),
            "capex": capex,
            "capex_yi": yi(capex),
            "ocf": ocf,
            "ocf_yi": yi(ocf),
            "revenue": revenue,
            "revenue_yi": yi(revenue),
        },
        "dimensions": {},
    }

    # 3.1 有形资产密集度
    ti = (tangible / total_assets * 100) if total_assets > 0 else 0
    halo["dimensions"]["tangible_intensity"] = {
        "value": round(ti, 2),
        "unit": "%",
        "desc": "有形资产/总资产",
        "formula": f"({yi(fixed_assets)}+{yi(cip)}+{yi(inventory)})/{yi(total_assets)}",
    }

    # 3.2 固定资产密集度
    fi = (fixed_assets / revenue * 100) if revenue > 0 else 0
    halo["dimensions"]["fixed_intensity"] = {
        "value": round(fi, 2),
        "unit": "%",
        "desc": "固定资产/营收",
    }

    # 3.3 固定资产份额
    fs = (fixed_assets / total_assets * 100) if total_assets > 0 else 0
    halo["dimensions"]["fixed_share"] = {
        "value": round(fs, 2),
        "unit": "%",
        "desc": "固定资产/总资产",
    }

    # 3.4 资本-劳动力比率
    if employee_count > 0:
        cle = tangible / employee_count / 1e4  # 万元/人
        halo["dimensions"]["capital_labor"] = {
            "value": round(cle, 0),
            "unit": "万元/人",
            "desc": "有形资产/员工数",
            "employee_count": employee_count,
        }
    else:
        halo["dimensions"]["capital_labor"] = {
            "value": None,
            "unit": "万元/人",
            "desc": "有形资产/员工数",
            "note": "需从F10获取员工人数",
        }

    # 3.5 Capex密集度
    ci = (capex / revenue * 100) if revenue > 0 else 0
    halo["dimensions"]["capex_intensity"] = {
        "value": round(ci, 2),
        "unit": "%",
        "desc": "Capex/营收",
    }

    # 3.6 Capex负担
    cb = (capex / ocf * 100) if ocf > 0 else 0
    halo["dimensions"]["capex_burden"] = {
        "value": round(cb, 2),
        "unit": "%",
        "desc": "Capex/经营现金流",
    }

    return halo


def calculate_financial_ratios(balance, income, cashflow):
    """计算衍生财务指标"""
    b = balance[0] if balance else {}
    i = income[0] if income else {}
    c = cashflow[0] if cashflow else {}

    total_assets = sf(b.get("资产总计"))
    total_liabilities = sf(b.get("负债合计"))
    current_assets = sf(b.get("流动资产合计"))
    current_liabilities = sf(b.get("流动负债合计"))
    inventory = sf(b.get("存货"))

    revenue = sf(i.get("营业收入"))
    net_profit = sf(i.get("净利润"))
    gross_profit = sf(i.get("营业利润", i.get("利润总额")))
    operating_cost = sf(i.get("营业成本"))

    ocf = sf(c.get("经营活动产生的现金流量净额"))

    ratios = {}

    # 盈利能力
    ratios["gross_margin"] = round((1 - operating_cost / revenue) * 100, 2) if revenue > 0 else 0
    ratios["net_margin"] = round(net_profit / revenue * 100, 2) if revenue > 0 else 0
    ratios["operating_margin"] = round(gross_profit / revenue * 100, 2) if revenue > 0 else 0

    # 偿债能力
    ratios["debt_ratio"] = round(total_liabilities / total_assets * 100, 2) if total_assets > 0 else 0
    ratios["current_ratio"] = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else 0
    quick_assets = current_assets - inventory
    ratios["quick_ratio"] = round(quick_assets / current_liabilities, 2) if current_liabilities > 0 else 0

    # 现金流质量
    ratios["cf_to_profit"] = round(ocf / net_profit, 2) if net_profit > 0 else 0

    # ROE/ROA（单期近似）
    net_equity = total_assets - total_liabilities
    ratios["roe"] = round(net_profit / net_equity * 100, 2) if net_equity > 0 else 0
    ratios["roa"] = round(net_profit / total_assets * 100, 2) if total_assets > 0 else 0

    return ratios


def _period_month(period_str):
    """提取报告期的月份: '2026-03-31' -> '03'"""
    if not period_str or len(period_str) < 7:
        return ""
    return period_str[5:7]


def calculate_growth(income):
    """
    计算成长性指标（需要多期数据）
    关键：同比要对比同类型报告期（Q1比Q1，年报比年报）
    """
    if len(income) < 2:
        return {"error": "需要至少2期数据"}

    latest = income[0]
    latest_month = _period_month(latest.get("period", ""))

    # 找到去年同期（同月份）
    prev_same_type = None
    for item in income[1:]:
        if _period_month(item.get("period", "")) == latest_month:
            prev_same_type = item
            break

    # 如果找不到去年同期，退回到上一期
    if prev_same_type is None:
        prev_same_type = income[1]

    rev_now = sf(latest.get("营业收入"))
    rev_prev = sf(prev_same_type.get("营业收入"))
    np_now = sf(latest.get("净利润"))
    np_prev = sf(prev_same_type.get("净利润"))

    growth = {
        "latest_period": latest.get("period", ""),
        "compare_period": prev_same_type.get("period", ""),
    }
    growth["revenue_yoy"] = round((rev_now / rev_prev - 1) * 100, 2) if rev_prev > 0 else 0
    growth["net_profit_yoy"] = round((np_now / np_prev - 1) * 100, 2) if np_prev > 0 else 0

    # 年度数据（12月报告期）
    annual_data = [item for item in income if _period_month(item.get("period", "")) == "12"]
    if len(annual_data) >= 2:
        a0 = annual_data[0]
        a1 = annual_data[1]
        growth["annual_revenue_yoy"] = round(
            (sf(a0.get("营业收入")) / sf(a1.get("营业收入")) - 1) * 100, 2
        ) if sf(a1.get("营业收入")) > 0 else 0
        growth["annual_profit_yoy"] = round(
            (sf(a0.get("净利润")) / sf(a1.get("净利润")) - 1) * 100, 2
        ) if sf(a1.get("净利润")) > 0 else 0

    # CAGR（如有3年以上年度数据）
    if len(annual_data) >= 4:
        rev_now_a = sf(annual_data[0].get("营业收入"))
        rev_3y_ago = sf(annual_data[3].get("营业收入"))
        if rev_3y_ago > 0:
            growth["revenue_cagr_3y"] = round((pow(rev_now_a / rev_3y_ago, 1/3) - 1) * 100, 2)
        np_3y_ago = sf(annual_data[3].get("净利润"))
        if np_3y_ago > 0:
            growth["net_profit_cagr_3y"] = round((pow(sf(annual_data[0].get("净利润")) / np_3y_ago, 1/3) - 1) * 100, 2)

    return growth


# ══════════════════════════════════════════
#  §7 主流程
# ══════════════════════════════════════════
def fetch_all(code):
    """
    拉取一只股票的全部数据
    返回完整 dict
    """
    print(f"\n{'='*60}")
    print(f"  HALO V5.0 数据获取 — {code}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    result = {
        "meta": {
            "stock_code": code,
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_sources": ["tencent", "eastmoney", "sina"],
            "version": "HALO V5.0",
        }
    }

    # 1. 腾讯行情
    print("\n  [1/7] 实时行情（腾讯）...")
    try:
        quote = fetch_tencent_quote(code)
        result["market"] = quote
        result["meta"]["stock_name"] = quote.get("name", "")
        print(f"    ✅ {quote.get('name','?')} {quote.get('price',0)}元")
    except Exception as e:
        print(f"    ❌ {e}")
        result["market"] = {}

    # 2. 东财公司信息
    print("  [2/8] 公司信息（东财）...")
    try:
        info = fetch_eastmoney_info(code)
        result["company"] = info
        print(f"    ✅ 行业={info.get('industry','?')} 市值={yi(info.get('mcap'))}亿")
    except Exception as e:
        print(f"    ❌ {e}")
        result["company"] = {}

    # 2.5 F10详细数据（员工人数等）
    print("  [2.5/8] F10详情（东财）...")
    try:
        f10 = fetch_f10_detail(code)
        result["f10"] = f10
        emp = f10.get("employee_count", 0)
        print(f"    ✅ 员工{int(emp)}人 董事长={f10.get('chairman','?')} 行业={f10.get('industry_csrc','?')}")
    except Exception as e:
        print(f"    ❌ {e}")
        result["f10"] = {}

    # 3. 概念板块
    print("  [3/8] 所属板块（东财）...")
    try:
        blocks = fetch_concept_blocks(code)
        result["concepts"] = blocks
        print(f"    ✅ 归属 {len(blocks)} 个板块/概念")
    except Exception as e:
        print(f"    ❌ {e}")
        result["concepts"] = []

    # 4-6. 新浪财报三表
    income, balance, cashflow = fetch_all_financial_statements(code)
    result["financial"] = {
        "income": income,
        "balance": balance,
        "cashflow": cashflow,
    }
    print(f"    ✅ 三表获取完成 (各{len(income)}期)")

    # 7. 资金流向
    print("  [7/7] 资金流向（东财）...")
    try:
        fund_flow = fetch_fund_flow(code, days=30)
        result["fund_flow"] = fund_flow
        # 汇总近5日
        recent5 = fund_flow[-5:] if len(fund_flow) >= 5 else fund_flow
        main_total = sum(sf(f.get("main_net_inflow")) for f in recent5)
        result["fund_flow_summary"] = {
            "days": len(fund_flow),
            "recent_5d_main_net": wan(main_total),
            "recent_5d_main_unit": "万元",
        }
        print(f"    ✅ {len(fund_flow)}日资金流 近5日主力={wan(main_total)}万")
    except Exception as e:
        print(f"    ❌ {e}")
        result["fund_flow"] = []
        result["fund_flow_summary"] = {}

    # ── 衍生计算 ──
    print("\n  📊 衍生计算...")

    industry = result.get("company", {}).get("industry", "")
    employee_count = int(result.get("f10", {}).get("employee_count", 0))

    # HALO 六维
    halo = calculate_halo(balance, cashflow, income, industry, employee_count)
    result["halo"] = halo
    print(f"    HALO: 行业分类={halo.get('asset_type','?')}")
    for dim_name, dim_data in halo.get("dimensions", {}).items():
        print(f"      {dim_name}: {dim_data.get('value', 'N/A')}{dim_data.get('unit','')}")

    # 财务指标
    ratios = calculate_financial_ratios(balance, income, cashflow)
    result["ratios"] = ratios
    print(f"    财务指标: ROE={ratios.get('roe')}% ROA={ratios.get('roa')}% 负债率={ratios.get('debt_ratio')}%")

    # 成长性
    growth = calculate_growth(income)
    result["growth"] = growth
    print(f"    成长性: 营收同比={growth.get('revenue_yoy', 'N/A')}% 净利同比={growth.get('net_profit_yoy', 'N/A')}%")

    # 数据质量摘要
    result["meta"]["data_quality"] = {
        "has_market_data": bool(result.get("market")),
        "has_company_info": bool(result.get("company")),
        "income_periods": len(income),
        "balance_periods": len(balance),
        "cashflow_periods": len(cashflow),
        "fund_flow_days": len(result.get("fund_flow", [])),
        "latest_period": income[0].get("period", "") if income else "",
    }

    # 保存 JSON
    output_file = os.path.join(OUTPUT_DIR, f"{code}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  ✅ 完成! 保存到 {output_file}")
    print(f"  📊 文件大小: {os.path.getsize(output_file)/1024:.1f} KB")
    print(f"  📅 最新报告期: {result['meta']['data_quality']['latest_period']}")
    print(f"{'='*60}\n")

    # ── Harness 数据层校验 ──
    print("\n  🔍 运行数据层 harness 校验...")
    try:
        harness_result = validate_data(code)
        if not harness_result["ok"]:
            print(f"  ⚠️ 数据层 harness 未通过，请查看 data/{code}_harness.json")
            sys.exit(1)
        print("  ✅ 数据层 harness 通过")
    except Exception as e:
        print(f"  ⚠️ harness 运行失败: {e}")

    return result


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python fetch_stock_data.py <股票代码>")
        print("示例: python fetch_stock_data.py 600519")
        sys.exit(1)

    code = sys.argv[1]
    if not re.match(r'^\d{6}$', code):
        print("错误: 股票代码必须是6位数字")
        sys.exit(1)

    fetch_all(code)

