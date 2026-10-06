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
