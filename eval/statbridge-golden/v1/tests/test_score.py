import sys, unittest
from pathlib import Path
V1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V1 / "scripts"))
import score as S

DISC = {"status": "labeled", "expected_status": "select",
        "acceptable_table_ids": ["DT_A", "DT_B"], "required_set": ["DT_A", "DT_B"],
        "forbidden_table_ids": ["DT_X"]}

class TestDiscovery(unittest.TestCase):
    def test_exact_match(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A", "DT_B"]})
        self.assertEqual(out["exact"], True); self.assertEqual(out["f1"], 1.0)

    def test_partial_recall(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A"]})
        self.assertFalse(out["exact"]); self.assertAlmostEqual(out["recall"], 0.5)

    def test_forbidden_hit(self):
        out = S.score_discovery(DISC, {"status": "select", "table_ids": ["DT_A", "DT_B", "DT_X"]})
        self.assertTrue(out["forbidden_hit"])


class TestGraph(unittest.TestCase):
    FX = {"series": [{"table_id": "DT_A", "item_id": "1",
                      "points": [{"period": "202501", "value": 1.0}, {"period": "202502", "value": 2.0}]}]}
    G = {"status": "labeled", "chart_type": "line", "layout": "combined"}

    def test_graph_exact(self):
        pred = {"chart_type": "line", "layout": "combined",
                "series": [{"table_id": "DT_A", "item_id": "1",
                            "points": [{"period": "202501", "value": 1.0}, {"period": "202502", "value": 2.0}]}]}
        out = S.score_graph(self.G, self.FX, pred, tol=0.01)
        self.assertTrue(out["type_ok"] and out["layout_ok"] and out["series_ok"] and out["points_ok"])

    def test_graph_wrong_type(self):
        out = S.score_graph(self.G, self.FX, {"chart_type": "bar", "layout": "combined", "series": []}, tol=0.01)
        self.assertFalse(out["type_ok"]); self.assertFalse(out["series_ok"])


class TestInterpretation(unittest.TestCase):
    G = {"status": "labeled",
         "required_claims": [{"id": "c1", "type": "direction", "series": "수출", "period": "2025-01~2025-06", "expected": "down"},
                             {"id": "c2", "type": "level", "period": "202512", "expected_value": 94.8, "tolerance": 0.5}],
         "forbidden_claims": [{"type": "hallucination", "text": "하락세였다"}]}

    def test_hit_all(self):
        claims = [{"type": "direction", "series": "수출", "period": "2025-01~2025-06", "expected": "down"},
                  {"type": "level", "period": "202512", "value": 94.9}]
        out = S.score_interpretation(self.G, {"claims": claims})
        self.assertAlmostEqual(out["claim_recall"], 1.0); self.assertFalse(out["forbidden_hit"])

    def test_forbidden(self):
        out = S.score_interpretation(self.G, {"claims": [{"type": "hallucination", "text": "하락세였다"}]})
        self.assertTrue(out["forbidden_hit"])

    def test_partial(self):
        out = S.score_interpretation(self.G, {"claims": []})
        self.assertAlmostEqual(out["claim_recall"], 0.0)


class TestGrade(unittest.TestCase):
    def test_status_hierarchy(self):
        self.assertEqual(S.classify({"forbidden_hit": True, "exact": True}), "forbidden_hit")
        self.assertEqual(S.classify({"forbidden_hit": False, "exact": True}), "correct")
        self.assertEqual(S.classify({"forbidden_hit": False, "exact": False}), "mismatch")
