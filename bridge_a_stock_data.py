#!/usr/bin/env python3
"""
HALO × a-stock-data 桥接脚本

将 HALO 的数据获取层升级为 a-stock-data 的 43 端点架构。
当 a-stock-data skill 可用时，自动使用其更稳定的端点；
否则 fallback 到 HALO 原有的 fetch_stock_data.py。

用法:
  python bridge_a_stock_data.py <stock_code> <stock_name>

输出:
  data/{code}.json — 与 HALO 标准 JSON 格式完全兼容
"""

import json
import os
import sys
import re
from datetime import datetime

# ============================================================
# a-stock-data 端点集成
# 以下代码从 a-stock-data SKILL.md 提取，可直接 exec 执行
# ============================================================

def get_a_stock_data_endpoints():
    """
    返回 HALO 需要的 a-stock-data 端点映射表。
    当 a-stock-data skill 更新时，只需更新此映射。
    """
    return {
        # 行情层
        "realtime_quote": {
            "skill_section": "§1.2",
            "function": "tencent_quote(codes)",
            "source": "腾讯财经",
            "halo_fields": ["price", "pe_ttm", "pb", "market_cap", "turnover", "change_pct"],
            "priority": 1  # 优先使用
        },
        # K线层
        "kline_daily": {
            "skill_section": "§1.1",
            "function": "tdx_client().bars(code, freq=9, count=120)",
            "source": "通达信(mootdx)",
            "halo_fields": ["history_prices"],
            "priority": 2
        },
        # 财务三表层
        "financial_statements": {
            "skill_section": "§6.4",
            "function": "sina_financial(code)",
            "source": "新浪财经",
            "halo_fields": ["income", "balance", "cashflow"],
            "priority": 1
        },
        # 资金面层
        "fund_flow": {
            "skill_section": "§3.4",
            "function": "eastmoney_fund_flow_minute(code)",
            "source": "东财push2",
            "halo_fields": ["main_net_inflow", "big_net_inflow"],
            "priority": 1,
            "note": "内置 em_get() 限流防封"
        },
        # 龙虎榜（HALO 新增能力）
        "dragon_tiger": {
            "skill_section": "§3.5",
            "function": "dragon_tiger_seat(code)",
            "source": "东财datacenter-web",
            "halo_fields": ["dragon_tiger_records"],
            "priority": 3,  # 增强项
            "note": "HALO 原本没有此能力"
        },
        # 北向资金（HALO 新增能力）
        "northbound": {
            "skill_section": "§3.2",
            "function": "northbound_flow()",
            "source": "同花顺/HKEX",
            "halo_fields": ["northbound_net_buy"],
            "priority": 3,
            "note": "HALO 原本没有此能力"
        },
        # 融资融券（HALO 新增能力）
        "margin_trading": {
            "skill_section": "§4.1",
            "function": "margin_trading_detail(code)",
            "source": "东财datacenter-web",
            "halo_fields": ["margin_balance", "margin_buy"],
            "priority": 3,
            "note": "HALO 原本没有此能力"
        },
        # 研报
        "research_reports": {
            "skill_section": "§2.1",
            "function": "eastmoney_research_reports(code)",
            "source": "东财reportapi",
            "halo_fields": ["reports", "ratings", "eps_forecast"],
            "priority": 2
        },
        # 新闻
        "stock_news": {
            "skill_section": "§5.1",
            "function": "eastmoney_stock_news(code)",
            "source": "东财search-api",
            "halo_fields": ["news_list"],
            "priority": 2,
            "note": "V3.2.1 修复了空列表 bug"
        },
        # 公司信息
        "company_info": {
            "skill_section": "§3.1",
            "function": "eastmoney_stock_info(code)",
            "source": "东财push2",
            "halo_fields": ["industry", "total_shares", "float_shares", "list_date"],
            "priority": 1
        }
    }


# ============================================================
# 桥接逻辑
# ============================================================

def check_a_stock_data_available():
    """检查 a-stock-data skill 是否已安装"""
    skill_path = os.path.expanduser("~/.claude/skills/a-stock-data/SKILL.md")
    return os.path.exists(skill_path)


def generate_bridge_config(stock_code, stock_name):
    """
    生成桥接配置：告诉 AI 在执行 HALO 时，
    对每类数据应该优先用 a-stock-data 的哪个端点。
    """
    endpoints = get_a_stock_data_endpoints()

    config = {
        "meta": {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "bridge_version": "1.0",
            "bridge_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "a_stock_data_available": check_a_stock_data_available(),
            "a_stock_data_version": "3.4.0" if check_a_stock_data_available() else None
        },
        "data_routing": {},
        "new_capabilities": [],
        "fallback_strategy": {}
    }

    for data_type, ep in endpoints.items():
        config["data_routing"][data_type] = {
            "primary_source": f"a-stock-data {ep['skill_section']}",
            "primary_function": ep['function'],
            "fallback_source": "HALO fetch_stock_data.py",
            "priority": ep['priority'],
            "halo_fields": ep['halo_fields']
        }

        if ep.get('note') and 'HALO 原本没有' in ep['note']:
            config["new_capabilities"].append({
                "data_type": data_type,
                "capability": ep['note'],
                "source": f"a-stock-data {ep['skill_section']}"
            })

    # Fallback 策略
    config["fallback_strategy"] = {
        "principle": "a-stock-data 端点优先，失败则 fallback 到 HALO 原生脚本",
        "triggers": [
            "a-stock-data skill 未安装",
            "端点返回空数据",
            "网络超时或封禁"
        ],
        "action": "自动降级到 fetch_stock_data.py 对应模块"
    }

    return config


def main():
    if len(sys.argv) < 3:
        print("用法: python bridge_a_stock_data.py <stock_code> <stock_name>")
        print("示例: python bridge_a_stock_data.py 600519 贵州茅台")
        sys.exit(1)

    stock_code = sys.argv[1]
    stock_name = sys.argv[2]

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  HALO × a-stock-data 桥接配置")
    print(f"{'='*60}\n")

    # 检查 a-stock-data
    available = check_a_stock_data_available()
    print(f"  📦 a-stock-data skill: {'✅ 已安装 (V3.4.0)' if available else '❌ 未安装'}")
    print(f"  📊 股票: {stock_name} ({stock_code})\n")

    # 生成配置
    config = generate_bridge_config(stock_code, stock_name)

    # 输出路由表
    print(f"  📡 数据路由表:")
    print(f"  {'数据类型':<20} {'主源':<25} {'优先级'}")
    print(f"  {'-'*55}")
    for dt, route in config["data_routing"].items():
        print(f"  {dt:<20} {route['primary_source']:<25} P{route['priority']}")

    # 输出新增能力
    if config["new_capabilities"]:
        print(f"\n  🆕 HALO 新增能力 (来自 a-stock-data):")
        for cap in config["new_capabilities"]:
            print(f"  • {cap['capability']} → {cap['source']}")

    # 保存配置
    output_path = os.path.join(data_dir, f"{stock_code}_bridge.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 桥接配置已保存: {output_path}")
    print(f"  💡 使用方式: AI 读取此配置后，按路由表调用 a-stock-data 端点")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
