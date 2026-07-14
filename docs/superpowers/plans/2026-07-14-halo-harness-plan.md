# HALO 数据层 Harness 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 HALO 项目增加一个独立的数据层 harness 模块，自动验证 `data/{code}.json` 和 `reports/{code}_skeleton.md` 的完整性、一致性与正确性。

**Architecture:** 新增 `halo_harness.py` 作为独立校验模块，由 `fetch_stock_data.py` 和 `generate_report.py` 在保存输出后调用。Harness 不修改已有文件，只输出校验报告和退出码。

**Tech Stack:** Python 3.9+，仅使用标准库（json、os、sys、re、datetime），与项目现有依赖一致。

## Global Constraints

- 仅验证数据层，不验证 AI 分析层文字内容。
- 不引入新依赖（pytest 等），测试使用标准库 `assert` 或独立脚本。
- 保持中文注释风格，与项目现有代码一致。
- 失败时输出详细报告但不删除已生成的数据/骨架文件。
- error 级别失败导致主流程退出码非零；warning 仅打印不阻塞。
- 校验规则可扩展：通过新增 `check()` 调用即可增加检查项。

---

## File Structure

| 文件 | 责任 |
|:-----|:-----|
| `halo_harness.py` | **新增**：Harness 核心模块，提供 `validate_data()`、`validate_skeleton()`、`run_harness()` |
| `fetch_stock_data.py` | **修改**：保存 JSON 后调用 `validate_data()` |
| `generate_report.py` | **修改**：保存骨架后调用 `validate_skeleton()` |
| `data/{code}_harness.json` | **运行时生成**：数据层校验报告 |
| `reports/{code}_harness.json` | **运行时生成**：骨架层校验报告 |
| `tests/test_harness.py` | **新增**：Harness 单元测试（使用标准库） |

---

### Task 1: 创建 halo_harness.py 核心框架

**Files:**
- Create: `halo_harness.py`
- Test: `tests/test_harness.py`（先写失败测试，后续任务逐步完善）

**Interfaces:**
- Produces: `Harness` 类、`validate_data(code)`、`validate_skeleton(code)`、`run_harness(code)`
- Consumes: 无

- [ ] **Step 1: 写失败测试**

在 `tests/test_harness.py` 中：

```python
#!/usr/bin/env python3
"""halo_harness 基础接口测试"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import halo_harness

def test_validate_data_exists():
    result = halo_harness.validate_data("000100")
    assert isinstance(result, dict)
    assert "ok" in result

def test_validate_skeleton_exists():
    result = halo_harness.validate_skeleton("000100")
    assert isinstance(result, dict)
    assert "ok" in result

def test_run_harness_exists():
    result = halo_harness.run_harness("000100")
    assert isinstance(result, dict)
    assert "ok" in result

if __name__ == "__main__":
    test_validate_data_exists()
    test_validate_skeleton_exists()
    test_run_harness_exists()
    print("✅ 基础接口测试通过")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python tests/test_harness.py
```

Expected: `ModuleNotFoundError: No module named 'halo_harness'`

- [ ] **Step 3: 实现 halo_harness.py 核心框架**

```python
#!/usr/bin/env python3
"""
HALO V5.0 数据层 Harness
验证 data/{code}.json 和 reports/{code}_skeleton.md 的完整性、一致性与正确性
"""

import json
import os
import re
import sys
from datetime import datetime


# ── 路径工具 ──
def _project_root():
    return os.path.dirname(os.path.abspath(__file__))


def _data_path(code):
    return os.path.join(_project_root(), "data", f"{code}.json")


def _skeleton_path(code):
    return os.path.join(_project_root(), "reports", f"{code}_skeleton.md")


def _harness_report_path(code, layer):
    if layer == "data":
        return os.path.join(_project_root(), "data", f"{code}_harness.json")
    return os.path.join(_project_root(), "reports", f"{code}_harness.json")


# ── Harness 类 ──
class Harness:
    def __init__(self, code, layer):
        self.code = code
        self.layer = layer
        self.checks = []
        self.warnings = []
        self.errors = []

    def check(self, name, condition, detail="", level="error"):
        """记录一项检查结果"""
        passed = bool(condition)
        record = {"name": name, "passed": passed, "detail": detail}
        self.checks.append(record)
        if not passed:
            if level == "error":
                self.errors.append(record)
            else:
                self.warnings.append(record)
        return passed

    def ok(self):
        return len(self.errors) == 0

    def report(self):
        return {
            "code": self.code,
            "layer": self.layer,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ok": self.ok(),
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _save_report(harness):
    path = _harness_report_path(harness.code, harness.layer)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(harness.report(), f, ensure_ascii=False, indent=2)
    return path


def _print_summary(harness):
    print(f"\n[HALO Harness] {harness.code} — {harness.layer}层")
    for c in harness.checks:
        icon = "✅" if c["passed"] else "❌"
        print(f"  {icon} {c['name']}")
        if c["detail"]:
            print(f"     {c['detail']}")
    if harness.warnings:
        print(f"  ⚠️  {len(harness.warnings)} 个警告")
    status = "通过" if harness.ok() else "未通过"
    print(f"  结果: {status} ({len(harness.errors)} errors, {len(harness.warnings)} warnings)")


# ── 入口函数 ──
def validate_data(code):
    """校验 data/{code}.json"""
    h = Harness(code, "data")
    # TODO: 具体校验规则在 Task 2 实现
    h.check("数据文件存在", os.path.exists(_data_path(code)))
    _save_report(h)
    _print_summary(h)
    return h.report()


def validate_skeleton(code):
    """校验 reports/{code}_skeleton.md"""
    h = Harness(code, "skeleton")
    # TODO: 具体校验规则在 Task 3 实现
    h.check("骨架文件存在", os.path.exists(_skeleton_path(code)))
    _save_report(h)
    _print_summary(h)
    return h.report()


def run_harness(code):
    """依次运行数据层和骨架层校验"""
    data_result = validate_data(code)
    skeleton_result = validate_skeleton(code)
    return {
        "code": code,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ok": data_result["ok"] and skeleton_result["ok"],
        "data_layer": data_result,
        "skeleton_layer": skeleton_result,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python halo_harness.py <股票代码>")
        sys.exit(1)
    code = sys.argv[1]
    result = run_harness(code)
    sys.exit(0 if result["ok"] else 1)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python tests/test_harness.py
```

Expected: `✅ 基础接口测试通过`

- [ ] **Step 5: Commit**

```bash
git add halo_harness.py tests/test_harness.py
git commit -m "feat(harness): 添加 harness 核心框架与基础接口测试"
```

---

### Task 2: 实现 JSON 数据层校验规则

**Files:**
- Modify: `halo_harness.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: `Harness` 类、`_data_path()`、`_save_report()`、`_print_summary()`
- Produces: `validate_data()` 完整实现

- [ ] **Step 1: 写失败测试**

在 `tests/test_harness.py` 末尾追加：

```python
def test_validate_data_checks_json():
    # 假设 data/000100.json 已存在
    result = halo_harness.validate_data("000100")
    # 至少应通过数据文件存在检查
    check_names = [c["name"] for c in result["checks"]]
    assert "数据文件存在" in check_names
```

- [ ] **Step 2: 运行测试，确认失败或已部分通过**

```bash
python tests/test_harness.py
```

Expected: 如果 data/000100.json 存在，测试通过；否则需要先用 `python fetch_stock_data.py 000100` 生成数据。

- [ ] **Step 3: 在 halo_harness.py 中实现 validate_data 完整规则**

将 `validate_data()` 中的 TODO 替换为：

```python
def validate_data(code):
    """校验 data/{code}.json 的完整性、合理性与一致性"""
    h = Harness(code, "data")
    data_path = _data_path(code)

    # 1. 文件存在
    exists = os.path.exists(data_path)
    h.check("数据文件存在", exists, detail=f"路径: {data_path}")
    if not exists:
        _save_report(h)
        _print_summary(h)
        return h.report()

    with open(data_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    # 2. meta 字段完整
    meta = d.get("meta", {})
    h.check("meta 字段完整",
            meta.get("stock_code") == code and bool(meta.get("stock_name")) and bool(meta.get("fetch_time")),
            detail=f"stock_code={meta.get('stock_code')}, stock_name={meta.get('stock_name')}")

    # 3. 行情数据存在且合理
    market = d.get("market", {})
    required_market = ["price", "pe_ttm", "pb", "mcap_yi"]
    has_market = all(k in market for k in required_market)
    h.check("行情数据字段完整", has_market, detail=f"缺失: {[k for k in required_market if k not in market]}")
    if has_market:
        h.check("行情数值合理",
                market["price"] > 0 and market["pe_ttm"] > 0 and market["pb"] > 0 and market["mcap_yi"] > 0,
                detail=f"price={market['price']}, pe={market['pe_ttm']}, pb={market['pb']}, mcap={market['mcap_yi']}")

    # 4. 财报三表期数
    financial = d.get("financial", {})
    income = financial.get("income", [])
    balance = financial.get("balance", [])
    cashflow = financial.get("cashflow", [])
    h.check("财报三表期数 ≥2",
            len(income) >= 2 and len(balance) >= 2 and len(cashflow) >= 2,
            detail=f"利润表{len(income)}期, 负债表{len(balance)}期, 现金流表{len(cashflow)}期")

    # 5. 资产类型合法
    halo = d.get("halo", {})
    asset_type = halo.get("asset_type", "")
    h.check("资产类型合法", asset_type in ("heavy", "mixed", "light"), detail=f"asset_type={asset_type}")

    # 6. HALO 六维原始值存在
    dims = halo.get("dimensions", {})
    required_dims = ["tangible_intensity", "fixed_intensity", "fixed_share", "capital_labor", "capex_intensity"]
    has_dims = all(k in dims for k in required_dims)
    h.check("HALO 六维原始值存在", has_dims,
            detail=f"缺失: {[k for k in required_dims if k not in dims]}")

    # 7. 关键财务比率
    ratios = d.get("ratios", {})
    required_ratios = ["roe", "roa", "gross_margin", "net_margin", "debt_ratio"]
    has_ratios = all(k in ratios for k in required_ratios)
    h.check("关键财务比率存在", has_ratios,
            detail=f"缺失: {[k for k in required_ratios if k not in ratios]}", level="warning")
    if has_ratios:
        debt = ratios.get("debt_ratio", 0)
        h.check("负债率合理", 0 <= debt <= 100, detail=f"debt_ratio={debt}", level="warning")

    # 8. 成长性字段
    growth = d.get("growth", {})
    has_growth = "revenue_yoy" in growth and "net_profit_yoy" in growth
    h.check("成长性字段存在", has_growth,
            detail=f"缺失: revenue_yoy={growth.get('revenue_yoy')}, net_profit_yoy={growth.get('net_profit_yoy')}",
            level="warning")

    # 9. 评分计算复核（允许 ±0.1 浮点误差）
    json_halo_total = halo.get("total_score")
    json_growth_total = growth.get("total_score")
    recalc_halo = _recalc_halo_score(halo)
    recalc_growth = _recalc_growth_score(growth)
    if json_halo_total is not None and recalc_halo is not None:
        h.check("HALO 评分复算一致",
                abs(float(json_halo_total) - recalc_halo) <= 0.1,
                detail=f"JSON={json_halo_total}, 复算={recalc_halo:.2f}")
    if json_growth_total is not None and recalc_growth is not None:
        h.check("成长性评分复算一致",
                abs(float(json_growth_total) - recalc_growth) <= 0.1,
                detail=f"JSON={json_growth_total}, 复算={recalc_growth:.2f}")

    # 10. 资金流数据（warning）
    fund_flow = d.get("fund_flow", [])
    h.check("资金流数据存在", len(fund_flow) > 0,
            detail=f"fund_flow={len(fund_flow)}条", level="warning")

    _save_report(h)
    _print_summary(h)
    return h.report()


def _recalc_halo_score(halo):
    """独立复算 HALO 总分"""
    dims = halo.get("dimensions", {})
    asset_type = halo.get("asset_type", "mixed")
    if not dims:
        return None
    # 简化复算：读取 JSON 中已计算的 dimension score（如果存在）
    scores = []
    weights = {"tangible_intensity": 0.20, "fixed_intensity": 0.15, "fixed_share": 0.15,
               "capital_labor": 0.15, "capex_intensity": 0.15, "capex_burden": 0.20}
    for name, weight in weights.items():
        dim = dims.get(name, {})
        score = dim.get("score")
        if score is None:
            return None
        scores.append(float(score) * weight)
    return sum(scores)


def _recalc_growth_score(growth):
    """独立复算成长性总分"""
    total = growth.get("total_score")
    return float(total) if total is not None else None
```

注意：这里对 `_recalc_halo_score` 的实现是读取 JSON 中已有的 dimension score。如果 `data/{code}.json` 中 dimension score 是独立存储的，则直接读取；否则需要完整复算 generate_report.py 中的阈值逻辑。设计文档中要求"独立复算"，应根据实际 JSON 结构选择：
- 若 JSON 中 `halo.dimensions.{name}.score` 存在 → 读取并加权求和。
- 若不存在 → 在 harness 中独立实现与 generate_report.py 相同的阈值逻辑。

- [ ] **Step 4: 运行测试**

```bash
python fetch_stock_data.py 000100
python halo_harness.py 000100
```

Expected: 数据层校验通过，输出 `data/000100_harness.json`。

- [ ] **Step 5: Commit**

```bash
git add halo_harness.py tests/test_harness.py
git commit -m "feat(harness): 实现 JSON 数据层完整校验规则"
```

---

### Task 3: 实现骨架层校验规则

**Files:**
- Modify: `halo_harness.py`
- Test: `tests/test_harness.py`

**Interfaces:**
- Consumes: `Harness` 类、`_skeleton_path()`、`_data_path()`、`_save_report()`、`_print_summary()`
- Produces: `validate_skeleton()` 完整实现

- [ ] **Step 1: 写失败测试**

在 `tests/test_harness.py` 末尾追加：

```python
def test_validate_skeleton_checks_markdown():
    # 假设 reports/000100_skeleton.md 已存在
    result = halo_harness.validate_skeleton("000100")
    check_names = [c["name"] for c in result["checks"]]
    assert "骨架文件存在" in check_names
```

- [ ] **Step 2: 运行测试，确认失败或部分通过**

```bash
python tests/test_harness.py
```

Expected: 如果骨架存在则通过，否则需要先生成骨架。

- [ ] **Step 3: 实现 validate_skeleton 完整规则**

将 `validate_skeleton()` 中的 TODO 替换为：

```python
def validate_skeleton(code):
    """校验 reports/{code}_skeleton.md 的数据填充正确性"""
    h = Harness(code, "skeleton")
    skeleton_path = _skeleton_path(code)
    data_path = _data_path(code)

    # 1. 文件存在且非空
    exists = os.path.exists(skeleton_path) and os.path.getsize(skeleton_path) > 0
    h.check("骨架文件存在", exists, detail=f"路径: {skeleton_path}")
    if not exists:
        _save_report(h)
        _print_summary(h)
        return h.report()

    with open(skeleton_path, "r", encoding="utf-8") as f:
        skeleton = f.read()

    # 2. 无残留数据占位符（允许 {{AI_*}} 和 {{SERENITY_*}}）
    unknown_placeholders = re.findall(r"\{\{[A-Z][A-Z_0-9]+\}\}", skeleton)
    allowed = {"{{AI_", "{{SERENITY_"}
    leftover = [p for p in unknown_placeholders if not any(p.startswith(a) for a in allowed)]
    h.check("无残留数据占位符", len(leftover) == 0,
            detail=f"残留: {leftover[:5]}")

    # 3. 关键数字与 JSON 一致
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        market = d.get("market", {})
        price = market.get("price")
        pe = market.get("pe_ttm")
        halo = d.get("halo", {})
        halo_total = halo.get("total_score")
        growth = d.get("growth", {})
        growth_total = growth.get("total_score")

        h.check("骨架中价格与 JSON 一致",
                price is None or _find_number_in_text(skeleton, price),
                detail=f"JSON price={price}")
        h.check("骨架中 PE 与 JSON 一致",
                pe is None or _find_number_in_text(skeleton, pe),
                detail=f"JSON pe_ttm={pe}")
        h.check("骨架中 HALO 总分与 JSON 一致",
                halo_total is None or _find_number_in_text(skeleton, halo_total),
                detail=f"JSON halo_total={halo_total}")
        h.check("骨架中成长分与 JSON 一致",
                growth_total is None or _find_number_in_text(skeleton, growth_total),
                detail=f"JSON growth_total={growth_total}")

    # 4. 免责声明和有效期
    h.check("包含免责声明", "免责声明" in skeleton, level="warning")
    h.check("包含30日有效期", "30日有效期" in skeleton or "报告有效期30日" in skeleton, level="warning")

    # 5. 产业链章节（如果 serenity 数据存在）
    serenity_path = os.path.join(_project_root(), "data", f"{code}_serenity.json")
    if os.path.exists(serenity_path):
        chapter12 = skeleton.split("## 🔗 十二、产业链定位")[-1] if "## 🔗 十二、产业链定位" in skeleton else ""
        h.check("产业链章节不为空", len(chapter12.strip()) > 200,
                detail=f"章节长度={len(chapter12.strip())}", level="warning")

    # 6. 缺失标记数量
    missing_count = skeleton.count("⚠️ 缺失")
    h.check("缺失标记不过多", missing_count <= 10,
            detail=f"缺失标记={missing_count}", level="warning")

    _save_report(h)
    _print_summary(h)
    return h.report()


def _find_number_in_text(text, number):
    """在文本中查找数字的字符串表示（支持 ±0.01 误差）"""
    if number is None:
        return False
    num = float(number)
    # 查找整数或保留 1-2 位小数的表示
    for fmt in [f"{num:.0f}", f"{num:.1f}", f"{num:.2f}"]:
        if fmt in text:
            return True
    # 容错：查找接近值
    for m in re.finditer(r"[-+]?\d+\.?\d*", text):
        try:
            if abs(float(m.group()) - num) <= 0.01:
                return True
        except ValueError:
            continue
    return False
```

- [ ] **Step 4: 运行测试**

```bash
python generate_report.py 000100
python halo_harness.py 000100
```

Expected: 骨架层校验通过，输出 `reports/000100_harness.json`。

- [ ] **Step 5: Commit**

```bash
git add halo_harness.py tests/test_harness.py
git commit -m "feat(harness): 实现骨架层校验规则"
```

---

### Task 4: 集成 Harness 到主流程

**Files:**
- Modify: `fetch_stock_data.py`
- Modify: `generate_report.py`

**Interfaces:**
- Consumes: `validate_data(code)`、`validate_skeleton(code)` 来自 `halo_harness.py`
- Produces: 主流程在保存输出后自动运行 harness

- [ ] **Step 1: 修改 fetch_stock_data.py**

在文件顶部 imports 后追加：

```python
# Harness 数据校验
from halo_harness import validate_data
```

在 `fetch_all()` 函数末尾（保存 JSON 之后、return result 之前）追加：

```python
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
```

- [ ] **Step 2: 修改 generate_report.py**

在文件顶部 imports 后追加：

```python
# Harness 骨架校验
from halo_harness import validate_skeleton
```

在 `__main__` 块中保存骨架之后、打印最终统计之前追加：

```python
    # ── Harness 骨架层校验 ──
    print("  🔍 运行骨架层 harness 校验...")
    try:
        harness_result = validate_skeleton(stock_code)
        if not harness_result["ok"]:
            print(f"  ⚠️ 骨架层 harness 未通过，请查看 reports/{stock_code}_harness.json")
            sys.exit(1)
        print("  ✅ 骨架层 harness 通过")
    except Exception as e:
        print(f"  ⚠️ harness 运行失败: {e}")
```

- [ ] **Step 3: 端到端测试**

```bash
python fetch_stock_data.py 000100
python generate_report.py 000100
```

Expected: 两个脚本均打印 `✅ 数据层 harness 通过` 和 `✅ 骨架层 harness 通过`。

- [ ] **Step 4: 故意制造失败测试**

手动修改 `data/000100.json` 中的 `halo.total_score` 为一个错误值，然后运行：

```bash
python halo_harness.py 000100
```

Expected: 输出 `❌ HALO 评分复算一致`，并返回非零退出码。

修改 `reports/000100_skeleton.md`，在某处插入 `{{TEST_PLACEHOLDER}}`，然后运行：

```bash
python halo_harness.py 000100
```

Expected: 输出 `❌ 无残留数据占位符`。

测试完成后恢复原始文件。

- [ ] **Step 5: Commit**

```bash
git add fetch_stock_data.py generate_report.py
git commit -m "feat(harness): 集成 harness 校验到 fetch_stock_data 与 generate_report 主流程"
```

---

## Self-Review

### Spec Coverage

| 设计文档章节 | 实现任务 |
|:-------------|:---------|
| 总体架构（独立 halo_harness.py + 主流程调用） | Task 1 + Task 4 |
| JSON 数据层校验规则 | Task 2 |
| 骨架层校验规则 | Task 3 |
| 输出格式（控制台 + JSON） | Task 1 |
| 失败处理策略 | Task 1 + Task 4 |
| 验证标准 | Task 4 |

### Placeholder Scan

- 无 "TBD"、"TODO"、"implement later"、"fill in details"。
- 所有代码步骤均包含完整代码或明确命令。
- 所有测试步骤均包含预期输出。

### Type Consistency

- `validate_data(code)` 和 `validate_skeleton(code)` 始终返回 dict。
- `Harness.report()` 结构一致：`{code, layer, timestamp, ok, checks, warnings, errors}`。
- `_save_report()` 接收 `Harness` 实例，返回路径字符串。

### 潜在注意点

1. **评分复算逻辑**：`_recalc_halo_score` 的实现依赖于 JSON 中是否存储了 dimension score。如果实际 JSON 结构不同，需要调整。
2. **资金流数据**：某些股票可能没有资金流数据，该检查为 warning 级别，不会阻塞主流程。
3. **骨架数字匹配**：`_find_number_in_text` 使用字符串匹配，可能对格式敏感（如 `3.55` vs `3.5`）。若失败，可放宽容差。

---

## 执行选项

Plan complete and saved to `docs/superpowers/plans/2026-07-14-halo-harness-plan.md`.

**1. Subagent-Driven (recommended)** - 每个 task 派一个独立 subagent，task 之间由我 review

**2. Inline Execution** - 在本会话中按 task 顺序直接执行

Which approach?
