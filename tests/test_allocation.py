"""자산배분 비율 정규화 회귀 테스트 — 합계가 항상 정확히 100인지(포트폴리오 CHECK 제약) 검증.

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_allocation.py -v
"""

import os
import sys
import unittest

os.environ.setdefault("PERSONA_GENERATION_MODEL", "test-model")  # 모듈 로드 시 RuntimeError 방지

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from pipelines.data_ingestion.generate_finance_data import RATIO_KEYS, normalize_ratios


class TestNormalizeRatios(unittest.TestCase):
    def _assert_sum_100(self, alloc):
        r = normalize_ratios(alloc)
        self.assertEqual(set(r), set(RATIO_KEYS))
        self.assertAlmostEqual(sum(r.values()), 100.0, places=2)
        self.assertTrue(all(v >= 0 for v in r.values()))

    def test_already_100(self):
        self._assert_sum_100({"stock": 55, "bond": 15, "deposit": 10, "real_estate": 10, "gold": 5, "cash": 5})

    def test_needs_scaling(self):
        self._assert_sum_100({"stock": 30, "bond": 30, "deposit": 30, "real_estate": 30, "gold": 30, "cash": 30})

    def test_rounding_residual(self):
        # 1/3씩 → 33.33*3 = 99.99, 잔차가 최대 버킷에 흡수돼야 함
        self._assert_sum_100({"stock": 1, "bond": 1, "deposit": 1, "real_estate": 0, "gold": 0, "cash": 0})

    def test_empty_falls_back(self):
        r = normalize_ratios({})
        self.assertAlmostEqual(sum(r.values()), 100.0, places=2)

    def test_missing_and_none_keys(self):
        self._assert_sum_100({"stock": 70, "bond": None, "cash": 30})


if __name__ == "__main__":
    unittest.main()
