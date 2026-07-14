# HALO 数据层 Harness 设计文档

> 版本：v1.0  
> 日期：2026-07-14  
> 目标：为 HALO A股可信分析框架增加数据层验证 harness，确保 Python 生成的 JSON 数据和报告骨架符合质量与一致性要求。

---

## 1. 背景与目标

HALO 的核心设计原则是"数据层与分析层彻底分离"：Python 脚本负责从公开 API 获取数据并生成 JSON/骨架，AI 只负责在预留槽位里写分析文字。

随着数据源和评分逻辑增加，需要一种机制来确保：

- 每次生成的 JSON 数据完整、合理、可溯源。
- `generate_report.py` 填充到骨架中的数字与 JSON 源数据一致。
- 评分计算（HALO 六维、成长性）在不同模块中结果一致。
- 数据缺失或异常能被及时发现并报告，而不是被 AI 误用。

本 harness 只验证**数据层**，不验证 AI 分析层的文字内容。

---

## 2. 总体架构

新增一个独立模块 `halo_harness.py`，由现有主流程在关键节点调用：

```
fetch_stock_data.py ──保存 data/{code}.json──► 调用 validate_data(code)
                                                         │
                                                         ▼
                                              data/{code}_harness.json


generate_report.py ──保存 reports/{code}_skeleton.md──► 调用 validate_skeleton(code)
                                                                  │
                                                                  ▼
                                                       reports/{code}_harness.json
```

`halo_harness.py` 不修改任何已有数据文件，只读取并校验，输出校验结果。

---

## 3. 组件设计

### 3.1 `halo_harness.py`

对外提供三个函数：

```python
def validate_data(code: str) -> dict:
    """校验 data/{code}.json 的完整性、合理性与一致性。"""

def validate_skeleton(code: str) -> dict:
    """校验 reports/{code}_skeleton.md 的数据填充正确性。"""

def run_harness(code: str) -> dict:
    """依次运行 validate_data 和 validate_skeleton，返回汇总结果。"""
```

内部结构：

```python
class Harness:
    def __init__(self, code):
        self.code = code
        self.errors = []
        self.warnings = []
        self.checks = []

    def check(self, name, condition, detail=""):
        # 记录一项检查结果

    def run_data_checks(self):
        # 执行 JSON 层校验

    def run_skeleton_checks(self):
        # 执行骨架层校验

    def report(self):
        # 返回结构化报告
```

### 3.2 与主流程集成

在 `fetch_stock_data.py` 保存 `data/{code}.json` 之后，追加调用：

```python
from halo_harness import validate_data
harness_result = validate_data(code)
if not harness_result["ok"]:
    print("⚠️ 数据层 harness 未通过，请检查 data/{code}_harness.json")
    sys.exit(1)
```

在 `generate_report.py` 保存 `reports/{code}_skeleton.md` 之后，追加调用：

```python
from halo_harness import validate_skeleton
harness_result = validate_skeleton(code)
if not harness_result["ok"]:
    print("⚠️ 骨架 harness 未通过，请检查 reports/{code}_harness.json")
    sys.exit(1)
```

这种设计保持 harness 与主流程解耦：harness 可以单独导入测试，也可以被主流程自动调用。

---

## 4. 校验规则

### 4.1 JSON 数据层校验（`validate_data`）

| # | 检查项 | 规则 | 失败级别 |
|:-:|:-------|:-----|:--------:|
| 1 | meta 字段完整 | `meta.stock_code`、`meta.stock_name`、`meta.fetch_time` 必须存在 | error |
| 2 | 行情数据存在 | `market_data.price`、`pe_ttm`、`pb`、`mcap_yi` 必须存在 | error |
| 3 | 行情数值合理 | price > 0，pe_ttm > 0，pb > 0，mcap_yi > 0 | error |
| 4 | 财报三表期数 | `income_statement`、`balance_sheet`、`cashflow_statement` 各 ≥2 期 | error |
| 5 | 资产类型合法 | `halo.asset_type` 必须是 heavy / mixed / light 之一 | error |
| 6 | HALO 原始值存在 | `halo.dimensions` 下六维原始值存在 | error |
| 7 | 关键财务比率 | `ratios.roe`、`roa`、`gross_margin`、`net_margin`、`debt_ratio` 存在 | warning |
| 8 | 成长性字段 | `growth.revenue_yoy`、`growth.net_profit_yoy` 存在 | warning |
| 9 | 评分计算复核 | 独立复算 HALO 总分和成长分，与 JSON 中比对，允许 ±0.1 浮点误差 | error |
| 10 | 负债率合理 | debt_ratio 在 0-100 之间 | warning |
| 11 | 资金流数据 | `money_flow` 存在且非空（如果适用） | warning |

### 4.2 骨架层校验（`validate_skeleton`）

| # | 检查项 | 规则 | 失败级别 |
|:-:|:-------|:-----|:--------:|
| 1 | 文件存在 | `reports/{code}_skeleton.md` 存在且大小 >0 | error |
| 2 | 无残留数据占位符 | 骨架中不应存在 `{{字段名}}` 形式的数据占位符（`{{AI_*}}` 和 `{{SERENITY_*}}` 可保留） | error |
| 3 | 关键数字一致 | 骨架中价格、PE、HALO 总分、成长分与 JSON 一致 | error |
| 4 | 免责声明 | 骨架末尾包含"免责声明"和"30日有效期"字样 | warning |
| 5 | 产业链章节 | 如果 `data/{code}_serenity.json` 存在，第十二章不应为空 | warning |
| 6 | 无异常缺失标记 | 骨架中不应大量出现 `⚠️ 缺失`（阈值：>10 处） | warning |

---

## 5. 输出格式

### 5.1 控制台输出

```
[HALO Harness] 600519

数据层检查:
  ✅ meta 字段完整
  ✅ 行情数据存在
  ✅ 行情数值合理
  ✅ 财报三表期数 ≥2
  ✅ 资产类型合法 (light)
  ✅ HALO 原始值存在
  ⚠️ 资金流数据缺失
  ✅ HALO 评分复算一致 (3.55)
  ✅ 成长性评分复算一致 (6.5)

骨架层检查:
  ✅ 骨架文件存在
  ✅ 无残留数据占位符
  ✅ 关键数字与 JSON 一致
  ✅ 包含免责声明
  ✅ 产业链章节已填充

结果: 通过 (2 warnings)
```

### 5.2 JSON 报告

`data/{code}_harness.json` / `reports/{code}_harness.json`：

```json
{
  "code": "600519",
  "timestamp": "2026-07-14T13:45:00",
  "ok": true,
  "data_layer": {
    "ok": true,
    "checks": [
      {"name": "meta 字段完整", "passed": true},
      {"name": "行情数值合理", "passed": true}
    ],
    "warnings": [
      {"name": "资金流数据", "message": "money_flow 为空"}
    ],
    "errors": []
  },
  "skeleton_layer": {
    "ok": true,
    "checks": [...],
    "warnings": [],
    "errors": []
  }
}
```

---

## 6. 失败处理策略

- **error 级别失败**：主流程退出码非零，阻止继续生成最终报告。
- **warning 级别失败**：打印警告，但不阻止主流程继续。
- 不删除已生成的 `data/{code}.json` 或 `reports/{code}_skeleton.md`，便于人工排查。
- harness 报告文件始终写入，无论通过与否。

---

## 7. 验证标准

本设计实现后，应满足：

1. `python halo_harness.py 600519` 可独立运行并输出结果。
2. `python fetch_stock_data.py 600519` 保存 JSON 后自动运行数据层校验。
3. `python generate_report.py 600519` 保存骨架后自动运行骨架层校验。
4. 若手动篡改 JSON 中的评分或骨架中的数字，harness 能够检测并报告不一致。
5. 校验规则可通过新增 `Harness.check()` 调用简单扩展。

---

## 8. 后续可扩展方向

- 增加 AI 行为 harness：验证 AI 填充后的最终报告是否修改了数据区域。
- 增加数据源健康监控：定期轮询腾讯/东财/新浪 API，记录可用性。
- 增加回归测试集：基于 `test-prompts.json` 自动跑一组股票，生成 harness 汇总报告。

---

*设计完成，待进入实现计划阶段。*
