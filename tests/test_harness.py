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
