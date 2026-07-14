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
    print("✅ 基础接口测试通过")
