#!/usr/bin/env python3
"""HALO V5.0 数据测试 — 拉取 600519 贵州茅台的核心数据"""

import sys, json, time, random, socket, urllib.request, requests
from mootdx.quotes import Quotes

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ── TDX Client ──
_TDX_SERVERS = [
    ('119.97.185.59', 7709), ('124.70.133.119', 7709), ('116.205.183.150', 7709),
    ('123.60.73.44', 7709), ('116.205.163.254', 7709), ('121.36.225.169', 7709),
]

def _probe(ip, port, timeout=2.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def tdx_client(market='std'):
    for ip, port in _TDX_SERVERS:
        if _probe(ip, port):
            return Quotes.factory(market=market, server=(ip, port))
    try:
        return Quotes.factory(market=market, bestip=True)
    except Exception:
        pass
    try:
        return Quotes.factory(market=market)
    except Exception as e:
        raise RuntimeError(f"All TDX servers unreachable: {e}")

# ── Eastmoney throttle ──
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = 1.0
_em_last_call = [0.0]

def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()

# ── §1.2 Tencent Quote ──
def tencent_quote(codes):
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1], "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result

# ── §6.3 Eastmoney Stock Info ──
def eastmoney_stock_info(code):
    market_code = 1 if code.startswith("6") else 0
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
        "secid": f"{market_code}.{code}",
    }
    r = em_get(url, params=params, headers={"User-Agent": UA}, timeout=10)
    d = r.json().get("data", {})
    return {
        "code": d.get("f57", ""), "name": d.get("f58", ""),
        "industry": d.get("f127", ""),
        "total_shares": d.get("f84", 0), "float_shares": d.get("f85", 0),
        "mcap": d.get("f116", 0), "float_mcap": d.get("f117", 0),
        "list_date": str(d.get("f189", "")), "price": d.get("f43", 0),
    }

# ── §6.4 Sina Financial Report ──
def sina_financial_report(code, report_type="lrb", num=8):
    prefix = "sh" if code.startswith("6") else "sz"
    paper_code = f"{prefix}{code}"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": paper_code, "source": report_type,
        "type": "0", "page": "1", "num": str(num),
    }
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
    report_list = r.json().get("result", {}).get("data", {}).get("report_list", {}) or {}
    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
            tongbi = it.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_同比"] = tongbi
        rows.append(rec)
    return rows


# ══════════════════════════════════════════
#  主测试流程
# ══════════════════════════════════════════
CODE = sys.argv[1] if len(sys.argv) > 1 else "600519"
print(f"{'='*60}")
print(f"  HALO V5.0 数据测试 — {CODE}")
print(f"{'='*60}\n")

result = {"meta": {"stock_code": CODE, "test_time": time.strftime("%Y-%m-%d %H:%M:%S")}}

# 1) Tencent Quote
print("【1】实时行情（腾讯）...")
try:
    quotes = tencent_quote([CODE])
    q = quotes.get(CODE, {})
    result["market_data"] = q
    print(f"  ✅ {q.get('name','?')}({CODE}): {q.get('price',0)}元")
    print(f"     PE(TTM)={q.get('pe_ttm',0)} PB={q.get('pb',0)} 市值={q.get('mcap_yi',0)}亿")
    print(f"     涨跌幅={q.get('change_pct',0)}% 换手={q.get('turnover_pct',0)}%")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 2) mootdx Finance
print("\n【2】财务快照（通达信）...")
try:
    client = tdx_client()
    fin = client.finance(symbol=CODE)
    if fin:
        result["finance_snapshot"] = {k: v for k, v in fin.items() if v is not None}
        print(f"  ✅ EPS={fin.get('eps')} ROE={fin.get('roe')}%")
        print(f"     净利={fin.get('profit')} 营收={fin.get('income')}")
        print(f"     总股本={fin.get('zongguben')} 流通股={fin.get('liutongguben')}")
        print(f"     每股净资产={fin.get('bvps')}")
        # Show all available fields
        print(f"     [共 {len([v for v in fin.values() if v is not None])} 个有效字段]")
    else:
        print("  ❌ 返回空")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 3) Eastmoney Info
print("\n【3】公司基本信息（东财）...")
try:
    info = eastmoney_stock_info(CODE)
    result["company_info"] = info
    print(f"  ✅ {info['name']}({info['code']})")
    print(f"     行业={info['industry']} 市值={info['mcap']/1e8:.0f}亿")
    print(f"     总股本={info['total_shares']} 流通股={info['float_shares']}")
    print(f"     上市日期={info['list_date']}")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 4) Sina Financial Reports (3 tables)
print("\n【4】利润表（新浪）...")
try:
    lrb = sina_financial_report(CODE, "lrb", num=4)
    result["income_statement"] = lrb
    if lrb:
        print(f"  ✅ 获取 {len(lrb)} 期数据")
        latest = lrb[0]
        print(f"     最新期: {latest.get('报告期','?')}")
        print(f"     营业收入: {latest.get('营业收入', 'N/A')}")
        print(f"     净利润: {latest.get('净利润', 'N/A')}")
        print(f"     每股收益: {latest.get('基本每股收益', latest.get('每股收益', 'N/A'))}")
        # Show some key fields
        key_fields = [k for k in latest.keys() if k not in ('报告期',) and not k.endswith('_同比')][:10]
        print(f"     [关键字段]: {', '.join(key_fields)}")
    else:
        print("  ❌ 返回空")
except Exception as e:
    print(f"  ❌ 失败: {e}")

print("\n【5】资产负债表（新浪）...")
try:
    fzb = sina_financial_report(CODE, "fzb", num=4)
    result["balance_sheet"] = fzb
    if fzb:
        print(f"  ✅ 获取 {len(fzb)} 期数据")
        latest = fzb[0]
        print(f"     最新期: {latest.get('报告期','?')}")
        key_items = ['资产总计', '负债合计', '所有者权益合计', '货币资金',
                     '固定资产', '存货', '应收账款', '流动资产合计']
        for item in key_items:
            val = latest.get(item, 'N/A')
            print(f"     {item}: {val}")
    else:
        print("  ❌ 返回空")
except Exception as e:
    print(f"  ❌ 失败: {e}")

print("\n【6】现金流量表（新浪）...")
try:
    llb = sina_financial_report(CODE, "llb", num=4)
    result["cashflow_statement"] = llb
    if llb:
        print(f"  ✅ 获取 {len(llb)} 期数据")
        latest = llb[0]
        print(f"     最新期: {latest.get('报告期','?')}")
        key_items = ['经营活动产生的现金流量净额', '投资活动产生的现金流量净额',
                     '筹资活动产生的现金流量净额', '购建固定资产、无形资产和其他长期资产支付的现金']
        for item in key_items:
            val = latest.get(item, 'N/A')
            print(f"     {item}: {val}")
    else:
        print("  ❌ 返回空")
except Exception as e:
    print(f"  ❌ 失败: {e}")

# 5) Save to JSON
output_file = f"data/{CODE}_test.json"
import os
os.makedirs("data", exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)

print(f"\n{'='*60}")
print(f"  ✅ 数据已保存到 {output_file}")
print(f"  📊 JSON 大小: {os.path.getsize(output_file)/1024:.1f} KB")
print(f"{'='*60}")
