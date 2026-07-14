#!/usr/bin/env python3
"""halo_harness 基础接口与行为测试（仅标准库 assert，无 pytest）"""

import sys, os, json, tempfile
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import halo_harness


@contextmanager
def _patch_project_root(tmp_dir):
    """临时将 halo_harness._project_root 指向 tmp_dir"""
    original = halo_harness._project_root
    halo_harness._project_root = lambda: tmp_dir
    try:
        yield tmp_dir
    finally:
        halo_harness._project_root = original


def _make_minimal_data(code, tmp_dir, **overrides):
    """在 tmp_dir/data/{code}.json 写入一份可通过 harness 的最小 JSON"""
    data = {
        "meta": {"stock_code": code, "stock_name": "测试", "fetch_time": "2026-07-14T10:00:00"},
        "market": {"price": 10.0, "pe_ttm": 15.0, "pb": 2.0, "mcap_yi": 100.0},
        "financial": {
            "income": [{"period": "2024-12-31"}, {"period": "2024-09-30"}],
            "balance": [{"period": "2024-12-31"}, {"period": "2024-09-30"}],
            "cashflow": [{"period": "2024-12-31"}, {"period": "2024-09-30"}],
        },
        "halo": {
            "asset_type": "mixed",
            "dimensions": {
                "tangible_intensity": {"value": 50},
                "fixed_intensity": {"value": 40},
                "fixed_share": {"value": 15},
                "capital_labor": {"value": 100},
                "capex_intensity": {"value": 5},
            },
            "raw": {"capex_yi": 10.0, "ocf_yi": 20.0},
        },
        "ratios": {
            "roe": 10, "roa": 5, "gross_margin": 30,
            "net_margin": 15, "debt_ratio": 40, "cf_to_profit": 1.0,
        },
        "growth": {"revenue_yoy": 20, "net_profit_yoy": 25, "annual_revenue_yoy": 15},
        "fund_flow": [{"date": "2026-07-14"}],
    }
    data.update(overrides)
    data_dir = os.path.join(tmp_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{code}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def _make_minimal_skeleton(code, tmp_dir, content):
    """在 tmp_dir/reports/{code}_skeleton.md 写入骨架内容"""
    reports_dir = os.path.join(tmp_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{code}_skeleton.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_validate_data_ok():
    code = "TEST0001"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir)
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_data(code)
        assert isinstance(result, dict)
        assert result["ok"] is True
        assert len(result["errors"]) == 0


def test_validate_data_checks_json():
    code = "TEST0002"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir)
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_data(code)
        check_names = [c["name"] for c in result["checks"]]
        assert "数据文件存在" in check_names


def test_validate_data_corrupt_json():
    code = "TEST0003"
    with tempfile.TemporaryDirectory() as tmp_dir:
        data_dir = os.path.join(tmp_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, f"{code}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ 不是合法 JSON")
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_data(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert checks["JSON 文件可解析"]["passed"] is False
        assert checks["JSON 文件可解析"]["level"] == "error"
        assert result["ok"] is False


def test_validate_data_non_numeric_market():
    code = "TEST0004"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir, market={"price": "N/A", "pe_ttm": None, "pb": 2.0, "mcap_yi": 100.0})
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_data(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert checks["行情数值合理"]["passed"] is False
        assert result["ok"] is False  # 行情数值合理是 error 级别


def test_validate_skeleton_exists():
    code = "TEST0005"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir)
        _make_minimal_skeleton(code, tmp_dir, "# HALO 报告\n价格: 10.00 元\nPE: 15.0\nHALO总分: 3.60\n成长分: 6.5\n免责声明\n报告有效期30日\n")
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_skeleton(code)
        assert isinstance(result, dict)
        assert result["ok"] is True


def test_run_harness_exists():
    code = "TEST0006"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir)
        _make_minimal_skeleton(code, tmp_dir, "# HALO 报告\n价格: 10.00 元\nPE: 15.0\nHALO总分: 3.60\n成长分: 6.5\n免责声明\n报告有效期30日\n")
        with _patch_project_root(tmp_dir):
            result = halo_harness.run_harness(code)
        assert isinstance(result, dict)
        assert result["ok"] is True


def test_harness_warning_does_not_fail():
    h = halo_harness.Harness("000100", "data")
    h.check("warning test", False, level="warning")
    assert h.ok() is True
    assert len(h.warnings) == 1
    assert len(h.errors) == 0


def test_harness_error_fails():
    h = halo_harness.Harness("000100", "data")
    h.check("error test", False, level="error")
    assert h.ok() is False
    assert len(h.errors) == 1


def test_harness_check_records_level():
    h = halo_harness.Harness("000100", "data")
    h.check("x", False, level="warning")
    assert h.checks[0]["level"] == "warning"


def test_score_halo_missing_dim_value_returns_none():
    halo = {"asset_type": "mixed", "dimensions": {"tangible_intensity": {}}}
    assert halo_harness._score_halo_dimensions(halo) is None


def test_score_halo_dimensions_match_generate_report():
    import generate_report
    code = "TEST0007"
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = _make_minimal_data(code, tmp_dir)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        expected = generate_report.score_halo(d)["total"]
        assert abs(halo_harness._recalc_halo_score(d["halo"]) - expected) < 1e-9


def test_score_growth_matches_generate_report():
    import generate_report
    code = "TEST0008"
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = _make_minimal_data(code, tmp_dir)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        expected = generate_report.score_growth(d)["total"]
        assert abs(halo_harness._recalc_growth_score(d["growth"], d["ratios"]) - expected) < 1e-9


def test_validate_skeleton_checks_markdown():
    code = "TEST0009"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir)
        _make_minimal_skeleton(code, tmp_dir, "# HALO 报告\n价格: 10.00 元\nPE: 15.0\nHALO总分: 3.60\n成长分: 6.5\n免责声明\n报告有效期30日\n")
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_skeleton(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert "骨架文件存在" in checks
        assert checks["骨架文件存在"]["passed"] is True
        assert checks["骨架文件存在"]["level"] == "error"
        assert "无残留数据占位符" in checks
        assert checks["无残留数据占位符"]["level"] == "error"


def test_validate_skeleton_score_consistency():
    code = "TEST0010"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_data(code, tmp_dir)
        _make_minimal_skeleton(code, tmp_dir, "# HALO 报告\n价格: 10.00 元\nPE: 15.0\nHALO总分: 3.60\n成长分: 6.5\n免责声明\n报告有效期30日\n")
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_skeleton(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert checks["骨架中 HALO 总分与 JSON 一致"]["passed"] is True
        assert checks["骨架中成长分与 JSON 一致"]["passed"] is True


def test_validate_skeleton_detects_leftover_placeholders():
    code = "FAKE9999"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_skeleton(code, tmp_dir, "# 报告\n价格: {{PRICE}} 元\nPE: {{PE_TTM}}\n{{AI_SUMMARY}}\n")
        # 构造一份可解析的最小 JSON，使关键数字校验能执行
        data_dir = os.path.join(tmp_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        data_path = os.path.join(data_dir, f"{code}.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump({
                "meta": {"stock_code": code, "stock_name": "测试", "fetch_time": "2026-07-14"},
                "market": {"price": 99.99, "pe_ttm": 25.5, "pb": 3.0, "mcap_yi": 100},
                "halo": {"asset_type": "mixed", "total_score": 3.5, "dimensions": {}, "raw": {}},
                "growth": {"total_score": 5.5},
            }, f, ensure_ascii=False)

        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_skeleton(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert checks["骨架文件存在"]["passed"] is True
        assert checks["无残留数据占位符"]["passed"] is False
        assert checks["无残留数据占位符"]["level"] == "error"
        assert "{{PRICE}}" in checks["无残留数据占位符"]["detail"]


def test_validate_skeleton_corrupt_json_logs_error():
    code = "FAKE9998"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_skeleton(code, tmp_dir, "# 报告\n价格: 99.99 元\n")
        data_dir = os.path.join(tmp_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        data_path = os.path.join(data_dir, f"{code}.json")
        with open(data_path, "w", encoding="utf-8") as f:
            f.write("{ 这不是合法 JSON")

        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_skeleton(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert checks["JSON 文件可解析"]["passed"] is False
        assert checks["JSON 文件可解析"]["level"] == "error"


def test_validate_skeleton_missing_data_file_warns():
    code = "FAKE9997"
    with tempfile.TemporaryDirectory() as tmp_dir:
        _make_minimal_skeleton(code, tmp_dir, "# 报告\n")
        with _patch_project_root(tmp_dir):
            result = halo_harness.validate_skeleton(code)
        checks = {c["name"]: c for c in result["checks"]}
        assert checks["数据文件存在"]["passed"] is False
        assert checks["数据文件存在"]["level"] == "warning"


def test_find_number_in_text_false_positive_rounded_integer():
    """回归测试：查找 3.60 不应误匹配到 '2024' 中的 '4'"""
    assert halo_harness._find_number_in_text("2024年", 3.60) is False


def test_find_number_in_text_matches_expected_formats():
    assert halo_harness._find_number_in_text("价格 3.60 元", 3.60) is True
    assert halo_harness._find_number_in_text("总分 3.6", 3.60) is True
    assert halo_harness._find_number_in_text("整数 4", 4.0) is True


if __name__ == "__main__":
    test_validate_data_ok()
    test_validate_data_checks_json()
    test_validate_data_corrupt_json()
    test_validate_data_non_numeric_market()
    test_validate_skeleton_exists()
    test_run_harness_exists()
    test_harness_warning_does_not_fail()
    test_harness_error_fails()
    test_harness_check_records_level()
    test_score_halo_missing_dim_value_returns_none()
    test_score_halo_dimensions_match_generate_report()
    test_score_growth_matches_generate_report()
    test_validate_skeleton_checks_markdown()
    test_validate_skeleton_score_consistency()
    test_validate_skeleton_detects_leftover_placeholders()
    test_validate_skeleton_corrupt_json_logs_error()
    test_validate_skeleton_missing_data_file_warns()
    test_find_number_in_text_false_positive_rounded_integer()
    test_find_number_in_text_matches_expected_formats()
    print("✅ 基础接口测试通过")
