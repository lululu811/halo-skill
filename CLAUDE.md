# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

HALO 是一个 A 股基本面分析 Agent Skill。核心设计原则:**数据层与分析层彻底分离**——所有数字(行情、财报、HALO 评分、财务比率)由 Python 从公开 API 获取并计算,AI 只在预留槽位里写分析文字,绝不编造或修改数字。

项目语言为**中文**:注释、文档、报告、JSON 键名均使用中文或中英混合。新增代码请保持中文注释与日志。

更详尽的 Agent 指南见 `AGENTS.md`;评分框架与工作流定义见 `SKILL.md`。本文件聚焦架构大局、常用命令,以及上述两份文档未覆盖的新模块。

## 常用命令

```bash
# 激活虚拟环境(唯一显式依赖:requests)
source .venv/bin/activate

# 端到端流程(每步输出 data/ 或 reports/ 下的文件)
python fetch_stock_data.py 600519 贵州茅台      # → data/{code}.json(量化+HALO原始值+评分复算校验)
python fetch_qualitative.py 600519 贵州茅台     # → data/{code}_qualitative.json
python generate_serenity.py 600519              # → data/{code}_serenity.json(产业链启发式)
python generate_report.py 600519                # → reports/{code}_skeleton.md(含骨架校验,失败 exit 1)
python integrate_serenity.py 600519             # 手动将 Serenity 集成进已生成骨架

# 数据层连通性测试(腾讯/东财/新浪/mootdx)
python test_data.py 600519

# Harness 校验(独立运行数据层+骨架层)
python halo_harness.py 600519

# 测试(仅标准库 assert,无需 pytest 也能跑)
pytest tests/                                   # 全部
pytest tests/test_harness.py::test_validate_data_ok   # 单个
python tests/test_harness.py                    # 直接运行(含 __main__)

# 语法检查(无配置文件,无 requirements.txt)
python3 -m py_compile fetch_stock_data.py fetch_qualitative.py generate_report.py generate_serenity.py integrate_serenity.py bridge_a_stock_data.py halo_harness.py halo_thresholds.py test_data.py
```

## 架构大局

### 数据流水线

```
公开API(腾讯/东财/新浪/巨潮)
  → fetch_stock_data.py / fetch_qualitative.py / generate_serenity.py
    → data/{code}.json / {code}_qualitative.json / {code}_serenity.json
      → generate_report.py(从 JSON 精确填充所有数字,留空 {{AI_*}} 槽位)
        → reports/{code}_skeleton.md
          → AI 填充分析槽位
            → reports/{code}_halo_v5.md
```

关键约束:数字只能从 JSON 流向骨架,**反向不可**。AI 填充阶段只动 `{{AI_*}}` 槽位文字。

### 评分阈值的单一真相源(`halo_thresholds.py`)

HALO 六维评分和成长性评分的阈值/权重集中在 `halo_thresholds.py`,被两个消费方共享:

- `generate_report.py`——生成骨架时计算评分写入报告
- `halo_harness.py`——校验时**独立复算**评分,与 JSON 中存储的值比对(允许 ±0.1 浮点误差)

`tests/test_harness.py` 中的 `test_score_halo_dimensions_match_generate_report` 和 `test_score_growth_matches_generate_report` 是 **parity 测试**,断言两套实现结果完全一致。**修改阈值时只改 `halo_thresholds.py` 一处**,不要在 `generate_report.py` 里另起一份,否则 parity 测试会失败。

### 数据层 Harness(`halo_harness.py`)

主流程在两个节点**自动调用** harness 校验,无需手动触发:

- `fetch_stock_data.py` 保存 JSON 后调用 `validate_data(code)`——校验 meta/行情/三表期数/资产类型/维度原始值/比率/成长性,并复算 HALO 与成长性总分。未通过时返回 `{"ok": False}`,JSON 仍保留。
- `generate_report.py` 保存骨架后调用 `validate_skeleton(code)`——校验无残留数据占位符(只允许 `{{AI_*}}`/`{{SERENITY_*}}`)、骨架中价格/PE/HALO总分/成长分与 JSON 一致、含免责声明与 30 日有效期。**未通过则 `sys.exit(1)`**,骨架文件保留供排查。

校验结果写入 `data/{code}_harness.json` 和 `reports/{code}_harness.json`(注意:这两个文件未被 `.gitignore` 忽略,而 `data/*.json` 和 `reports/*.md` 是被忽略的)。

Harness 区分 `error`(使 `ok=False`)与 `warning`(不阻断)。新增校验项时注意级别:数字一致性、占位符残留是 error;资金流缺失、比率缺失、缺失标记过多是 warning。

## 关键约定

- **占位符前缀不可改动**:`{{字段名}}` 数据槽位(由 Python 填充)、`{{AI_*}}` AI 分析槽位、`{{SERENITY_*}}` 产业链槽位。harness 用正则 `\{\{[A-Z][A-Z_0-9]+\}\}` 识别残留,只放行 `AI_`/`SERENITY_` 前缀。
- **数值单位**:JSON 中金额统一为**元**(原始值);报告/日志显示为亿元(`fmt_yi` 除以 1e8)或万元(`fmt_wan` 除以 1e4);百分比保留 2 位小数;评分保留 1 位小数。
- **资产类型**:`heavy`/`mixed`/`light` 三类,由 `fetch_stock_data.py` 自动判定并写入 `halo.asset_type`。三类对应不同的 HALO 评分阈值(见 `halo_thresholds.py` 的 `HALO_DIMENSION_THRESHOLDS`)。
- **数据铁律**:骨架标注 `⚠️ 缺失` 处,AI 不得估算或编造;新浪财报 API 失败时脚本输出 `{"error": "缺少财务数据"}` 并**停止流程**。
- **行业分类与综合评分公式**:详见 `SKILL.md`(11 维度、权重、评级梯队)。

## Git 忽略与发布边界

`.gitignore` 忽略 `data/*.json`、`reports/*.md`、`baseline/`、`.venv/`、`halo_v4.3.md`、`halo_v5.0.md`、`fill_*.py`。其中 `halo_v4.3.md`/`fill_*.py`/`baseline/` 为归档/内部打磨用,不对外发布。发布产物为 `README.md`、`SKILL.md`、Python 脚本。注意 `halo_v5.0.md` 虽被忽略,但 `SKILL.md` 内嵌了 V5.0 模板内容,是实际生效的真相源。
