#!/usr/bin/env python3
"""
HALO V5.0 定性数据获取脚本
通过搜索引擎抓取舆情/ESG/研报/管理层等定性信息
输出: data/{stock_code}_qualitative.json

数据源:
  - 东财个股新闻 (search-api-web)
  - 东财研报 (reportapi)
  - 新浪财经新闻
  - 百度搜索 (ESG/管理层/舆情)
"""

import sys, json, os, time, random, re
import urllib.request, urllib.parse
import requests
from datetime import datetime

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
#  §1 东财个股新闻
# ══════════════════════════════════════════
def fetch_eastmoney_news(code, num=20):
    """个股近30日新闻"""
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    params = {
        "cb": "jQuery_callback",
        "param": json.dumps({
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": num,
                    "preTag": "",
                    "postTag": "",
                }
            }
        })
    }
    try:
        r = em_get(url, params=params, timeout=15)
        text = r.text
        # Parse JSONP
        json_str = text[text.index("(") + 1:text.rindex(")")]
        data = json.loads(json_str)
        articles_raw = data.get("result", {}).get("cmsArticleWebOld", [])
        # cmsArticleWebOld is directly a list (not a dict with "list" key)
        articles = articles_raw if isinstance(articles_raw, list) else articles_raw.get("list", [])
        result = []
        for a in articles[:num]:
            result.append({
                "title": a.get("title", "").replace("<em>", "").replace("</em>", ""),
                "date": a.get("date", ""),
                "source": a.get("mediaName", ""),
                "url": a.get("url", ""),
                "summary": a.get("content", "")[:200],
            })
        return result
    except Exception as e:
        print(f"    ⚠️ 东财新闻异常: {e}")
        return []


# ══════════════════════════════════════════
#  §2 东财研报
# ══════════════════════════════════════════
def fetch_eastmoney_reports(code, num=10):
    """个股研报（评级+目标价+核心观点）"""
    url = "https://reportapi.eastmoney.com/report/list"
    params = {
        "industryCode": "*", "pageSize": num,
        "industry": "*", "rating": "*", "ratingChange": "*",
        "beginTime": "", "endTime": "",
        "pageNo": 1, "fields": "",
        "qType": 0, "orgCode": "",
        "rcode": "", "code": code,
    }
    try:
        r = em_get(url, params=params, timeout=15)
        data = r.json()
        reports = data.get("data", [])
        result = []
        for rpt in (reports or [])[:num]:
            # researcher is a string (name), not a dict
            researcher = rpt.get("researcher", "")
            author = researcher if isinstance(researcher, str) else ""
            result.append({
                "date": rpt.get("publishDate", "")[:10],
                "broker": rpt.get("orgName", ""),
                "title": rpt.get("title", ""),
                "rating": rpt.get("emRatingName", ""),
                "target_price": rpt.get("predictPrice", None),
                "author": author,
                "eps_this_year": rpt.get("predictThisYearEps"),
                "eps_next_year": rpt.get("predictNextYearEps"),
            })
        return result
    except Exception as e:
        print(f"    ⚠️ 东财研报异常: {e}")
        return []


# ══════════════════════════════════════════
#  §3 替代搜索: 用新浪财经 + 巨潮公告代替百度
# ══════════════════════════════════════════
def fetch_sina_news(code, num=10):
    """新浪财经个股新闻"""
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php"
    params = {"symbol": f"{prefix}{code}", "Page": 1, "num": num}
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
        # Extract news titles from HTML
        titles = re.findall(r'href=[\'"](.*?)[\'"]\s*(?:target=.*?)?>(.*?)</a>', r.text, re.S)
        result = []
        seen = set()
        for link, title in titles:
            title = re.sub(r'<[^>]+>', '', title).strip()
            if title and len(title) > 5 and title not in seen and 'news' in link.lower() or 'finance' in link.lower():
                seen.add(title)
                result.append({"title": title, "url": link, "source": "sina"})
            if len(result) >= num:
                break
        return result
    except Exception as e:
        print(f"    ⚠️ 新浪新闻异常: {e}")
        return []


def fetch_cninfo_announcements(code, num=10):
    """巨潮公告检索"""
    prefix = "0" if code.startswith("6") else "1"
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    data_post = {
        "stock": f"{code}",
        "tabName": "fulltext",
        "pageSize": num,
        "pageNum": 1,
        "column": "szse" if prefix == "1" else "sse",
        "category": "",
        "plate": "",
        "seDate": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    try:
        r = requests.post(url, data=data_post, headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
        }, timeout=15)
        items = r.json().get("announcements", [])
        result = []
        for item in (items or [])[:num]:
            result.append({
                "title": item.get("announcementTitle", "").replace("<em>", "").replace("</em>", ""),
                "date": item.get("announcementTime", ""),
                "type": item.get("adjunctUrl", ""),
            })
        return result
    except Exception as e:
        print(f"    ⚠️ 巨潮公告异常: {e}")
        return []


def fetch_qualitative_data(stock_name, code):
    """获取全部定性数据"""
    result = {}

    # 1. 东财新闻
    print("  [1/5] 个股新闻（东财）...")
    news = fetch_eastmoney_news(code, num=20)
    result["news"] = news
    print(f"    ✅ {len(news)} 条新闻")

    # 2. 东财研报
    print("  [2/5] 研报评级（东财）...")
    reports = fetch_eastmoney_reports(code, num=15)
    result["reports"] = reports
    # 统计评级分布
    if reports:
        ratings = {}
        for r in reports:
            rt = r.get("rating", "未知")
            ratings[rt] = ratings.get(rt, 0) + 1
        result["reports_summary"] = {
            "total": len(reports),
            "ratings": ratings,
            "latest": reports[0] if reports else None,
        }
    print(f"    ✅ {len(reports)} 篇研报")

    # 3. 巨潮公告（代替百度ESG搜索）
    print("  [3/5] 公司公告（巨潮）...")
    announcements = fetch_cninfo_announcements(code, num=15)
    result["announcements"] = announcements
    print(f"    ✅ {len(announcements)} 条公告")

    # 4. 新浪新闻（补充新闻源）
    print("  [4/5] 新浪财经新闻...")
    sina_news = fetch_sina_news(code, num=10)
    result["sina_news"] = sina_news
    print(f"    ✅ {len(sina_news)} 条新闻")

    # 5. 以下维度由 AI 在报告生成时通过 MCP 搜索工具补充
    result["ai_fill_later"] = {
        "esg": "AI通过搜索工具获取ESG报告、环保处罚、社会责任信息",
        "management": "AI通过搜索获取管理层变动、战略、激励信息",
        "sentiment_risk": "AI通过搜索获取舆情风险、诉讼、处罚信息",
        "note": "这些定性维度在报告生成阶段由AI实时搜索填充",
    }

    return result


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python fetch_qualitative.py <股票代码> <股票名称>")
        print("示例: python fetch_qualitative.py 600519 贵州茅台")
        sys.exit(1)

    code = sys.argv[1]
    name = sys.argv[2]

    print(f"\n{'='*60}")
    print(f"  HALO V5.0 定性数据获取 — {name}({code})")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    data = fetch_qualitative_data(name, code)

    # 添加元信息
    output = {
        "meta": {
            "stock_code": code,
            "stock_name": name,
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "qualitative",
        },
        **data,
    }

    # 保存
    output_file = os.path.join(OUTPUT_DIR, f"{code}_qualitative.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"  ✅ 保存到 {output_file}")
    print(f"  📊 文件大小: {os.path.getsize(output_file)/1024:.1f} KB")
    print(f"  📰 新闻: {len(data.get('news', []))} 条")
    print(f"  📄 研报: {len(data.get('reports', []))} 篇")
    print(f"  🌍 ESG: {len(data.get('esg', []))} 条")
    print(f"  👔 管理层: {len(data.get('management', []))} 条")
    print(f"  ⚠️ 舆情: {len(data.get('sentiment_risk', []))} 条")
    print(f"{'='*60}\n")
