#!/usr/bin/env python3
"""
Serenity 产业链数据自动生成脚本

基于 HALO JSON 数据（行业/财务/业务信息），通过规则引擎生成产业链分析数据。
这是启发式分析——不如人工/Serenity skill深度，但提供基础框架。

输入: data/{code}.json（HALO 主数据）
输出: data/{code}_serenity.json（Serenity 产业链数据）

用法: python generate_serenity.py <stock_code>
"""

import json
import os
import sys
from datetime import datetime

# ══════════════════════════════════════════
#  行业 → 产业链映射表
# ══════════════════════════════════════════

# 行业关键词 → 产业链信息
INDUSTRY_CHAIN_MAP = {
    # 半导体显示
    "面板": {
        "chain": "半导体显示 - LCD/OLED面板制造",
        "layer": "中游面板制造层",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["TCL华星", "京东方", "面板", "LCD", "OLED", "显示"]
    },
    "显示": {
        "chain": "半导体显示 - LCD/OLED面板制造",
        "layer": "中游面板制造层",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["TCL华星", "京东方", "面板", "显示"]
    },
    # 半导体
    "半导体": {
        "chain": "半导体 - 芯片设计/制造/封测",
        "layer": "根据细分领域而定",
        "scarcity": "高",
        "scarcity_score": 7.5,
        "keywords": ["晶圆", "芯片", "封测", "设计", "制造"]
    },
    "芯片": {
        "chain": "半导体 - 芯片设计/制造/封测",
        "layer": "根据细分领域而定",
        "scarcity": "高",
        "scarcity_score": 7.5,
        "keywords": ["晶圆", "芯片", "封测"]
    },
    # 光伏
    "光伏": {
        "chain": "新能源 - 光伏产业链",
        "layer": "根据细分环节而定（硅料/硅片/电池/组件）",
        "scarcity": "低",
        "scarcity_score": 4.0,
        "keywords": ["硅片", "电池", "组件", "硅料", "光伏"]
    },
    # 白酒
    "白酒": {
        "chain": "消费品 - 高端白酒",
        "layer": "品牌制造层（产业链核心利润环节）",
        "scarcity": "极高",
        "scarcity_score": 8.5,
        "keywords": ["茅台", "五粮液", "白酒", "品牌"]
    },
    "酒": {
        "chain": "消费品 - 酒类",
        "layer": "品牌制造层",
        "scarcity": "高",
        "scarcity_score": 7.0,
        "keywords": ["白酒", "啤酒", "红酒"]
    },
    # 医药
    "医药": {
        "chain": "医药健康 - 制药/医疗器械",
        "layer": "根据细分领域（创新药/仿制药/器械/ CXO）",
        "scarcity": "中高",
        "scarcity_score": 6.5,
        "keywords": ["创新药", "仿制药", "器械", "CXO"]
    },
    "制药": {
        "chain": "医药健康 - 制药",
        "layer": "药品研发/生产层",
        "scarcity": "中高",
        "scarcity_score": 6.5,
        "keywords": ["创新药", "仿制药"]
    },
    # 新能源/电池
    "电池": {
        "chain": "新能源 - 动力电池/储能",
        "layer": "电芯制造层（产业链核心）",
        "scarcity": "中高",
        "scarcity_score": 6.5,
        "keywords": ["宁德时代", "比亚迪", "电池", "锂电"]
    },
    "新能源": {
        "chain": "新能源 - 综合",
        "layer": "根据细分领域",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["光伏", "风电", "储能", "电池"]
    },
    # 汽车
    "汽车": {
        "chain": "汽车 - 整车制造",
        "layer": "整车集成层",
        "scarcity": "中等",
        "scarcity_score": 5.0,
        "keywords": ["整车", "零部件", "新能源车企"]
    },
    # 家电
    "家电": {
        "chain": "消费品 - 家电制造",
        "layer": "品牌制造层",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["美的", "格力", "海尔", "家电"]
    },
    # 钢铁/有色
    "钢铁": {
        "chain": "大宗商品 - 钢铁",
        "layer": "冶炼制造层（大宗商品周期型）",
        "scarcity": "低",
        "scarcity_score": 3.5,
        "keywords": ["钢铁", "螺纹钢", "热卷"]
    },
    "有色": {
        "chain": "大宗商品 - 有色金属",
        "layer": "冶炼/加工层",
        "scarcity": "低-中",
        "scarcity_score": 4.0,
        "keywords": ["铜", "铝", "锂", "钴"]
    },
    # 煤炭/能源
    "煤炭": {
        "chain": "能源 - 煤炭开采",
        "layer": "资源开采层（资源禀赋决定）",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["煤炭", "动力煤", "焦煤"]
    },
    # 银行/金融
    "银行": {
        "chain": "金融 - 银行业",
        "layer": "金融中介层（牌照壁垒）",
        "scarcity": "高（牌照）",
        "scarcity_score": 7.0,
        "keywords": ["银行", "存贷", "金融"]
    },
    # 互联网/软件
    "互联网": {
        "chain": "科技 - 互联网平台",
        "layer": "平台运营层（网络效应）",
        "scarcity": "极高（头部）",
        "scarcity_score": 8.5,
        "keywords": ["腾讯", "阿里", "平台", "互联网"]
    },
    "软件": {
        "chain": "科技 - 软件服务",
        "layer": "软件开发层",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["SaaS", "软件", "云服务"]
    },
    # 通信/光纤
    "通信": {
        "chain": "通信 - 通信设备/光纤光缆",
        "layer": "设备制造层",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["华为", "中兴", "光纤", "光缆"]
    },
    "光纤": {
        "chain": "通信 - 光纤光缆",
        "layer": "光纤预制棒/拉丝/成缆",
        "scarcity": "中等",
        "scarcity_score": 5.5,
        "keywords": ["光纤", "光缆", "预制棒"]
    },
    # 默认
    "default": {
        "chain": "待确定",
        "layer": "待确定",
        "scarcity": "待评估",
        "scarcity_score": 5.0,
        "keywords": []
    }
}


def match_industry(industry_str, company_name="", business_scope=""):
    """根据行业字符串匹配产业链信息"""
    industry_lower = industry_str.lower()
    name_lower = company_name.lower()
    scope_lower = business_scope.lower()
    search_text = f"{industry_lower} {name_lower} {scope_lower}"

    # 先按公司名称匹配
    for key, info in INDUSTRY_CHAIN_MAP.items():
        if key == "default":
            continue
        for kw in info.get("keywords", []):
            if kw.lower() in name_lower:
                return key, info

    # 再按行业+经营范围匹配
    for key, info in INDUSTRY_CHAIN_MAP.items():
        if key == "default":
            continue
        if key in industry_lower:
            return key, info
        for kw in info.get("keywords", []):
            if kw.lower() in search_text:
                return key, info

    return "default", INDUSTRY_CHAIN_MAP["default"]


def compute_halo_total(halo_data):
    """从 HALO 维度值计算总分（简化版）"""
    dims = halo_data.get("halo", {}).get("dimensions", {})
    asset_type = halo_data.get("halo", {}).get("asset_type", "mixed")

    scores = {}

    # 3.1 有形资产密集度
    ti = dims.get("tangible_intensity", {}).get("value", 0)
    if asset_type == "heavy":
        scores["3_1"] = 5 if ti >= 80 else 4 if ti >= 60 else 3 if ti >= 40 else 2 if ti >= 20 else 1
    elif asset_type == "light":
        scores["3_1"] = 5 if ti >= 60 else 4 if ti >= 40 else 3 if ti >= 20 else 2 if ti >= 10 else 1
    else:  # mixed
        scores["3_1"] = 5 if ti >= 70 else 4 if ti >= 50 else 3 if ti >= 30 else 2 if ti >= 15 else 1

    # 3.2 固定资产密集度
    fi = dims.get("fixed_intensity", {}).get("value", 0)
    if asset_type == "heavy":
        scores["3_2"] = 5 if fi >= 100 else 4 if fi >= 80 else 3 if fi >= 60 else 2
    elif asset_type == "light":
        scores["3_2"] = 5 if fi >= 30 else 4 if fi >= 15 else 3 if fi >= 5 else 2
    else:
        scores["3_2"] = 5 if fi >= 60 else 4 if fi >= 40 else 3 if fi >= 20 else 2

    # 3.3 固定资产份额
    fs = dims.get("fixed_share", {}).get("value", 0)
    scores["3_3"] = 5 if fs >= 25 else 4 if fs >= 15 else 3 if fs >= 8 else 2 if fs >= 4 else 1

    # 3.4 资本-劳动力比率
    cl = dims.get("capital_labor", {}).get("value", 0)
    scores["3_4"] = 5 if cl >= 200 else 4 if cl >= 100 else 3 if cl >= 50 else 2 if cl >= 20 else 1

    # 3.5 Capex密集度
    ci = dims.get("capex_intensity", {}).get("value", 0)
    if asset_type == "heavy":
        scores["3_5"] = 5 if ci >= 15 else 4 if ci >= 10 else 3 if ci >= 5 else 2
    elif asset_type == "light":
        scores["3_5"] = 5 if ci >= 5 else 4 if ci >= 2 else 3 if ci >= 0.5 else 2
    else:
        scores["3_5"] = 5 if ci >= 10 else 4 if ci >= 5 else 3 if ci >= 2 else 2

    # 3.6 Capex负担
    cb = dims.get("capex_burden", {}).get("value", 100)
    scores["3_6"] = 5 if cb < 5 else 4 if cb < 15 else 3 if cb < 30 else 2 if cb < 50 else 1

    # 加权
    weights = {"3_1": 0.20, "3_2": 0.15, "3_3": 0.15, "3_4": 0.15, "3_5": 0.15, "3_6": 0.20}
    total = sum(scores.get(k, 3) * w for k, w in weights.items())
    return round(total, 1)


def generate_serenity_data(halo_data, industry_key, industry_info):
    """基于 HALO 数据和行业信息生成 Serenity 数据"""

    meta = halo_data.get("meta", {})
    stock_code = meta.get("stock_code", "")
    stock_name = meta.get("stock_name", "")
    halo = halo_data.get("halo", {})
    asset_type = halo.get("asset_type", "mixed")

    # 根据资产类型调整评分
    scarcity_score = industry_info["scarcity_score"]
    if asset_type == "heavy":
        scarcity_score = min(scarcity_score + 0.5, 10)  # 重资产略加稀缺性
    elif asset_type == "light":
        scarcity_score = max(scarcity_score - 0.5, 1)  # 轻资产看情况

    # 构建证据（基于 HALO 数据）
    evidence = []

    # 证据1：财务数据
    revenue_yoy = halo_data.get("growth", {}).get("revenue_yoy", 0)
    profit_yoy = halo_data.get("growth", {}).get("net_profit_yoy", 0)
    if profit_yoy > 50:
        evidence.append({
            "content": f"财务表现强劲：营收同比+{revenue_yoy:.1f}%，净利润同比+{profit_yoy:.1f}%，业绩拐点确认",
            "strength": "⭐⭐⭐⭐⭐"
        })
    elif profit_yoy > 10:
        evidence.append({
            "content": f"财务稳健增长：营收同比+{revenue_yoy:.1f}%，净利润同比+{profit_yoy:.1f}%",
            "strength": "⭐⭐⭐⭐"
        })
    else:
        evidence.append({
            "content": f"财务表现平淡：营收同比+{revenue_yoy:.1f}%，净利润同比+{profit_yoy:.1f}%，增长动力不足",
            "strength": "⭐⭐⭐"
        })

    # 证据2：HALO评分
    halo_total = compute_halo_total(halo_data)
    if halo_total >= 4.0:
        evidence.append({
            "content": f"HALO评分{halo_total:.1f}/5.0（极强），重资产属性突出，在滞胀环境具备天然防御力",
            "strength": "⭐⭐⭐⭐"
        })
    elif halo_total >= 3.0:
        evidence.append({
            "content": f"HALO评分{halo_total:.1f}/5.0（强），重资产属性适中",
            "strength": "⭐⭐⭐"
        })
    else:
        evidence.append({
            "content": f"HALO评分{halo_total:.1f}/5.0，重资产属性一般",
            "strength": "⭐⭐"
        })

    # 证据3：行业地位
    evidence.append({
        "content": f"行业地位：{industry_info['chain']}，处于{industry_info['layer']}，稀缺性{industry_info['scarcity']}",
        "strength": "⭐⭐⭐"
    })

    # 填充第三条（如需要）
    if len(evidence) < 3:
        evidence.append({
            "content": "待进一步研究补充",
            "strength": "⭐⭐"
        })

    # 风险
    risks = {
        "substitute": f"技术替代风险取决于{industry_info['chain']}的具体细分领域，需进一步分析",
        "expansion": f"扩产风险：{industry_info['chain']}行业的扩产周期和资本开支强度决定了供给释放节奏",
        "demand": "需求风险：需跟踪下游需求的真实强度和可持续性",
        "falsification": "证伪条件：①若连续2季度营收/利润低于预期说明景气度下行 ②若毛利率显著下滑说明定价权不足 ③若市占率下降说明竞争力减弱"
    }

    # 综合构建
    serenity = {
        "meta": {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "scan_date": datetime.now().strftime("%Y-%m-%d"),
            "theme": f"A股 {industry_info['chain']}",
            "methodology": "Serenity 供应链瓶颈研究（自动启发式版本）",
            "note": "本数据由规则引擎自动生成，建议结合 /serenity 深度分析验证"
        },
        "chain": industry_info["chain"],
        "layer": industry_info["layer"],
        "bottleneck": f"{industry_info['chain']}的关键瓶颈环节需根据具体公司业务进一步确认",
        "scarcity_rating": f"{'🟢' if scarcity_score >= 7 else '🟡' if scarcity_score >= 5 else '🔴'} {industry_info['scarcity']}（自动评估，建议人工验证）",
        "expansion_difficulty": "扩产难度取决于具体细分领域的技术壁垒和资本开支强度",
        "position_analysis": f"{stock_name}处于{industry_info['chain']}的{industry_info['layer']}。HALO评分{halo_total:.1f}/5.0，资产类型{asset_type}。自动启发式分析——建议使用 /serenity 进行深度产业链研究。",
        "evidence": evidence[:3],
        "evidence_analysis": f"以上{len(evidence)}条证据初步构建了{stock_name}的产业链定位逻辑。但自动分析存在局限：①缺乏对具体产品和客户的深度了解 ②未验证竞争格局的真实壁垒 ③未考虑政策/技术突变因素。建议运行 /serenity 进行源端验证。",
        "risks": risks,
        "risk_analysis": f"{stock_name}的主要风险来自{industry_info['chain']}的周期波动和竞争格局变化。自动分析仅覆盖通用风险，具体公司的特有风险需人工研究。",
        "scores": {
            "scarcity": scarcity_score,
            "scarcity_comment": f"自动评估：{industry_info['scarcity']}（基于行业分类启发式判断）",
            "control": min(scarcity_score + 0.5, 10) if halo_total >= 3.5 else max(scarcity_score - 0.5, 1),
            "control_comment": f"控制力与HALO评分{'正' if halo_total >= 3.5 else '负'}相关（HALO {halo_total:.1f}）",
            "evidence": min(7.0 + len(evidence) * 0.3, 9.0),
            "evidence_comment": f"基于{len(evidence)}条自动生成的证据，完整度中等",
            "total": round((scarcity_score + min(scarcity_score + 0.5, 10) + min(7.0 + len(evidence) * 0.3, 9.0)) / 3, 1),
            "total_comment": f"自动综合评分（启发式），建议使用 /serenity 深度验证"
        },
        "research_priority": f"{'🟢' if scarcity_score >= 7 else '🟡'} {'高' if scarcity_score >= 7 else '中'}优先级 — 自动评估，建议 /serenity 验证",
        "next_steps": [
            f"运行 /serenity A股 {industry_info['chain']} {stock_code} 进行深度产业链分析",
            f"跟踪{industry_info['chain']}的行业景气度指标",
            "验证公司在产业链中的真实议价能力和竞争壁垒",
            "对比同行业公司的产业链定位差异"
        ]
    }

    return serenity


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_serenity.py <stock_code>")
        print("示例: python generate_serenity.py 000100")
        sys.exit(1)

    stock_code = sys.argv[1]
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    # 读取 HALO 主数据
    halo_path = os.path.join(data_dir, f"{stock_code}.json")
    if not os.path.exists(halo_path):
        print(f"❌ 找不到 HALO 数据: {halo_path}")
        print(f"   请先运行: python fetch_stock_data.py {stock_code} <股票名称>")
        sys.exit(1)

    with open(halo_path, 'r', encoding='utf-8') as f:
        halo_data = json.load(f)

    # 获取行业和公司名称（多路径查找）
    meta = halo_data.get("meta", {})
    company_info = halo_data.get("company", {})
    f10_info = halo_data.get("f10", {})
    business_scope = f10_info.get("business_scope", "")

    industry = (
        company_info.get("industry") or
        f10_info.get("industry") or
        f10_info.get("industry_csrc") or
        halo_data.get("halo", {}).get("industry", "") or
        ""
    )
    stock_name = meta.get("stock_name", company_info.get("name", ""))
    full_name = f10_info.get("full_name", "")

    print(f"\n{'='*60}")
    print(f"  Serenity 产业链数据自动生成 — {stock_name}({stock_code})")
    print(f"{'='*60}\n")

    # 匹配行业（含经营范围）
    industry_key, industry_info = match_industry(industry, stock_name, business_scope)
    print(f"  📦 行业匹配: {industry or '(空)'} → {industry_key}")
    if business_scope and industry_key != "default":
        print(f"  📋 经营范围关键词匹配")
    print(f"  🔗 产业链: {industry_info['chain']}")
    print(f"  📍 层级: {industry_info['layer']}")
    print(f"  ⭐ 稀缺性: {industry_info['scarcity']} ({industry_info['scarcity_score']}/10)")

    # 生成 Serenity 数据
    serenity_data = generate_serenity_data(halo_data, industry_key, industry_info)

    # 保存
    output_path = os.path.join(data_dir, f"{stock_code}_serenity.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serenity_data, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 已保存: {output_path}")
    print(f"  📊 文件大小: {os.path.getsize(output_path)/1024:.1f} KB")
    print(f"  💡 建议: 运行 /serenity 进行深度产业链分析以验证和补充")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
