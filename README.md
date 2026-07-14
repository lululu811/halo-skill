<div align="center">

# 🔷 HALO · A股可信分析框架

> *「你让AI分析一只股票，它给了你一堆数字——但你不知道哪些是真的。」*

[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-HALO-blueviolet)](SKILL.md)
[![HALO V5.0](https://img.shields.io/badge/HALO-V5.0-green)](SKILL.md)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-lululu811/halo--skill-blue?logo=github)](https://github.com/lululu811/halo-skill)

**Python锁定每一个数据，AI只做分析判断。数据100%来自API，绝不编造。**

[看效果](#效果示例) · [安装](#快速开始) · [触发方式](#触发方式) · [和同类有什么不同](#和同类有什么不同) · [安全边界](#安全边界)

</div>

---

## 它解决什么问题

你让Claude分析贵州茅台，它告诉你"PE 18倍、ROE 30%"——但你怎么知道这些数字是真的？

市面上大多数AI股票分析Skill的工作方式是：**让大模型自己算**。模型可能算对，也可能幻觉出一个看似合理的数字。你无从验证。

HALO换了一个思路：**数据层和分析层彻底分离**。

1. **Python脚本**从腾讯/东财/新浪API拉取真实数据，生成JSON
2. **另一个Python脚本**从JSON生成报告骨架——所有数字精确填充，AI的槽位留空
3. **AI只填空**——在预留的分析槽位里写判断，不碰任何一个数字

你看到报告里的每一个数字，都能追溯到API原始数据。这不是"AI觉得"，是"API说了"。

---

## 效果示例

输入：`/halo 600519`

输出：一份 **500+ 行的11维度分析报告**，包含：

```
📋 执行摘要
├─ HALO评分：3.55/5.0 🟡强
├─ 成长性：6.5/10 🟡强
├─ 护城河：9.0/10 🟢极强
├─ 滞胀防御：8.5/10 🟢极强
└─ 综合评级：增持（目标价1400-1600元）

🔷 HALO六维（行业调整版）
├─ 轻资产型(light) — 采用light型评分阈值
├─ 有形资产密集度：3分 → 核心资产占比高
├─ 固定资产密集度：5分 → 远超行业均值
└─ Capex负担：5分 → 资本开支极轻

💡 投资建议
├─ 品牌护城河无可撼动，定价权绝对
├─ 滞胀环境下的超级防御者
└─ PE 18.3倍，处于近10年估值低位
```

**真实案例**（可直接查看）：

| 股票 | 报告 | 数据量 | HALO评分 | 综合评级 |
|:-----|:-----|:------:|:--------:|:--------:|
| 贵州茅台(600519) | [查看](reports/600519_halo_v5.md) | 112KB JSON | 3.55/5.0 🟡 | 增持 |
| 亨通光电(600487) | [查看](reports/600487_halo_v5.md) | 125KB JSON | 3.20/5.0 🟡 | 中性 |
| 稳健医疗(300888) | [查看](reports/300888_skeleton.md) | 112KB JSON | 3.05/5.0 🟡 | 骨架 |

---

## 快速开始

### 前置条件

- Python 3.9+
- Claude Code（或其他支持Agent Skill的运行时）

### 安装

```bash
# 克隆到 skills 目录
git clone https://github.com/lululu811/halo-skill.git ~/.claude/skills/halo-skill

# 进入目录，建立虚拟环境
cd ~/.claude/skills/halo-skill
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖（仅 requests，无其他）
pip install requests
```

### 使用

对Claude说：

```
/halo 600519
```

或自然语言：

```
帮我分析一下贵州茅台
```

**30秒内**，你会得到一份完整的11维度分析报告。

---

## 触发方式

```
/halo 600519
/halo 分析贵州茅台
帮我看看亨通光电基本面
600487 值不值得买
用HALO框架分析一下300888
```

---

## 和同类有什么不同

| 维度 | 同类Skill | HALO |
|:-----|:----------|:-----|
| **数据可信度** | 大模型自行计算，可能幻觉 | Python锁定数据层，100%来自API |
| **分析框架** | 多为技术面（MA/MACD/RSI） | 11维度基本面（HALO+护城河+滞胀+ESG…） |
| **行业公平** | 一刀切评分 | 重/混合/轻资产三类阈值 |
| **产业链视角** | 无 | Serenity供应链瓶颈集成 |
| **数据韧性** | 单源，挂了就没 | 桥接a-stock-data 43端点+备用源降级 |
| **可验证性** | 黑箱输出 | 每个数字可追溯到JSON→API |
| **目标用户** | 短线交易者 | 基本面投资者 |

> HALO不做技术面信号、不给买卖点。它回答的问题是：**这家公司值不值得深入研究？**

### 🔗 生态互补

HALO 不是孤立的——它可以和 A股 Skill 生态互补：

| Skill | 定位 | 与HALO的关系 |
|:------|:-----|:-------------|
| [a-stock-data](https://github.com/simonlin1212/a-stock-data) | 43端点A股数据底座 | **数据层互补**：桥接后可获得龙虎榜/北向/融资融券 |
| Serenity | 产业链瓶颈扫描 | **分析层互补**：输出集成到HALO第十二章 |
| 东方财富妙想(mx-*) | 官方数据+选股+模拟 | **工具层互补**：自然语言选股+模拟交易 |

---

## 评分框架速览

**11个维度，3个评级梯队**：

| 维度 | 满分 | 权重 | 衡量什么 |
|:-----|:----:|:----:|:---------|
| 🔷 HALO六维 | 5.0 | 15% | 重资产属性（行业调整） |
| 🌱 成长性 | 10 | 15% | 营收/利润增速+质量+持续性 |
| 🏰 护城河 | 10 | 15% | 技术壁垒+客户粘性+竞争格局 |
| 🛡️ 滞胀防御 | 10 | 10% | 实物资产+定价权+现金流 |
| 🌍 ESG | 10 | 10% | 环境+社会+治理 |
| 👔 管理层 | 10 | 10% | 战略+资本配置+激励+诚信 |
| 💰 资金面 | 10 | 5% | 股东+北向+主力+融资 |
| 💵 估值 | 10 | 10% | PE/PB/DCF多维评估 |
| ⚠️ 风险 | 10 | -10% | 7类风险矩阵（越低越好） |

综合评分 ≥6.5 → 强，5.0-6.5 → 中等，<5.0 → 弱

---

## 安全边界

**HALO 不会：**
- ❌ 编造任何财务数据——所有数字来自API
- ❌ 给出具体买卖建议——只提供分析框架
- ❌ 访问你的账户或交易数据
- ❌ 向外部发送任何请求（除数据API外）
- ❌ 修改你的文件系统（除 reports/ 目录外）

**HALO 会：**
- ✅ 在数据缺失时标注"⚠️ 缺失"，不估算
- ✅ 在分析中标注"AI判断"，与数据层区分
- ✅ 标注数据来源（腾讯/东财/新浪）和有效期
- ✅ 在报告末尾附免责声明

---

## 文件结构

```
halo-skill/
├── SKILL.md                    # Skill定义 + 评分框架 + 工作流
├── README.md                   # 本文件
├── fetch_stock_data.py         # 量化数据获取（行情+财报+资金流）
├── fetch_qualitative.py        # 定性数据获取（新闻+研报+公告）
├── generate_report.py          # 骨架生成（🔒数据层锁定）
├── integrate_serenity.py       # Serenity产业链数据集成
├── test_data.py                # 数据完整性测试
├── data/                       # JSON数据输出目录
│   ├── {code}.json             # 量化数据
│   ├── {code}_qualitative.json # 定性数据
│   └── {code}_serenity.json    # 产业链数据（可选）
└── reports/                    # 报告输出目录
    ├── {code}_skeleton.md      # 骨架（数据锁定，AI待填）
    └── {code}_halo_v5.md       # 最终报告
```

---

## 验证与测试

**验收prompt**：

```
/halo 600519
```

**合格表现**：
1. 生成 `data/600519.json`（>100KB）
2. 生成 `data/600519_qualitative.json`（>15KB）
3. 生成 `reports/600519_skeleton.md`（所有数字已填充，AI槽位留空）
4. AI填充分析槽位，生成 `reports/600519_halo_v5.md`
5. 报告中所有财务数字与JSON源数据一致

---

## 致谢

- 数据源：[腾讯财经](https://finance.qq.com) / [东方财富](https://www.eastmoney.com) / [新浪财经](https://finance.sina.com.cn)
- 产业链分析：Serenity供应链瓶颈研究方法
- Skill标准：参考 [microsoft/skills](https://github.com/microsoft/skills) 规范

---

## License

[MIT](LICENSE)

---

<div align="center">

*数据不编造，分析有框架。*

</div>
