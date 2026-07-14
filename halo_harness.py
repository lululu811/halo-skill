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
