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

    def test_disabled_source_is_skipped(self):
        original = discover.discover_arxiv
        discover.discover_arxiv = lambda *_args: self.fail("disabled source should not run")
        try:
            candidates, health = discover.run(
                {
                    "sources": ["disabled-for-test"],
                    "keywords": [],
                    "negative_keywords": [],
                    "domain_boost_keywords": [],
                    "relevance_threshold": 0,
                },
                discover.date(2026, 8, 1),
                discover.date(2026, 8, 2),
            )
        finally:
            discover.discover_arxiv = original
        self.assertTrue(health["arxiv"]["skipped"])
        self.assertIsInstance(candidates, list)

    def test_llm_profile_uses_general_language_model_signals(self):
        config = {
            "profile": "llm",
            "keywords": ["large language model", "retrieval augmented generation"],
            "domain_boost_keywords": ["retrieval augmented generation"],
            "negative_keywords": [],
        }
        score, reasons = discover.relevance(
            {"title": "Retrieval Augmented Generation for Long Documents", "abstract": "A large language model retrieves grounded evidence."},
            config,
        )
        self.assertGreaterEqual(score, 5)
        self.assertTrue(reasons)
        self.assertEqual(discover.relevance({"title": "Graph optimization", "abstract": "A numerical solver."}, config)[0], 0)


if __name__ == "__main__":
    unittest.main()
