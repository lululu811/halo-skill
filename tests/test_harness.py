#!/usr/bin/env python3
"""halo_harness 基础接口与行为测试"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import halo_harness


def test_validate_data_ok():
    result = halo_harness.validate_data("000100")
    assert isinstance(result, dict)
    assert result["ok"] is True
    assert len(result["errors"]) == 0


def test_validate_data_checks_json():
    result = halo_harness.validate_data("000100")
    check_names = [c["name"] for c in result["checks"]]
    assert "数据文件存在" in check_names


def test_validate_skeleton_exists():
    result = halo_harness.validate_skeleton("000100")
    assert isinstance(result, dict)
    assert "ok" in result


def test_run_harness_exists():
    result = halo_harness.run_harness("000100")
    assert isinstance(result, dict)
    assert "ok" in result


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
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "000100.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    expected = generate_report.score_halo(d)["total"]
    assert abs(halo_harness._recalc_halo_score(d["halo"]) - expected) < 1e-9


def test_score_growth_matches_generate_report():
    import generate_report
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "000100.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    expected = generate_report.score_growth(d)["total"]
    assert abs(halo_harness._recalc_growth_score(d["growth"], d["ratios"]) - expected) < 1e-9


def test_validate_skeleton_checks_markdown():
    # 假设 reports/000100_skeleton.md 已存在
    result = halo_harness.validate_skeleton("000100")
    checks = {c["name"]: c for c in result["checks"]}
    assert "骨架文件存在" in checks
    assert checks["骨架文件存在"]["passed"] is True
    assert checks["骨架文件存在"]["level"] == "error"
    assert "无残留数据占位符" in checks
    assert checks["无残留数据占位符"]["level"] == "error"


def test_validate_skeleton_detects_leftover_placeholders(tmp_path, monkeypatch):
    # 创建临时骨架，包含残留数据占位符
    code = "FAKE9999"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    skeleton_path = reports_dir / f"{code}_skeleton.md"
    skeleton_path.write_text("# 报告\n价格: {{PRICE}} 元\nPE: {{PE_TTM}}\n{{AI_SUMMARY}}\n", encoding="utf-8")

    # 构造一份可解析的最小 JSON，使关键数字校验能执行
    data_path = data_dir / f"{code}.json"
    data_path.write_text(json.dumps({
        "meta": {"stock_code": code, "stock_name": "测试", "fetch_time": "2026-07-14"},
        "market": {"price": 99.99, "pe_ttm": 25.5, "pb": 3.0, "mcap_yi": 100},
        "halo": {"asset_type": "mixed", "total_score": 3.5, "dimensions": {}, "raw": {}},
        "growth": {"total_score": 5.5},
    }), encoding="utf-8")

    monkeypatch.setattr(halo_harness, "_project_root", lambda: str(tmp_path))
    result = halo_harness.validate_skeleton(code)
    checks = {c["name"]: c for c in result["checks"]}
    assert checks["骨架文件存在"]["passed"] is True
    assert checks["无残留数据占位符"]["passed"] is False
    assert checks["无残留数据占位符"]["level"] == "error"
    assert "{{PRICE}}" in checks["无残留数据占位符"]["detail"]


def test_validate_skeleton_corrupt_json_logs_error(tmp_path, monkeypatch):
    code = "FAKE9998"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    skeleton_path = reports_dir / f"{code}_skeleton.md"
    skeleton_path.write_text("# 报告\n价格: 99.99 元\n", encoding="utf-8")

    data_path = data_dir / f"{code}.json"
    data_path.write_text("{ 这不是合法 JSON", encoding="utf-8")

    monkeypatch.setattr(halo_harness, "_project_root", lambda: str(tmp_path))
    result = halo_harness.validate_skeleton(code)
    checks = {c["name"]: c for c in result["checks"]}
    assert checks["JSON 文件可解析"]["passed"] is False
    assert checks["JSON 文件可解析"]["level"] == "error"


def test_validate_skeleton_missing_data_file_warns(tmp_path, monkeypatch):
    code = "FAKE9997"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    skeleton_path = reports_dir / f"{code}_skeleton.md"
    skeleton_path.write_text("# 报告\n", encoding="utf-8")

    monkeypatch.setattr(halo_harness, "_project_root", lambda: str(tmp_path))
    result = halo_harness.validate_skeleton(code)
    checks = {c["name"]: c for c in result["checks"]}
    assert checks["数据文件存在"]["passed"] is False
    assert checks["数据文件存在"]["level"] == "warning"


if __name__ == "__main__":
    test_validate_data_ok()
    test_validate_data_checks_json()
    test_validate_skeleton_exists()
    test_run_harness_exists()
    test_harness_warning_does_not_fail()
    test_harness_error_fails()
    test_harness_check_records_level()
    test_score_halo_missing_dim_value_returns_none()
    test_score_halo_dimensions_match_generate_report()
    test_score_growth_matches_generate_report()
    test_validate_skeleton_checks_markdown()
    print("✅ 基础接口测试通过")
