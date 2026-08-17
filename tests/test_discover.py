from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("discover", ROOT / "scripts" / "discover.py")
discover = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(discover)


class DiscoveryTests(unittest.TestCase):
    def test_identifiers_and_merge(self):
        a = {"title": "Neural CAD", "doi": "https://doi.org/10.1/ABC", "abstract": "short"}
        b = {"title": "Neural CAD", "doi": "10.1/abc", "abstract": "a longer abstract", "authors": ["A"]}
        self.assertEqual(discover.stable_id(a), "doi:10.1/abc")
        merged = discover.merge_candidates([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["abstract"], "a longer abstract")

    def test_relevance_requires_cad_signal(self):
        config = {"keywords": ["CAD"], "domain_boost_keywords": ["b-rep"], "negative_keywords": ["medical imaging"], "relevance_threshold": 4}
        self.assertGreaterEqual(discover.relevance({"title": "B-Rep generation for parametric CAD", "abstract": "neural model"}, config)[0], 4)
        self.assertLess(discover.relevance({"title": "Medical imaging segmentation", "abstract": "deep learning"}, config)[0], 4)
        self.assertEqual(discover.relevance({"title": "Non-parametric continual learning", "abstract": "language model memory"}, config)[0], 0)
        self.assertEqual(discover.relevance({"title": "Generative AI in education", "abstract": "non-parametric comparisons"}, config)[0], 0)
        self.assertLess(discover.relevance({"title": "CAD learning video for fashion students", "abstract": "classroom teaching"}, config)[0], 5)


if __name__ == "__main__":
    unittest.main()
