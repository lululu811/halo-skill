# HALO · A股可信分析框架 — Agent 指南

> 本文件面向 AI 编码 Agent。阅读前默认不了解本项目。

---

## 1. 项目概述

**HALO** 是一个针对 A 股的基本面分析 Agent Skill，核心设计原则是：

- **数据层与分析层彻底分离**：所有数字（行情、财报、HALO 评分、财务比率）由 Python 从公开 API 获取并计算；AI 只负责在预留槽位里写分析文字。
- **数据 100% 来自 API**：腾讯财经、东方财富、新浪财经、巨潮资讯等公开源，绝不编造。
- **行业公平评分**：HALO 六维不再一刀切，按重资产 / 混合型 / 轻资产三类阈值评分。
- **11 维度综合框架**：HALO 六维 + 成长性 + 护城河 + 滞胀防御 + ESG + 管理层 + 资金面 + 估值 - 风险。

项目语言：**中文**（注释、文档、报告、JSON 键名均使用中文或中英混合）。

---

## 2. 仓库结构

```
halo-skill/
├── README.md                   # 面向用户的总览与安装说明
├── SKILL.md                    # Skill 定义、评分框架、完整工作流（AI 触发时读取）
├── halo_v5.0.md                # V5.0 报告模板原文（含占位符规范）
├── halo_v4.3.md                # 旧版模板（已归档）
├── install.sh                  # 一键安装脚本（Git + venv + requests）
├── test-prompts.json           # 验收测试用例集
├── test_data.py                # 数据层连通性测试（含 TDX/mootdx）
│
├── fetch_stock_data.py         # 量化数据获取：行情+财报+资金流 → data/{code}.json
├── fetch_qualitative.py        # 定性数据获取：新闻+研报+公告 → data/{code}_qualitative.json
├── generate_serenity.py        # 产业链数据自动生成 → data/{code}_serenity.json
├── generate_report.py          # 骨架生成器：JSON → reports/{code}_skeleton.md
├── integrate_serenity.py       # Serenity 手动集成到报告
├── bridge_a_stock_data.py      # a-stock-data 43 端点桥接配置
├── fill_300888.py              # 早期一次性填充脚本（已归档，勿复用）
│
├── data/                       # 运行时数据输出（.gitignore 忽略 *.json）
│   ├── {code}.json             # 量化数据
│   ├── {code}_qualitative.json # 定性数据
│   ├── {code}_serenity.json    # 产业链数据
│   └── {code}_bridge.json      # 桥接配置
│
├── reports/                    # 报告输出（.gitignore 忽略 *.md）
│   ├── {code}_skeleton.md      # 数据锁定后的骨架
│   └── {code}_halo_v5.md       # AI 填充后的最终报告
│
├── baseline/                   # 鲁班打磨用基线（.gitignore 忽略）
└── examples/                   # 展示材料
```

---

## 3. 技术栈

- **语言**：Python 3.9+（当前环境为 Python 3.14.6）
- **运行时**：Claude Code / 支持 Agent Skill 的 AI 运行时
- **外部依赖**：标准库 + `requests`（唯一显式依赖，见 `install.sh`）
- **数据协议**：HTTP/HTTPS 公开 API（腾讯 `qt.gtimg.cn`、东财 `push2.eastmoney.com` / `datacenter-web.eastmoney.com`、新浪 `quotes.sina.cn`、巨潮 `cninfo.com.cn`）
- **输出格式**：JSON（数据）、Markdown（报告）

### 依赖安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests
```

> `test_data.py` 还会尝试使用 `mootdx`，但非主流程强依赖。

---

## 4. 核心工作流

完整的端到端流程如下：

```bash
# Step 1: 激活虚拟环境
source .venv/bin/activate

# Step 2: 获取量化数据
python fetch_stock_data.py <股票代码>
# 输出：data/{code}.json

# Step 3: 获取定性数据
python fetch_qualitative.py <股票代码> <股票名称>
# 输出：data/{code}_qualitative.json

# Step 4: 生成产业链数据
python generate_serenity.py <股票代码>
# 输出：data/{code}_serenity.json

# Step 5: 生成报告骨架（自动集成 Serenity）
python generate_report.py <股票代码>
# 输出：reports/{code}_skeleton.md

# Step 6: AI 填充 {{AI_*}} 槽位，保存最终报告
# 输出：reports/{code}_halo_v5.md
```

### 触发方式

在 Claude Code 中，用户可通过以下方式触发：

```
/halo 600519
/halo 分析贵州茅台
帮我看看亨通光电基本面
600487 值不值得买
用HALO框架分析一下300888
```

---

## 5. 各模块职责

### 5.1 `fetch_stock_data.py`

- 输入：6 位 A 股代码
- 输出：`data/{code}.json`
- 数据源：
  - 腾讯行情：实时价、PE/PB、市值、涨跌幅
  - 东财 `push2`：行业、股本、上市日期
  - 东财 F10：公司全称、员工人数、董事长/总经理
  - 东财板块：所属概念
  - 新浪财报：利润表、资产负债表、现金流量表（各 8 期）
  - 东财资金流向：日级主力净流入（最近 30 日）
- 核心计算：
  - `calculate_halo()`：HALO 六维原始值 + 行业分类（heavy / mixed / light）
  - `calculate_financial_ratios()`：ROE/ROA/毛利率/净利率/负债率/流动比率/现金流质量
  - `calculate_growth()`：营收/利润同比、年度同比、3 年 CAGR

### 5.2 `fetch_qualitative.py`

- 输入：股票代码 + 股票名称
- 输出：`data/{code}_qualitative.json`
- 数据源：
  - 东财 `search-api-web`：个股新闻 20 条
  - 东财 `reportapi`：研报 15 篇（含评级/目标价）
  - 巨潮资讯：公告 15 条
  - 新浪财经：个股新闻 10 条（补充）
- 注意：ESG、管理层、舆情风险等深度定性内容由 AI 在报告阶段通过搜索工具补充。

### 5.3 `generate_serenity.py`

- 输入：`data/{code}.json`
- 输出：`data/{code}_serenity.json`
- 基于行业关键词映射 + HALO 财务数据，启发式生成产业链定位、证据链、风险与证伪条件、产业链评分。
- 属于**自动版**；可升级为 `/serenity` skill 的**深度版**。

### 5.4 `generate_report.py`

- 输入：`data/{code}.json`、可选 `data/{code}_qualitative.json`
- 输出：`reports/{code}_skeleton.md`
- 功能：
  - 从 JSON 精确填充所有数据字段
  - 计算 HALO 六维评分（按行业类型阈值）
  - 计算成长性评分
  - 自动生成第十二章产业链占位符
  - 若 `data/{code}_serenity.json` 存在，**自动调用 `integrate_serenity_inline()` 填充产业链数据**
  - 统计并输出剩余 `{{AI_*}}` 槽位数量

### 5.5 `integrate_serenity.py`

- 输入：`reports/{code}_skeleton.md`、`data/{code}_serenity.json`
- 输出：`reports/{code}_halo_v5.md`
- 用于手动将 Serenity 数据集成到已生成的骨架。

### 5.6 `bridge_a_stock_data.py`

- 输入：股票代码 + 股票名称
- 输出：`data/{code}_bridge.json`
- 生成 HALO × a-stock-data 数据路由表。当 a-stock-data skill 可用时，优先调用其端点；失败则 fallback 到 HALO 原生脚本。
- 新增能力：龙虎榜、北向资金、融资融券。

---

## 6. 代码组织约定

### 6.1 编码风格

- 使用 **Python 3 类型注解**较少，主要依赖 docstring 说明。
- 函数内部大量使用中文注释说明业务含义。
- 数值单位约定：
  - 金额在 JSON 中统一为 **元**（原始值）
  - 报告/日志中显示为 **亿元**（`yi()`）或 **万元**（`wan()`）
  - 百分比保留 2 位小数
  - 评分保留 1 位小数

### 6.2 命名约定

- 模块内常量大写，如 `UA`、`OUTPUT_DIR`、`HEAVY_ASSET_INDUSTRIES`
- 占位符使用 Mustache 风格：`{{字段名}}` 表示数据，`{{AI_*}}` 表示 AI 槽位，`{{SERENITY_*}}` 表示产业链数据
- JSON 中中文键名直接来自财报源（如 `"营业收入"`、`"资产总计"`）

### 6.3 错误处理

- 网络/API 失败时打印异常并继续（非核心数据缺失可降级）
- 财务三表缺失时返回 `{"error": "缺少财务数据"}`，主流程不应继续生成报告
- 数据缺失时在报告中显示 `⚠️ 缺失`，**禁止估算或编造**

---

## 7. 测试策略

### 7.1 验收测试

测试用例定义在 `test-prompts.json`，包含：

- 600519 贵州茅台：轻资产型
- 600487 亨通光电：混合型
- 601398 工商银行：重资产型
- 自然语言触发
- 688019 安集科技：Serenity 集成

### 7.2 数据层测试

```bash
python test_data.py [股票代码]
```

该脚本测试：腾讯行情、通达信财务快照（mootdx）、东财公司信息、新浪三表，并保存 `data/{code}_test.json`。

### 7.3 脚本语法检查

```bash
python3 -m py_compile fetch_stock_data.py fetch_qualitative.py generate_report.py generate_serenity.py integrate_serenity.py bridge_a_stock_data.py test_data.py
```

---

## 8. 构建/运行命令速查

| 目标 | 命令 |
|:-----|:-----|
| 安装 | `bash install.sh` 或手动创建 venv + `pip install requests` |
| 获取量化数据 | `python fetch_stock_data.py 600519` |
| 获取定性数据 | `python fetch_qualitative.py 600519 贵州茅台` |
| 生成产业链数据 | `python generate_serenity.py 600519` |
| 生成骨架 | `python generate_report.py 600519` |
| 手动集成 Serenity | `python integrate_serenity.py 600519` |
| 生成桥接配置 | `python bridge_a_stock_data.py 600519 贵州茅台` |
| 数据测试 | `python test_data.py 600519` |

---

## 9. 数据铁律与安全边界

### 9.1 数据层（Python 锁定）

- 价格 / PE / PB / 市值 / 营收 / 利润 / 资产 / 负债 / 现金流
- HALO 六维评分、财务比率、成长性评分
- 报告结构、表头、emoji、数据来源标注

以上由 `generate_report.py` 从 JSON 精确填充，**AI 不得修改**。

### 9.2 分析层（AI 填充）

- `{{AI_*}}` 槽位中的分析文字
- 护城河、滞胀、ESG、管理层、股东、风险等定性评分
- 投资建议、SWOT、总结

### 9.3 禁止行为

1. **AI 绝对不能修改**骨架中已有的任何数字。
2. **AI 绝对不能编造**骨架中不存在的数据。
3. 如果骨架标注 `⚠️ 缺失`，分析中必须说明数据缺失，不得估算。

### 9.4 安全边界

- 不访问用户账户或交易数据
- 不修改用户文件系统（除 `reports/` 和 `data/` 目录外）
- 不编造财务数据
- 报告末尾必须包含免责声明和 30 日有效期

---

## 10. 部署与发布

- **安装入口**：`install.sh`（curl 管道安装）或 `npx clawhub install @lululu811/halo`
- **Git 忽略**：`data/*.json`、`reports/*.md`、`baseline/`、`.venv/`
- **发布基线**：README.md、SKILL.md、Python 脚本为发布产物；`halo_v4.3.md`、`fill_*.py`、`baseline/` 为归档/内部打磨用，不对外发布。
- **版本标签**：README 中显式声明 `v1.1（2026-07-14）`，SKILL.md 中声明框架版本 `V5.0`。

---

## 11. 常见失败模式与降级

| 失败场景 | 处理方式 |
|:-----|:-----|
| 腾讯行情 API 失败 | JSON 中价格/PE/PB 为空，报告中标注 `⚠️ 缺失` |
| 东财公司信息失败 | 行业/股本缺失，不影响核心分析 |
| 新浪财报 API 失败 | 输出 `{"error": "缺少财务数据"}`，**停止流程** |
| 财务数据不足 2 期 | 成长性评分降级为数据不足 |
| 股票代码不存在 | 腾讯 API 返回空，提示用户 |
| Serenity 数据缺失 | 第十二章占位符保留，跳过集成 |

---

## 12. 给 Agent 的开发建议

1. **修改评分阈值**：只改 `generate_report.py` 中的 `score_halo()` / `score_growth()`，并同步更新 `SKILL.md` 与 `halo_v5.0.md` 附录。
2. **新增数据源**：优先在 `fetch_stock_data.py` 中按现有源结构追加，保持 JSON 输出字段兼容。
3. **新增报告章节**：修改 `generate_report.py` 的 `generate_skeleton()`，并确保新增字段已写入 JSON。
4. **不要改占位符前缀**：`{{AI_*}}` 和 `{{SERENITY_*}}` 是 AI 填充阶段识别槽位的关键约定。
5. **测试改动**：至少运行一次 `python generate_report.py 000100`（已存在数据），检查骨架中是否有报错或残留字段。
6. **保持中文注释和文档**：项目面向中文用户，新增代码注释、日志输出、文档均使用中文。

---

## 13. 关键外部依赖说明

- `requests`：HTTP 请求（东财、新浪、巨潮）
- `urllib.request`：腾讯行情请求
- `mootdx`（仅 `test_data.py`）：通达信客户端测试，主流程不使用
- 无需 `pyproject.toml`、`setup.py`、`requirements.txt` 等配置，依赖在 `install.sh` 中硬编码安装

---

*最后更新：2026-07-14*  
*对应项目版本：HALO V5.0 / Skill v1.1*
