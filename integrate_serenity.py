#!/usr/bin/env python3
"""
Serenity 产业链数据集成到 HALO 报告

读取 Serenity 产业链扫描结果 → 填充 HALO 骨架中的 {{SERENITY_*}} 槽位

用法:
  python integrate_serenity.py <stock_code> [serenity_json_path]

如果未提供 serenity_json_path，则尝试读取 data/{code}_serenity.json
"""

import json, os, sys


def integrate_serenity(skeleton_path, serenity_data):
    """将 Serenity 数据填充到骨架中"""

    with open(skeleton_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Serenity 字段映射
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
            replacements[f"{{{{SERENITY_STRENGTH_{i+1}}}}}"] = evidence[i].get("strength", "⚠️")
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
        content = content.replace(k, v)

    return content


def main():
    if len(sys.argv) < 2:
        print("用法: python integrate_serenity.py <stock_code> [serenity_json_path]")
        print("示例: python integrate_serenity.py 688019 data/688019_serenity.json")
        sys.exit(1)

    stock_code = sys.argv[1]
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

    # Serenity 数据路径
    if len(sys.argv) >= 3:
        serenity_path = sys.argv[2]
    else:
        serenity_path = os.path.join(data_dir, f"{stock_code}_serenity.json")

    skeleton_path = os.path.join(reports_dir, f"{stock_code}_skeleton.md")
    output_path = os.path.join(reports_dir, f"{stock_code}_halo_v5.md")

    # 检查文件存在
    if not os.path.exists(serenity_path):
        print(f"❌ 找不到 Serenity 数据: {serenity_path}")
        print(f"   请先运行 Serenity 产业链扫描，或使用 /serenity 命令生成数据")
        sys.exit(1)

    if not os.path.exists(skeleton_path):
        print(f"❌ 找不到骨架文件: {skeleton_path}")
        print(f"   请先运行: python generate_report.py {stock_code}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Serenity 产业链集成 — {stock_code}")
    print(f"{'='*60}\n")

    # 读取 Serenity 数据
    with open(serenity_path, 'r', encoding='utf-8') as f:
        serenity_data = json.load(f)

    print(f"  📊 读取 Serenity 数据: {os.path.getsize(serenity_path)/1024:.1f} KB")
    print(f"  🔗 产业链: {serenity_data.get('chain', '?')}")
    print(f"  📍 卡点: {serenity_data.get('bottleneck', '?')}")
    print(f"  ⭐ 稀缺性: {serenity_data.get('scarcity_rating', '?')}")

    # 集成
    final_content = integrate_serenity(skeleton_path, serenity_data)

    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"\n  ✅ 集成完成!")
    print(f"  📄 最终报告: {output_path}")
    print(f"  📊 文件大小: {os.path.getsize(output_path)/1024:.1f} KB")
    print(f"  📝 报告行数: {len(final_content.splitlines())}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
